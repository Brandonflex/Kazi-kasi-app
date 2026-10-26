"""The weekly brief: what changed in your band, in one message.

The digest answers "what is new that fits". The brief answers the slower, more
interesting question: *is this market moving toward me or away from me?* - and
it is the surface that gives a returning visitor something to read when nothing
new has arrived.

Every figure is computed from the corpus with its window attached, and the
message has a hard length limit, because it is read on a phone.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone

from . import momentum, pulse, ranking

EAT = timezone(timedelta(hours=3))


def _as_dt(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _median(values):
    clean = [value for value in values if value]
    return round(statistics.median(clean)) if clean else None


def _in_scope(rows, profile, now):
    """Eligible matches, plus the score, without the ranking limit."""
    out = []
    for row in rows:
        if ranking.constraints(dict(row), profile, now):
            continue
        out.append(ranking.score_job(dict(row), profile, now))
    out.sort(key=lambda match: (-match.score, match.row.get("deadline") or "9999"))
    return out


def overview(conn, profile, *, now: datetime | None = None, days: int = 7) -> dict:
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    previous_start = start - timedelta(days=days)

    rows = pulse.live_rows(conn)
    matches = _in_scope([row for row in rows], profile, now)

    fresh, carried, paid_this, paid_last = [], [], [], []
    for match in matches:
        row = match.row
        seen = _as_dt(row.get("first_seen_at"))
        if seen and seen >= start:
            fresh.append(match)
        elif seen:
            carried.append(match)
        if row.get("pay_period") == "month" and row.get("pay_min") and seen:
            if seen >= start:
                paid_this.append(row["pay_min"])
            elif previous_start <= seen < start:
                paid_last.append(row["pay_min"])

    closing = 0
    for match in matches:
        raw = match.row.get("deadline")
        if not raw:
            continue
        try:
            day = datetime.fromisoformat(str(raw)[:10]).date()
        except ValueError:
            continue
        today = now.astimezone(EAT).date()
        if today <= day <= today + timedelta(days=days):
            closing += 1

    this_band, last_band = _median(paid_this), _median(paid_last)
    if this_band and last_band:
        delta = round(100 * (this_band - last_band) / last_band)
    else:
        delta = None

    families: dict[str, int] = {}
    for match in matches:
        for name in match.families[:1]:
            families[name] = families.get(name, 0) + 1

    move = None
    if fresh:
        best = fresh[0]
        move = {
            "title": best.title,
            "employer": best.employer,
            "job_id": best.job_id,
            "reason": (best.reasons[0] if best.reasons else "new in your scope"),
        }

    return {
        "as_of": now,
        "week": momentum.week_key(now),
        "days": days,
        "in_scope": len(matches),
        "new": len(fresh),
        "closing": closing,
        "band_this_week": this_band,
        "band_last_week": last_band,
        "delta_pct": delta,
        "sample": len(paid_this),
        "families": sorted(families.items(), key=lambda pair: (-pair[1], pair[0]))[:3],
        "move": move,
        "momentum": momentum.status(conn, profile.id, now=now),
    }


def headline(data: dict, profile) -> str:
    """The one sentence a person reads first. No exclamation marks, ever."""
    if data["new"] == 0:
        return "Nothing new in your scope this week. That is a real answer, not a silence."
    name = profile.name.split(" — ")[0]
    return (
        f"{data['new']} new {'role' if data['new'] == 1 else 'roles'} landed in "
        f"{name}'s scope this week."
    )


def band_line(data: dict) -> str:
    if not data["delta_pct"]:
        return "Not enough adverts stated pay to compare this week with last."
    direction = "up" if data["delta_pct"] > 0 else "down"
    return (
        f"Advertised pay {direction} {abs(data['delta_pct'])}% on last week "
        f"(KES {data['band_last_week']:,} → {data['band_this_week']:,}, n={data['sample']})."
    )


def message(data: dict, profile, *, base: str | None = None) -> str:
    """The WhatsApp brief. Short, dated, and one action."""
    from .shortlist import DEFAULT_BASE
    import os

    root = (base or os.environ.get("KAZIKASI_BASE_URL") or DEFAULT_BASE).rstrip("/")
    lines = [
        f"*Kazi-Kasi · week {data['week'].split('-W')[1]}*",
        headline(data, profile),
    ]
    if data["closing"]:
        lines.append(f"{data['closing']} closing in the next {data['days']} days.")
    if data["delta_pct"]:
        lines.append(band_line(data))
    if data["move"]:
        move = data["move"]
        lines.append(f"Start with: {move['title']}" + (f" - {move['employer']}" if move["employer"] else ""))
        lines.append(f"{root}/job/{move['job_id']}")
    lines.append(f"{root}/brief")
    return "\n".join(lines)
