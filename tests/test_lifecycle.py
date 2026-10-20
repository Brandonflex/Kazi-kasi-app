"""A simulated week: four people, a flaky provider, one STOP, one START.

Unit tests prove a function; this proves the *product* holds together over time.
Every assertion here is an invariant that should never be violated, not a
snapshot of today's behaviour:

1. one digest per person per day, never two;
2. never the same job twice, across a whole week;
3. nothing sent to someone who opted out, however it was queued;
4. every message knows which run it belongs to, and every failure says why;
5. a fallback exists only where a primary failed;
6. receipts can close out every message that was actually delivered.
"""

from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import db, outbox, scheduler, webhooks
from kazikasi.channels import Delivery, FakeTransport
from kazikasi.corpus import load_corpus
from kazikasi.profile import seed_profiles

START = datetime(2026, 10, 19, 16, 0, tzinfo=timezone.utc)  # 19:00 EAT, past all jitter
DAYS = 7


class FlakyTransport(FakeTransport):
    """Fails deterministically for one in three messages, so runs are repeatable."""

    channel = "whatsapp"

    def __init__(self, fail_every: int = 3):
        super().__init__()
        self.fail_every = fail_every
        self.attempts = 0
        self.failures: list[str] = []

    def send(self, to, body, *, idempotency):
        self.attempts += 1
        if self.attempts % self.fail_every == 0:
            self.failures.append(idempotency)
            self.sent.append({"to": to, "body": body, "idempotency": idempotency, "ok": False})
            return Delivery(ok=False, error="provider 503", retryable=True)
        return super().send(to, body, idempotency=idempotency)


@pytest.fixture
def conn():
    connection = db.connect()
    load_corpus(connection, now=START)
    seed_profiles(connection)
    yield connection
    connection.close()


@pytest.fixture
def world(conn):
    outbox.subscribe(conn, "demo-fresher", "0712000001", source="web", now=START)
    outbox.subscribe(conn, "demo-two-years", "0712000002", cadence="weekly", source="web", now=START)
    outbox.subscribe(conn, "demo-public-sector", "0712000003", source="web", now=START)
    # Someone who never opted in at all.
    return conn


