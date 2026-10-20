"""Consent, composition, queueing and delivery for the digest.

The outbox exists because sending is the part that breaks in ways users notice:

* **A retry must not send twice.** Every message carries an idempotency key with
  a unique constraint behind it, so a crashed send loop cannot produce two
  copies of the same digest.
* **A failure must be visible.** Messages carry ``attempts`` and ``last_error``;
  a message that vanished is not a state this schema can represent.
* **A failure must have a fallback.** After the last retry, a WhatsApp message
  becomes an SMS if the person gave us a fallback channel — retrying WhatsApp is
  not a fallback.
* **Consent is checked at send time, not at compose time.** Someone who replies
  STOP between composition and delivery must not receive the message.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from . import digest as digest_module
from . import ranking, tracking
from .db import _now_iso
from .graph import feed as graph_feed
from .profile import load_profile

MAX_ATTEMPTS = 3
#: Backoff between retries, in minutes, indexed by attempt number.
BACKOFF_MINUTES = (0, 5, 30)


# --------------------------------------------------------------------------
# Subscriptions (consent)
# --------------------------------------------------------------------------


@dataclass
class Subscription:
    profile_id: str
    channel: str
    msisdn: str
    consented_at: str | None = None
    consent_source: str = "cli"
    cadence: str = "daily"
    window_start: str = "18:00"
    window_end: str = "20:00"
    max_items: int = digest_module.DEFAULT_MAX_ITEMS
    fallback_channel: str | None = "sms"
    unsubscribed_at: str | None = None

    @property
    def active(self) -> bool:
        return self.unsubscribed_at is None

    def to_dict(self, *, mask: bool = True) -> dict:
        return {
            "profile_id": self.profile_id,
            "channel": self.channel,
            "msisdn": digest_module.mask_msisdn(self.msisdn) if mask else self.msisdn,
            "consented_at": self.consented_at,
            "consent_source": self.consent_source,
            "cadence": self.cadence,
            "window": f"{self.window_start}–{self.window_end}",
            "max_items": self.max_items,
            "fallback_channel": self.fallback_channel,
            "active": self.active,
            "unsubscribed_at": self.unsubscribed_at,
        }


def subscribe(
    conn,
    profile_id: str,
    msisdn: str,
    *,
    channel: str = "whatsapp",
    source: str = "cli",
    cadence: str = "daily",
    fallback_channel: str | None = "sms",
    max_items: int = digest_module.DEFAULT_MAX_ITEMS,
    now: datetime | None = None,
) -> Subscription:
    """Record consent. Re-subscribing clears a previous opt-out and re-dates it."""
    number = digest_module.normalise_msisdn(msisdn)
    if load_profile(conn, profile_id) is None:
        raise ValueError(f"unknown profile {profile_id!r}; run `kazikasi profiles --seed`")
    if channel not in ("whatsapp", "sms"):
        raise ValueError(f"unsupported channel {channel!r}")

    at = _now_iso(now)
    conn.execute(
        """INSERT INTO subscriptions
           (profile_id, channel, msisdn, msisdn_hash, consented_at, consent_source,
            cadence, window_start, window_end, max_items, fallback_channel,
            unsubscribed_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL,?)
           ON CONFLICT(profile_id) DO UPDATE SET
             channel = excluded.channel,
             msisdn = excluded.msisdn,
             msisdn_hash = excluded.msisdn_hash,
             consented_at = excluded.consented_at,
             consent_source = excluded.consent_source,
             cadence = excluded.cadence,
             max_items = excluded.max_items,
             fallback_channel = excluded.fallback_channel,
             unsubscribed_at = NULL,
             updated_at = excluded.updated_at""",
        (
            profile_id,
            channel,
            number,
            digest_module.hash_msisdn(number),
            at,
            source,
            cadence,
            "18:00",
            "20:00",
            max_items,
            fallback_channel,
            at,
        ),
    )
    conn.commit()
    return load_subscription(conn, profile_id)  # type: ignore[return-value]


def unsubscribe(conn, profile_id: str, *, now: datetime | None = None, reason: str | None = None) -> bool:
    """Opt out. The row is kept and dated: consent needs a history, not a delete."""
    cursor = conn.execute(
        "UPDATE subscriptions SET unsubscribed_at = ?, updated_at = ? WHERE profile_id = ? AND unsubscribed_at IS NULL",
        (_now_iso(now), _now_iso(now), profile_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def load_subscription(conn, profile_id: str) -> Subscription | None:
    row = conn.execute("SELECT * FROM subscriptions WHERE profile_id = ?", (profile_id,)).fetchone()
    if row is None:
        return None
    data = dict(row)
    return Subscription(
        profile_id=data["profile_id"],
        channel=data["channel"],
        msisdn=data["msisdn"],
        consented_at=data["consented_at"],
        consent_source=data["consent_source"],
        cadence=data["cadence"],
        window_start=data["window_start"],
        window_end=data["window_end"],
        max_items=int(data["max_items"]),
        fallback_channel=data["fallback_channel"],
        unsubscribed_at=data["unsubscribed_at"],
    )


def active_subscriptions(conn) -> list[Subscription]:
    rows = conn.execute(
        "SELECT profile_id FROM subscriptions WHERE unsubscribed_at IS NULL ORDER BY profile_id"
    ).fetchall()
    return [load_subscription(conn, row["profile_id"]) for row in rows]  # type: ignore[misc]


# --------------------------------------------------------------------------
# Composition
# --------------------------------------------------------------------------


def already_sent_job_ids(conn, profile_id: str) -> set[str]:
    """Jobs that have been in a digest for this person, sent or still queued."""
    return {
        row["job_id"]
        for row in conn.execute(
            """SELECT DISTINCT i.job_id
               FROM digest_items i JOIN digest_runs r ON r.id = i.run_id
               WHERE r.profile_id = ? AND r.state IN ('queued', 'sent')""",
            (profile_id,),
        )
    }


def compose(
    conn,
    profile_id: str,
    *,
    now: datetime | None = None,
    max_items: int | None = None,
) -> digest_module.Digest:
    """Rank the live feed for one person and pick today's cards."""
    profile = load_profile(conn, profile_id)
    if profile is None:
        raise ValueError(f"unknown profile {profile_id!r}")

    subscription = load_subscription(conn, profile_id)
    today = digest_module.local_date(now)

    rows = [dict(row) for row in graph_feed(conn, limit=500, include_stale=True)]
    matches = ranking.rank(rows, profile, now=now, limit=200)

    return digest_module.select(
        matches,
        profile_id=profile.id,
        profile_name=profile.name,
        for_date=today,
        already_sent=already_sent_job_ids(conn, profile_id),
        acted_on=tracking.applied_job_ids(conn, profile_id),
        dismissed=tracking.dismissed_job_ids(conn, profile_id),
        max_items=max_items or (subscription.max_items if subscription else digest_module.DEFAULT_MAX_ITEMS),
    )


