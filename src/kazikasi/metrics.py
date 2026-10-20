"""The numbers we judge the pipeline by.

Two of these decide whether the product's core promise is being kept:

* **duplication rate** — if MyJobMag and BrighterMonday overlap by 40–60% (the
  research estimate) and our rate is near zero, dedupe is broken, not clean.
* **entry-fit share** — the feed is for people with 0–3 years of experience. If
  most live jobs are ``experienced``, the sources are wrong, not the filter.

Everything here is a read; nothing mutates.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone


def _rows(conn, sql: str, params: tuple = ()) -> list:
    return conn.execute(sql, params).fetchall()


def stats(conn, *, now: datetime | None = None, closing_within_days: int = 7) -> dict:
    now = now or datetime.now(timezone.utc)
    today = now.date()

    by_status = {
        row["status"]: row["c"]
        for row in _rows(conn, "SELECT status, COUNT(*) AS c FROM jobs GROUP BY status")
    }
    live = by_status.get("open", 0) + by_status.get("needs_review", 0)
    observations = _rows(conn, "SELECT COUNT(*) AS c FROM observations")[0]["c"]
    jobs = sum(by_status.values())

    cross_source = _rows(conn, "SELECT COUNT(*) AS c FROM jobs WHERE source_count > 1")[0]["c"]
    duplicate_rate = round(1 - (jobs / observations), 3) if observations else 0.0

    entry_fit = {
        row["entry_fit"]: row["c"]
        for row in _rows(
            conn, "SELECT entry_fit, COUNT(*) AS c FROM jobs WHERE status IN ('open','needs_review') GROUP BY entry_fit"
        )
    }
    counties = [
        {"county": row["county"] or "unresolved", "jobs": row["c"]}
        for row in _rows(
            conn,
            """SELECT county, COUNT(*) AS c FROM jobs WHERE status IN ('open','needs_review')
               GROUP BY county ORDER BY c DESC""",
        )
    ]

    cutoff = (today + timedelta(days=closing_within_days)).isoformat()
    closing_soon = _rows(
        conn,
        """SELECT COUNT(*) AS c FROM jobs
           WHERE status IN ('open','needs_review') AND deadline IS NOT NULL AND deadline <= ?""",
        (cutoff,),
    )[0]["c"]

    flagged = [
        row["id"]
        for row in _rows(conn, "SELECT id, scam_flags FROM jobs WHERE status IN ('open','needs_review')")
        if json.loads(row["scam_flags"])
    ]

    per_source = {
        row["source_id"]: row["c"]
        for row in _rows(
            conn,
            """SELECT o.source_id, COUNT(DISTINCT m.job_id) AS c
               FROM observations o LEFT JOIN job_members m ON m.observation_id = o.id
               GROUP BY o.source_id ORDER BY c DESC""",
        )
    }

    return {
        "as_of": now.isoformat(),
        "jobs": jobs,
        "live_jobs": live,
        "observations": observations,
        "by_status": by_status,
        "duplication_rate": duplicate_rate,
        "cross_source_jobs": cross_source,
        "observations_per_job": round(observations / jobs, 2) if jobs else 0.0,
        "entry_fit": entry_fit,
        "entry_fit_share_open_to_freshers": (
            round(entry_fit.get("open_to_freshers", 0) / live, 3) if live else 0.0
        ),
        "counties": counties,
        "closing_within_7_days": closing_soon,
        "scam_flagged_jobs": len(flagged),
        "review_queue_open": _rows(
            conn, "SELECT COUNT(*) AS c FROM review_queue WHERE resolved_at IS NULL"
        )[0]["c"],
        "jobs_per_source": per_source,
        "stale_jobs": by_status.get("stale", 0) + by_status.get("suspect_closed", 0),
    }


def health(conn, *, now: datetime | None = None) -> list[dict]:
    """Per-source health, judged by the only thing that matters: recent sightings."""
    now = now or datetime.now(timezone.utc)
    today = now.date()
    out = []
    for row in _rows(
        conn,
        """SELECT o.source_id,
                  COUNT(DISTINCT m.job_id)                                    AS jobs,
                  COUNT(*)                                                    AS observations,
                  MAX(o.fetched_at)                                           AS last_fetch
           FROM observations o LEFT JOIN job_members m ON m.observation_id = o.id
           GROUP BY o.source_id ORDER BY o.source_id""",
    ):
        last_fetch = row["last_fetch"]
        age_days = None
        if last_fetch:
            age_days = (now - datetime.fromisoformat(last_fetch)).days
        stale = age_days is None or age_days > 1
        out.append(
            {
                "source_id": row["source_id"],
                "jobs": row["jobs"],
                "observations": row["observations"],
                "last_fetch": last_fetch,
                "age_days": age_days,
                "healthy": not stale,
                "checked_on": today.isoformat(),
            }
        )
    return out


def closing_soon(conn, *, now: datetime | None = None, days: int = 7, limit: int = 20) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    cutoff = (now.date() + timedelta(days=days)).isoformat()
    rows = _rows(
        conn,
        """SELECT id, title, employer_name, county, deadline
           FROM jobs WHERE status IN ('open','needs_review')
             AND deadline IS NOT NULL AND deadline <= ? AND deadline >= ?
           ORDER BY deadline LIMIT ?""",
        (cutoff, now.date().isoformat(), limit),
    )
    return [dict(row) for row in rows]


def deadline_urgency(job: dict, *, today: date | None = None) -> int:
    """Days left to apply, or a large number when unbounded."""
    if not job.get("deadline"):
        return 10_000
    return (date.fromisoformat(job["deadline"]) - (today or date.today())).days