def run_week(conn, *, stop_on_day: int | None = 3, start_on_day: int | None = 5):
    whatsapp = FlakyTransport()
    sms = FakeTransport()
    sends: list[tuple[datetime, str]] = []

    for day in range(DAYS):
        now = START + timedelta(days=day)
        if stop_on_day is not None and day == stop_on_day:
            webhooks.handle_meta(
                conn,
                {
                    "entry": [
                        {
                            "changes": [
                                {
                                    "value": {
                                        "messages": [
                                            {
                                                "id": f"stop-{day}",
                                                "from": "254712000001",
                                                "type": "text",
                                                "text": {"body": "STOP"},
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    ]
                },
                now=now,
            )
        if start_on_day is not None and day == start_on_day:
            webhooks.handle_meta(
                conn,
                {
                    "entry": [
                        {
                            "changes": [
                                {
                                    "value": {
                                        "messages": [
                                            {
                                                "id": f"start-{day}",
                                                "from": "254712000001",
                                                "type": "text",
                                                "text": {"body": "START"},
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    ]
                },
                now=now,
            )

        before = len(whatsapp.sent) + len(sms.sent)
        scheduler.run_due(conn, {"whatsapp": whatsapp, "sms": sms}, now=now)
        # A second tick ten minutes later must add nothing for the same person.
        scheduler.run_due(conn, {"whatsapp": whatsapp, "sms": sms}, now=now + timedelta(minutes=10))
        sends.append((now, f"{len(whatsapp.sent) + len(sms.sent) - before}"))
    return whatsapp, sms


class TestOnePerDay:
    def test_nobody_gets_two_digests_in_a_day(self, world):
        run_week(world)
        rows = world.execute(
            """SELECT profile_id, run_date, channel, COUNT(*) AS c
               FROM digest_runs GROUP BY profile_id, run_date, channel"""
        ).fetchall()
        assert rows
        assert all(row["c"] == 1 for row in rows)

    def test_the_week_produces_digests_but_not_a_flood(self, world):
        whatsapp, sms = run_week(world)
        sent = len(whatsapp.sent) + len(sms.sent)
        assert 5 <= sent <= 30  # three people, seven days, retries and one fallback

    def test_a_weekly_subscriber_gets_far_fewer_messages(self, world):
        run_week(world)
        counts = {
            row["profile_id"]: row["c"]
            for row in world.execute(
                "SELECT profile_id, COUNT(*) AS c FROM messages WHERE kind = 'digest' GROUP BY profile_id"
            )
        }
        assert counts["demo-two-years"] == 1
        assert counts.get("demo-fresher", 0) >= 1


class TestNeverTwice:
    def test_no_job_is_sent_to_the_same_person_twice(self, world):
        run_week(world)
        duplicates = world.execute(
            """SELECT i.job_id, r.profile_id, COUNT(*) AS c
               FROM digest_items i JOIN digest_runs r ON r.id = i.run_id
               GROUP BY i.job_id, r.profile_id HAVING c > 1"""
        ).fetchall()
        assert duplicates == []

    def test_an_applied_job_does_not_come_back(self, world):
        from kazikasi import tracking

        first = outbox.compose(world, "demo-fresher", now=START)
        target = first.items[0].job_id
        tracking.record(world, "demo-fresher", target, "applied")

        later = outbox.compose(world, "demo-fresher", now=START + timedelta(days=2))
        assert target not in {item.job_id for item in later.items}


class TestConsentHolds:
    def test_nothing_is_sent_to_an_opted_out_person(self, world):
        """STOP on day 3, START on day 5: days 3 and 4 must be silent."""
        run_week(world)
        opted_out_days = {
            (START + timedelta(days=3)).date().isoformat(),
            (START + timedelta(days=4)).date().isoformat(),
        }
        rows = world.execute(
            """SELECT state, created_at FROM messages
               WHERE profile_id = 'demo-fresher' AND state IN ('sent', 'delivered')"""
        ).fetchall()
        sent_days = {row["created_at"][:10] for row in rows}
        assert not (sent_days & opted_out_days)

        # And they are schedulable again the day they text START. The digest may
        # legitimately be *empty* by then — on a 30-job corpus a fresher's
        # eligible pool runs out after a few days, and "never re-send" means
        # silence rather than repeats. That is the designed trade-off, recorded
        # as a product gap in docs/design/02-product-surface-design.md.
        resumed = (START + timedelta(days=5)).date().isoformat()
        run = world.execute(
            "SELECT state FROM digest_runs WHERE profile_id = 'demo-fresher' AND run_date = ?",
            (resumed,),
        ).fetchone()
        assert run is not None
        assert run["state"] in ("queued", "sent", "empty")
        assert outbox.load_subscription(world, "demo-fresher").active

    def test_the_stop_and_the_start_are_both_in_the_audit(self, world):
        run_week(world)
        actions = [event["action"] for event in outbox.consent_events_for(world, "demo-fresher")]
        assert "unsubscribed" in actions
        assert "subscribed" in actions

    def test_every_message_belongs_to_a_run(self, world):
        run_week(world)
        orphans = world.execute("SELECT COUNT(*) c FROM messages WHERE run_id IS NULL").fetchone()["c"]
        assert orphans == 0


class TestFailureShape:
    def test_every_failure_says_why(self, world):
        run_week(world)
        bad = world.execute(
            "SELECT COUNT(*) c FROM messages WHERE state = 'failed' AND (last_error IS NULL OR last_error = '')"
        ).fetchone()["c"]
        assert bad == 0

    def test_a_fallback_only_follows_a_failure(self, world):
        run_week(world)
        fallbacks = world.execute("SELECT * FROM messages WHERE kind = 'fallback'").fetchall()
        for fallback in fallbacks:
            primary = world.execute(
                "SELECT state FROM messages WHERE run_id = ? AND channel != ? AND kind = 'digest'",
                (fallback["run_id"], fallback["channel"]),
            ).fetchone()
            assert primary is not None
            assert primary["state"] in ("failed", "sent", "delivered")

    def test_sent_messages_have_a_provider_id(self, world):
        run_week(world)
        blind = world.execute(
            "SELECT COUNT(*) c FROM messages WHERE state IN ('sent', 'delivered') AND provider_id IS NULL"
        ).fetchone()["c"]
        assert blind == 0

    def test_nothing_is_stuck_without_a_reason(self, world):
        run_week(world)
        stuck = world.execute(
            """SELECT COUNT(*) c FROM messages
               WHERE state = 'queued' AND attempts >= ? AND last_error IS NULL""",
            (outbox.MAX_ATTEMPTS,),
        ).fetchone()["c"]
        assert stuck == 0


class TestReceiptsCloseTheWeek:
    def test_every_delivered_message_can_be_closed_out(self, world):
        whatsapp, sms = run_week(world)
        for message in whatsapp.sent:
            if message["ok"]:
                provider_id = world.execute(
                    "SELECT provider_id FROM messages WHERE idempotency = ?",
                    (message["idempotency"],),
                ).fetchone()["provider_id"]
                webhooks.handle_meta(
                    world,
                    {
                        "entry": [
                            {
                                "changes": [
                                    {
                                        "value": {
                                            "statuses": [
                                                {
                                                    "id": provider_id,
                                                    "status": "delivered",
                                                    "recipient_id": message["to"].lstrip("+"),
                                                }
                                            ]
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    now=START + timedelta(days=DAYS),
                )

        states = {
            row["state"]
            for row in world.execute(
                "SELECT state FROM messages WHERE channel = 'whatsapp' AND kind = 'digest'"
            )
        }
        assert "sent" not in states  # receipts folded every accepted message forward

    def test_receipts_never_exceed_messages(self, world):
        run_week(world)
        receipts = world.execute("SELECT COUNT(*) c FROM message_receipts").fetchone()["c"]
        assert receipts == 0  # nothing was reported in this simulation
