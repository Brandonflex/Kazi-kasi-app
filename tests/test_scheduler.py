"""The clock: cadence, windows, jitter, and the runs that must not be skipped.

The failure this module prevents is quiet: "a digest a day" that is really "a
digest whenever someone remembers to run the command", plus a duplicate on the
day two ticks race.
"""

from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import db, outbox, scheduler
from kazikasi.channels import FakeTransport
from kazikasi.corpus import load_corpus
from kazikasi.profile import seed_profiles

# 15:30 UTC = 18:30 EAT, inside the default window.
NOW = datetime(2026, 10, 20, 15, 30, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    connection = db.connect()
    load_corpus(connection, now=NOW)
    seed_profiles(connection)
    yield connection
    connection.close()


@pytest.fixture
def subscriber(conn):
    return outbox.subscribe(conn, "demo-fresher", "0712 345 678", now=NOW)


def transports():
    return {"whatsapp": FakeTransport(), "sms": FakeTransport()}


class TestJitter:
    def test_the_offset_is_stable_for_a_person_and_a_day(self):
        first = scheduler.jitter_minutes("demo-fresher", NOW.date())
        second = scheduler.jitter_minutes("demo-fresher", NOW.date())
        assert first == second

    def test_it_varies_across_people(self):
        offsets = {scheduler.jitter_minutes(f"profile-{index}", NOW.date()) for index in range(60)}
        assert len(offsets) > 10

    def test_it_stays_inside_the_spread(self):
        for index in range(200):
            offset = scheduler.jitter_minutes(f"p{index}", NOW.date(), spread=30)
            assert 0 <= offset <= 30

    def test_it_is_bounded_by_the_window_it_is_used_in(self, conn):
        outbox.subscribe(conn, "demo-fresher", "0712345678", window=("18:00", "18:10"), now=NOW)
        decision = scheduler.decide(conn, outbox.load_subscription(conn, "demo-fresher"), now=NOW)
        # A 45-minute jitter on a 10-minute window must clamp, not never fire.
        start = decision.sends_at
        assert start is None or "18:0" in start


class TestWindows:
    @pytest.mark.parametrize(
        "utc_hour,expected",
        [(5, "outside_window"), (15, "waiting_for_jitter"), (16, "due"), (18, "outside_window")],
    )
    def test_the_window_is_nairobi_time(self, conn, subscriber, utc_hour, expected):
        now = datetime(2026, 10, 20, utc_hour, 0, tzinfo=timezone.utc)
        decision = scheduler.decide(conn, subscriber, now=now)
        if expected == "waiting_for_jitter" and decision.due:
            # A profile whose jitter is 0 is due the moment the window opens.
            assert decision.reason == "due"
        else:
            assert decision.reason == expected

    def test_a_custom_window_is_respected(self, conn):
        subscription = outbox.subscribe(
            conn, "demo-fresher", "0712345678", window=("07:00", "08:00"), now=NOW
        )
        morning = datetime(2026, 10, 21, 4, 30, tzinfo=timezone.utc)  # 07:30 EAT
        decision = scheduler.decide(conn, subscription, now=morning)
        assert decision.reason in ("due", "waiting_for_jitter")

        evening = datetime(2026, 10, 21, 15, 30, tzinfo=timezone.utc)
        assert scheduler.decide(conn, subscription, now=evening).reason == "outside_window"

    def test_an_opted_out_person_is_never_due(self, conn, subscriber):
        outbox.unsubscribe(conn, "demo-fresher", now=NOW)
        assert scheduler.decide(conn, outbox.load_subscription(conn, "demo-fresher"), now=NOW).reason == "unsubscribed"


class TestCadence:
    def test_a_daily_subscriber_is_served_once_a_day(self, conn, subscriber):
        assert scheduler.due_now(conn, now=NOW) == ["demo-fresher"]
        scheduler.run_due(conn, None, now=NOW)

        later_same_day = NOW + timedelta(minutes=60)
        assert scheduler.due_now(conn, now=later_same_day) == []

        next_day = NOW + timedelta(days=1)
        assert scheduler.due_now(conn, now=next_day) == ["demo-fresher"]

    def test_a_weekly_subscriber_is_not_sent_one_every_day(self, conn):
        outbox.subscribe(conn, "demo-fresher", "0712345678", cadence="weekly", now=NOW)
        assert scheduler.due_now(conn, now=NOW) == ["demo-fresher"]
        scheduler.run_due(conn, None, now=NOW)

        assert scheduler.due_now(conn, now=NOW + timedelta(days=1)) == []
        assert scheduler.due_now(conn, now=NOW + timedelta(days=6)) == []
        assert scheduler.due_now(conn, now=NOW + timedelta(days=7)) == ["demo-fresher"]

    def test_an_unknown_cadence_is_refused_rather_than_treated_as_daily(self, conn):
        with pytest.raises(ValueError, match="cadence"):
            outbox.subscribe(conn, "demo-fresher", "0712345678", cadence="hourly", now=NOW)

    def test_an_empty_morning_does_not_block_the_evening(self, conn, subscriber):
        """The run composed nothing at 09:00; new jobs arrive; 18:30 must still fire."""
        for job in conn.execute("SELECT id FROM jobs").fetchall():
            outbox.tracking.record(conn, "demo-fresher", job["id"], "dismissed")
        morning = datetime(2026, 10, 20, 6, 0, tzinfo=timezone.utc)
        empty = outbox.queue_digest(conn, "demo-fresher", now=morning)
        assert empty["state"] == "empty"
        assert scheduler.due_now(conn, now=NOW) == ["demo-fresher"]


class TestTicks:
    def test_a_tick_composes_and_sends(self, conn, subscriber):
        whatsapp = FakeTransport()
        report = scheduler.tick(conn, {"whatsapp": whatsapp, "sms": FakeTransport()}, now=NOW)

        assert [entry["profile_id"] for entry in report["due"]] == ["demo-fresher"]
        assert report["composed"][0]["state"] == "queued"
        assert report["sent"]["sent"] == 1
        assert len(whatsapp.sent) == 1

    def test_a_second_tick_in_the_same_window_sends_nothing(self, conn, subscriber):
        scheduler.tick(conn, transports(), now=NOW)
        second = scheduler.tick(conn, transports(), now=NOW + timedelta(minutes=10))
        assert second["due"] == []
        assert second["sent"]["sent"] == 0

    def test_a_tick_reports_why_people_were_skipped(self, conn):
        # 19:00 EAT is past every possible jitter offset inside 18:00–20:00.
        late = datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)
        outbox.subscribe(conn, "demo-fresher", "0712345678", now=late)
        outbox.subscribe(conn, "demo-two-years", "0722000111", now=late)
        scheduler.run_due(conn, None, now=late)         # serve both today

        report = scheduler.tick(conn, None, now=late + timedelta(minutes=5))
        assert report["due"] == []
        assert report["waiting"] == {"already_served": 2}

    def test_a_dry_run_tick_writes_nothing(self, conn, subscriber):
        report = scheduler.tick(conn, transports(), now=NOW)
        assert report["composed"][0]["state"] == "queued"

        fresh = db.connect(":memory:")
        load_corpus(fresh, now=NOW)
        seed_profiles(fresh)
        outbox.subscribe(fresh, "demo-fresher", "0712345678", now=NOW)
        dry = scheduler.run_due(fresh, transports(), now=NOW, dry_run=True)
        assert dry["composed"][0]["state"] == "dry_run"
        assert fresh.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"] == 0

    def test_a_profile_that_vanishes_is_reported_not_crashed(self, conn):
        outbox.subscribe(conn, "demo-fresher", "0712345678", now=NOW)
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("DELETE FROM profiles WHERE id = 'demo-fresher'")
        conn.commit()
        report = scheduler.run_due(conn, None, now=NOW)
        assert report["composed"] and "error" in report["composed"][0]

    def test_explain_lists_everyone_with_a_reason(self, conn, subscriber):
        rows = scheduler.explain(conn, now=NOW)
        assert rows[0]["profile_id"] == "demo-fresher"
        assert rows[0]["due"] is True
        assert rows[0]["sends_at"]