def persist_run(conn, digest: digest_module.Digest, *, channel: str, now: datetime | None = None) -> int:
    """Record the run and its items. Re-running the same day is idempotent."""
    existing = conn.execute(
        "SELECT id FROM digest_runs WHERE profile_id = ? AND run_date = ? AND channel = ?",
        (digest.profile_id, digest.for_date.isoformat(), channel),
    ).fetchone()
    if existing:
        return int(existing["id"])

    cursor = conn.execute(
        """INSERT INTO digest_runs (profile_id, channel, run_date, created_at, item_count, state)
           VALUES (?,?,?,?,?,?)""",
        (
            digest.profile_id,
            channel,
            digest.for_date.isoformat(),
            _now_iso(now),
            len(digest.items),
            "empty" if digest.is_empty else "composed",
        ),
    )
    run_id = int(cursor.lastrowid)
    for item in digest.items:
        conn.execute(
            "INSERT OR IGNORE INTO digest_items (run_id, job_id, position, reason) VALUES (?,?,?,?)",
            (run_id, item.job_id, item.position, " · ".join(item.reasons[:2])),
        )
    conn.commit()
    return run_id


def set_run_state(conn, run_id: int, state: str) -> None:
    conn.execute("UPDATE digest_runs SET state = ? WHERE id = ?", (state, run_id))
    conn.commit()


# --------------------------------------------------------------------------
# Queue
# --------------------------------------------------------------------------


