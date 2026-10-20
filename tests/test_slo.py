"""D8: the freshness promise, as a number someone can check."""

from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import db, slo
from kazikasi.corpus import load_corpus

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    connection = db.connect()
    load_corpus(connection, now=NOW)
    yield connection
    connection.close()


class TestSourceStatus:
    def test_a_source_fetched_just_now_is_on_time(self, conn):
        status = slo.source_status(conn, "brightermonday", now=NOW)
        assert status["state"] == "on_time"
        assert status["meets_slo"] is True
        assert status["age_minutes"] == 0

    def test_a_missed_cycle_is_late(self, conn):
        # BrighterMonday targets 15 minutes; three cycles is red.
        assert slo.source_status(conn, "brightermonday", now=NOW + timedelta(minutes=25))["state"] == "late"
        assert slo.source_status(conn, "brightermonday", now=NOW + timedelta(minutes=61))["state"] == "stale"

    def test_a_source_never_fetched_says_so(self, conn):
        status = slo.source_status(conn, "psc", now=NOW)
        assert status["state"] == "never_fetched"
        assert status["last_fetch"] is None
        assert status["meets_slo"] is False

    def test_target_comes_from_the_manifest(self, conn):
        assert slo.source_status(conn, "brightermonday", now=NOW)["target_minutes"] == 15
        assert slo.source_status(conn, "reliefweb", now=NOW)["target_minutes"] == 120


class TestReport:
    def test_reports_every_registered_source(self, conn):
        payload = slo.report(conn, now=NOW)
        ids = {source["source_id"] for source in payload["sources"]}
        assert ids == {"brightermonday", "fuzu", "myjobmag", "reliefweb", "psc", "nairobi_county"}

    def test_counts_only_sources_that_have_reported(self, conn):
        payload = slo.report(conn, now=NOW)
        assert payload["sources_reporting"] == 4
        assert payload["slo_rate"] == 1.0

    def test_slo_rate_falls_when_a_source_goes_quiet(self, conn):
        later = slo.report(conn, now=NOW + timedelta(hours=5))
        assert later["slo_rate"] < 1.0

    def test_feed_age_is_reported(self, conn):
        assert slo.report(conn, now=NOW)["feed_age_minutes"] == 0
        assert slo.report(conn, now=NOW + timedelta(minutes=90))["feed_age_minutes"] == 90

    def test_empty_graph_is_not_a_healthy_graph(self):
        conn = db.connect()
        try:
            payload = slo.report(conn, now=NOW)
            assert payload["slo_rate"] == 0.0
            assert payload["feed_last_updated"] is None
            assert slo.worst_state(payload) == "never_fetched"
        finally:
            conn.close()

    def test_worst_state_picks_the_weakest_link(self, conn):
        payload = slo.report(conn, now=NOW)
        assert slo.worst_state(payload) == "never_fetched"
        payload["sources"] = [source for source in payload["sources"] if source["last_fetch"]]
        assert slo.worst_state(payload) == "on_time"
