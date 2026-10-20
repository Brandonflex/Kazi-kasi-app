"""Closing-soon alerts: the one message a saved job is worth.

A saved job is a promise to yourself. The failure mode is not "I forgot to look
at my shortlist" — it is that the deadline moved from three weeks away to
tomorrow while nobody was looking. `shortlist.reminders_due()` already knows
which saved jobs are inside the window and has the exact text; the /shortlist
page renders it. What was missing is the *send*.

This module is deliberately the thinnest possible bridge: it takes that same
text and puts it in the outbox, where consent, backoff, suppression and receipts
already live. It adds one idea of its own, and it is the important one:

    the idempotency key includes the deadline

so a re-run, a crash and a restart all converge on one message per job per
deadline, and an employer who extends the deadline gets a new message rather
than silence. That is also why nothing is marked as "reminded" here: the outbox
row *is* the record of having spoken. Marking it at queue time would tell the
shortlist page the person had been warned before the message left.

One more rule, inherited from the digest: **a message needs consent.** A saved
job is an in-app action; it is not permission to send a text. No active
subscription means no alert, and the job simply stays on the page where it
already appears.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import outbox, shortlist
from .digest import Outgoing


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


@dataclass
class Alert:
    profile_id: str
    job_id: str
    deadline: datetime
    text: str
    idempotency: str

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "job_id": self.job_id,
            "closes": self.deadline.isoformat(),
            "characters": len(self.text),
            "idempotency": self.idempotency,
        }


@dataclass
class Report:
    considered: int = 0
    queued: int = 0
    already: int = 0
    no_consent: list[str] = field(default_factory=list)
    alerts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "considered": self.considered,
            "queued": self.queued,
            "already": self.already,
            "no_consent": self.no_consent,
            "alerts": self.alerts,
        }


def idempotency_key(profile_id: str, job_id: str, deadline: datetime) -> str:
    """One message per job per deadline. A moved deadline is a new promise."""
    return f"closing:{profile_id}:{job_id}:{deadline.date().isoformat()}"


def due(
    conn, *, now: datetime | None = None, hours: int | None = None, base: str | None = None
) -> list[Alert]:
    """Alerts that should be sent, without touching the outbox.

    Pure enough to be read in a test and printed by a dry run.
    """
    moment = _now(now)
    hours = shortlist.REMINDER_HOURS if hours is None else int(hours)
    alerts: list[Alert] = []
    for subscription in outbox.active_subscriptions(conn):
        for job in shortlist.closing_soon(conn, subscription.profile_id, now=moment, hours=hours):
            deadline = shortlist.deadline_at(job)
            if deadline is None:  # pragma: no cover - closing_soon filters these
                continue
            alerts.append(
                Alert(
                    profile_id=subscription.profile_id,
                    job_id=job["id"],
                    deadline=deadline,
                    # The same composer the shortlist page uses, so the page and
                    # the message say exactly the same thing.
                    text=shortlist.reminder_text(job, base=base),
                    idempotency=idempotency_key(subscription.profile_id, job["id"], deadline),
                )
            )
    return alerts


def queue(
    conn,
    *,
    now: datetime | None = None,
    hours: int | None = None,
    base: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Put every due alert in the outbox. Sends nothing; the tick does that."""
    moment = _now(now)
    subscriptions = {s.profile_id: s for s in outbox.active_subscriptions(conn)}
    report = Report()
    for alert in due(conn, now=moment, hours=hours, base=base):
        report.considered += 1
        subscription = subscriptions.get(alert.profile_id)
        if subscription is None:
            report.no_consent.append(alert.profile_id)
            continue
        if dry_run:
            report.alerts.append(alert.to_dict())
            continue
        added = outbox.enqueue(
            conn,
            Outgoing(
                profile_id=alert.profile_id,
                channel=subscription.channel,
                msisdn=subscription.msisdn,
                body=alert.text,
                idempotency=alert.idempotency,
                kind="closing",
            ),
            now=moment,
        )
        if added:
            report.queued += 1
            report.alerts.append(alert.to_dict())
        else:
            report.already += 1
    return report.to_dict()