def enqueue(conn, outgoing: digest_module.Outgoing, *, now: datetime | None = None) -> bool:
    """Put a message in the outbox. Returns False if it was already there.

    The unique idempotency key is the whole safety story: a re-run, a crash and
    a restart all converge on one message.
    """
    at = _now_iso(now)
    cursor = conn.execute(
        """INSERT OR IGNORE INTO messages
           (idempotency, profile_id, channel, to_msisdn, body, kind, state, created_at, updated_at)
           VALUES (?,?,?,?,?,?, 'queued', ?, ?)""",
        (
            outgoing.idempotency,
            outgoing.profile_id,
            outgoing.channel,
            outgoing.msisdn,
            outgoing.body,
            outgoing.kind,
            at,
            at,
        ),
    )
    conn.commit()
    return cursor.rowcount > 0


def queue_digest(
    conn,
    profile_id: str,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
    link_base: str | None = None,
) -> dict:
    """Compose, persist and enqueue one person's digest. Sends nothing."""
    subscription = load_subscription(conn, profile_id)
    if subscription is None:
        raise ValueError(f"no subscription for {profile_id!r}; run `kazikasi digest --subscribe`")
    if not subscription.active:
        return {"profile_id": profile_id, "state": "unsubscribed", "queued": 0}

    digest = compose(conn, profile_id, now=now)
    run_id = persist_run(conn, digest, channel=subscription.channel, now=now)

    if digest.is_empty:
        set_run_state(conn, run_id, "empty")
        return {
            "profile_id": profile_id,
            "run_id": run_id,
            "state": "empty",
            "queued": 0,
            "messages": [],
            "digest": digest.to_dict(),
            "preview": "",
        }

    messages = digest_module.build_messages(
        digest, channel=subscription.channel, msisdn=subscription.msisdn, link_base=link_base
    )
    queued = 0
    for message in messages:
        if dry_run:
            continue
        if enqueue(conn, message, now=now):
            queued += 1

    if not dry_run and queued:
        # Only a run that actually queued something new becomes "queued"; a
        # re-run of a day already delivered must not demote a sent run.
        set_run_state(conn, run_id, "queued")

    state = "dry_run"
    if not dry_run:
        if queued:
            state = "queued"
        else:
            row = conn.execute("SELECT state FROM digest_runs WHERE id = ?", (run_id,)).fetchone()
            state = row["state"] if row else "queued"

    return {
        "profile_id": profile_id,
        "run_id": run_id,
        "state": state,
        "queued": queued,
        "messages": [message.to_dict() for message in messages],
        "digest": digest.to_dict(),
        "preview": messages[0].body if messages else "",
    }


# --------------------------------------------------------------------------
# Delivery
# --------------------------------------------------------------------------


@dataclass
class SendReport:
    sent: int = 0
    failed: int = 0
    retried: int = 0
    suppressed: int = 0
    fell_back: int = 0
    skipped_out_of_window: int = 0
    deferred: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.errors = self.errors or []

    def to_dict(self) -> dict:
        return {
            "sent": self.sent,
            "failed": self.failed,
            "retried": self.retried,
            "suppressed": self.suppressed,
            "fell_back": self.fell_back,
            "skipped_out_of_window": self.skipped_out_of_window,
            "deferred": self.deferred,
            "errors": self.errors[:10],
        }


def _backoff_due(message_row, now: datetime) -> bool:
    attempts = int(message_row["attempts"])
    if attempts == 0:
        return True
    delay = BACKOFF_MINUTES[min(attempts, len(BACKOFF_MINUTES) - 1)]
    last = datetime.fromisoformat(message_row["updated_at"])
    return now >= last + timedelta(minutes=delay)


