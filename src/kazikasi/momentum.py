"""Momentum: a weekly run, with one free skip.

Nobody job-hunts every day, so the unit is the week. A week counts if the person
paid attention - opened the brief, saved something, followed an advert, told us
they applied, or dismissed a role as not for them. Applying is not required,
because the product cannot control outcomes and should not pretend to.

The rules, and why they are these rules:

* **One skipped week is forgiven, once.** Duolingo's evidence is that streaks
  survive because of the repair mechanic, not despite it; a run that breaks on a
  bad week teaches people to stop rather than to restart.
* **Attention, never applications.** Counting applications would make the
  product optimise for volume, and volume is how job boards become spam.
* **Weeks are ISO weeks in EAT.** Monday to Sunday, Nairobi time, because that
  is the week the person is living in.
* **No points, no badges, no flame.** Four small marks and a sentence.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

EAT = timezone(timedelta(hours=3))

#: What counts as paying attention. `reminded` and `viewed` do not: one is the
#: system talking, the other is a page being rendered.
ATTENTION = ("saved", "clicked_through", "applied", "dismissed")

#: How far back the run may reach.
MAX_WEEKS = 52


def week_key(moment: datetime) -> str:
    """ISO week in Nairobi time, e.g. ``2026-W43``."""
    local = moment.astimezone(EAT)
    iso = local.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _previous(key: str) -> str:
    year, week = key.split("-W")
    monday = datetime.fromisocalendar(int(year), int(week), 1).replace(tzinfo=EAT)
    return week_key(monday - timedelta(days=1))


def _as_dt(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def attention_weeks(conn: sqlite3.Connection, profile_id: str) -> set[str]:
    """Weeks in which this person did something, or looked at the brief."""
    rows = conn.execute(
        f"""SELECT at FROM apply_events
             WHERE profile_id = ? AND kind IN ({','.join('?' for _ in ATTENTION)})
            UNION ALL
            SELECT at FROM profile_activity WHERE profile_id = ? AND kind = 'checked_in'""",
        (profile_id, *ATTENTION, profile_id),
    ).fetchall()
    weeks = set()
    for row in rows:
        moment = _as_dt(row["at"])
        if moment:
            weeks.add(week_key(moment))
    return weeks


def check_in(conn: sqlite3.Connection, profile_id: str, *, now: datetime) -> bool:
    """Record that this profile looked this week. Idempotent; returns True if new."""
    key = week_key(now)
    existing = conn.execute(
        "SELECT 1 FROM profile_activity WHERE profile_id = ? AND kind = 'checked_in' AND detail = ?",
        (profile_id, key),
    ).fetchone()
    if existing or key in attention_weeks(conn, profile_id):
        return False
    conn.execute(
        "INSERT INTO profile_activity (profile_id, kind, at, detail) VALUES (?,?,?,?)",
        (profile_id, "checked_in", now.isoformat(), key),
    )
    conn.commit()
    return True


def status(conn: sqlite3.Connection, profile_id: str, *, now: datetime | None = None) -> dict:
    """The run, the marks, and whether the skip is still in hand."""
    now = now or datetime.now(timezone.utc)
    weeks = attention_weeks(conn, profile_id)
    this_week = week_key(now)

    # Walk back from this week, allowing one missed week to be bridged.
    run = 0
    skip_used = False
    cursor = this_week
    for _ in range(MAX_WEEKS):
        if cursor in weeks:
            run += 1
        elif not skip_used:
            skip_used = True
        else:
            break
        cursor = _previous(cursor)

    # A week that has not been touched yet is not a broken run until it ends,
    # so the walk above already forgives it (it becomes the skip).
    if run == 0:
        skip_used = False
    marks = []
    cursor = this_week
    for _ in range(8):
        marks.append(cursor in weeks)
        cursor = _previous(cursor)
    marks.reverse()

    local = now.astimezone(EAT)
    days_left = 6 - local.weekday()
    resets = (local + timedelta(days=days_left)).replace(
        hour=23, minute=59, second=0, microsecond=0
    )
    return {
        "run": run,
        "unit": "weeks",
        "this_week": this_week in weeks,
        "skip_used": skip_used,
        "skip_in_hand": not skip_used,
        "marks": marks,
        "week": this_week,
        "resets_at": resets,
        "weeks_seen": len(weeks),
    }


def line(state: dict) -> str:
    """One sentence, the same on the feed, the brief and the digest."""
    if state["run"] == 0:
        return "No run yet - one week is all it takes to start."
    if state["run"] == 1:
        return "Week 1 of your run. One more and it starts to feel like a habit."
    if not state["this_week"]:
        return (
            f"{state['run']} weeks. This week is untouched - your skip is covering it."
            if state["skip_in_hand"]
            else f"{state['run']} weeks. This week is untouched."
        )
    return f"{state['run']} weeks running. Nothing else to do until Sunday."
