"""The market, as arithmetic.

The public page this feeds is not a blog and not a dashboard: it is the answer
to "what does hiring actually look like in Nairobi this week", computed from the
adverts we have checked, with the sample size and the date range attached.

Three rules, because a public number is a promise:

* **Only what we counted.** No estimates, no extrapolation, no "up to". If four
  adverts stated a monthly salary this week, the median says n = 4.
* **Flagged adverts never enter a public statistic.** They stay in the corpus so
  the review queue can see them, but they do not move a number people quote.
* **Every figure carries its window.** "Live" means open today; "new" means first
  seen in the last seven days and still open.
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone

#: Nairobi time, because every date this product stores is a Kenyan date.
EAT = timezone(timedelta(hours=3))

#: Only these can be shown as work someone could take today.
LIVE_STATUSES = ("open", "needs_review")

_SELECT = """
    SELECT id, title, employer_name, county, sub_county, entry_fit, employment_type,
           work_mode, deadline, pay_min, pay_max, pay_period, first_seen_at,
           last_seen_at, status, scam_flags, source_count
      FROM jobs
"""


def _as_dt(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def live_rows(conn) -> list[dict]:
    """Open, unflagged adverts - the only rows a public number may be built from."""
    rows = conn.execute(_SELECT + " WHERE status IN ('open','needs_review')").fetchall()
    out = []
    for row in rows:
        item = dict(row)
        if json.loads(item.get("scam_flags") or "[]"):
            continue
        out.append(item)
    return out


def band(values: list[float]) -> dict | None:
    """A median with its quartiles and its n. None when there is nothing to say."""
    clean = sorted(float(value) for value in values if value)
    if not clean:
        return None
    if len(clean) == 1:
        return {"n": 1, "p25": clean[0], "median": clean[0], "p75": clean[0]}
    quartiles = statistics.quantiles(clean, n=4, method="inclusive")
    return {
        "n": len(clean),
        "p25": round(quartiles[0]),
        "median": round(statistics.median(clean)),
        "p75": round(quartiles[2]),
    }


def monthly_pay(rows: list[dict]) -> list[float]:
    return [row["pay_min"] for row in rows if row.get("pay_period") == "month" and row.get("pay_min")]


def _closing(row, now: datetime, days: int) -> bool:
    """Deadlines are dates, so the window is dates - the same rule as the feed."""
    raw = row.get("deadline")
    if not raw:
        return False
    try:
        day = datetime.fromisoformat(str(raw)[:10]).date()
    except ValueError:
        return False
    today = now.astimezone(EAT).date()
    return today <= day <= today + timedelta(days=days)


def _new(row, now: datetime, days: int) -> bool:
    seen = _as_dt(row.get("first_seen_at"))
    return bool(seen and seen >= now - timedelta(days=days))


def overview(conn, *, now: datetime | None = None, days: int = 7) -> dict:
    """Everything the pulse page shows, in one read."""
    now = now or datetime.now(timezone.utc)
    rows = live_rows(conn)

    by_county: dict[str, list[dict]] = {}
    for row in rows:
        by_county.setdefault(row.get("county") or "Unresolved", []).append(row)

    counties = []
    for name, group in by_county.items():
        counties.append(
            {
                "county": name,
                "live": len(group),
                "closing": sum(1 for row in group if _closing(row, now, days)),
                "new": sum(1 for row in group if _new(row, now, days)),
                "band": band(monthly_pay(group)),
            }
        )
    counties.sort(key=lambda item: (-item["live"], item["county"]))

    employers: dict[str, int] = {}
    for row in rows:
        if row.get("employer_name"):
            employers[row["employer_name"]] = employers.get(row["employer_name"], 0) + 1

    sources = {
        row["source_id"]: row["c"]
        for row in conn.execute(
            """SELECT o.source_id, COUNT(DISTINCT m.job_id) AS c
                 FROM observations o LEFT JOIN job_members m ON m.observation_id = o.id
                GROUP BY o.source_id ORDER BY c DESC"""
        )
    }

    return {
        "as_of": now,
        "window_days": days,
        "live": len(rows),
        "new": sum(1 for row in rows if _new(row, now, days)),
        "closing": sum(1 for row in rows if _closing(row, now, days)),
        "band": band(monthly_pay(rows)),
        "fresher_share": (
            round(
                100
                * sum(1 for row in rows if row.get("entry_fit") == "open_to_freshers")
                / len(rows)
            )
            if rows
            else None
        ),
        "counties": counties,
        "employers": sorted(employers.items(), key=lambda pair: (-pair[1], pair[0]))[:8],
        "sources": sources,
    }


def county(conn, name: str, *, now: datetime | None = None, days: int = 7) -> dict | None:
    """One county's numbers and its live adverts. None when we have never seen it."""
    now = now or datetime.now(timezone.utc)
    rows = [row for row in live_rows(conn) if (row.get("county") or "") == name]
    if not rows:
        return None
    rows.sort(key=lambda row: (row.get("deadline") or "9999-12-31", row.get("title") or ""))
    return {
        "as_of": now,
        "county": name,
        "window_days": days,
        "live": len(rows),
        "new": sum(1 for row in rows if _new(row, now, days)),
        "closing": sum(1 for row in rows if _closing(row, now, days)),
        "band": band(monthly_pay(rows)),
        "jobs": rows,
    }


def slug(name: str) -> str:
    return "-".join(part for part in str(name).lower().replace("/", " ").split() if part)


def by_slug(conn, wanted: str, *, now: datetime | None = None) -> dict | None:
    names = {
        row["county"]
        for row in conn.execute("SELECT DISTINCT county FROM jobs WHERE county IS NOT NULL")
    }
    for name in names:
        if slug(name) == wanted:
            return county(conn, name, now=now)
    return None
