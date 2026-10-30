"""Scheduled sweep: fetch each source, update jobs, refresh source health.

Runs from the cron tick (18:00 EAT daily) and on-demand via ``/api/sweep``.
Idempotent: re-running within a source's cadence is a no-op for that source.

Why a separate module and not ``pipeline.ingest``?

``ingest`` is the one-shot import: it fetches a source end-to-end and writes to
the raw store. It does not touch the ``jobs`` table, does not track source
health, and does not decide whether a source is due. The sweep orchestrates
those concerns:

* ``should_run(source, now)`` - has the source been fetched within its cadence?
* ``refresh(source, conn, now)`` - fetch, parse, upsert observations, update
  ``jobs.last_seen_at`` (and flip status from "closed" back to "open" if we see
  it again), record source health.
* ``write_job(candidate, conn, now)`` - upsert a single candidate into ``jobs``
  and ``job_members``, keyed by ``source_id + source_job_id``.

The upsert is the whole point: the sweep is the thing that makes "this job was
open on Monday, closed by Wednesday" representable at all. Without it, the
``last_seen_at`` on a job row never moves and the board thinks every job it ever
scraped is still live.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from . import pipeline
from .models import JobCandidate
from .sources import REGISTRY, Adapter

log = logging.getLogger(__name__)

SOURCE_HEALTH_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_health (
    source_id        TEXT PRIMARY KEY,
    last_seen_at     TEXT,
    last_error       TEXT,
    status           TEXT NOT NULL DEFAULT 'ok',  -- ok | warn | dead
    cadence_minutes  INTEGER NOT NULL DEFAULT 1440,
    updated_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_source_health_status ON source_health (status);
"""


def add_source_health_schema(conn) -> None:
    """Apply the source_health schema. Safe to call on every startup - every
    statement is IF NOT EXISTS."""
    if hasattr(conn, "executescript"):
        # sqlite
        conn.executescript(SOURCE_HEALTH_SCHEMA)
    else:
        # psycopg - split on semicolons
        for stmt in (s.strip() for s in SOURCE_HEALTH_SCHEMA.split(";") if s.strip()):
            conn.execute(stmt)
    conn.commit()


def should_run(adapter: Adapter, now: datetime, conn) -> bool:
    """Is this source due for a fetch right now?

    Returns True if the source has never been fetched, or if the last fetch is
    older than the source's cadence. Sources with status='dead' are skipped
    unless ``force=True`` (caller decides).
    """
    row = conn.execute(
        "SELECT last_seen_at, status FROM source_health WHERE source_id = %s"
        if _is_postgres(conn)
        else "SELECT last_seen_at, status FROM source_health WHERE source_id = ?",
        (adapter.manifest.id,),
    ).fetchone()
    if row is None:
        return True
    if dict(row)["status"] == "dead":
        return False
    last_seen = dict(row)["last_seen_at"]
    if not last_seen:
        return True
    last = datetime.fromisoformat(last_seen)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (now - last) > timedelta(minutes=adapter.manifest.cadence_minutes)


