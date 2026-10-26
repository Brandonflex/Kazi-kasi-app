"""One role a week that ignores the filters - and says so.

Filters are how a scope stays honest, and also how it goes stale. Every week the
page offers exactly one advert that the person's constraints would have hidden,
chosen because the evidence says they would be good at it, labelled as an
exception, and dismissed with one click like anything else.

The rules that keep it from being a growth trick:

* **One per week, deterministic.** Same person, same week, same role - from a
  hash, not a random draw, so a reload is not a slot machine.
* **Only a single, fixable blocker.** "6 km past your limit" is a widening of
  the scope; "needs 5 years" is not an opportunity, it is a rejection.
* **Never something they already saw or acted on.** Dismissed, saved, applied
  and shortlisted adverts are out.
* **Never labelled as a recommendation engine.** It says *outside your scope*.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from . import graph, ranking, shortlist, tracking

#: Blockers that are a matter of reach or taste, not of qualification. A role
#: past the commute limit is worth seeing; a role that needs five years is not.
#: The markers match the wording `ranking.constraints` produces.
FIXABLE = ("km away", "beyond your window", " role", " contract")

#: A wildcard has to clear this, or it is just a random job.
MIN_SCORE = 0.40


def week_key(moment: datetime) -> str:
    iso = moment.astimezone(timezone(timedelta(hours=3))).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _pick(candidates: list, seed: str):
    """Deterministic choice: the same week always offers the same role."""
    if not candidates:
        return None
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return candidates[int(digest[:8], 16) % len(candidates)]


def pick(conn, profile, *, now: datetime | None = None):
    """The week's exception, or None when nothing clears the bar."""
    now = now or datetime.now(timezone.utc)
    seen = (
        tracking.dismissed_job_ids(conn, profile.id)
        | tracking.applied_job_ids(conn, profile.id)
        | shortlist.saved_job_ids(conn, profile.id)
    )

    rows = [row for row in graph.feed(conn, limit=500, include_stale=True) if row["id"] not in seen]
    candidates = []
    for row in rows:
        blockers = ranking.constraints(dict(row), profile, now)
        if len(blockers) != 1:
            continue
        if not any(marker in blockers[0] for marker in FIXABLE):
            continue
        # Score it as if the gate were open, so the number on the card is the
        # number the ranking would give it, not a zero caused by the gate.
        open_profile = replace(
            profile,
            max_commute_km=None,
            deadline_within_days=None,
            work_modes=[],
            employment_types=[],
        )
        match = ranking.score_job(dict(row), open_profile, now)
        relevance = match.relevance
        if relevance < MIN_SCORE:
            continue
        deadline = row.get("deadline")
        if deadline:
            try:
                day = datetime.fromisoformat(str(deadline)[:10]).date()
            except ValueError:
                day = None
            if day and day < now.date():
                continue
        candidates.append(
            {
                "job_id": row["id"],
                "title": row.get("title") or "",
                "employer": row.get("employer_name"),
                "blocker": blockers[0],
                "row": dict(row),
                "match": match,
                "relevance": relevance,
            }
        )

    candidates.sort(key=lambda item: (-item["relevance"], item["title"]))
    return _pick(candidates[:8], f"{profile.id}:{week_key(now)}")


def sentence(item: dict, profile) -> str:
    """Why it is here, in the product's voice: plain, specific, unexcited."""
    return (
        f"Outside your scope - {item['blocker']}. We thought you would be good at it, "
        f"so it is here for this week only."
    )
