"""The employer as a body of evidence, not a logo.

A candidate deciding whether to spend an evening on an application wants to know
three things a job card cannot answer: *does this employer actually hire*, *what
do they pay when they say*, and *how long do they leave you*. Every number below
is computed from adverts we already hold, and every number carries its sample.

Two rules shape the whole module:

* **A merge is shown, not hidden.** "Haba Data Systems" and "Haba Data Systems
  Ltd" are treated as one employer, and the page lists the names it merged. A
  silent merge would confidently report the wrong history.
* **Silence is a finding.** If they have never published a salary, the page says
  "never stated" rather than showing a market average as though it were theirs.

The dossier is not for sale and never will be without a label: employer ranking
is not a product we sell, and a candidate who cannot trust the order cannot use
the list.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import profile as profile_module
from . import pulse

LEGAL_SUFFIXES = (
    "limited", "ltd", "plc", "llp", "inc", "inc.", "incorporated", "co", "co.",
    "company", "kenya",
)
SLUG = re.compile(r"[^a-z0-9]+")


def normalise(name: str | None) -> str:
    """The grouping key: case, punctuation and legal form are not identity."""
    if not name:
        return ""
    words = SLUG.sub(" ", name.strip().lower()).split()
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def slug(name: str | None) -> str:
    return SLUG.sub("-", normalise(name)).strip("-")


def display(name: str | None) -> str:
    """The shortest name the employer has used, so the heading is not the longest advert."""
    return (name or "Employer not stated").strip()


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values)) if values else None


def _as_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


@dataclass
class Report:
    name: str
    key: str
    variants: list[str] = field(default_factory=list)
    live: int = 0
    total: int = 0
    first_seen: str | None = None
    last_seen: str | None = None
    counties: list[tuple[str, int]] = field(default_factory=list)
    families: list[tuple[str, int]] = field(default_factory=list)
    pay: dict = field(default_factory=dict)
    closing: dict = field(default_factory=dict)
    months: list[tuple[str, int]] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)
    flagged: int = 0
    jobs: list[dict] = field(default_factory=list)
    cadence_days: float | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "key": self.key,
            "variants": self.variants,
            "live": self.live,
            "total": self.total,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "counties": self.counties,
            "families": self.families,
            "pay": self.pay,
            "closing": self.closing,
            "months": self.months,
            "checks": self.checks,
            "flagged": self.flagged,
            "jobs": self.jobs,
            "cadence_days": self.cadence_days,
        }


def _jobs_for(conn, key: str) -> list[dict]:
    """Every advert whose employer name normalises to this key."""
    rows = [dict(row) for row in conn.execute("SELECT * FROM jobs ORDER BY first_seen_at")]
    return [row for row in rows if normalise(row["employer_name"]) == key]


def resolve(conn, wanted: str | None) -> str | None:
    """Accept "Haba Data Systems Ltd", "haba-data-systems" or the bare slug."""
    if not wanted:
        return None
    target = normalise(wanted.replace("-", " "))
    keys = {normalise(row["employer_name"]) for row in conn.execute("SELECT employer_name FROM jobs")}
    keys.discard("")
    if target in keys:
        return target
    slugged = slug(wanted)
    for key in keys:
        if slug(key) == slugged:
            return key
    return None


def report(conn, wanted: str | None, *, now=None) -> Report | None:
    key = resolve(conn, wanted)
    if not key:
        return None
    rows = _jobs_for(conn, key)
    if not rows:
        return None
    today = (now.date() if now else date.today())
    live_rows = [row for row in rows if row["status"] == "open" and (row.get("deadline") or "9999") >= today.isoformat()]

    variants = sorted({row["employer_name"] for row in rows if row["employer_name"]})
    name = min(variants, key=lambda value: (len(value), value)) if variants else "Employer not stated"

    counties: dict[str, int] = {}
    families: dict[str, int] = {}
    months: dict[str, int] = {}
    pays: list[float] = []
    lead_times: list[int] = []
    opens: list[date] = []
    flagged = 0

    for row in rows:
        if row["county"]:
            counties[row["county"]] = counties.get(row["county"], 0) + 1
        for family in profile_module.families_for(row["title"]) or ["other"]:
            families[family] = families.get(family, 0) + 1
        seen = _as_date(row.get("first_seen_at"))
        deadline = _as_date(row.get("deadline"))
        if seen:
            months[seen.strftime("%Y-%m")] = months.get(seen.strftime("%Y-%m"), 0) + 1
            opens.append(seen)
        if seen and deadline and deadline >= seen:
            lead_times.append((deadline - seen).days)
        if row.get("pay_min"):
            pays.append(float(row["pay_min"]))
        if row.get("scam_flags") not in (None, "", "[]"):
            flagged += 1

    cadence = None
    opens.sort()
    if len(opens) >= 2:
        gaps = [(later - earlier).days for earlier, later in zip(opens, opens[1:])]
        cadence = round(statistics.median(gaps), 1)

    pay = {
        "stated": len(pays),
        "median": _median(pays),
        "low": min(pays) if pays else None,
        "high": max(pays) if pays else None,
        "period": next((row.get("pay_period") for row in reversed(rows) if row.get("pay_min")), None),
        "share": round(len(pays) / len(rows), 2),
    }
    closing = {
        "n": len(lead_times),
        "median_days": round(statistics.median(lead_times)) if lead_times else None,
        "shortest": min(lead_times) if lead_times else None,
        "within_week_share": round(sum(1 for days in lead_times if days <= 7) / len(lead_times), 2)
        if lead_times
        else None,
    }

    # What we can check, and what we cannot. These are verifiable facts about the
    # advert, not a trust score, and nothing here is paid for.
    domains = sorted({row["employer_domain"] for row in rows if row.get("employer_domain")})
    sources = sorted(
        {
            row["source_id"]
            for row in conn.execute(
                """SELECT DISTINCT o.source_id
                     FROM observations o
                     JOIN jobs j ON j.primary_observation_id = o.id
                    WHERE j.employer_name IN ({})""".format(",".join("?" * len(variants))),
                tuple(variants),
            )
        }
    ) if variants else []
    checks = [
        {
            "label": "Adverts seen",
            "value": f"{len(rows)} since {min(opens).strftime('%B %Y')}" if opens else f"{len(rows)}",
            "ok": True,
        },
        {
            "label": "Own domain used",
            "value": ", ".join(domains) if domains else "no domain given in any advert",
            "ok": bool(domains),
        },
        {
            "label": "Sources",
            "value": ", ".join(sources) if sources else "not recorded",
            "ok": bool(sources),
        },
        {
            "label": "Flagged adverts",
            "value": str(flagged) if flagged else "none",
            "ok": flagged == 0,
        },
    ]

    jobs = [
        {
            "id": row["id"],
            "title": row["title"],
            "county": row.get("county"),
            "deadline": row.get("deadline"),
            "pay_min": row.get("pay_min"),
            "pay_max": row.get("pay_max"),
            "pay_period": row.get("pay_period"),
            "entry_fit": row.get("entry_fit"),
        }
        for row in sorted(live_rows, key=lambda row: row.get("deadline") or "9999")
    ]

    return Report(
        name=name,
        key=key,
        variants=variants,
        live=len(live_rows),
        total=len(rows),
        first_seen=min(opens).isoformat() if opens else None,
        last_seen=max((_as_date(row.get("last_seen_at")) for row in rows), default=None).isoformat()
        if any(row.get("last_seen_at") for row in rows)
        else None,
        counties=sorted(counties.items(), key=lambda pair: (-pair[1], pair[0])),
        families=sorted(families.items(), key=lambda pair: (-pair[1], pair[0])),
        pay=pay,
        closing=closing,
        months=sorted(months.items()),
        checks=checks,
        flagged=flagged,
        jobs=jobs,
        cadence_days=cadence,
    )


def index(conn, *, now=None, limit: int | None = None) -> list[dict]:
    """Every employer with at least one live advert, most live first.

    Ties break on the employer's name, never on anything that can be bought.
    """
    today = (now.date() if now else date.today())
    rows = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM jobs WHERE status = 'open' AND (deadline IS NULL OR deadline >= ?)",
            (today.isoformat(),),
        )
    ]
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        key = normalise(row["employer_name"])
        if not key:
            continue
        grouped.setdefault(key, []).append(row)

    entries = []
    for key, group in grouped.items():
        pays = [float(row["pay_min"]) for row in group if row.get("pay_min")]
        entries.append(
            {
                "name": display(min({row["employer_name"] for row in group}, key=len)),
                "key": key,
                "slug": slug(key),
                "live": len(group),
                "median_pay": _median(pays),
                "pay_n": len(pays),
                "counties": sorted({row["county"] for row in group if row.get("county")}),
            }
        )
    entries.sort(key=lambda item: (-item["live"], item["name"]))
    return entries[:limit] if limit else entries


def line(report_: Report) -> str:
    """One honest sentence for a job page."""
    bits = [f"{report_.live} open now" if report_.live else "no adverts open right now"]
    if report_.total > report_.live:
        bits.append(f"{report_.total} advertised since {_month(report_.first_seen)}")
    if report_.pay["median"]:
        bits.append(f"median advertised minimum {report_.pay['median']:,.0f}")
    return " · ".join(bits)


def _month(stamp: str | None) -> str:
    if not stamp:
        return "we started counting"
    parsed = _as_date(stamp)
    return parsed.strftime("%B %Y") if parsed else "we started counting"
