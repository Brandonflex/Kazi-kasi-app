"""Matching: constraints first, then relevance, then utility.

D9 in the research pack. Three stages, in this order, because they answer
different questions and must not be blended:

1. **Constraints** - can this person take this job at all? Wrong county, wrong
   work mode, too little pay, too much experience required: excluded, with the
   reason stated. A gate is not a low score; showing an impossible job at 4% is
   worse than not showing it.
2. **Relevance** - is this the kind of work they asked for? Role family overlap
   and title signal.
3. **Utility** - is it worth doing something about *today*? Deadline urgency,
   freshness, whether we can corroborate it, how far it is.

Every component is returned with the numbers that produced it, so the card can
say "closes tomorrow · 4 km away · open to freshers" rather than a bare score.
No model, no embeddings: this is tunable, testable arithmetic, and when it is
wrong it is wrong in a way a person can read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import re

from . import geo
from .profile import Profile, families_for, title_relevance

# Component weights. Relevance leads because a well-timed, nearby job you cannot
# do is still the wrong job.
WEIGHTS = {"relevance": 0.45, "utility": 0.40, "distance": 0.15}

ENTRY_FIT_LABEL = {
    "open_to_freshers": "open to freshers",
    "some_experience": "1–2 years",
    "experienced": "3+ years",
    "unknown": "eligibility unstated",
}


@dataclass
class Match:
    job_id: str
    title: str
    employer: str | None
    eligible: bool
    score: float
    relevance: float
    utility: float
    distance_score: float
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    families: list[str] = field(default_factory=list)
    distance: geo.Distance | None = None
    row: dict | None = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "title": self.title,
            "employer": self.employer,
            "eligible": self.eligible,
            "score": round(self.score, 3),
            "relevance": round(self.relevance, 3),
            "utility": round(self.utility, 3),
            "distance_score": round(self.distance_score, 3),
            "reasons": self.reasons,
            "blockers": self.blockers,
            "families": self.families,
            "distance": self.distance.to_dict() if self.distance else None,
            "deadline": self.row.get("deadline") if self.row else None,
        }


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _age_days(last_seen: str | None, now: datetime) -> int | None:
    if not last_seen:
        return None
    try:
        return max(0, (now - datetime.fromisoformat(last_seen)).days)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------


def constraints(row: dict, profile: Profile, now: datetime | None = None) -> list[str]:
    """Hard blockers. Anything returned here means the job is not shown."""
    now = now or datetime.now(timezone.utc)
    blockers: list[str] = []

    entry_fit = row.get("entry_fit") or "unknown"
    if profile.entry_fits and entry_fit not in profile.entry_fits and entry_fit != "unknown":
        blockers.append(f"needs {ENTRY_FIT_LABEL.get(entry_fit, entry_fit)}")

    if profile.work_modes and (row.get("work_mode") or "unknown") not in profile.work_modes:
        blockers.append(f"{row.get('work_mode') or 'unstated'} role")

    if profile.employment_types and (row.get("employment_type") or "unknown") not in profile.employment_types:
        blockers.append(f"{row.get('employment_type') or 'unstated'} contract")

    if profile.deadline_within_days is not None:
        deadline = _as_date(row.get("deadline"))
        if deadline is not None:
            days = (deadline - now.date()).days
            if days > profile.deadline_within_days:
                blockers.append(f"closes in {days} days, beyond your window")

    distance = geo.distance_between(
        profile.home_area, profile.home_county, row.get("sub_county"), row.get("county")
    )
    remote_ok = profile.include_remote and (row.get("work_mode") == "remote")
    if (
        not remote_ok
        and profile.max_commute_km is not None
        and distance is not None
        and distance.km > profile.max_commute_km
    ):
        blockers.append(f"{distance.km:.0f} km away, beyond your {profile.max_commute_km:g} km limit")

    return blockers


# --------------------------------------------------------------------------
# Components
# --------------------------------------------------------------------------


def relevance_score(row: dict, profile: Profile, families: list[str]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    family = profile.overlapping_role_score(families)
    title = title_relevance(profile, row.get("title") or "")

    matched_skills: list[str] = []
    if profile.skills:
        job_text = f"{row.get('title') or ''} {row.get('description') or row.get('description_md') or ''}".lower()
        matched_skills = [
            skill for skill in profile.skills
            if skill.strip() and re.search(rf"(?<!\w){re.escape(skill.strip().lower())}(?!\w)", job_text)
        ]
        skill_fit = len(matched_skills) / max(1, len(profile.skills))
        score = 0.55 * family + 0.20 * title + 0.25 * skill_fit
        if matched_skills:
            reasons.append("skills: " + ", ".join(matched_skills[:4]))
    else:
        score = 0.7 * family + 0.3 * title

    matched = sorted(set(profile.role_families) & set(families))
    if matched:
        reasons.append("matches " + ", ".join(matched))
    elif families:
        reasons.append("adjacent: " + ", ".join(families))
    else:
        reasons.append("role type unclear from the advert")

    if (row.get("employment_type") or "") in ("internship", "attachment"):
        score = min(1.0, score + 0.05)
        reasons.append(f"{row['employment_type']} - entry route")
    return round(min(1.0, score), 3), reasons


def utility_score(row: dict, profile: Profile, now: datetime) -> tuple[float, list[str]]:
    reasons: list[str] = []
    parts: list[tuple[float, float]] = []

    # Deadline urgency: doing something is worth more as the door closes.
    deadline = _as_date(row.get("deadline"))
    if deadline is not None:
        days = (deadline - now.date()).days
        if days <= 1:
            urgency = 1.0
            reasons.append("closes today" if days == 0 else "closes tomorrow")
        elif days <= 7:
            urgency = 0.85
            reasons.append(f"closes in {days} days")
        elif days <= 21:
            urgency = 0.55
        else:
            urgency = 0.3
        parts.append((0.35, urgency))
    else:
        # No stated deadline is common on boards and is not a defect we can fix.
        reasons.append("no closing date stated")
        parts.append((0.35, 0.35))

    # Freshness: a posting we have not re-seen is worth less, and says so.
    age = _age_days(row.get("last_seen_at"), now)
    if age is None:
        freshness = 0.4
    elif age <= 1:
        freshness = 1.0
    elif age <= 3:
        freshness = 0.75
    elif age <= 7:
        freshness = 0.45
    else:
        freshness = 0.15
        reasons.append(f"not re-checked for {age} days")
    parts.append((0.3, freshness))

    # Corroboration: two independent sources carrying a posting is a real signal.
    sources = int(row.get("source_count") or 1)
    corroboration = 1.0 if sources >= 2 else 0.6
    if sources >= 2:
        reasons.append(f"confirmed on {sources} sources")
    parts.append((0.15, corroboration))

    # Pay: clearing the floor is worth something; missing pay is neutral.
    pay_min = row.get("pay_min")
    pay_max = row.get("pay_max")
    pay = pay_max or pay_min
    if profile.min_monthly_pay and pay:
        period = (row.get("pay_period") or "month").lower()
        monthly = pay * {"month": 1, "year": 1 / 12, "week": 4.33, "day": 21.7, "hour": 173}.get(period, 1)
        pay_fit = 1.0 if monthly >= profile.min_monthly_pay else 0.0
        if pay_fit:
            reasons.append(f"pays above your KES {profile.min_monthly_pay:,.0f} floor")
        parts.append((0.1, pay_fit))
    elif pay:
        parts.append((0.1, 0.8))
        reasons.append("salary stated")
    else:
        parts.append((0.1, 0.4))  # unstated pay is not a red flag on its own

    # Scam signals subtract rather than gate: flags are evidence for a human,
    # not proof, and a wrongly hidden real job is the worse error.
    flags = row.get("scam_flags") or "[]"
    penalty = 0.0
    if flags not in ("[]", "", None):
        penalty = 0.25
        reasons.append("flagged for review")

    total = sum(weight * value for weight, value in parts) - penalty

    # A job that is effectively an internship stipend is worth flagging honestly.
    if (row.get("employment_type") or "") in ("internship", "attachment") and not pay:
        total -= 0.05

    return round(max(0.0, min(1.0, total)), 3), reasons


def distance_component(row: dict, profile: Profile) -> tuple[float, geo.Distance | None, list[str]]:
    if row.get("work_mode") == "remote":
        return 1.0, None, ["remote - no commute"]
    distance = geo.distance_between(
        profile.home_area, profile.home_county, row.get("sub_county"), row.get("county")
    )
    if distance is None:
        return 0.5, None, ["location not stated"]
    reasons = [f"{distance.km:.0f} km away ({distance.band}, approximate)"]
    return round(geo.commute_utility(distance.km), 3), distance, reasons


# --------------------------------------------------------------------------
# The ranked feed
# --------------------------------------------------------------------------


def score_job(row: dict, profile: Profile, now: datetime | None = None) -> Match:
    now = now or datetime.now(timezone.utc)
    families = families_for(row.get("title"), None)

    blockers = constraints(row, profile, now)
    relevance, reason_bits = relevance_score(row, profile, families)
    utility, utility_bits = utility_score(row, profile, now)
    distance_score, distance, distance_bits = distance_component(row, profile)

    total = (
        WEIGHTS["relevance"] * relevance
        + WEIGHTS["utility"] * utility
        + WEIGHTS["distance"] * distance_score
    )

    return Match(
        job_id=row["id"],
        title=row.get("title") or "",
        employer=row.get("employer_name"),
        eligible=not blockers,
        score=round(0.0 if blockers else min(1.0, total), 3),
        relevance=relevance,
        utility=utility,
        distance_score=distance_score,
        reasons=[*reason_bits, *utility_bits, *distance_bits],
        blockers=blockers,
        families=families,
        distance=distance,
        row=dict(row),
    )


def rank(
    rows,
    profile: Profile,
    *,
    now: datetime | None = None,
    limit: int = 40,
    include_blocked: bool = False,
) -> list[Match]:
    """Score and order. Blocked jobs are returned only if explicitly asked for."""
    matches = [score_job(dict(row), profile, now) for row in rows]
    if not include_blocked:
        matches = [match for match in matches if match.eligible]
    matches.sort(
        key=lambda match: (
            not match.eligible,
            -match.score,
            # Ties: the one closing sooner wins, then the closer one.
            (match.row or {}).get("deadline") or "9999",
        )
    )
    return matches[:limit]


def explain(match: Match) -> str:
    """One line a person can read, for the CLI and logs."""
    if not match.eligible:
        return f"{match.title}: excluded - {'; '.join(match.blockers)}"
    return f"{match.title} ({match.score:.2f}): " + " · ".join(match.reasons[:4])


def relevance_ceiling(profile: Profile) -> float:
    """Highest score a perfect job could reach. Used to normalise display bars."""
    return sum(WEIGHTS.values())
