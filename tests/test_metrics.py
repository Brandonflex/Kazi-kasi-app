"""Coverage and health numbers, computed over the synthetic corpus."""

from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import db, graph, metrics
from kazikasi.corpus import build_corpus, load_corpus

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


@pytest.fixture
def loaded():
    conn = db.connect()
    load_corpus(conn, now=NOW)
    yield conn
    conn.close()


def test_corpus_is_deterministic():
    first = [(c.source_id, c.source_job_id, c.title) for c in build_corpus(now=NOW)]
    second = [(c.source_id, c.source_job_id, c.title) for c in build_corpus(now=NOW)]
    assert first == second
    assert len(first) == len(set(first))


def test_stats_add_up(loaded):
    payload = metrics.stats(conn=loaded, now=NOW)
    assert payload["jobs"] == sum(payload["by_status"].values())
    assert payload["live_jobs"] == payload["by_status"].get("open", 0) + payload["by_status"].get("needs_review", 0)
    assert payload["observations"] >= payload["jobs"]
    assert 0 <= payload["duplication_rate"] < 1


def test_cross_source_duplicates_were_actually_merged(loaded):
    payload = metrics.stats(conn=loaded, now=NOW)
    # Two planted duplicates: Clerical Officer and Business Development Associate.
    assert payload["cross_source_jobs"] == 2
    assert payload["duplication_rate"] > 0


def test_nairobi_dominates_the_corpus(loaded):
    payload = metrics.stats(conn=loaded, now=NOW)
    assert payload["counties"][0]["county"] == "Nairobi"
    assert payload["counties"][0]["jobs"] > 10


def test_entry_fit_distribution_is_reported(loaded):
    payload = metrics.stats(conn=loaded, now=NOW)
    assert set(payload["entry_fit"]) <= {"open_to_freshers", "some_experience", "experienced", "unknown"}
    assert 0 < payload["entry_fit_share_open_to_freshers"] < 1


def test_review_queue_is_visible(loaded):
    payload = metrics.stats(conn=loaded, now=NOW)
    assert payload["review_queue_open"] == 2


def test_scam_flagged_jobs_are_counted_and_excluded_from_the_feed(loaded):
    payload = metrics.stats(conn=loaded, now=NOW)
    assert payload["scam_flagged_jobs"] == 1
    assert all(row["scam_flags"] == "[]" for row in graph.feed(loaded))


def test_closing_soon_matches_the_jobs_just_before_their_deadline(loaded):
    soon = metrics.closing_soon(loaded, now=NOW, days=7)
    assert soon
    assert all(row["deadline"] <= "2026-10-27" for row in soon)
    assert [row["deadline"] for row in soon] == sorted(row["deadline"] for row in soon)


def test_health_flags_a_source_that_has_not_been_fetched_today(loaded):
    health = {row["source_id"]: row for row in metrics.health(loaded, now=NOW)}
    assert set(health) == {"brightermonday", "fuzu", "myjobmag", "reliefweb"}
    assert all(row["healthy"] for row in health.values())

    later = metrics.health(loaded, now=NOW + timedelta(days=2))
    assert all(not row["healthy"] for row in later)


def test_deadline_urgency():
    assert metrics.deadline_urgency({"deadline": "2026-10-23"}, today=NOW.date()) == 3
    assert metrics.deadline_urgency({"deadline": None}) > 1000