def write_job(candidate: JobCandidate, conn, now: datetime) -> str:
    """Upsert a candidate into jobs + job_members.

    Returns the job id (created or existing). The upsert key is
    ``source_id + source_job_id`` - every source owns its own namespace, so
    "BM-1001" on BrighterMonday and "BM-1001" on Fuzu are two different jobs.

    If the job already exists and its status is "closed", seeing it again flips
    it back to "open" and updates ``last_seen_at``. That is how a job that
    disappears from a board and reappears later is represented: closed, then
    reopened, not deleted.
    """
    job_id = f"{candidate.source_id}:{candidate.source_job_id}"
    payload = candidate.to_dict()

    # Observation row - append-only, keyed by (source_id, source_job_id, fingerprint).
    # Fingerprint is a hash of the candidate's identifying fields; if the provenance
    # has no fingerprint method, fall back to the job id.
    try:
        prov = candidate.provenance()
        fingerprint = f"{prov.source_id}:{prov.source_job_id}:{prov.source_url}"
    except Exception:
        fingerprint = job_id
    if _is_postgres(conn):
        conn.execute(
            "INSERT INTO observations (source_id, source_job_id, source_url, fetched_at, "
            "parser_version, fingerprint, payload) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (source_id, source_job_id, fingerprint) DO NOTHING",
            (
                candidate.source_id,
                candidate.source_job_id,
                candidate.source_url,
                now.isoformat(),
                "1.0",
                fingerprint,
                _json_dumps(payload),
            ),
        )
        obs_id_row = conn.execute(
            "SELECT id FROM observations WHERE source_id = %s AND source_job_id = %s AND fingerprint = %s",
            (candidate.source_id, candidate.source_job_id, fingerprint),
        ).fetchone()
        observation_id = dict(obs_id_row)["id"] if obs_id_row else None
    else:
        conn.execute(
            "INSERT OR IGNORE INTO observations (source_id, source_job_id, source_url, fetched_at, "
            "parser_version, fingerprint, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                candidate.source_id,
                candidate.source_job_id,
                candidate.source_url,
                now.isoformat(),
                "1.0",
                fingerprint,
                _json_dumps(payload),
            ),
        )
        row = conn.execute(
            "SELECT id FROM observations WHERE source_id = ? AND source_job_id = ? AND fingerprint = ?",
            (candidate.source_id, candidate.source_job_id, fingerprint),
        ).fetchone()
        observation_id = dict(row)["id"] if row else None

    # Job upsert.
    status = "open" if candidate.status == "extracted" else candidate.status
    deadline_iso = candidate.deadline.isoformat() if candidate.deadline else None

    if _is_postgres(conn):
        conn.execute(
            "INSERT INTO jobs (id, title, employer_name, employer_domain, county, sub_county, "
            "entry_fit, employment_type, work_mode, deadline, pay_min, pay_max, pay_period, "
            "first_seen_at, last_seen_at, status, confidence, scam_flags, source_count) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1) "
            "ON CONFLICT (id) DO UPDATE SET "
            "last_seen_at = EXCLUDED.last_seen_at, "
            "status = CASE WHEN jobs.status = 'closed' AND EXCLUDED.status = 'open' THEN 'open' ELSE jobs.status END",
            (
                job_id,
                candidate.title,
                candidate.employer_name,
                candidate.employer_domain,
                candidate.county,
                candidate.sub_county,
                candidate.entry_fit,
                candidate.employment_type,
                candidate.work_mode,
                deadline_iso,
                candidate.pay.min_amount if candidate.pay else None,
                candidate.pay.max_amount if candidate.pay else None,
                candidate.pay.period if candidate.pay else None,
                now.isoformat(),
                now.isoformat(),
                status,
                candidate.extraction_confidence,
                _json_dumps(candidate.scam_flags),
            ),
        )
    else:
        conn.execute(
            "INSERT INTO jobs (id, title, employer_name, employer_domain, county, sub_county, "
            "entry_fit, employment_type, work_mode, deadline, pay_min, pay_max, pay_period, "
            "first_seen_at, last_seen_at, status, confidence, scam_flags, source_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1) "
            "ON CONFLICT (id) DO UPDATE SET "
            "last_seen_at = excluded.last_seen_at, "
            "status = CASE WHEN jobs.status = 'closed' AND excluded.status = 'open' THEN 'open' ELSE jobs.status END",
            (
                job_id,
                candidate.title,
                candidate.employer_name,
                candidate.employer_domain,
                candidate.county,
                candidate.sub_county,
                candidate.entry_fit,
                candidate.employment_type,
                candidate.work_mode,
                deadline_iso,
                candidate.pay.min_amount if candidate.pay else None,
                candidate.pay.max_amount if candidate.pay else None,
                candidate.pay.period if candidate.pay else None,
                now.isoformat(),
                now.isoformat(),
                status,
                candidate.extraction_confidence,
                _json_dumps(candidate.scam_flags),
            ),
        )

    # Job membership - link this observation to the job.
    if observation_id is not None:
        if _is_postgres(conn):
            conn.execute(
                "INSERT INTO job_members (job_id, observation_id, match_reason, confidence, added_at) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (job_id, observation_id) DO NOTHING",
                (job_id, observation_id, "source_id+source_job_id", candidate.extraction_confidence, now.isoformat()),
            )
        else:
            conn.execute(
                "INSERT OR IGNORE INTO job_members (job_id, observation_id, match_reason, confidence, added_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (job_id, observation_id, "source_id+source_job_id", candidate.extraction_confidence, now.isoformat()),
            )

    return job_id