def send_due(
    conn,
    transports: dict,
    *,
    now: datetime | None = None,
    limit: int = 100,
    respect_window: bool = True,
    dry_run: bool = False,
) -> SendReport:
    """Deliver queued messages, with retries, opt-out checks and SMS fallback.

    ``dry_run`` really does call the transports (so a fake transport proves the
    body renders) but throws the state transitions away, which is what makes it
    safe to run against a demo DB.
    """
    now = now or datetime.now(timezone.utc)
    report = SendReport()

    def apply(sql: str, params: tuple) -> None:  # noqa: ANN001
        if not dry_run:
            conn.execute(sql, params)

    rows = conn.execute(
        "SELECT * FROM messages WHERE state = 'queued' ORDER BY created_at LIMIT ?", (limit,)
    ).fetchall()

    for row in rows:
        subscription = load_subscription(conn, row["profile_id"])

        # Consent is re-checked here, not trusted from compose time.
        if subscription is None or not subscription.active:
            apply(
                "UPDATE messages SET state = 'suppressed', updated_at = ? WHERE id = ?",
                (_now_iso(now), row["id"]),
            )
            report.suppressed += 1
            continue

        if respect_window and not digest_module.in_window(
            now, subscription.window_start, subscription.window_end
        ):
            report.skipped_out_of_window += 1
            continue

        if not _backoff_due(row, now):
            # Still waiting out a retry backoff; not an error, not a send.
            report.deferred += 1
            continue

        transport = transports.get(row["channel"])
        if transport is None:
            report.errors.append(f"no transport for channel {row['channel']!r}")
            report.failed += 1
            continue

        delivery = transport.send(row["to_msisdn"], row["body"], idempotency=row["idempotency"])
        attempts = int(row["attempts"]) + 1

        if delivery.ok:
            apply(
                """UPDATE messages SET state = 'sent', attempts = ?, provider_id = ?,
                   last_error = NULL, sent_at = ?, updated_at = ? WHERE id = ?""",
                (attempts, delivery.provider_id, _now_iso(now), _now_iso(now), row["id"]),
            )
            if not dry_run:
                _mark_run_sent(conn, row["profile_id"], row["channel"])
            report.sent += 1
            continue

        if delivery.retryable and attempts < MAX_ATTEMPTS:
            apply(
                "UPDATE messages SET attempts = ?, last_error = ?, updated_at = ? WHERE id = ?",
                (attempts, delivery.error, _now_iso(now), row["id"]),
            )
            report.retried += 1
            continue

        # Give up on this channel; fall back if the person gave us another one.
        apply(
            "UPDATE messages SET state = 'failed', attempts = ?, last_error = ?, updated_at = ? WHERE id = ?",
            (attempts, delivery.error, _now_iso(now), row["id"]),
        )
        report.failed += 1
        report.errors.append(f"{row['channel']} {row['idempotency']}: {delivery.error}")

        fallback = subscription.fallback_channel
        if fallback and fallback != row["channel"] and fallback in transports:
            run = conn.execute(
                "SELECT * FROM digest_runs WHERE profile_id = ? AND channel = ? ORDER BY run_date DESC LIMIT 1",
                (row["profile_id"], row["channel"]),
            ).fetchone()
            digest = _digest_from_run(conn, run) if run else None
            if digest is not None and not digest.is_empty:
                for message in digest_module.build_messages(
                    digest, channel=fallback, msisdn=subscription.msisdn
                ):
                    if dry_run:
                        if not (conn.execute(
                            "SELECT 1 FROM messages WHERE idempotency = ?", (message.idempotency,)
                        ).fetchone()):
                            report.fell_back += 1
                    elif enqueue(conn, message, now=now):
                        report.fell_back += 1
    if not dry_run:
        conn.commit()
    return report


def _mark_run_sent(conn, profile_id: str, channel: str) -> None:
    conn.execute(
        "UPDATE digest_runs SET state = 'sent' WHERE profile_id = ? AND channel = ? AND state = 'queued'",
        (profile_id, channel),
    )


def _digest_from_run(conn, run_row) -> digest_module.Digest | None:
    if run_row is None:
        return None
    items = []
    for row in conn.execute(
        """SELECT i.*, j.title, j.employer_name, j.county, j.sub_county, j.entry_fit,
                  j.deadline, j.pay_min, j.pay_max, j.pay_period, j.scam_flags, j.status
           FROM digest_items i JOIN jobs j ON j.id = i.job_id
           WHERE i.run_id = ? ORDER BY i.position""",
        (run_row["id"],),
    ):
        items.append(
            digest_module.DigestItem(
                job_id=row["job_id"],
                title=row["title"],
                employer=row["employer_name"],
                score=0.0,
                reasons=[row["reason"]] if row["reason"] else [],
                row=dict(row),
                position=row["position"],
            )
        )
    return digest_module.Digest(
        profile_id=run_row["profile_id"],
        profile_name=run_row["profile_id"],
        for_date=date.fromisoformat(run_row["run_date"]),
        items=items,
    )


def messages_for(conn, profile_id: str, limit: int = 20) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM messages WHERE profile_id = ? ORDER BY created_at DESC LIMIT ?",
            (profile_id, limit),
        )
    ]


def outbox_summary(conn) -> dict:
    rows = conn.execute("SELECT state, COUNT(*) AS c FROM messages GROUP BY state").fetchall()
    counts = {row["state"]: row["c"] for row in rows}
    return {"counts": counts, "queued": counts.get("queued", 0), "failed": counts.get("failed", 0)}
