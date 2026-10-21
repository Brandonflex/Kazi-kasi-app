"""Schema, migrations and the model round-trip."""

import sqlite3

import pytest

from kazikasi import db
from kazikasi.models import JobCandidate, JobPay


def test_connect_creates_the_schema_and_records_a_version(tmp_path):
    conn = db.connect(tmp_path / "kazi.db")
    try:
        version = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()["v"]
        assert version == db.SCHEMA_VERSION
        counts = db.table_counts(conn)
        assert set(counts) == {
            "observations",
            "jobs",
            "job_keys",
            "job_members",
            "job_events",
            "review_queue",
            "profiles",
            "apply_events",
            "subscriptions",
            "digest_runs",
            "digest_items",
            "messages",
            "consent_events",
            "message_receipts",
        }
        assert all(value == 0 for value in counts.values())
    finally:
        conn.close()


def test_migrate_is_idempotent(tmp_path):
    path = tmp_path / "kazi.db"
    first = db.connect(path)
    db.migrate(first)
    db.migrate(first)
    rows = first.execute("SELECT COUNT(*) AS c FROM schema_version").fetchone()["c"]
    first.close()
    assert rows == 1


def test_an_older_database_upgrades_in_place(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    legacy = sqlite3.connect(path)
    legacy.executescript(
        """
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        INSERT INTO schema_version VALUES (2, '2026-10-20T00:00:00+00:00');
        """
    )
    legacy.commit()
    legacy.close()

    conn = db.connect(path)
    try:
        versions = [row["version"] for row in conn.execute("SELECT version FROM schema_version ORDER BY version")]
        assert versions == [2, db.SCHEMA_VERSION]
        assert db.table_counts(conn)["profiles"] == 0
    finally:
        conn.close()


def test_a_v4_database_gains_the_v5_columns_and_tables(tmp_path):
    """The upgrade path Phase 5 databases will actually take."""
    path = tmp_path / "v4.db"
    legacy = sqlite3.connect(path)
    legacy.executescript(
        """
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        INSERT INTO schema_version VALUES (4, '2026-10-20T00:00:00+00:00');
        CREATE TABLE messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            idempotency TEXT NOT NULL UNIQUE,
            profile_id  TEXT NOT NULL,
            channel     TEXT NOT NULL,
            to_msisdn   TEXT NOT NULL,
            body        TEXT NOT NULL,
            kind        TEXT NOT NULL DEFAULT 'digest',
            state       TEXT NOT NULL DEFAULT 'queued',
            attempts    INTEGER NOT NULL DEFAULT 0,
            provider_id TEXT,
            last_error  TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            sent_at     TEXT
        );
        """
    )
    legacy.commit()
    legacy.close()

    conn = db.connect(path)
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(messages)")}
        assert {"run_id", "delivered_at"} <= columns
        assert db.table_counts(conn)["message_receipts"] == 0
        assert db.table_counts(conn)["consent_events"] == 0
        versions = [row["version"] for row in conn.execute("SELECT version FROM schema_version")]
        assert versions == [4, db.SCHEMA_VERSION]
    finally:
        conn.close()


def test_foreign_keys_are_enforced(tmp_path):
    conn = db.connect(tmp_path / "kazi.db")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO job_members (job_id, observation_id, match_reason, confidence, added_at) VALUES (?,?,?,?,?)",
                ("no-such-job", 1, "new", 1.0, "2026-10-20T00:00:00+00:00"),
            )
    finally:
        conn.close()


def test_two_connections_see_the_same_file(tmp_path):
    path = tmp_path / "kazi.db"
    first = db.connect(path)
    first.execute(
        """INSERT INTO jobs (id, title, first_seen_at, last_seen_at, status)
           VALUES ('j1', 'Records Clerk', '2026-10-20T00:00:00+00:00', '2026-10-20T00:00:00+00:00', 'open')"""
    )
    first.commit()
    second = db.connect(path)
    try:
        assert second.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"] == 1
    finally:
        second.close()
        first.close()


def test_candidate_round_trip_through_the_stored_payload():
    from datetime import date

    candidate = JobCandidate(
        source_id="brightermonday",
        source_job_id="BM-1",
        source_url="https://example.co.ke/1",
        title="Software Support Analyst",
        employer_name="Haba Data Systems Ltd",
        county="Nairobi",
        deadline=date(2026, 11, 5),
        pay=JobPay(min_amount=55000, max_amount=75000, currency="KES", period="month", source="stated"),
        entry_fit="open_to_freshers",
        entry_fit_evidence="Fresh graduates are encouraged to apply.",
    )
    restored = JobCandidate.from_dict(candidate.to_dict())
    assert restored.deadline == date(2026, 11, 5)
    assert restored.pay.min_amount == 55000
    assert restored.entry_fit_evidence.startswith("Fresh graduates")


def test_from_dict_tolerates_fields_written_by_an_older_version():
    payload = {
        "source_id": "s",
        "source_job_id": "1",
        "source_url": "u",
        "title": "Clerk",
        "field_that_no_longer_exists": True,
    }
    candidate = JobCandidate.from_dict(payload)
    assert candidate.title == "Clerk"