def record_source_health(conn, source_id: str, *, status: str, last_error: str | None = None, now: datetime, cadence_minutes: int = 1440) -> None:
    """Upsert source health. Safe to call on every fetch."""
    if _is_postgres(conn):
        conn.execute(
            "INSERT INTO source_health (source_id, last_seen_at, last_error, status, cadence_minutes, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (source_id) DO UPDATE SET "
            "last_seen_at = EXCLUDED.last_seen_at, "
            "last_error = EXCLUDED.last_error, "
            "status = EXCLUDED.status, "
            "cadence_minutes = EXCLUDED.cadence_minutes, "
            "updated_at = EXCLUDED.updated_at",
            (source_id, now.isoformat(), last_error, status, cadence_minutes, now.isoformat()),
        )
    else:
        conn.execute(
            "INSERT INTO source_health (source_id, last_seen_at, last_error, status, cadence_minutes, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (source_id) DO UPDATE SET "
            "last_seen_at = excluded.last_seen_at, "
            "last_error = excluded.last_error, "
            "status = excluded.status, "
            "cadence_minutes = excluded.cadence_minutes, "
            "updated_at = excluded.updated_at",
            (source_id, now.isoformat(), last_error, status, cadence_minutes, now.isoformat()),
        )
    conn.commit()


def refresh(adapter: Adapter, conn, *, now: datetime | None = None, pages: int = 1, limit: int | None = None, timeout: float = 20.0, allow_unverified: bool = False) -> dict[str, Any]:
    """Fetch one HTML/PDF source, normalize candidates, and update the graph.

    ``timeout`` bounds an individual HTTP request. ``limit`` bounds detail
    pages, keeping scheduled sweeps polite and predictable.
    """
    now = now or datetime.now(timezone.utc)
    report: dict[str, Any] = {
        "source_id": adapter.manifest.id,
        "fetched": 0,
        "parsed": 0,
        "stored": 0,
        "verified": 0,
        "errors": [],
    }
    fetcher = pipeline.HttpFetcher(
        timeout=timeout,
        min_interval=max(0.2, 60.0 / max(1, adapter.manifest.rate_limit_per_minute)),
    )
    try:
        ingest_report = pipeline.ingest(
            adapter,
            fetcher,
            _InMemoryRawStore(),
            pages=pages,
            limit=limit,
            verify_records=True,
            allow_unverified=allow_unverified,
        )
    except Exception as exc:  # a source failure must not abort the whole sweep
        log.exception("ingest failed for %s", adapter.manifest.id)
        record_source_health(
            conn, adapter.manifest.id, status="dead", last_error=repr(exc)[:500],
            now=now, cadence_minutes=adapter.manifest.cadence_minutes,
        )
        report["errors"].append({"stage": "ingest", "error": repr(exc)[:500]})
        conn.commit()
        return report
    finally:
        fetcher.close()

    report["fetched"] = ingest_report.payloads + ingest_report.listing_pages
    report["errors"] = ingest_report.errors
    for candidate in ingest_report.candidates:
        try:
            write_job(candidate, conn, now=now)
            report["stored"] += 1
        except Exception as exc:  # one malformed record must not lose its siblings
            log.exception("could not store candidate from %s", adapter.manifest.id)
            report["errors"].append({
                "stage": "write_job",
                "candidate": f"{candidate.source_id}:{candidate.source_job_id}",
                "error": repr(exc)[:500],
            })
    report["parsed"] = len(ingest_report.candidates)
    report["verified"] = sum(candidate.status == "open" for candidate in ingest_report.candidates)

    no_verified_jobs = report["verified"] == 0
    health_status = "warn" if report["errors"] or no_verified_jobs else "ok"
    error_summary = None
    if report["errors"]:
        error_summary = "; ".join(str(item.get("error", "source error")) for item in report["errors"][:2])[:500]
    elif no_verified_jobs:
        error_summary = "no parsed candidates passed verification for the live feed"
    record_source_health(
        conn, adapter.manifest.id, status=health_status, last_error=error_summary,
        now=now, cadence_minutes=adapter.manifest.cadence_minutes,
    )
    conn.commit()
    return report


