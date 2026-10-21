"""D8 — the freshness promise, measured and shown.

The product's claim is "current data, constant update". That claim is only worth
anything if it is a number someone can check. So:

* every source has a target cadence (from its ``Manifest``);
* every source is scored against that cadence from its **last observed fetch**;
* the score is published at ``/slo``, including when it is bad.

A job feed that says "verified" without saying when is doing the thing this
product exists to stop.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .sources import REGISTRY

#: A source is amber after one missed cycle and red after three.
AMBER_MULTIPLIER = 1.0
RED_MULTIPLIER = 3.0


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def source_status(conn, source_id: str, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    manifest = REGISTRY[source_id].manifest if source_id in REGISTRY else None
    target_minutes = manifest.cadence_minutes if manifest else 60
    enabled = getattr(manifest, "status", "active") == "active" if manifest else True

    row = conn.execute(
        "SELECT MAX(fetched_at) AS last_fetch, COUNT(*) AS observations FROM observations WHERE source_id = ?",
        (source_id,),
    ).fetchone()
    last_fetch = _parse(row["last_fetch"]) if row else None

    if not enabled:
        # A source we have deliberately not switched on is not "late"; counting it
        # would make the ops page permanently red and teach everyone to ignore it.
        age_minutes = None if last_fetch is None else (now - last_fetch).total_seconds() / 60
        state = "not_enabled"
    elif last_fetch is None:
        age_minutes = None
        state = "never_fetched"
    else:
        age_minutes = (now - last_fetch).total_seconds() / 60
        if age_minutes <= target_minutes * AMBER_MULTIPLIER:
            state = "on_time"
        elif age_minutes <= target_minutes * RED_MULTIPLIER:
            state = "late"
        else:
            state = "stale"

    return {
        "source_id": source_id,
        "label": manifest.label if manifest else source_id,
        "target_minutes": target_minutes,
        "last_fetch": last_fetch.isoformat() if last_fetch else None,
        "age_minutes": round(age_minutes, 1) if age_minutes is not None else None,
        "observations": row["observations"] if row else 0,
        "state": state,
        "enabled": enabled,
        "meets_slo": state == "on_time",
    }


def report(conn, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    statuses = [source_status(conn, source_id, now=now) for source_id in sorted(REGISTRY)]

    known = [status for status in statuses if status["last_fetch"] and status["enabled"]]
    met = sum(1 for status in known if status["meets_slo"])

    # The user-facing promise: how stale is the *feed*, not any one source.
    feed_row = conn.execute("SELECT MAX(last_seen_at) AS newest FROM jobs").fetchone()
    newest = _parse(feed_row["newest"]) if feed_row else None
    feed_age_minutes = round((now - newest).total_seconds() / 60, 1) if newest else None

    return {
        "as_of": now.isoformat(),
        "sources": statuses,
        "sources_reporting": len(known),
        "sources_meeting_slo": met,
        "slo_rate": round(met / len(known), 3) if known else 0.0,
        "feed_last_updated": newest.isoformat() if newest else None,
        "feed_age_minutes": feed_age_minutes,
    }


def worst_state(report_payload: dict) -> str:
    order = {"on_time": 0, "not_enabled": 1, "late": 2, "never_fetched": 3, "stale": 4}
    states = [source["state"] for source in report_payload["sources"] if source.get("enabled", True)]
    return max(states, key=lambda state: order.get(state, 0)) if states else "never_fetched"
