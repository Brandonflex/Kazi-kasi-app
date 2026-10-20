"""D10 — link out, and remember what happened.

The product never applies for anyone. It shows a job, links to the original
advert, and records that the user went. Those records are the only honest way to
answer the questions that matter later: which jobs people actually pursue, which
sources produce jobs worth pursuing, and whether the feed is getting better.

Two rules:

* **Nothing is inferred from a page view.** ``clicked_through`` means the apply
  link was opened; ``applied`` means the user told us they applied. Guessing
  would poison the numbers we plan to learn from.
* **Explicit dismissals are gold.** "Not this" is the strongest signal a feed
  gets, and it is the one most products throw away.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .db import _now_iso

KINDS = ("viewed", "clicked_through", "applied", "dismissed", "saved")


def record(conn, profile_id: str, job_id: str, kind: str, *, detail: str | None = None) -> int:
    """Append one apply-funnel event. Returns the event id."""
    if kind not in KINDS:
        raise ValueError(f"unknown event {kind!r}; expected one of {', '.join(KINDS)}")
    if conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone() is None:
        raise ValueError(f"unknown job {job_id!r}")
    if conn.execute("SELECT 1 FROM profiles WHERE id = ?", (profile_id,)).fetchone() is None:
        raise ValueError(f"unknown profile {profile_id!r}; run `kazikasi profiles --seed`")
    cursor = conn.execute(
        "INSERT INTO apply_events (profile_id, job_id, kind, at, detail) VALUES (?,?,?,?,?)",
        (profile_id, job_id, kind, _now_iso(), detail),
    )
    conn.commit()
    return int(cursor.lastrowid)


def events_for_job(conn, job_id: str) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM apply_events WHERE job_id = ? ORDER BY at", (job_id,)
        )
    ]


def events_for_profile(conn, profile_id: str, limit: int = 100) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            """SELECT e.*, j.title AS job_title, j.employer_name
               FROM apply_events e JOIN jobs j ON j.id = e.job_id
               WHERE e.profile_id = ? ORDER BY e.at DESC LIMIT ?""",
            (profile_id, limit),
        )
    ]


def dismissed_job_ids(conn, profile_id: str) -> set[str]:
    return {
        row["job_id"]
        for row in conn.execute(
            "SELECT DISTINCT job_id FROM apply_events WHERE profile_id = ? AND kind = 'dismissed'",
            (profile_id,),
        )
    }


def applied_job_ids(conn, profile_id: str) -> set[str]:
    return {
        row["job_id"]
        for row in conn.execute(
            "SELECT DISTINCT job_id FROM apply_events WHERE profile_id = ? AND kind IN ('applied', 'clicked_through')",
            (profile_id,),
        )
    }


def funnel(conn, *, days: int = 30, now: datetime | None = None) -> dict:
    """The only funnel that is honest with this little data."""
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT kind, COUNT(*) AS c FROM apply_events WHERE at >= ? GROUP BY kind", (since,)
    ).fetchall()
    counts = {row["kind"]: row["c"] for row in rows}
    clicked = counts.get("clicked_through", 0)
    applied = counts.get("applied", 0)
    return {
        "window_days": days,
        "events": counts,
        "click_through_rate": round(clicked / counts["viewed"], 3) if counts.get("viewed") else None,
        "apply_rate_of_clicks": round(applied / clicked, 3) if clicked else None,
        "dismissals": counts.get("dismissed", 0),
    }


def source_yield(conn, *, days: int = 30, now: datetime | None = None) -> list[dict]:
    """Which sources produce jobs people act on. Phase 2 metrics, answered properly.

    A source that supplies 40% of the feed and 4% of the clicks is not pulling
    its weight, and no amount of volume changes that.
    """
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT o.source_id,
                  COUNT(DISTINCT m.job_id)                                        AS jobs,
                  COUNT(DISTINCT CASE WHEN e.kind IN ('clicked_through','applied')
                                      THEN e.job_id END)                          AS acted_on
           FROM observations o
           LEFT JOIN job_members m ON m.observation_id = o.id
           LEFT JOIN apply_events e ON e.job_id = m.job_id AND e.at >= ?
           GROUP BY o.source_id ORDER BY jobs DESC""",
        (since,),
    ).fetchall()
    out = []
    for row in rows:
        jobs = row["jobs"] or 0
        acted = row["acted_on"] or 0
        out.append(
            {
                "source_id": row["source_id"],
                "jobs": jobs,
                "acted_on": acted,
                "yield": round(acted / jobs, 3) if jobs else 0.0,
            }
        )
    return out
