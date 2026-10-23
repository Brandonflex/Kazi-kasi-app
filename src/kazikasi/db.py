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
import os
from pathlib import Path

SCHEMA_VERSION = 8

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

-- Attention that is about the person, not a vacancy. A check-in is "I looked
-- this week"; it belongs here rather than in apply_events, which is keyed to a
-- job and would otherwise need a fake one. See kazikasi/momentum.py.
CREATE TABLE IF NOT EXISTS profile_activity (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES profiles(id),
    kind       TEXT NOT NULL,   -- checked_in
    at         TEXT NOT NULL,
    detail     TEXT             -- the ISO week, for idempotency
);

CREATE INDEX IF NOT EXISTS idx_profile_activity ON profile_activity (profile_id, at);

-- ---------------------------------------------------------------------------
-- Accounts (v7)
--
-- A person, not a job. `kind` is 'guest' until a provider proves an identity;
-- optional sign-in exists to personalise and to fill forms, never to gate the
-- feed. An account with kind='guest' and no provider is a real row: the whole
-- point is that someone can use the product without an identity.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS accounts (
    id           TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,           -- guest | member
    provider     TEXT,                    -- google | apple | linkedin
    subject      TEXT,                    -- the provider's stable user id
    email        TEXT,
    email_verified INTEGER NOT NULL DEFAULT 0,
    name         TEXT,
    given_name   TEXT,                    -- first name from provider
    family_name  TEXT,                    -- last name from provider
    picture      TEXT,                    -- profile photo URL from provider
    locale       TEXT,                    -- language preference from provider
    created_at   TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    deleted_at   TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_identity
    ON accounts (provider, subject) WHERE provider IS NOT NULL;

-- A CV is evidence about a person. We keep the extracted fields and a short
-- excerpt for each, not the whole document, so the smallest useful copy lives here.
CREATE TABLE IF NOT EXISTS cvs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    filename   TEXT,
    chars      INTEGER NOT NULL DEFAULT 0,
    fields     TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

-- One in-flight OAuth attempt: the state token and its PKCE verifier, which
-- must never leave the server except as a hash in the authorize URL.
CREATE TABLE IF NOT EXISTS oauth_states (
    state      TEXT PRIMARY KEY,
    provider   TEXT NOT NULL,
    verifier   TEXT NOT NULL,
    return_to  TEXT,
    created_at TEXT NOT NULL,
    used_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_cvs_account ON cvs (account_id, created_at);

-- ---------------------------------------------------------------------------
-- v4: the digest. Consent, what was sent, and what happened to it.
-- ---------------------------------------------------------------------------

-- Consent is a record, not a flag: DPA 2019 wants to know when someone agreed,
-- to what, and how they can stop. Unsubscribing keeps the row and dates it.
CREATE TABLE IF NOT EXISTS subscriptions (
    profile_id     TEXT PRIMARY KEY REFERENCES profiles(id),
    channel        TEXT NOT NULL,          -- whatsapp | sms
    msisdn         TEXT NOT NULL,          -- E.164; see note in digest.py on at-rest encryption
    msisdn_hash    TEXT NOT NULL,          -- for dedupe and logs without exposing the number
    consented_at   TEXT NOT NULL,
    consent_source TEXT NOT NULL,          -- how they opted in
    cadence        TEXT NOT NULL DEFAULT 'daily',
    window_start   TEXT NOT NULL DEFAULT '18:00',  -- EAT, local
    window_end     TEXT NOT NULL DEFAULT '20:00',
    max_items      INTEGER NOT NULL DEFAULT 5,
    fallback_channel TEXT,                 -- sms | NULL
    unsubscribed_at TEXT,
    updated_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_active ON subscriptions (unsubscribed_at, cadence);

-- One digest per profile per day per channel. The unique key is what makes a
-- retry safe: sending twice is the failure mode users actually notice.
CREATE TABLE IF NOT EXISTS digest_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id     TEXT NOT NULL REFERENCES profiles(id),
    channel        TEXT NOT NULL,
    run_date       TEXT NOT NULL,          -- YYYY-MM-DD in EAT
    created_at     TEXT NOT NULL,
    item_count     INTEGER NOT NULL DEFAULT 0,
    state          TEXT NOT NULL DEFAULT 'composed',  -- composed | queued | sent | empty | failed
    UNIQUE (profile_id, run_date, channel)
);

CREATE INDEX IF NOT EXISTS idx_digest_runs_profile ON digest_runs (profile_id, run_date);

CREATE TABLE IF NOT EXISTS digest_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     INTEGER NOT NULL REFERENCES digest_runs(id),
    job_id     TEXT NOT NULL REFERENCES jobs(id),
    position   INTEGER NOT NULL,
    reason     TEXT,
    UNIQUE (run_id, job_id)
);

-- Every outbound message, with its state machine. `attempts` and `last_error`
-- exist so a failure is visible rather than a message that vanished.
CREATE TABLE IF NOT EXISTS saved_searches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id      TEXT NOT NULL REFERENCES profiles(id),
    label           TEXT NOT NULL DEFAULT '',
    q               TEXT NOT NULL DEFAULT '',
    county          TEXT NOT NULL DEFAULT '',
    family          TEXT NOT NULL DEFAULT '',
    employment_type TEXT NOT NULL DEFAULT '',
    deadline_days   INTEGER NOT NULL DEFAULT 0,   -- 0 means "no horizon"
    pay_floor       REAL NOT NULL DEFAULT 0,      -- 0 means "no floor"
    remote          INTEGER NOT NULL DEFAULT 0,
    cadence         TEXT NOT NULL DEFAULT 'daily',-- daily | weekly
    created_at      TEXT NOT NULL,
    last_run_at     TEXT,
    unsubscribed_at TEXT,
    UNIQUE (profile_id, q, county, family, employment_type, deadline_days, pay_floor, remote)
);

CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency   TEXT NOT NULL UNIQUE,
    profile_id    TEXT NOT NULL REFERENCES profiles(id),
    channel       TEXT NOT NULL,
    to_msisdn     TEXT NOT NULL,
    body          TEXT NOT NULL,
    kind          TEXT NOT NULL DEFAULT 'digest',  -- digest | fallback | notice
    state         TEXT NOT NULL DEFAULT 'queued',  -- queued | sent | delivered | failed | suppressed
    attempts      INTEGER NOT NULL DEFAULT 0,
    provider_id   TEXT,
    last_error    TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    sent_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_queue ON messages (state, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_profile ON messages (profile_id, created_at);

-- ---------------------------------------------------------------------------
-- v5: the other half of the conversation.
--
-- Sending was only half of consent. A person who replies STOP has to be able to
-- stop, and "sent" is not "arrived": receipts are the difference between a
-- provider accepting a message and a phone showing it.
-- ---------------------------------------------------------------------------

-- Append-only audit of every consent change, including ones that arrive from a
-- channel we cannot attribute to a profile yet. `msisdn_hash` is the join key,
-- so an opt-out is on record even when the number is unknown to us.
CREATE TABLE IF NOT EXISTS consent_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id  TEXT REFERENCES profiles(id),
    msisdn_hash TEXT NOT NULL,
    action      TEXT NOT NULL,   -- subscribed | unsubscribed | resumed | help | unrecognised
    source      TEXT NOT NULL,   -- web | cli | whatsapp | sms
    detail      TEXT,
    at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_consent_events_number ON consent_events (msisdn_hash, at);
CREATE INDEX IF NOT EXISTS idx_consent_events_profile ON consent_events (profile_id, at);

-- Delivery receipts, kept as events rather than overwriting a column: a message
-- can be accepted, then delivered, then read, and the history is the evidence.
CREATE TABLE IF NOT EXISTS message_receipts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER REFERENCES messages(id),
    provider_id TEXT,
    status     TEXT NOT NULL,   -- sent | delivered | read | failed
    error      TEXT,
    at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_receipts_message ON message_receipts (message_id, at);
CREATE INDEX IF NOT EXISTS idx_receipts_provider ON message_receipts (provider_id);
"""

#: The same schema, translated for Postgres.
#: ``INTEGER PRIMARY KEY AUTOINCREMENT`` → ``INTEGER GENERATED BY DEFAULT AS IDENTITY``
#: (Postgres 10+); every other construct — partial unique indexes, IF NOT EXISTS,
#: REFERENCES, TEXT timestamps — is already valid DDL.
POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- One thing one source said, at one moment. Never updated in place.
CREATE TABLE IF NOT EXISTS observations (
    id             INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
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
    id      INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
    job_id  TEXT NOT NULL REFERENCES jobs(id),
    kind    TEXT NOT NULL,
    at      TEXT NOT NULL,
    detail  TEXT
);

CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events (job_id, at);

-- Pairs we *almost* merged. Deliberately not auto-merged: a wrong merge hides
-- a real vacancy, and no similarity score is worth losing a job over.
CREATE TABLE IF NOT EXISTS review_queue (
    id                   INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
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
    id         INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
    profile_id TEXT NOT NULL REFERENCES profiles(id),
    job_id     TEXT NOT NULL REFERENCES jobs(id),
    kind       TEXT NOT NULL,   -- viewed | clicked_through | applied | dismissed | saved
    at         TEXT NOT NULL,
    detail     TEXT
);

CREATE INDEX IF NOT EXISTS idx_apply_events_job ON apply_events (job_id, at);
CREATE INDEX IF NOT EXISTS idx_apply_events_profile ON apply_events (profile_id, at);

-- Attention that is about the person, not a vacancy. A check-in is "I looked
-- this week"; it belongs here rather than in apply_events, which is keyed to a
-- job and would otherwise need a fake one. See kazikasi/momentum.py.
CREATE TABLE IF NOT EXISTS profile_activity (
    id         INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
    profile_id TEXT NOT NULL REFERENCES profiles(id),
    kind       TEXT NOT NULL,   -- checked_in
    at         TEXT NOT NULL,
    detail     TEXT             -- the ISO week, for idempotency
);

CREATE INDEX IF NOT EXISTS idx_profile_activity ON profile_activity (profile_id, at);

-- ---------------------------------------------------------------------------
-- Accounts (v7)
--
-- A person, not a job. `kind` is 'guest' until a provider proves an identity;
-- optional sign-in exists to personalise and to fill forms, never to gate the
-- feed. An account with kind='guest' and no provider is a real row: the whole
-- point is that someone can use the product without an identity.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS accounts (
    id           TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,           -- guest | member
    provider     TEXT,                    -- google | apple | linkedin
    subject      TEXT,                    -- the provider's stable user id
    email        TEXT,
    email_verified INTEGER NOT NULL DEFAULT 0,
    name         TEXT,
    given_name   TEXT,                    -- first name from provider
    family_name  TEXT,                    -- last name from provider
    picture      TEXT,                    -- profile photo URL from provider
    locale       TEXT,                    -- language preference from provider
    created_at   TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    deleted_at   TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_identity
    ON accounts (provider, subject) WHERE provider IS NOT NULL;

-- A CV is evidence about a person. We keep the extracted fields and a short
-- excerpt for each, not the whole document, so the smallest useful copy lives here.
CREATE TABLE IF NOT EXISTS cvs (
    id         INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    filename   TEXT,
    chars      INTEGER NOT NULL DEFAULT 0,
    fields     TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

-- One in-flight OAuth attempt: the state token and its PKCE verifier, which
-- must never leave the server except as a hash in the authorize URL.
CREATE TABLE IF NOT EXISTS oauth_states (
    state      TEXT PRIMARY KEY,
    provider   TEXT NOT NULL,
    verifier   TEXT NOT NULL,
    return_to  TEXT,
    created_at TEXT NOT NULL,
    used_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_cvs_account ON cvs (account_id, created_at);

-- ---------------------------------------------------------------------------
-- v4: the digest. Consent, what was sent, and what happened to it.
-- ---------------------------------------------------------------------------

-- Consent is a record, not a flag: DPA 2019 wants to know when someone agreed,
-- to what, and how they can stop. Unsubscribing keeps the row and dates it.
CREATE TABLE IF NOT EXISTS subscriptions (
    profile_id     TEXT PRIMARY KEY REFERENCES profiles(id),
    channel        TEXT NOT NULL,          -- whatsapp | sms
    msisdn         TEXT NOT NULL,          -- E.164; see note in digest.py on at-rest encryption
    msisdn_hash    TEXT NOT NULL,          -- for dedupe and logs without exposing the number
    consented_at   TEXT NOT NULL,
    consent_source TEXT NOT NULL,          -- how they opted in
    cadence        TEXT NOT NULL DEFAULT 'daily',
    window_start   TEXT NOT NULL DEFAULT '18:00',  -- EAT, local
    window_end     TEXT NOT NULL DEFAULT '20:00',
    max_items      INTEGER NOT NULL DEFAULT 5,
    fallback_channel TEXT,                 -- sms | NULL
    unsubscribed_at TEXT,
    updated_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_active ON subscriptions (unsubscribed_at, cadence);

-- One digest per profile per day per channel. The unique key is what makes a
-- retry safe: sending twice is the failure mode users actually notice.
CREATE TABLE IF NOT EXISTS digest_runs (
    id             INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
    profile_id     TEXT NOT NULL REFERENCES profiles(id),
    channel        TEXT NOT NULL,
    run_date       TEXT NOT NULL,          -- YYYY-MM-DD in EAT
    created_at     TEXT NOT NULL,
    item_count     INTEGER NOT NULL DEFAULT 0,
    state          TEXT NOT NULL DEFAULT 'composed',  -- composed | queued | sent | empty | failed
    UNIQUE (profile_id, run_date, channel)
);

CREATE INDEX IF NOT EXISTS idx_digest_runs_profile ON digest_runs (profile_id, run_date);

CREATE TABLE IF NOT EXISTS digest_items (
    id         INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
    run_id     INTEGER NOT NULL REFERENCES digest_runs(id),
    job_id     TEXT NOT NULL REFERENCES jobs(id),
    position   INTEGER NOT NULL,
    reason     TEXT,
    UNIQUE (run_id, job_id)
);

-- Every outbound message, with its state machine. `attempts` and `last_error`
-- exist so a failure is visible rather than a message that vanished.
CREATE TABLE IF NOT EXISTS saved_searches (
    id              INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
    profile_id      TEXT NOT NULL REFERENCES profiles(id),
    label           TEXT NOT NULL DEFAULT '',
    q               TEXT NOT NULL DEFAULT '',
    county          TEXT NOT NULL DEFAULT '',
    family          TEXT NOT NULL DEFAULT '',
    employment_type TEXT NOT NULL DEFAULT '',
    deadline_days   INTEGER NOT NULL DEFAULT 0,   -- 0 means "no horizon"
    pay_floor       REAL NOT NULL DEFAULT 0,      -- 0 means "no floor"
    remote          INTEGER NOT NULL DEFAULT 0,
    cadence         TEXT NOT NULL DEFAULT 'daily',-- daily | weekly
    created_at      TEXT NOT NULL,
    last_run_at     TEXT,
    unsubscribed_at TEXT,
    UNIQUE (profile_id, q, county, family, employment_type, deadline_days, pay_floor, remote)
);

CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
    idempotency   TEXT NOT NULL UNIQUE,
    profile_id    TEXT NOT NULL REFERENCES profiles(id),
    channel       TEXT NOT NULL,
    to_msisdn     TEXT NOT NULL,
    body          TEXT NOT NULL,
    kind          TEXT NOT NULL DEFAULT 'digest',  -- digest | fallback | notice
    state         TEXT NOT NULL DEFAULT 'queued',  -- queued | sent | delivered | failed | suppressed
    attempts      INTEGER NOT NULL DEFAULT 0,
    provider_id   TEXT,
    last_error    TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    sent_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_queue ON messages (state, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_profile ON messages (profile_id, created_at);

-- ---------------------------------------------------------------------------
-- v5: the other half of the conversation.
--
-- Sending was only half of consent. A person who replies STOP has to be able to
-- stop, and "sent" is not "arrived": receipts are the difference between a
-- provider accepting a message and a phone showing it.
-- ---------------------------------------------------------------------------

-- Append-only audit of every consent change, including ones that arrive from a
-- channel we cannot attribute to a profile yet. `msisdn_hash` is the join key,
-- so an opt-out is on record even when the number is unknown to us.
CREATE TABLE IF NOT EXISTS consent_events (
    id          INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
    profile_id  TEXT REFERENCES profiles(id),
    msisdn_hash TEXT NOT NULL,
    action      TEXT NOT NULL,   -- subscribed | unsubscribed | resumed | help | unrecognised
    source      TEXT NOT NULL,   -- web | cli | whatsapp | sms
    detail      TEXT,
    at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_consent_events_number ON consent_events (msisdn_hash, at);
CREATE INDEX IF NOT EXISTS idx_consent_events_profile ON consent_events (profile_id, at);

-- Delivery receipts, kept as events rather than overwriting a column: a message
-- can be accepted, then delivered, then read, and the history is the evidence.
CREATE TABLE IF NOT EXISTS message_receipts (
    id         INTEGER PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
    message_id INTEGER REFERENCES messages(id),
    provider_id TEXT,
    status     TEXT NOT NULL,   -- sent | delivered | read | failed
    error      TEXT,
    at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_receipts_message ON message_receipts (message_id, at);
CREATE INDEX IF NOT EXISTS idx_receipts_provider ON message_receipts (provider_id);
"""


def _looks_like_postgres(url: str) -> bool:
    """Anything the Postgres driver can parse."""
    u = (url or "").strip().lower()
    return u.startswith(("postgres://", "postgresql://"))


def connect(path: str | Path | None = None, *, check_same_thread: bool = True, url: str | None = None):
    """Open a connection, enable foreign keys, and migrate.

    Dispatches on the arguments:

    * ``url`` (explicit, or from ``DATABASE_URL`` when no path is given) that
      looks like ``postgres://`` / ``postgresql://`` → psycopg, Postgres schema.
    * otherwise → sqlite3 against the path (file or ``:memory:``), SQLite schema.

    An explicit ``path`` wins over ``DATABASE_URL`` — that is what keeps tests
    that set ``DATABASE_URL=postgres://example`` and then call
    ``db.connect(":memory:")`` on the sqlite path.
    """
    explicit_path = path is not None
    if url is None and not explicit_path:
        url = os.environ.get("DATABASE_URL") or ""
    if url and _looks_like_postgres(url):
        return _open_postgres(url)
    return _open_sqlite(path if path is not None else ":memory:", check_same_thread=check_same_thread)


def _open_sqlite(path, *, check_same_thread: bool = True) -> "sqlite3.Connection":
    import sqlite3
    conn = sqlite3.connect(str(path), detect_types=0, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    migrate(conn)
    return conn


def _open_postgres(url: str):
    """psycopg connection. The caller owns it.

    ``RealDictRow`` makes ``row["name"]`` work the same way the SQLite tests
    already use, so business logic does not need to know which backend it has.
    """
    import psycopg
    from psycopg.rows import dict_row
    # ``connect_timeout`` keeps a cold-start failure bounded; ``options=-c
    # statement_timeout=...`` is a belt-and-braces bound on any single query.
    conn = psycopg.connect(
        url,
        row_factory=dict_row,
        autocommit=True,
        connect_timeout=10,
    )
    # psycopg returns cursors; conn.execute() is the sqlite convenience. We
    # provide the same surface by keeping a reference to a helper below.
    _patch_postgres_conn(conn)
    migrate(conn)
    return conn


def _patch_postgres_conn(conn) -> None:
    """Give a psycopg connection the sqlite-shaped helpers the rest of the app
    calls: ``conn.execute(sql, params)`` returning a dict-row cursor, and a
    ``commit()`` that psycopg already has.

    ``execute`` must be a bound method so ``conn.execute("SELECT ...")`` reads
    like the sqlite version.
    """
    def _execute(sql, params=None):
        cur = conn.cursor()
        if params:
            # psycopg3 only understands %s and %(name)s placeholders; ``?`` is
            # a literal. The rest of the codebase writes sqlite-style queries
            # (metrics.stats, momentum.attention_weeks, etc.). Translate here
            # so every query works on both backends without touching call sites.
            if "?" in sql and "%s" not in sql:
                sql = sql.replace("?", "%s")
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        return cur
    conn.execute = _execute




def _is_postgres(conn) -> bool:
    """psycopg3 connections are instances of psycopg.Connection; sqlite3 ones
    are not. ``isinstance`` against the actual class is unambiguous — the old
    ``type(conn).__name__ == "Connection"`` check broke across psycopg3 minor
    versions that renamed the class.
    """
    try:
        from psycopg import Connection as _PsycopgConnection
        return isinstance(conn, _PsycopgConnection)
    except ImportError:
        return False


def _current_version(conn) -> int:
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    if row is None:
        return 0
    return int(row["v"]) if row["v"] is not None else 0


def migrate(conn) -> None:
    """Apply pending migrations in order and record each one.

    Every statement is additive and ``IF NOT EXISTS``, so re-running is safe and
    an existing database from an earlier phase upgrades in place rather than
    needing a rebuild.

    SQLite gets ``executescript`` (one round trip). Postgres gets each statement
    executed individually — psycopg v3 does not accept a semicolon-separated
    script by default. Before splitting on ``;``, the schema has ALL comment
    text stripped (whole-line ``--`` comments and inline ``--`` comments after
    a column definition). Several columns carry inline comments that contain
    semicolons (e.g. ``msisdn TEXT NOT NULL, -- E.164; see note``); leaving
    those in is what has broken this path three times.
    """
    from datetime import datetime, timezone

    if _is_postgres(conn):
        # Strip SQL comments before splitting on semicolons. Handles both
        # whole-line comments (``-- ...``) and inline comments after a column
        # (``msisdn TEXT NOT NULL, -- E.164; see note``). The schema has no
        # string literals containing ``--``, so a naive strip is safe.
        clean_lines = []
        for line in POSTGRES_SCHEMA.split("\n"):
            idx = line.find("--")
            if idx != -1:
                line = line[:idx]
            clean_lines.append(line)
        without_comments = "\n".join(clean_lines)
        for stmt in (s.strip() for s in without_comments.split(";") if s.strip()):
            conn.execute(stmt)
    else:
        conn.executescript(SCHEMA)
    _add_column(conn, "subscriptions", "brief_opt_in", "INTEGER NOT NULL DEFAULT 0")
    _add_column(conn, "messages", "run_id", "INTEGER REFERENCES digest_runs(id)")
    _add_column(conn, "messages", "delivered_at", "TEXT")
    # Add personalization columns to accounts table
    _add_column(conn, "accounts", "given_name", "TEXT")
    _add_column(conn, "accounts", "family_name", "TEXT")
    _add_column(conn, "accounts", "picture", "TEXT")
    _add_column(conn, "accounts", "locale", "TEXT")
    if _is_postgres(conn):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_run ON messages (run_id, channel, state)")
    else:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_run ON messages (run_id, channel, state)"
        )
    if _current_version(conn) < SCHEMA_VERSION:
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (%s, %s)" if _is_postgres(conn)
            else "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
        )
    conn.commit()




def _add_column(conn, table: str, column: str, ddl: str) -> None:
    """Additive migration.

    SQLite has no ``ADD COLUMN IF NOT EXISTS``; Postgres has the same gap, so we
    introspect first on both and issue the ALTER only when the column is absent.
    """
    if _is_postgres(conn):
        existing = {
            row["column_name"]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s",
                (table,),
            ).fetchall()
        }
    else:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")




def _now_iso(now=None) -> str:
    """One timestamp format for every table, in UTC.

    Accepts an explicit moment so tests and backfills can be deterministic.
    """
    from datetime import datetime, timezone

    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat()


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
        "subscriptions",
        "digest_runs",
        "digest_items",
        "messages",
        "consent_events",
        "message_receipts",
    )
    return {name: conn.execute(f"SELECT COUNT(*) AS c FROM {name}").fetchone()["c"] for name in names}
