"""Persistence for the job graph.

SQLite is the development and test backend, chosen because it needs no server.
The schema is written to port to Postgres without redesign: text ISO-8601
timestamps, integer surrogate keys, no SQLite-only types, no triggers. The two
things to revisit for Postgres are ``AUTOINCREMENT`` → ``GENERATED ... AS
IDENTITY`` and ``TEXT`` → ``timestamptz`` for the timestamp columns.

Why a graph and not a table of jobs:

* an **observation** is what one source said at one moment;
* a **job** is the thing a user sees, assembled from one or more observations;
* a **key** is how we found them to be the same.

Keeping those three apart is what makes "this job was on two boards, and one of
them closed it" representable at all. Collapsing them into a single ``jobs``
table is the decision that makes freshness impossible to prove later.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- One thing one source said, at one moment. Never updated in place.
CREATE TABLE IF NOT EXISTS observations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id      TEXT NOT NULL,
    source_job_id  TEXT NOT NULL,
    source_url     TEXT NOT NULL,
    fetched_at     TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    fingerprint    TEXT NOT NULL,
    sha256         TEXT,
    payload        TEXT NOT NULL,
    UNIQUE (source_id, source_job_id, fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_observations_source ON observations (source_id, fetched_at);

-- What a user sees. Denormalised on purpose: the feed is read far more than
-- it is written, and every field here has a traceable source in job_members.
CREATE TABLE IF NOT EXISTS jobs (
    id               TEXT PRIMARY KEY,
    title            TEXT NOT NULL,
    employer_name    TEXT,
    employer_domain  TEXT,
    county           TEXT,
    sub_county       TEXT,
    entry_fit        TEXT NOT NULL DEFAULT 'unknown',
    employment_type  TEXT NOT NULL DEFAULT 'unknown',
    work_mode        TEXT NOT NULL DEFAULT 'unknown',
    deadline         TEXT,
    pay_min          REAL,
    pay_max          REAL,
    pay_period       TEXT,
    first_seen_at    TEXT NOT NULL,
    last_seen_at     TEXT NOT NULL,
    status           TEXT NOT NULL,
    confidence       REAL NOT NULL DEFAULT 0.0,
    scam_flags       TEXT NOT NULL DEFAULT '[]',
    source_count     INTEGER NOT NULL DEFAULT 1,
    primary_observation_id INTEGER REFERENCES observations(id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status, last_seen_at);
CREATE INDEX IF NOT EXISTS idx_jobs_county ON jobs (county, status);
CREATE INDEX IF NOT EXISTS idx_jobs_entry_fit ON jobs (entry_fit, status);

-- Every identity key that resolves to a job: apply target, dedupe key, reference.
CREATE TABLE IF NOT EXISTS job_keys (
    key    TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    kind   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_job_keys_job ON job_keys (job_id);

CREATE TABLE IF NOT EXISTS job_members (
    job_id         TEXT NOT NULL REFERENCES jobs(id),
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    match_reason   TEXT NOT NULL,
    confidence     REAL NOT NULL,
    added_at       TEXT NOT NULL,
    PRIMARY KEY (job_id, observation_id)
);

CREATE INDEX IF NOT EXISTS idx_job_members_observation ON job_members (observation_id);

-- Append-only history. "When did this job first appear, and when did we last
-- see it?" must be answerable without trusting the current row.
CREATE TABLE IF NOT EXISTS job_events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id  TEXT NOT NULL REFERENCES jobs(id),
    kind    TEXT NOT NULL,
    at      TEXT NOT NULL,
    detail  TEXT
);

CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events (job_id, at);

-- Pairs we *almost* merged. Deliberately not auto-merged: a wrong merge hides
-- a real vacancy, and no similarity score is worth losing a job over.
CREATE TABLE IF NOT EXISTS review_queue (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id       INTEGER NOT NULL REFERENCES observations(id),
    candidate_job_id     TEXT NOT NULL REFERENCES jobs(id),
    reason               TEXT NOT NULL,
    score                REAL NOT NULL,
    created_at           TEXT NOT NULL,
    resolved_at          TEXT,
    resolution           TEXT,
    UNIQUE (observation_id, candidate_job_id, reason)
);

CREATE INDEX IF NOT EXISTS idx_review_open ON review_queue (resolved_at, score DESC);

-- ---------------------------------------------------------------------------
-- v3: the product surface. Constraints in, ranked feed out, applies tracked.
-- ---------------------------------------------------------------------------

-- One jobseeker's constraints. Stored, not inferred: the whole promise of the
-- product is that it is tailored to *these* limits, and a user must be able to
-- see and change them.
CREATE TABLE IF NOT EXISTS profiles (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    home_county       TEXT,
    home_area         TEXT,
    max_commute_km    REAL,
    role_families     TEXT NOT NULL DEFAULT '[]',
    entry_fits        TEXT NOT NULL DEFAULT '["open_to_freshers","some_experience"]',
    employment_types  TEXT NOT NULL DEFAULT '[]',
    work_modes        TEXT NOT NULL DEFAULT '[]',
    min_monthly_pay   REAL,
    deadline_within_days INTEGER,
    include_remote    INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

-- Append-only. An apply click is evidence that the feed did its job; a "closed
-- the tab" is evidence that it did not. Never inferred from page views.
CREATE TABLE IF NOT EXISTS apply_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES profiles(id),
    job_id     TEXT NOT NULL REFERENCES jobs(id),
    kind       TEXT NOT NULL,   -- viewed | clicked_through | applied | dismissed | saved
    at         TEXT NOT NULL,
    detail     TEXT
);

CREATE INDEX IF NOT EXISTS idx_apply_events_job ON apply_events (job_id, at);
CREATE INDEX IF NOT EXISTS idx_apply_events_profile ON apply_events (profile_id, at);
"""


def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open a connection, enable foreign keys, and migrate.

    The caller owns the connection and should close it (or use it as a context
    manager). In-memory databases are per-connection: use ``tmp_path`` in tests
    when more than one connection is needed.
    """
    conn = sqlite3.connect(str(path), detect_types=0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    migrate(conn)
    return conn


def _current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return int(row["v"]) if row and row["v"] is not None else 0


def migrate(conn: sqlite3.Connection) -> None:
    """Apply pending migrations in order and record each one.

    Every statement is additive and ``IF NOT EXISTS``, so re-running is safe and
    an existing database from an earlier phase upgrades in place rather than
    needing a rebuild.
    """
    from datetime import datetime, timezone

    conn.executescript(SCHEMA)
    current = _current_version(conn)
    if current == 0:
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
        )
    elif current < SCHEMA_VERSION:
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
        )
    conn.commit()


def _now_iso() -> str:
    """One timestamp format for every table, in UTC."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = (
        "observations",
        "jobs",
        "job_keys",
        "job_members",
        "job_events",
        "review_queue",
        "profiles",
        "apply_events",
    )
    return {name: conn.execute(f"SELECT COUNT(*) AS c FROM {name}").fetchone()["c"] for name in names}
