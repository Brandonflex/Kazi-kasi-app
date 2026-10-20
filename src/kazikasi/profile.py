"""What a jobseeker is actually looking for — constraints, not a CV.

The research was specific about the audience: 0–3 years of experience, all
white-collar, searching from one place, on a phone, with a commute they can
afford. So the profile is deliberately small:

* **where** they are (county + area, for distance) and how far they will travel;
* **what** they are looking for (role families, not a free-text query);
* **what they can accept** (entry fit, employment type, work mode, pay floor);
* **how fresh** a posting has to be.

Nothing here is inferred. A tailored feed the user cannot inspect is just an
opaque feed, and this product's whole claim is that it tells you *why*.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .extract import title_tokens

# --------------------------------------------------------------------------
# Role families
# --------------------------------------------------------------------------

#: Deliberately coarse. These are the lanes a Kenyan graduate actually searches
#: in, and a title is assigned to at most two of them.
ROLE_FAMILIES: dict[str, tuple[str, ...]] = {
    "it": (
        "software", "developer", "engineer", "ict", "support analyst",
        "data analyst", "data scientist", "data engineer", "database",
        "systems", "network", "devops", "qa", "tester", "it officer",
        "technical support", "helpdesk", "cyber",
    ),
    "finance": (
        "finance", "account", "audit", "tax", "treasury", "bookkeep",
        "credit", "payable", "receivable", "cpa",
    ),
    "admin": (
        "administrator", "administration", "admin", "secretary", "clerical",
        "records", "registry", "front office", "receptionist", "office assistant",
        "data entry", "personal assistant",
    ),
    "operations": (
        "operations", "logistics", "procurement", "supply chain", "warehouse",
        "stores", "fleet", "dispatch", "coordinator",
    ),
    "sales": (
        "sales", "business development", "account manager", "retail", "telesales",
        "field sales", "agents",
    ),
    "marketing": (
        "marketing", "communications", "brand", "social media", "content",
        "public relations", "graphic", "digital marketing",
    ),
    "hr": (
        "human resources", "hr ", "recruit", "people", "talent", "payroll",
        "industrial relations",
    ),
    "programme": (
        "programme", "program", "project", "monitoring", "evaluation", "m&e",
        "community", "field officer", "ngo", "humanitarian", "volunteer",
    ),
    "customer": (
        "customer", "client service", "call centre", "call center", "support",
        "service desk",
    ),
    "legal": ("legal", "advocate", "paralegal", "compliance", "counsel"),
    "health": ("nurse", "clinical", "health", "pharmac", "lab ", "medical"),
    "education": ("teacher", "tutor", "lecturer", "training", "instructor"),
}

FAMILY_PATTERNS = {
    family: re.compile(r"\b(?:" + "|".join(re.escape(term) for term in terms) + r")", re.I)
    for family, terms in ROLE_FAMILIES.items()
}


def families_for(title: str | None, description: str | None = None) -> list[str]:
    """Best-effort families for a job. Title first; description only to break ties."""
    found = [family for family, pattern in FAMILY_PATTERNS.items() if pattern.search(title or "")]
    if not found and description:
        found = [family for family, pattern in FAMILY_PATTERNS.items() if pattern.search(description[:600])]
    return found


# --------------------------------------------------------------------------
# Profile
# --------------------------------------------------------------------------

ENTRY_FIT_ORDER = ("open_to_freshers", "some_experience", "experienced", "unknown")


@dataclass
class Profile:
    id: str
    name: str
    home_county: str | None = "Nairobi"
    home_area: str | None = None
    max_commute_km: float | None = 25.0
    role_families: list[str] = field(default_factory=list)
    entry_fits: list[str] = field(default_factory=lambda: ["open_to_freshers", "some_experience"])
    employment_types: list[str] = field(default_factory=list)  # empty = any
    work_modes: list[str] = field(default_factory=list)  # empty = any
    min_monthly_pay: float | None = None
    deadline_within_days: int | None = None  # only posts closing by then
    include_remote: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = self.__dict__.copy()
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        payload = dict(data)
        for key in ("created_at", "updated_at"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                payload[key] = datetime.fromisoformat(value)
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in payload.items() if k in known})

    def describe(self) -> str:
        bits = [self.home_area or self.home_county or "anywhere"]
        if self.max_commute_km:
            bits.append(f"≤ {self.max_commute_km:g} km")
        if self.role_families:
            bits.append(" / ".join(self.role_families))
        return " · ".join(bits)

    def overlapping_role_score(self, families: list[str]) -> float:
        """Jaccard between what the user wants and what the job is."""
        wanted, offered = set(self.role_families), set(families)
        if not wanted or not offered:
            return 0.5  # no stated preference, or an unclassifiable title
        return len(wanted & offered) / len(wanted | offered)


# --------------------------------------------------------------------------
# Demo profiles
# --------------------------------------------------------------------------

DEMO_PROFILES: tuple[Profile, ...] = (
    Profile(
        id="demo-fresher",
        name="Wanjiru — IT graduate, 0 years",
        home_county="Nairobi",
        home_area="Kasarani",
        max_commute_km=18.0,
        role_families=["it", "admin", "customer"],
        entry_fits=["open_to_freshers"],
        min_monthly_pay=None,
    ),
    Profile(
        id="demo-two-years",
        name="Otieno — finance, 2 years",
        home_county="Nairobi",
        home_area="Westlands",
        max_commute_km=12.0,
        role_families=["finance", "operations"],
        entry_fits=["some_experience", "open_to_freshers"],
        min_monthly_pay=40000,
    ),
    Profile(
        id="demo-public-sector",
        name="Amina — any entry-level public service post",
        home_county="Nairobi",
        home_area="Embakasi",
        max_commute_km=30.0,
        role_families=["admin", "programme", "operations"],
        entry_fits=["open_to_freshers", "some_experience"],
        deadline_within_days=30,
    ),
    Profile(
        id="demo-remote",
        name="Brian — remote-only, marketing",
        home_county="Nairobi",
        home_area="Kilimani",
        max_commute_km=None,
        role_families=["marketing", "customer"],
        entry_fits=["open_to_freshers", "some_experience"],
        work_modes=["remote", "hybrid"],
    ),
)


def seed_profiles(conn, profiles=None) -> int:
    """Insert the demo profiles if they are missing. Returns how many were added."""
    added = 0
    for profile in profiles or DEMO_PROFILES:
        exists = conn.execute("SELECT 1 FROM profiles WHERE id = ?", (profile.id,)).fetchone()
        if exists:
            continue
        save_profile(conn, profile)
        added += 1
    conn.commit()
    return added


def save_profile(conn, profile: Profile) -> None:
    from .db import _now_iso

    now = _now_iso()
    conn.execute(
        """INSERT INTO profiles
           (id, name, home_county, home_area, max_commute_km, role_families, entry_fits,
            employment_types, work_modes, min_monthly_pay, deadline_within_days,
            include_remote, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             name = excluded.name,
             home_county = excluded.home_county,
             home_area = excluded.home_area,
             max_commute_km = excluded.max_commute_km,
             role_families = excluded.role_families,
             entry_fits = excluded.entry_fits,
             employment_types = excluded.employment_types,
             work_modes = excluded.work_modes,
             min_monthly_pay = excluded.min_monthly_pay,
             deadline_within_days = excluded.deadline_within_days,
             include_remote = excluded.include_remote,
             updated_at = excluded.updated_at""",
        (
            profile.id,
            profile.name,
            profile.home_county,
            profile.home_area,
            profile.max_commute_km,
            json.dumps(profile.role_families),
            json.dumps(profile.entry_fits),
            json.dumps(profile.employment_types),
            json.dumps(profile.work_modes),
            profile.min_monthly_pay,
            profile.deadline_within_days,
            int(profile.include_remote),
            now,
            now,
        ),
    )
    conn.commit()


def load_profile(conn, profile_id: str) -> Profile | None:
    row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["role_families"] = json.loads(data["role_families"])
    data["entry_fits"] = json.loads(data["entry_fits"])
    data["employment_types"] = json.loads(data["employment_types"])
    data["work_modes"] = json.loads(data["work_modes"])
    data["include_remote"] = bool(data["include_remote"])
    return Profile.from_dict(data)


def list_profiles(conn) -> list[Profile]:
    return [load_profile(conn, row["id"]) for row in conn.execute("SELECT id FROM profiles ORDER BY name")]


def title_relevance(profile: Profile, title: str) -> float:
    """Token overlap between the job title and the families the user wants."""
    tokens = title_tokens(title)
    wanted_terms: set[str] = set()
    for family in profile.role_families:
        for term in ROLE_FAMILIES.get(family, ()):
            wanted_terms.update(term.split())
    if not tokens or not wanted_terms:
        return 0.0
    return len(tokens & wanted_terms) / len(tokens)
