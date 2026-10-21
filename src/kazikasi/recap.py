"""Your year in the market — the December artifact, built honestly.

The temptation is a Spotify-Wrapped confetti page that reveals how many rejections
you collected. We are not building that. Three constraints hold the whole feature:

1. **Private by default.** The page is not linked from anywhere public, is not in
   the sitemap, and carries `noindex`. It exists for one person at one URL.
2. **Only what we actually recorded.** We know what was shown, saved, opened and
   self-reported. We do **not** know outcomes — no offers, no rejections — and the
   page says so rather than manufacturing an "interview rate".
3. **The shareable card names no employer.** A single card can leave the page; it
   carries counts, months and a band, never the name of a company someone applied
   to. Sharing an application is not ours to do.

Everything is computed from `apply_events`, `profile_activity` and the corpus, so
the page is reproducible: same inputs, same year.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from . import profile as profile_module
from . import ranking, tracking
from .graph import feed as graph_feed

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def _month_name(number: int) -> str:
    return MONTHS[number - 1]


def _median(values: list[float]) -> int | None:
    return round(statistics.median(values)) if values else None


@dataclass
class Recap:
    profile_id: str
    name: str
    year: int
    seen: int = 0
    saved: int = 0
    applied: int = 0
    dismissed: int = 0
    active_months: list[str] = field(default_factory=list)
    most_active: str | None = None
    band_aimed: int | None = None
    band_aimed_n: int = 0
    band_in_scope: int | None = None
    band_in_scope_n: int = 0
    almost: dict | None = None
    closed_while_saved: int = 0
    in_reach_today: int = 0
    months: list[tuple[str, int]] = field(default_factory=list)
    first_event: str | None = None
    last_event: str | None = None

    @property
    def has_history(self) -> bool:
        return self.seen > 0 or self.saved > 0 or self.applied > 0

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "year": self.year,
            "seen": self.seen,
            "saved": self.saved,
            "applied": self.applied,
            "dismissed": self.dismissed,
            "active_months": self.active_months,
            "most_active": self.most_active,
            "band_aimed": self.band_aimed,
            "band_aimed_n": self.band_aimed_n,
            "band_in_scope": self.band_in_scope,
            "band_in_scope_n": self.band_in_scope_n,
            "almost": self.almost,
            "closed_while_saved": self.closed_while_saved,
            "in_reach_today": self.in_reach_today,
            "months": self.months,
            "first_event": self.first_event,
            "last_event": self.last_event,
            "has_history": self.has_history,
        }


def _year_events(conn, profile_id: str, year: int) -> list[dict]:
    rows = conn.execute(
        """SELECT e.*, j.title, j.employer_name, j.deadline, j.pay_min, j.status
             FROM apply_events e JOIN jobs j ON j.id = e.job_id
            WHERE e.profile_id = ? AND substr(e.at, 1, 4) = ?
            ORDER BY e.at""",
        (profile_id, str(year)),
    ).fetchall()
    return [dict(row) for row in rows]


def build(conn, profile, *, year: int | None = None, now: datetime | None = None) -> Recap:
    """One person, one calendar year, only the facts we hold."""
    now = now or datetime.now(timezone.utc)
    year = year or (now + timedelta(hours=3)).year
    events = _year_events(conn, profile.id, year)

    recap = Recap(profile_id=profile.id, name=profile.name, year=year)

    saved_jobs: dict[str, dict] = {}
    applied_jobs: dict[str, bool] = {}
    seen_jobs: set[str] = set()
    dismissed_jobs: set[str] = set()
    per_month: dict[str, int] = {}
    pay_aimed: list[float] = []
    visit_counts: dict[str, int] = {}

    for event in events:
        job_id = event["job_id"]
        seen_jobs.add(job_id)
        per_month[event["at"][:7]] = per_month.get(event["at"][:7], 0) + 1
        if event["kind"] == "viewed":
            visit_counts[job_id] = visit_counts.get(job_id, 0) + 1
        elif event["kind"] == "saved":
            saved_jobs[job_id] = event
            if event.get("pay_min"):
                pay_aimed.append(float(event["pay_min"]))
        elif event["kind"] == "unsaved":
            saved_jobs.pop(job_id, None)
        elif event["kind"] == "applied":
            applied_jobs[job_id] = True
            if event.get("pay_min"):
                pay_aimed.append(float(event["pay_min"]))
        elif event["kind"] == "dismissed":
            dismissed_jobs.add(job_id)

    recap.seen = len(seen_jobs)
    # "Kept" means still on the shortlist and not yet sent — the same rule the
    # activity page uses, so the two pages cannot disagree about one job.
    recap.saved = len([job_id for job_id in saved_jobs if job_id not in applied_jobs])
    recap.applied = len(applied_jobs)
    recap.dismissed = len(dismissed_jobs)
    recap.band_aimed = _median(pay_aimed)
    recap.band_aimed_n = len(pay_aimed)
    recap.months = sorted(per_month.items())

    check_ins = {
        row["at"][:7]
        for row in conn.execute(
            "SELECT at FROM profile_activity WHERE profile_id = ? AND substr(at, 1, 4) = ?",
            (profile.id, str(year)),
        )
    }
    active = sorted(set(per_month) | check_ins)
    recap.active_months = [_month_name(int(month[5:7])) for month in active if len(month) >= 7]
    if per_month:
        busiest = max(sorted(per_month), key=lambda month: per_month[month])
        recap.most_active = _month_name(int(busiest[5:7]))

    if events:
        recap.first_event = events[0]["at"][:10]
        recap.last_event = events[-1]["at"][:10]

    # The band you were shown, not the band you were offered: we never learn the
    # offer, and inventing a comparison would be the one dishonest number here.
    today = now.date()
    rows = graph_feed(conn, limit=500, include_stale=True)
    matches = ranking.rank(rows, profile, now=now, limit=500, include_blocked=True)
    in_scope = [match for match in matches if match.eligible]
    recap.in_reach_today = len(in_scope)
    scope_pay = [
        float(match.row["pay_min"])
        for match in in_scope
        if match.row and match.row.get("pay_min")
    ]
    recap.band_in_scope = _median(scope_pay)
    recap.band_in_scope_n = len(scope_pay)

    # "The one you almost took": opened more than once or saved, never applied,
    # chosen by how close it came to the deadline, then by how often you looked.
    candidates = []
    for job_id, event in saved_jobs.items():
        if job_id in applied_jobs:
            continue
        candidates.append((event, visit_counts.get(job_id, 0)))
    for job_id, count in visit_counts.items():
        if job_id in applied_jobs or job_id in saved_jobs:
            continue
        row = conn.execute(
            "SELECT j.* FROM apply_events e JOIN jobs j ON j.id = e.job_id WHERE e.job_id = ? LIMIT 1",
            (job_id,),
        ).fetchone()
        if row is not None:
            candidates.append((dict(row), count))

    if candidates:
        def rank_key(pair):
            event, count = pair
            deadline = event.get("deadline") or "9999"
            closed = deadline < today.isoformat()
            return (0 if closed else 1, deadline, -count)

        event, count = sorted(candidates, key=rank_key)[0]
        recap.almost = {
            "job_id": event.get("job_id") or event.get("id"),
            "title": event.get("title"),
            "employer": event.get("employer_name"),
            "deadline": event.get("deadline"),
            "opened": count,
            "closed": (event.get("deadline") or "9999") < today.isoformat(),
        }

    recap.closed_while_saved = sum(
        1 for event in saved_jobs.values() if (event.get("deadline") or "9999") < today.isoformat()
    )
    return recap


def headline(recap: Recap) -> str:
    if not recap.has_history:
        return "Your year starts when you do"
    if recap.applied:
        return f"{recap.applied} application{'s' if recap.applied != 1 else ''} out the door"
    if recap.saved:
        return f"{recap.saved} kept, none sent yet"
    return f"{recap.seen} roles looked at"


def card_lines(recap: Recap) -> list[str]:
    """The shareable card. Counts, months, a band — never an employer's name."""
    if not recap.has_history:
        return []
    lines = [f"My {recap.year} in the Nairobi market"]
    bits = [f"{recap.seen} roles seen"]
    if recap.saved:
        bits.append(f"{recap.saved} kept")
    if recap.applied:
        bits.append(f"{recap.applied} applied")
    lines.append(" · ".join(bits))
    if recap.most_active:
        lines.append(f"Most active in {recap.most_active}")
    if recap.band_aimed:
        lines.append(f"Aiming at KES {recap.band_aimed:,.0f} a month")
    lines.append("kazi-kasi.app")
    return lines


def note(recap: Recap) -> str:
    """What we do not know, said out loud, so the page cannot imply more."""
    if not recap.has_history:
        return (
            "Nothing recorded yet this year. Open a role, save one, or tell us you "
            "applied, and this page starts counting — it only ever counts what we "
            "actually saw."
        )
    return (
        "What this page does not know: whether anyone replied, what you were "
        "offered, or how many other people applied. We do not ask, so we do not "
        "invent it."
    )
