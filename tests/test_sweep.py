"""The scheduled sweep: fetch sources, update jobs, track source health.

The sweep is what makes the digest fresh. Without it the digest composes from
whatever happened to be in the jobs table yesterday. With it, every 18:00 EAT
cron run fetches the sources that are due and upserts their vacancies first.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kazikasi import db, sweep


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    yield c
    c.close()


class TestSourceHealth:
    def test_schema_is_created(self, conn):
        sweep.add_source_health_schema(conn)
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='source_health'").fetchone()
        assert row is not None

    def test_record_and_read(self, conn):
        sweep.add_source_health_schema(conn)
        now = datetime(2026, 10, 21, tzinfo=timezone.utc)
        sweep.record_source_health(conn, "brightermonday", status="ok", now=now, cadence_minutes=1440)
        row = conn.execute("SELECT status, cadence_minutes FROM source_health WHERE source_id = ?", ("brightermonday",)).fetchone()
        assert row["status"] == "ok"
        assert row["cadence_minutes"] == 1440

    def test_upsert_updates_last_seen(self, conn):
        sweep.add_source_health_schema(conn)
        now1 = datetime(2026, 10, 20, tzinfo=timezone.utc)
        now2 = datetime(2026, 10, 21, tzinfo=timezone.utc)
        sweep.record_source_health(conn, "fuzu", status="ok", now=now1, cadence_minutes=720)
        sweep.record_source_health(conn, "fuzu", status="warn", last_error="timeout", now=now2, cadence_minutes=720)
        row = conn.execute("SELECT status, last_error FROM source_health WHERE source_id = ?", ("fuzu",)).fetchone()
        assert row["status"] == "warn"
        assert row["last_error"] == "timeout"


class TestShouldRun:
    def test_never_fetched_runs(self, conn):
        sweep.add_source_health_schema(conn)
        from kazikasi.sources import REGISTRY
        adapter = REGISTRY["brightermonday"]()
        assert sweep.should_run(adapter, datetime.now(timezone.utc), conn) is True

    def test_fetched_within_cadence_skips(self, conn):
        sweep.add_source_health_schema(conn)
        from kazikasi.sources import REGISTRY
        adapter = REGISTRY["brightermonday"]()
        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        sweep.record_source_health(conn, "brightermonday", status="ok", now=now, cadence_minutes=adapter.manifest.cadence_minutes)
        # 5 minutes later — within 15-minute cadence
        assert sweep.should_run(adapter, datetime(2026, 10, 21, 12, 5, tzinfo=timezone.utc), conn) is False

    def test_fetched_outside_cadence_runs(self, conn):
        sweep.add_source_health_schema(conn)
        from kazikasi.sources import REGISTRY
        adapter = REGISTRY["brightermonday"]()
        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        sweep.record_source_health(conn, "brightermonday", status="ok", now=now, cadence_minutes=adapter.manifest.cadence_minutes)
        # 20 minutes later — past 15-minute cadence
        assert sweep.should_run(adapter, datetime(2026, 10, 21, 12, 20, tzinfo=timezone.utc), conn) is True

    def test_dead_source_skips(self, conn):
        sweep.add_source_health_schema(conn)
        now = datetime(2026, 10, 1, tzinfo=timezone.utc)
        sweep.record_source_health(conn, "brightermonday", status="dead", now=now, cadence_minutes=1440)
        from kazikasi.sources import REGISTRY
        adapter = REGISTRY["brightermonday"]()
        assert sweep.should_run(adapter, datetime(2026, 10, 21, tzinfo=timezone.utc), conn) is False


class TestRunSweep:
    def test_run_sweep_returns_report(self, conn):
        sweep.add_source_health_schema(conn)
        report = sweep.run_sweep(conn, now=datetime(2026, 10, 21, tzinfo=timezone.utc), force=True)
        assert "sources" in report
        assert "totals" in report
        assert report["totals"]["ran"] > 0
        # Sources will have errors because we can't reach the internet from tests,
        # but the structure must be right.
        for src in report["sources"]:
            assert "source_id" in src
            assert "errors" in src