def refresh_reliefweb(adapter, conn, *, now: datetime | None = None, limit: int = 100, timeout: float = 20.0) -> dict[str, Any]:
    """Ingest ReliefWeb's official JSON API, which does not use HTML detail pages."""
    if not adapter.appname:
        return {
            "source_id": adapter.manifest.id, "fetched": 0, "parsed": 0,
            "stored": 0, "verified": 0, "errors": [], "skipped": "RELIEFWEB_APPNAME is not configured",
        }
    now = now or datetime.now(timezone.utc)
    report = {"source_id": adapter.manifest.id, "fetched": 0, "parsed": 0, "stored": 0, "verified": 0, "errors": []}
    fetcher = pipeline.HttpFetcher(timeout=timeout, min_interval=6.0)
    try:
        payload = fetcher.get(adapter.manifest.listing_urls[0], json_body=adapter.request_body())
        items = adapter.parse_listing(payload.text)[:limit]
        candidates = [pipeline.verify(adapter.item_to_candidate(item)) for item in items]
        report["fetched"] = 1
        report["parsed"] = len(candidates)
        report["verified"] = sum(candidate.status == "open" for candidate in candidates)
        for candidate in candidates:
            write_job(candidate, conn, now)
            report["stored"] += 1
        status = "ok" if report["verified"] else "warn"
        error = None if report["verified"] else "no API candidates passed verification for the live feed"
    except Exception as exc:
        log.exception("ReliefWeb ingest failed")
        report["errors"].append({"stage": "api", "error": repr(exc)[:500]})
        status, error = "warn", repr(exc)[:500]
    finally:
        fetcher.close()
    record_source_health(conn, adapter.manifest.id, status=status, last_error=error,
                         now=now, cadence_minutes=adapter.manifest.cadence_minutes)
    conn.commit()
    return report


def run_sweep(
    conn, *, now: datetime | None = None, force: bool = False,
    timeout: float = 20.0, limit: int | None = 15,
    allow_unverified: bool = False, source_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Refresh due, verified sources and return a per-source report.

    Unverified sources are reported as skipped instead of being marked dead.
    ``source_ids`` can restrict a run to an explicit allow-list. Each detail
    crawl is bounded by ``limit`` and each HTTP request by ``timeout``.
    """
    now = now or datetime.now(timezone.utc)
    add_source_health_schema(conn)
    requested = set(REGISTRY.keys() if source_ids is None else source_ids)
    unknown = requested - set(REGISTRY)
    if unknown:
        raise ValueError(f"unknown source ids: {', '.join(sorted(unknown))}")
    totals = {"fetched": 0, "parsed": 0, "stored": 0, "verified": 0, "errors": 0, "ran": 0, "skipped": 0}
    reports: list[dict[str, Any]] = []
    for source_id in sorted(requested):
        adapter = REGISTRY[source_id]()
        if adapter.manifest.status != "active" and not allow_unverified:
            totals["skipped"] += 1
            reports.append({
                "source_id": source_id, "fetched": 0, "parsed": 0, "stored": 0, "verified": 0,
                "errors": [], "skipped": f"source status is {adapter.manifest.status}",
            })
            continue
        if not force and not should_run(adapter, now, conn):
            totals["skipped"] += 1
            reports.append({
                "source_id": source_id, "fetched": 0, "parsed": 0, "stored": 0, "verified": 0,
                "errors": [], "skipped": "within source refresh cadence",
            })
            continue
        totals["ran"] += 1
        from .sources.reliefweb import ReliefWeb
        if isinstance(adapter, ReliefWeb):
            report = refresh_reliefweb(adapter, conn, now=now, limit=limit or 100, timeout=timeout)
        else:
            report = refresh(
                adapter, conn, now=now, timeout=timeout, limit=limit,
                allow_unverified=allow_unverified,
            )
        if report.get("skipped"):
            totals["ran"] -= 1
            totals["skipped"] += 1
        reports.append(report)
        totals["fetched"] += report["fetched"]
        totals["parsed"] += report["parsed"]
        totals["stored"] += report["stored"]
        totals["verified"] += report.get("verified", 0)
        totals["errors"] += len(report["errors"])
    return {"sources": reports, "totals": totals}


# --- internals ---------------------------------------------------------------

class _InMemoryRawStore:
    """A raw store that throws away the payload.

    The sweep's job is to update the jobs table; the raw HTML belongs in a
    separate archive step (``pipeline.ingest`` with a real RawStore). Until that
    is wired, we accept the fetch but do not store the bytes.
    """

    def put(self, raw: bytes, content_type: str, meta: dict) -> None:
        return None


def _is_postgres(conn) -> bool:
    return type(conn).__name__ == "Connection" and hasattr(conn, "info")


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, default=str)
