"""The shortlist, and the one reminder it earns.

A saved job is the strongest signal this product gets: the user has told us, in
advance, what they intend to do. That makes it the only legitimate reason to
interrupt someone - and the only one we allow ourselves.

Three rules shape this module:

* **Append-only.** Saving, un-saving and being reminded are events, not
  mutations. The history is the truth, and the latest event wins.
* **One reminder, 48 hours out.** Not a countdown, not a nudge per day. If the
  deadline moves, the job is mentioned again when it is true again.
* **No employer ever sees this.** A save is never a lead. It is not shared, not
  sold, and not used to rank the job for anyone else.
"""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone

from . import graph, tracking

#: How close to the deadline the one reminder fires.
REMINDER_HOURS = 48

#: EAT, because every deadline this product stores is a Nairobi deadline.
EAT = timezone(timedelta(hours=3))

#: The public base URL used in reminder text. Override in production.
DEFAULT_BASE = "https://kazi-kasi.app"


def deadline_at(row) -> datetime | None:
    """A date deadline means "end of that day in Nairobi", never midnight UTC."""
    raw = row.get("deadline")
    if not raw:
        return None
    try:
        day = date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None
    return datetime.combine(day, time(23, 59), tzinfo=EAT)


def _states(conn, profile_id: str) -> dict[str, str]:
    """The latest save/dismiss event per job. Older events are history, not state."""
    rows = conn.execute(
        """SELECT e.job_id, e.kind FROM apply_events e
             JOIN (SELECT job_id, MAX(at) AS at FROM apply_events
                    WHERE profile_id = ? AND kind IN ('saved', 'unsaved', 'dismissed')
                    GROUP BY job_id) latest
               ON latest.job_id = e.job_id AND latest.at = e.at
            WHERE e.profile_id = ?""",
        (profile_id, profile_id),
    ).fetchall()
    return {row["job_id"]: row["kind"] for row in rows}


def saved_job_ids(conn, profile_id: str) -> set[str]:
    return {job_id for job_id, kind in _states(conn, profile_id).items() if kind == "saved"}


def save(conn, profile_id: str, job_id: str) -> None:
    tracking.record(conn, profile_id, job_id, "saved")


def unsave(conn, profile_id: str, job_id: str) -> None:
    tracking.record(conn, profile_id, job_id, "unsaved")


def entries(conn, profile_id: str, *, now: datetime | None = None) -> list[dict]:
    """Saved jobs: still-open ones first, soonest deadline first, undated last.

    A shortlist that puts a closed job above a live one is a list that has
    stopped helping. Closed entries stay visible - they are the user's own
    history - but they never displace something still decidable.
    """
    now = now or datetime.now(timezone.utc)
    rows = []
    for job_id in saved_job_ids(conn, profile_id):
        row = graph.job_row(conn, job_id)
        if row is not None:
            rows.append(dict(row))

    def closed(row) -> bool:
        deadline = deadline_at(row)
        return bool(deadline and deadline < now) or row.get("status") not in ("open", "stale")

    return sorted(
        rows,
        key=lambda row: (
            closed(row),
            row.get("deadline") or "9999-12-31",
            row.get("title") or "",
        ),
    )


def _reminded(conn, profile_id: str, job_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM apply_events WHERE profile_id = ? AND job_id = ? AND kind = 'reminded'",
        (profile_id, job_id),
    ).fetchone()
    return row is not None


def closing_soon(conn, profile_id: str, *, now: datetime, hours: int = REMINDER_HOURS) -> list[dict]:
    """Saved jobs whose deadline lands inside the window and has not passed."""
    horizon = now + timedelta(hours=hours)
    out = []
    for row in entries(conn, profile_id, now=now):
        if row.get("status") not in ("open", "stale"):
            continue
        deadline = deadline_at(row)
        if deadline is None:
            continue
        if now <= deadline <= horizon:
            out.append(row)
    return out


def reminder_text(row, *, base: str | None = None) -> str:
    """The exact message a person would receive. One deadline, one link, no upsell."""
    root = (base or os.environ.get("KAZIKASI_BASE_URL") or DEFAULT_BASE).rstrip("/")
    deadline = deadline_at(row)
    when = f"closes {deadline:%a %-d %b}, 11:59pm EAT" if deadline else ""
    employer = row.get("employer_name") or "Employer not stated"
    lines = [f"*{row.get('title') or 'Saved job'}*", employer]
    if when:
        lines.append(f"{when} - on your shortlist")
    else:
        lines.append("on your shortlist")
    lines.append(f"{root}/job/{row.get('id')}")
    return "\n".join(lines)


def reminders_due(conn, profile_id: str, *, now: datetime, base: str | None = None) -> list[dict]:
    """At most one message per job, ever, unless the deadline moves."""
    due = []
    for row in closing_soon(conn, profile_id, now=now):
        if _reminded(conn, profile_id, row["id"]):
            continue
        due.append({"job": row, "text": reminder_text(row, base=base)})
    return due


def mark_reminded(conn, profile_id: str, job_id: str) -> None:
    tracking.record(conn, profile_id, job_id, "reminded")


def compare_fields(rows: list[dict]) -> list[tuple[str, list[str]]]:
    """The rows of the comparison table: label, then one cell per job."""
    def money(row):
        low, high = row.get("pay_min"), row.get("pay_max")
        if low and high and low != high:
            return f"KES {low:,.0f}–{high:,.0f}/{(row.get('pay_period') or 'month')}"
        if low:
            return f"KES {low:,.0f}/{(row.get('pay_period') or 'month')}"
        return "not stated"

    def place(row):
        if row.get("sub_county") and row.get("county"):
            return f"{row['sub_county']}, {row['county']}"
        return row.get("county") or "not stated"

    def deadline(row):
        at = deadline_at(row)
        return f"{at:%a %-d %b}" if at else "not stated"

    return [
        ("Employer", [row.get("employer_name") or "not stated" for row in rows]),
        ("Pay", [money(row) for row in rows]),
        ("Deadline", [deadline(row) for row in rows]),
        ("Place", [place(row) for row in rows]),
        ("Eligibility", [(row.get("entry_fit") or "unknown").replace("_", " ") for row in rows]),
        ("Type", [(row.get("employment_type") or "unknown").replace("_", " ") for row in rows]),
        ("Work mode", [(row.get("work_mode") or "unknown") for row in rows]),
        ("Sources", [str(row.get("source_count") or 1) for row in rows]),
        ("Status", [(row.get("status") or "").replace("_", " ") for row in rows]),
    ]
