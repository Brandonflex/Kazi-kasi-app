"""A corpus in a file: the deployable site without a database.

The interesting failures here are all about *trust*, not transport:

* a bundle with no date must not be presented as current;
* a bundle older than a day and a half must say so on the page;
* a line the parser cannot read must be skipped and counted, not fatal — one bad
  advert should not take the site down;
* a deployment that cannot reach its bundle must fall back and **say why**, not
  return 500 to every visitor.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from kazikasi import bundle, db, serve

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def clean_state():
    before = dict(bundle.STATE)
    yield
    bundle.STATE.clear()
    bundle.STATE.update(before)


@pytest.fixture
def conn():
    connection = serve.demo_connection(now=NOW)
    yield connection
    connection.close()


def empty_conn():
    return db.connect(":memory:")


class TestExport:
    def test_every_live_job_is_exported_once(self, conn):
        candidates = bundle.export(conn, now=NOW)
        live = conn.execute("SELECT COUNT(*) AS n FROM jobs WHERE status IN ('open','stale')").fetchone()["n"]
        assert len(candidates) == live

    def test_a_candidate_carries_what_the_feed_needs(self, conn):
        first = bundle.export(conn, now=NOW)[0]
        for key in ("source_id", "source_job_id", "source_url", "title"):
            assert first.get(key), key

    def test_the_header_counts_what_the_file_contains(self, conn):
        candidates = bundle.export(conn, now=NOW)
        head = bundle.header(candidates, now=NOW)
        assert head["kind"] == bundle.KIND and head["schema"] == bundle.SCHEMA
        assert head["count"] == len(candidates)
        assert head["built_at"] == NOW.isoformat()

    def test_a_closed_job_is_not_in_the_bundle(self, conn):
        job = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        before = len(bundle.export(conn, now=NOW))
        conn.execute("UPDATE jobs SET status = 'closed' WHERE id = ?", (job,))
        conn.commit()
        assert len(bundle.export(conn, now=NOW)) == before - 1


class TestRoundTrip:
    def test_write_then_read_returns_the_same_candidates(self, conn, tmp_path):
        path = tmp_path / "bundle.jsonl"
        payload = bundle.write(conn, path, now=NOW)
        read_back = bundle.from_file(path)
        assert read_back.count == payload["count"]
        assert read_back.built_at == NOW
        assert read_back.skipped == 0
        assert read_back.sha256 == payload["sha256"]

    def test_loading_into_an_empty_database_recreates_the_feed(self, conn, tmp_path):
        path = tmp_path / "bundle.jsonl"
        bundle.write(conn, path, now=NOW)
        with empty_conn() as fresh:
            report = bundle.load(fresh, bundle.from_file(path), now=NOW)
            assert sum(report["loaded"].values()) >= 20
            assert fresh.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"] >= 20
            assert fresh.execute(
                "SELECT COUNT(*) AS n FROM jobs WHERE status = 'open'"
            ).fetchone()["n"] >= 20

    def test_loading_twice_does_not_duplicate(self, conn, tmp_path):
        path = tmp_path / "bundle.jsonl"
        bundle.write(conn, path, now=NOW)
        with empty_conn() as fresh:
            first = bundle.load(fresh, bundle.from_file(path), now=NOW)
            second = bundle.load(fresh, bundle.from_file(path), now=NOW)
            assert first["loaded"].get("created", 0) > 0
            assert second["loaded"].get("created", 0) == 0

    def test_the_published_url_is_https_only(self):
        with pytest.raises(bundle.BundleError):
            bundle.fetch_text("http://example.com/bundle.jsonl")

    def test_a_url_is_read_through_an_injected_fetch(self, conn, tmp_path):
        path = tmp_path / "bundle.jsonl"
        bundle.write(conn, path, now=NOW)
        text = path.read_text()
        read_back = bundle.from_url("https://example.com/bundle.jsonl", fetch=lambda url: text)
        assert read_back.count >= 20


class TestValidation:
    def test_an_empty_file_is_refused(self):
        with pytest.raises(bundle.BundleError, match="empty"):
            bundle.parse("")

    def test_a_json_file_that_is_not_a_bundle_is_refused(self):
        with pytest.raises(bundle.BundleError, match="not a Kazi-Kasi bundle"):
            bundle.parse('{"jobs": []}')

    def test_a_future_schema_is_refused_rather_than_misread(self):
        head = {"kind": bundle.KIND, "schema": bundle.SCHEMA + 1, "built_at": NOW.isoformat()}
        with pytest.raises(bundle.BundleError, match="schema"):
            bundle.parse(json.dumps(head))

    def test_bad_lines_are_skipped_and_counted(self):
        text = "\n".join(
            [
                json.dumps({"kind": bundle.KIND, "schema": 1, "built_at": NOW.isoformat()}),
                json.dumps({"source_id": "a", "title": "Good job"}),
                "not json at all",
                json.dumps({"source_id": "a"}),
            ]
        )
        parsed = bundle.parse(text)
        assert parsed.count == 1 and parsed.skipped == 2

    def test_an_undated_bundle_is_stale(self):
        text = json.dumps({"kind": bundle.KIND, "schema": 1}) + "\n" + json.dumps(
            {"source_id": "a", "title": "x"}
        )
        assert bundle.parse(text).is_stale(now=NOW) is True


class TestStaleness:
    def test_fresh_is_not_stale(self, conn, tmp_path):
        path = tmp_path / "bundle.jsonl"
        bundle.write(conn, path, now=NOW)
        assert bundle.from_file(path).is_stale(now=NOW + timedelta(hours=1)) is False

    def test_a_day_and_a_half_old_is_stale(self, conn, tmp_path):
        path = tmp_path / "bundle.jsonl"
        bundle.write(conn, path, now=NOW)
        later = NOW + timedelta(hours=bundle.STALE_HOURS + 1)
        assert bundle.from_file(path).is_stale(now=later) is True

    def test_the_notice_says_how_long_ago(self):
        bundle.STATE.update({"source": "bundle", "built_at": NOW.isoformat(), "count": 26})
        fresh = bundle.notice(now=NOW + timedelta(minutes=5))
        assert "Live data, refreshed" in fresh and "EAT" in fresh

        stale = bundle.notice(now=NOW + timedelta(days=3))
        assert "has not run since" in stale

    def test_a_synthetic_corpus_says_nothing(self):
        bundle.STATE.update({"source": "synthetic"})
        assert bundle.notice(now=NOW) == ""


class TestTheDeployment:
    def test_bundle_state_flips_the_synthetic_flag(self, monkeypatch):
        monkeypatch.setenv("KAZIKASI_BUNDLE", "https://example.com/bundle.jsonl")
        assert serve.synthetic_build() is False
        monkeypatch.delenv("KAZIKASI_BUNDLE")
        assert serve.synthetic_build() is True

    def test_the_banner_shows_the_refresh_time_not_a_lie(self, conn):
        bundle.STATE.update({"source": "bundle", "built_at": NOW.isoformat(), "count": 26})
        body = serve.handle(conn, "GET", "/", {}, demo=False, now=NOW).body
        assert "Live data, refreshed" in body
        assert "Synthetic demo data" not in body

    def test_a_stale_bundle_is_labelled_on_the_page(self, conn):
        bundle.STATE.update({"source": "bundle", "built_at": (NOW - timedelta(days=4)).isoformat()})
        body = serve.handle(conn, "GET", "/", {}, demo=False, now=NOW).body
        assert "has not run since" in body

    def test_a_synthetic_deployment_still_says_synthetic(self, conn):
        bundle.STATE.update({"source": "synthetic"})
        body = serve.handle(conn, "GET", "/", {}, demo=True, now=NOW).body
        assert "Synthetic demo data" in body

    def test_health_reports_the_corpus(self, conn):
        bundle.STATE.update({"source": "bundle", "built_at": NOW.isoformat(), "count": 26, "error": None})
        payload = json.loads(serve.handle(conn, "GET", "/api/health", {}, demo=False, now=NOW).body)
        assert payload["corpus"]["source"] == "bundle"
        assert payload["corpus"]["count"] == 26
        assert payload["synthetic"] is False

    def test_a_broken_bundle_falls_back_and_says_why(self, monkeypatch, tmp_path):
        bad = tmp_path / "bad.jsonl"
        bad.write_text("{not a bundle")
        with empty_conn() as fresh:
            result = bundle.load_into(fresh, str(bad), now=NOW)
        assert result["ok"] is False
        assert bundle.STATE["source"] == "synthetic"
        assert "not JSON" in bundle.STATE["error"]

    def test_the_function_serves_a_bundle_when_it_is_configured(self, monkeypatch, tmp_path, conn):
        path = tmp_path / "bundle.jsonl"
        bundle.write(conn, path, now=NOW)
        monkeypatch.setenv("KAZIKASI_BUNDLE", str(path))
        # The adapter is not a package; load it the way Vercel does.
        spec = importlib.util.spec_from_file_location("kazi_shim", ROOT / "api" / "index.py")
        shim = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(shim)
        shim._STATE["conn"] = None
        served = shim._connection()
        assert bundle.STATE["source"] == "bundle"
        assert bundle.STATE["count"] >= 20
        assert served.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"] >= 20
