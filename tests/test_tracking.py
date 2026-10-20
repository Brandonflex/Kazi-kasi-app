"""D10: link out, remember what happened, never apply on anyone's behalf."""

from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import db, graph, tracking
from kazikasi.corpus import load_corpus
from kazikasi.profile import seed_profiles

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    connection = db.connect()
    load_corpus(connection, now=NOW)
    seed_profiles(connection)
    yield connection
    connection.close()


def job_id(conn, title="Software Support Analyst"):
    return conn.execute("SELECT id FROM jobs WHERE title = ?", (title,)).fetchone()["id"]


class TestRecording:
    def test_events_are_appended(self, conn):
        jid = job_id(conn)
        tracking.record(conn, "demo-fresher", jid, "viewed")
        tracking.record(conn, "demo-fresher", jid, "clicked_through", detail="fuzu")
        events = tracking.events_for_job(conn, jid)
        assert [event["kind"] for event in events] == ["viewed", "clicked_through"]
        assert events[1]["detail"] == "fuzu"

    def test_unknown_event_kind_is_rejected(self, conn):
        with pytest.raises(ValueError):
            tracking.record(conn, "demo-fresher", job_id(conn), "auto_applied")

    def test_unknown_job_is_rejected(self, conn):
        with pytest.raises(ValueError):
            tracking.record(conn, "demo-fresher", "no-such-job", "viewed")

    def test_events_are_per_profile(self, conn):
        jid = job_id(conn)
        tracking.record(conn, "demo-fresher", jid, "dismissed")
        assert tracking.events_for_profile(conn, "demo-two-years") == []
        assert len(tracking.events_for_profile(conn, "demo-fresher")) == 1


class TestSets:
    def test_dismissals_are_per_profile(self, conn):
        jid = job_id(conn)
        tracking.record(conn, "demo-fresher", jid, "dismissed")
        assert tracking.dismissed_job_ids(conn, "demo-fresher") == {jid}
        assert tracking.dismissed_job_ids(conn, "demo-two-years") == set()

    def test_applied_includes_clicks(self, conn):
        # A click-through counts as "acted on" for the source yield numbers, but
        # "applied" stays a claim only the user can make.
        first, second = job_id(conn), job_id(conn, "Finance Assistant")
        tracking.record(conn, "demo-fresher", first, "clicked_through")
        tracking.record(conn, "demo-fresher", second, "applied")
        acted = tracking.applied_job_ids(conn, "demo-fresher")
        assert acted == {first, second}

    def test_viewing_is_not_applying(self, conn):
        tracking.record(conn, "demo-fresher", job_id(conn), "viewed")
        assert tracking.applied_job_ids(conn, "demo-fresher") == set()


class TestFunnel:
    def test_rates_are_computed_from_events_not_guesses(self, conn):
        jid = job_id(conn)
        for _ in range(4):
            tracking.record(conn, "demo-fresher", jid, "viewed")
        tracking.record(conn, "demo-fresher", jid, "clicked_through")
        tracking.record(conn, "demo-fresher", jid, "applied")

        payload = tracking.funnel(conn, now=NOW + timedelta(minutes=1))
        assert payload["events"]["clicked_through"] == 1
        assert payload["click_through_rate"] == 0.25
        assert payload["apply_rate_of_clicks"] == 1.0

    def test_empty_funnel_is_none_not_zero(self, conn):
        payload = tracking.funnel(conn, now=NOW + timedelta(minutes=1))
        assert payload["click_through_rate"] is None

    def test_old_events_fall_out_of_the_window(self, conn):
        tracking.record(conn, "demo-fresher", job_id(conn), "clicked_through")
        payload = tracking.funnel(conn, days=1, now=NOW + timedelta(days=3))
        assert payload["events"] == {}


class TestSourceYield:
    def test_sources_with_no_actions_have_zero_yield(self, conn):
        yield_rows = {row["source_id"]: row for row in tracking.source_yield(conn, now=NOW)}
        assert set(yield_rows) == {"brightermonday", "fuzu", "myjobmag", "reliefweb"}
        assert all(row["yield"] == 0.0 for row in yield_rows.values())

    def test_acting_on_a_job_shows_up_against_its_sources(self, conn):
        jid = job_id(conn)
        tracking.record(conn, "demo-fresher", jid, "applied")
        yield_rows = {row["source_id"]: row for row in tracking.source_yield(conn, now=NOW)}
        assert yield_rows["brightermonday"]["acted_on"] >= 1
        assert yield_rows["brightermonday"]["yield"] > 0
