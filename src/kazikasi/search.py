"""Search: the feed, narrowed by hand instead of by profile.

The feed answers "what should I look at first?". It does not answer "show me
every internship in Nairobi that closes in the next ten days and pays something"
— which is the question someone asks the moment the ranked five do not include
what they were picturing.

This module is that query, kept as plain data so it can be tested without HTML:

* **terms are AND-ed, and search a document, not a column.** Title, employer,
  area, employment type, work mode and entry fit are one string; `"haba nairobi"`
  finds the Westlands role without anyone choosing a field.
* **filters are facts about the advert**, not scores: county, role family,
  employment type, work mode, a pay floor, and a deadline horizon.
* **the scope still applies.** A role outside your commute or entry fit is not
  hidden by search — it is shown *after* the roles you can take, with the reason,
  and only when you ask for it. Hiding it would be tidier and less honest;
  showing it unlabelled would be worse.

`blocked` is a deliberate part of the result shape: the point of
"outside your constraints" is the constraint, so it travels with the row.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from . import graph, ranking, tracking

#: More than this and the query is a paragraph, not a search.
MAX_TERMS = 6

#: Never render more than this in one page; the count still tells the truth.
MAX_RESULTS = 120

FAMILY_CHOICES = (
    "it",
    "customer",
    "finance",
    "admin",
    "sales",
    "hr",
    "operations",
    "data",
    "marketing",
    "legal",
    "health",
    "education",
)


def terms(query: str) -> list[str]:
    """Lower-cased words, in order, deduplicated, capped."""
    seen: list[str] = []
    for word in re.split(r"[\s,]+", (query or "").strip().lower()):
        word = word.strip("\"'()[]")
        if len(word) >= 2 and word not in seen:
            seen.append(word)
    return seen[:MAX_TERMS]


def haystack(row: dict) -> str:
    """Everything a person might type about this advert, in one string."""
    parts = [
        row.get("title"),
        row.get("employer_name"),
        row.get("county"),
        row.get("sub_county"),
        row.get("employment_type"),
        (row.get("work_mode") or "").replace("_", " "),
        (row.get("entry_fit") or "").replace("_", " "),
    ]
    return " ".join(str(part) for part in parts if part).lower().replace("_", " ")


def _matches_terms(row: dict, words: list[str]) -> bool:
    if not words:
        return True
    document = haystack(row)
    return all(word in document for word in words)


def _within(row: dict, days: int | None, now: datetime) -> bool:
    if days is None:
        return True
    days = max(0, min(int(days), 3650))  # a horizon, not an overflow
    raw = row.get("deadline")
    if not raw:
        return False  # a horizon you cannot check is not a match
    try:
        day = date.fromisoformat(str(raw)[:10])
    except ValueError:
        return False
    end = datetime(day.year, day.month, day.day, 23, 59, tzinfo=timezone(timedelta(hours=3)))
    return now <= end <= now + timedelta(days=int(days))


def _pays(row: dict, floor: float | None) -> bool:
    """A pay floor excludes adverts that state nothing — and says so.

    Treating "not stated" as a pass would put unpaid adverts in a search for
    paid ones; treating it as a fail silently hides most of the market. This
    returns them, and the caller reports how many were kept that way.
    """
    if not floor:
        return True
    low = row.get("pay_min")
    if low is None:
        return True  # kept, and labelled "pay not stated"
    return float(low) >= float(floor)


@dataclass
class Result:
    match: ranking.Match
    row: dict
    saved: bool = False
    applied: bool = False

    @property
    def blocked(self) -> bool:
        return not self.match.eligible

    def to_dict(self) -> dict:
        return {
            **self.match.to_dict(),
            "born": self.row.get("first_seen_at"),
            "place": self.row.get("sub_county") or self.row.get("county"),
            "saved": self.saved,
            "applied": self.applied,
        }


@dataclass
class Search:
    query: str
    terms: list[str]
    filters: dict
    matches: list[Result] = field(default_factory=list)
    blocked: list[Result] = field(default_factory=list)
    considered: int = 0
    narrowed: int = 0
    blocked_count: int = 0
    pay_unstated: int = 0
    counties: list[tuple[str, int]] = field(default_factory=list)
    families: list[tuple[str, int]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.matches) + len(self.blocked)

    @property
    def is_empty(self) -> bool:
        return self.total == 0

    @property
    def is_filtered(self) -> bool:
        return bool(self.terms) or any(
            value not in (None, "", False, 0) for value in self.filters.values()
        )

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "terms": self.terms,
            "filters": self.filters,
            "considered": self.considered,
            "narrowed": self.narrowed,
            "blocked_count": self.blocked_count,
            "matches": [item.to_dict() for item in self.matches],
            "blocked": [item.to_dict() for item in self.blocked],
            "pay_unstated": self.pay_unstated,
            "counties": self.counties,
            "families": self.families,
        }


def run(
    conn,
    profile,
    *,
    query: str = "",
    county: str = "",
    family: str = "",
    employment_type: str = "",
    deadline_days: int | None = None,
    pay_floor: float | None = None,
    remote: bool = False,
    include_blocked: bool = False,
    now: datetime | None = None,
) -> Search:
    """One query over the live graph, ranked by the same scorer as the feed."""
    now = now or datetime.now(timezone.utc)
    words = terms(query)
    filters = {
        "county": (county or "").strip() or None,
        "family": (family or "").strip() or None,
        "employment_type": (employment_type or "").strip() or None,
        "deadline_days": int(deadline_days) if deadline_days else None,
        "pay_floor": float(pay_floor) if pay_floor else None,
        "remote": bool(remote),
    }

    rows = graph.feed(conn, limit=800, include_stale=True)
    dismissed = tracking.dismissed_job_ids(conn, profile.id)
    rows = [row for row in rows if row["id"] not in dismissed]
    # Always rank with the blocked rows included: the page needs the *count* of
    # roles just outside the scope even when it is not asked to render them, and
    # a scorer that silently drops them cannot count them.
    ranked = ranking.rank(rows, profile, now=now, limit=len(rows) or 1, include_blocked=True)

    saved = _saved(conn, profile.id)
    applied = tracking.applied_job_ids(conn, profile.id)

    result = Search(
        query=query or "",
        terms=words,
        filters=filters,
        # Every live role the person has not dismissed, in or out of scope: the
        # denominator has to be the size of the market, not the size of the
        # person's slice of it, or "3 of 10" reads as a tiny market.
        considered=len(ranked),
    )
    for match in ranked:
        row = dict(match.row or {})
        if not _matches_terms(row, words):
            continue
        if filters["county"] and (row.get("county") or "").lower() != filters["county"].lower():
            continue
        if filters["family"] and filters["family"] not in match.families:
            continue
        if (
            filters["employment_type"]
            and (row.get("employment_type") or "").lower() != filters["employment_type"].lower()
        ):
            continue
        if filters["remote"] and row.get("work_mode") not in ("remote", "hybrid"):
            continue
        if not _within(row, filters["deadline_days"], now):
            continue
        if not _pays(row, filters["pay_floor"]):
            continue

        item = Result(
            match=match,
            row=row,
            saved=row.get("id") in saved,
            applied=row.get("id") in applied,
        )
        if item.blocked:
            result.blocked_count += 1
            if include_blocked:
                result.blocked.append(item)
                if filters["pay_floor"] and row.get("pay_min") is None:
                    result.pay_unstated += 1
        else:
            result.matches.append(item)
            if filters["pay_floor"] and row.get("pay_min") is None:
                result.pay_unstated += 1

    result.narrowed = len(result.matches) + result.blocked_count
    result.counties = _facets(conn, ranked, lambda row: row.get("county"))
    result.families = _facets(conn, ranked, None)
    return result


def _saved(conn, profile_id: str) -> set[str]:
    rows = conn.execute(
        """SELECT job_id, kind FROM apply_events
            WHERE profile_id = ? AND kind IN ('saved', 'unsaved')
            ORDER BY at ASC, id ASC""",
        (profile_id,),
    ).fetchall()
    state: dict[str, str] = {}
    for row in rows:
        state[row["job_id"]] = row["kind"]
    return {job_id for job_id, kind in state.items() if kind == "saved"}


def _facets(conn, ranked, key) -> list[tuple[str, int]]:
    """What is actually in the corpus, counted — never a hard-coded list."""
    counts: dict[str, int] = {}
    for match in ranked:
        row = dict(match.row or {})
        if not match.eligible:
            continue
        values = [key(row)] if key else list(match.families)
        for value in values:
            if not value:
                continue
            label = str(value)
            counts[label] = counts.get(label, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))[:12]
