"""Application tracker — Mokaru-style pipeline.

Tracks a user's journey from discovering a job to getting an offer.
Stages: watchlist → saved → applied → screening → interview → offer → rejected

Key patterns borrowed from Mokaru:
- One-click save instantly computes match score
- Match details show matching AND missing keywords
- Status machine with real transitions
- Follow-up reminders per application
- Contact tracking per application
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional


# Status machine: ordered pipeline
STAGES = [
    "watchlist",
    "saved",
    "applied",
    "screening",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
]

ACTIVE_STATUSES = {"watchlist", "saved", "applied", "screening", "interview"}
TERMINAL_STATUSES = {"offer", "rejected", "withdrawn"}

STAGE_LABELS = {
    "watchlist": "Watching",
    "saved": "Saved",
    "applied": "Applied",
    "screening": "Screening",
    "interview": "Interview",
    "offer": "Offer",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}


def _now(now: Optional[datetime] = None) -> datetime:
    return now or datetime.now(timezone.utc)


def save(
    conn,
    account_id: str,
    job_id: str,
    *,
    status: str = "saved",
    match_score: Optional[float] = None,
    match_details: Optional[dict] = None,
    salary_seen: Optional[str] = None,
    source_url: Optional[str] = None,
    now: Optional[datetime] = None,
) -> int:
    """Save or update an application record. Upserts on (account_id, job_id)."""
    moment = _now(now).isoformat()
    details_json = json.dumps(match_details, ensure_ascii=False) if match_details else "{}"

    row = conn.execute(
        """SELECT id, status FROM applications
           WHERE account_id = ? AND job_id = ?""",
        (account_id, job_id),
    ).fetchone()

    if row:
        # Update existing
        conn.execute(
            """UPDATE applications
               SET status = ?, last_action_at = ?,
                   match_score = COALESCE(?, match_score),
                   match_details = COALESCE(?, match_details),
                   salary_seen = COALESCE(?, salary_seen),
                   source_url = COALESCE(?, source_url)
               WHERE id = ?""",
            (status, moment, match_score, details_json, salary_seen, source_url, row["id"]),
        )
        conn.commit()
        return int(row["id"])

    # Insert new
    cursor = conn.execute(
        """INSERT INTO applications
           (account_id, job_id, status, last_action_at, match_score,
            match_details, salary_seen, source_url, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
        (account_id, job_id, status, moment, match_score,
         details_json, salary_seen, source_url, moment),
    )
    row_id = int(cursor.fetchone()[0])
    conn.commit()
    return row_id


def update_status(conn, application_id: int, new_status: str, *, now: Optional[datetime] = None) -> None:
    """Transition an application to a new status."""
    if new_status not in STAGES:
        raise ValueError(f"Invalid status: {new_status}. Must be one of {STAGES}")

    moment = _now(now).isoformat()
    applied_at_clause = ""
    applied_at_values = []

    if new_status == "applied":
        applied_at_clause = ", applied_at = ?"
        applied_at_values = [moment]

    conn.execute(
        f"""UPDATE applications
            SET status = ?, last_action_at = ?{applied_at_clause}
            WHERE id = ?""",
        (*applied_at_values, new_status, moment, application_id),
    )
    conn.commit()


def get(conn, account_id: str, job_id: str) -> Optional[dict]:
    """Get one application record."""
    row = conn.execute(
        """SELECT * FROM applications
           WHERE account_id = ? AND job_id = ?""",
        (account_id, job_id),
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    try:
        item["match_details"] = json.loads(item.get("match_details") or "{}")
    except json.JSONDecodeError:
        item["match_details"] = {}
    return item


def list_by_status(conn, account_id: str, status: Optional[str] = None) -> list[dict]:
    """List applications, optionally filtered by status."""
    if status:
        rows = conn.execute(
            """SELECT * FROM applications
               WHERE account_id = ? AND status = ?
               ORDER BY last_action_at DESC""",
            (account_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM applications
               WHERE account_id = ?
               ORDER BY last_action_at DESC""",
            (account_id,),
        ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        try:
            item["match_details"] = json.loads(item.get("match_details") or "{}")
        except json.JSONDecodeError:
            item["match_details"] = {}
        result.append(item)
    return result


def stats(conn, account_id: str) -> dict:
    """Pipeline statistics for the dashboard."""
    rows = conn.execute(
        """SELECT status, COUNT(*) as count
           FROM applications
           WHERE account_id = ?
           GROUP BY status""",
        (account_id,),
    ).fetchall()

    counts = {row["status"]: row["count"] for row in rows}
    total = sum(counts.values())

    return {
        "total": total,
        "by_status": {status: counts.get(status, 0) for status in STAGES},
        "active": sum(counts.get(s, 0) for s in ACTIVE_STATUSES),
        "converted": counts.get("offer", 0),
        "rejected": counts.get("rejected", 0),
    }


def compute_match_score(cv_fields: dict, job_keywords: list[str]) -> dict:
    """Compute match score between CV fields and job keywords.

    Returns dict with:
        - score: 0.0 to 1.0
        - matching: keywords found in CV
        - missing: keywords not found in CV
        - suggestions: what to emphasize

    This is the core Mokaru-style feature: transparent match scoring.
    """
    if not cv_fields or not job_keywords:
        return {"score": 0.0, "matching": [], "missing": job_keywords, "suggestions": []}

    # Extract all text from CV fields
    cv_text = ""
    for field_data in cv_fields.values():
        if isinstance(field_data, dict):
            val = field_data.get("value", "")
            if isinstance(val, list):
                cv_text += " " + " ".join(str(v) for v in val)
            else:
                cv_text += " " + str(val)
        elif isinstance(field_data, list):
            cv_text += " " + " ".join(str(v) for v in field_data)
        else:
            cv_text += " " + str(field_data)

    cv_lower = cv_text.lower()
    matching = []
    missing = []

    for keyword in job_keywords:
        kw_lower = keyword.lower()
        # Simple substring match (semantic matching would need embeddings)
        if kw_lower in cv_lower or any(
            word in cv_lower for word in kw_lower.split()
        ):
            matching.append(keyword)
        else:
            missing.append(keyword)

    total = len(job_keywords)
    score = len(matching) / total if total > 0 else 0.0

    # Generate suggestions
    suggestions = []
    if missing:
        suggestions.append(f"Consider adding these keywords to your CV: {', '.join(missing[:5])}")
    if matching and score < 0.5:
        suggestions.append("You have some relevant skills, but this role may require more experience")
    if score >= 0.7:
        suggestions.append("Strong match! Your CV aligns well with this role")

    return {
        "score": round(score, 2),
        "matching": matching,
        "missing": missing,
        "suggestions": suggestions,
    }


def follow_ups_due(conn, account_id: str, now: Optional[datetime] = None) -> list[dict]:
    """Get applications that need follow-up."""
    moment = _now(now).isoformat()
    rows = conn.execute(
        """SELECT * FROM applications
           WHERE account_id = ? AND follow_up_at IS NOT NULL
           AND follow_up_at <= ?
           AND status IN (?, ?, ?)
           ORDER BY follow_up_at ASC""",
        (account_id, moment, "applied", "screening", "interview"),
    ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        try:
            item["match_details"] = json.loads(item.get("match_details") or "{}")
        except json.JSONDecodeError:
            item["match_details"] = {}
        result.append(item)
    return result
