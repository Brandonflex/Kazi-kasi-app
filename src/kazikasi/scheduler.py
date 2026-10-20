"""The clock: who is due for a digest, when exactly, and how it is spaced.

Without this, "one message a day" is a claim about a command someone remembers
to run. The scheduler is deliberately tiny — a function you can call from cron,
a systemd timer, or the `kazikasi run --loop` loop — but the *rules* are here
and tested:

* **Cadence is real.** `daily` and `weekly` mean one digest per day or per
  rolling week; a subscriber who chose weekly is not quietly sent one anyway.
* **The window is the person's**, in Nairobi time, not the server's.
* **Jitter is deterministic.** Thousands of subscribers sharing 18:00–20:00
  would otherwise be one spike at 18:00:00 and a rate limit at 18:00:01. Each
  profile gets a stable offset derived from its id, so the digest is predictable
  for the operator and spread for the provider.
* **An empty day does not block the evening.** A run that composed nothing in
  the morning must still be retried at 18:00 when new jobs have arrived.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from . import digest as digest_module
from . import alerts, outbox

#: How far inside the window the first send may be pushed, in minutes.
JITTER_SPREAD_MINUTES = 45

#: A weekly subscriber is due seven days after the last digest went out.
WEEKLY_INTERVAL_DAYS = 7

#: Run states that mean "this person has already been served for this period".
SERVED_STATES = ("queued", "sent", "delivered")


def jitter_minutes(profile_id: str, for_date: date | None = None, spread: int = JITTER_SPREAD_MINUTES) -> int:
    """A stable 0..spread offset for this profile.

    Keyed on the profile alone, not the date: the same person gets their digest
    at the same minute every day, which is easier to explain to a support desk
    than a time that drifts. ``for_date`` is accepted so callers can be explicit
    about *when* they are scheduling without changing the answer.
    """
    seed = profile_id.encode("utf-8")
    digest = hashlib.blake2b(seed, digest_size=4).digest()
    return int.from_bytes(digest, "big") % (spread + 1)


@dataclass
class DueDecision:
    profile_id: str
    due: bool
    reason: str
    sends_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "due": self.due,
            "reason": self.reason,
            "sends_at": self.sends_at,
        }


def _minutes(value: str) -> int:
    hours, minutes = (int(part) for part in value.split(":"))
    return hours * 60 + minutes


def _last_served(conn, profile_id: str, channel: str) -> str | None:
    placeholders = ",".join("?" for _ in SERVED_STATES)
    row = conn.execute(
        f"""SELECT MAX(run_date) AS run_date FROM digest_runs
            WHERE profile_id = ? AND channel = ? AND state IN ({placeholders})""",
        (profile_id, channel, *SERVED_STATES),
    ).fetchone()
    return row["run_date"] if row and row["run_date"] else None


def decide(conn, subscription, *, now: datetime | None = None) -> DueDecision:
    """Is this subscriber due right now, and if not, why not?"""
    now = now or datetime.now(timezone.utc)
    today = digest_module.local_date(now)
    local = digest_module.eat_now(now)
    minutes = local.hour * 60 + local.minute

    if not subscription.active:
        return DueDecision(subscription.profile_id, False, "unsubscribed")

    start = _minutes(subscription.window_start)
    end = _minutes(subscription.window_end)
    inside = (
        start <= minutes < end if start <= end else (minutes >= start or minutes < end)
    )
    if not inside:
        return DueDecision(subscription.profile_id, False, "outside_window")

    offset = jitter_minutes(subscription.profile_id, today)
    window_minutes = (end - start) % (24 * 60) or 24 * 60
    if offset >= window_minutes:
        # A long jitter on a short window: clamp instead of never sending.
        offset = max(0, window_minutes - 1)
    send_at = (
        local.replace(hour=0, minute=0, second=0, microsecond=0)
        + timedelta(minutes=start + offset)
    ).strftime("%H:%M")

    # Already served this period? That is the honest answer, and it outranks
    # "your jitter has not elapsed" — the digest already left.
    last = _last_served(conn, subscription.profile_id, subscription.channel)
    if last:
        last_date = date.fromisoformat(last)
        interval = 1 if subscription.cadence == "daily" else WEEKLY_INTERVAL_DAYS
        if (today - last_date).days < interval:
            return DueDecision(subscription.profile_id, False, "already_served")

    if minutes < start + offset:
        return DueDecision(subscription.profile_id, False, "waiting_for_jitter", send_at)

    return DueDecision(subscription.profile_id, True, "due", send_at)


def due_subscriptions(conn, *, now: datetime | None = None) -> list[DueDecision]:
    now = now or datetime.now(timezone.utc)
    return [decide(conn, subscription, now=now) for subscription in outbox.active_subscriptions(conn)]


def due_now(conn, *, now: datetime | None = None) -> list[str]:
    return [decision.profile_id for decision in due_subscriptions(conn, now=now) if decision.due]


def run_due(
    conn,
    transports: dict | None = None,
    *,
    now: datetime | None = None,
    link_base: str | None = None,
    dry_run: bool = False,
    with_brief: bool = False,
    with_alerts: bool = False,
) -> dict:
    """One tick: compose for everyone due, then try to deliver.

    Composing and sending are separate steps because they fail differently — a
    ranking bug should not block a delivery, and a provider outage should not
    lose the composition that already happened.
    """
    now = now or datetime.now(timezone.utc)
    decisions = due_subscriptions(conn, now=now)
    waiting: dict[str, int] = {}
    for decision in decisions:
        if not decision.due:
            waiting[decision.reason] = waiting.get(decision.reason, 0) + 1
    composed: list[dict] = []
    for decision in decisions:
        if not decision.due:
            continue
        try:
            composed.append(
                outbox.queue_digest(
                    conn, decision.profile_id, now=now, dry_run=dry_run, link_base=link_base
                )
            )
        except ValueError as error:  # a subscription without a profile, or bad data
            composed.append({"profile_id": decision.profile_id, "error": str(error)})

    closing: dict | None = None
    if with_alerts:
        # Closing-soon alerts go in the same tick as the digest but through the
        # same outbox, so consent, backoff and receipts apply to them equally.
        closing = alerts.queue(conn, now=now, dry_run=dry_run, base=link_base)

    briefs: list[dict] = []
    if with_brief:
        for profile_id in outbox.brief_due(conn, now=now):
            try:
                briefs.append(
                    outbox.queue_brief(
                        conn, profile_id, now=now, dry_run=dry_run, link_base=link_base
                    )
                )
            except ValueError as error:
                briefs.append({"profile_id": profile_id, "error": str(error)})

    report = None
    if transports is not None and not dry_run:
        report = outbox.send_due(conn, transports, now=now).to_dict()
    elif transports is not None and dry_run:
        report = outbox.send_due(conn, transports, now=now, dry_run=True).to_dict()

    return {
        "now": digest_module.eat_now(now).isoformat(),
        "due": [decision.to_dict() for decision in decisions if decision.due],
        "waiting": waiting,
        "composed": composed,
        "briefs": briefs,
        "alerts": closing,
        "sent": report,
    }


def tick(
    conn,
    transports: dict,
    *,
    now: datetime | None = None,
    link_base: str | None = None,
) -> dict:
    """Compose and deliver in one call — what a cron entry actually wants."""
    return run_due(conn, transports, now=now, link_base=link_base)


def explain(conn, *, now: datetime | None = None) -> list[dict]:
    """Why each subscriber is or is not getting a digest right now."""
    return [decision.to_dict() for decision in due_subscriptions(conn, now=now)]
