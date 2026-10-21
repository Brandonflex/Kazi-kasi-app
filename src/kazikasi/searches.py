"""Saved searches: the search you meant, watched for you.

Phase 12 built the query. A saved search is that query with a name and a clock —
the one feature that turns "there is nothing today" into a message three days
later when something appears.

Four rules, and every one of them is a test:

* **Consent first.** A saved search is not a subscription. It only ever sends
  through an *active* subscription, and saving one without a subscription is
  refused with the reason — not queued and quietly dropped.
* **New means new.** The first run starts at the moment the search was saved, and
  every run advances the watermark to the moment it ran. A job that was already
  there yesterday is not news today.
* **One message per search per period.** The idempotency key is the day (or the
  ISO week), so a re-run, a crash and a restart converge; and a search that keeps
  matching the same three jobs does not keep texting about them.
* **Quiet when nothing changed.** No "no new matches" message, ever. Silence is
  the feature; a notification that says nothing teaches people to ignore the ones
  that matter.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import outbox, search as search_module
from .digest import Outgoing

CADENCES = ("daily", "weekly")
#: More than this and the message is a list, not a nudge.
MAX_ITEMS = 3

DEFAULT_BASE = "https://kazi-kasi-app.vercel.app"


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def _base(base: str | None = None) -> str:
    return (base or os.environ.get("KAZIKASI_BASE_URL") or DEFAULT_BASE).rstrip("/")


def filters(q, county, family, employment_type, deadline_days, pay_floor, remote) -> dict:
    """The canonical form stored in the row, with 0/'' meaning "not set"."""
    return {
        "q": (q or "").strip(),
        "county": (county or "").strip(),
        "family": (family or "").strip(),
        "employment_type": (employment_type or "").strip(),
        "deadline_days": int(deadline_days or 0),
        "pay_floor": float(pay_floor or 0),
        "remote": 1 if remote else 0,
    }


def label_for(values: dict) -> str:
    """What the person would call this search. Built from the filters, not typed."""
    parts = []
    if values["q"]:
        parts.append(f"“{values['q']}”")
    if values["family"]:
        parts.append(values["family"])
    if values["employment_type"]:
        parts.append(values["employment_type"].replace("_", " "))
    if values["county"]:
        parts.append(f"in {values['county']}")
    if values["remote"]:
        parts.append("remote")
    if values["pay_floor"]:
        parts.append(f"≥ KES {values['pay_floor']:,.0f}")
    if values["deadline_days"]:
        parts.append(f"closing within {values['deadline_days']} days")
    return " ".join(parts) or "everything live"


def watch(
    conn,
    profile_id: str,
    *,
    q: str = "",
    county: str = "",
    family: str = "",
    employment_type: str = "",
    deadline_days: int | None = None,
    pay_floor: float | None = None,
    remote: bool = False,
    cadence: str = "daily",
    now: datetime | None = None,
) -> dict:
    """Save (or re-save) a search. Requires a live subscription, and says so."""
    moment = _now(now)
    subscription = outbox.load_subscription(conn, profile_id)
    if subscription is None or not subscription.active:
        return {
            "state": "no_consent",
            "saved": False,
            "detail": "A saved search sends messages, so it needs a subscription first.",
        }
    if cadence not in CADENCES:
        raise ValueError(f"unsupported cadence {cadence!r}; choose one of {', '.join(CADENCES)}")

    values = filters(q, county, family, employment_type, deadline_days, pay_floor, remote)
    label = label_for(values)
    existing = conn.execute(
        """SELECT * FROM saved_searches
            WHERE profile_id = ? AND q = ? AND county = ? AND family = ?
              AND employment_type = ? AND deadline_days = ? AND pay_floor = ? AND remote = ?""",
        (
            profile_id,
            values["q"],
            values["county"],
            values["family"],
            values["employment_type"],
            values["deadline_days"],
            values["pay_floor"],
            values["remote"],
        ),
    ).fetchone()
    if existing is not None:
        # Re-saving an opted-out search re-subscribes it, but never rewinds the
        # watermark: the messages it missed are still missed.
        conn.execute(
            "UPDATE saved_searches SET unsubscribed_at = NULL, cadence = ? WHERE id = ?",
            (cadence, existing["id"]),
        )
        conn.commit()
        return {"state": "resumed", "saved": True, "id": existing["id"], "label": existing["label"]}

    cursor = conn.execute(
        """INSERT INTO saved_searches
           (profile_id, label, q, county, family, employment_type, deadline_days,
            pay_floor, remote, cadence, created_at, last_run_at, unsubscribed_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL,NULL)""",
        (
            profile_id,
            label,
            values["q"],
            values["county"],
            values["family"],
            values["employment_type"],
            values["deadline_days"],
            values["pay_floor"],
            values["remote"],
            cadence,
            _iso(moment),
        ),
    )
    conn.commit()
    return {"state": "saved", "saved": True, "id": cursor.lastrowid, "label": label}


def stop(conn, profile_id: str, search_id: int, *, now: datetime | None = None) -> bool:
    cursor = conn.execute(
        """UPDATE saved_searches SET unsubscribed_at = ?
            WHERE id = ? AND profile_id = ? AND unsubscribed_at IS NULL""",
        (_iso(_now(now)), int(search_id), profile_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def for_profile(conn, profile_id: str) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM saved_searches
            WHERE profile_id = ? AND unsubscribed_at IS NULL
            ORDER BY created_at DESC, id DESC""",
        (profile_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def due(conn, *, now: datetime | None = None) -> list[dict]:
    """Searches that should be considered on this tick.

    Consent is re-checked here rather than trusted from save time: a person can
    unsubscribe from the digest and still have saved searches on file.
    """
    moment = _now(now)
    active = {subscription.profile_id for subscription in outbox.active_subscriptions(conn)}
    out = []
    for row in conn.execute(
        "SELECT * FROM saved_searches WHERE unsubscribed_at IS NULL ORDER BY id"
    ).fetchall():
        item = dict(row)
        if item["profile_id"] not in active:
            continue
        last = item.get("last_run_at")
        if last:
            try:
                previous = datetime.fromisoformat(last)
            except ValueError:
                previous = None
            if previous and item["cadence"] == "daily":
                # One run a day is what the cadence promises; a tick every ten
                # minutes must not re-query the graph forty times before lunch.
                gap = moment.astimezone(timezone.utc).date() - previous.astimezone(timezone.utc).date()
                if gap.days < 1:
                    continue
            if previous and item["cadence"] == "weekly":
                if moment - previous < timedelta(days=7):
                    continue
        out.append(item)
    return out


def new_matches(conn, row: dict, *, now: datetime | None = None):
    """Rows that appeared since this search last ran (or since it was saved)."""
    moment = _now(now)
    since = row.get("last_run_at")
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            since_dt = None
    if since_dt is None:
        created = row.get("created_at")
        since_dt = datetime.fromisoformat(created) if created else moment

    from .profile import load_profile

    profile = load_profile(conn, row["profile_id"])
    if profile is None:
        return []
    found = search_module.run(
        conn,
        profile,
        query=row["q"],
        county=row["county"],
        family=row["family"],
        employment_type=row["employment_type"],
        deadline_days=row["deadline_days"] or None,
        pay_floor=row["pay_floor"] or None,
        remote=bool(row["remote"]),
        include_blocked=False,
        since=since_dt,
        now=moment,
    )
    return found.matches


def message(row: dict, matches, *, base: str | None = None) -> str:
    """The exact text a person receives. Short, dated, and stoppable."""
    root = _base(base)
    total = len(matches)
    head = f"*{total} new role{'s' if total != 1 else ''}: {row['label']}*"
    lines = [head]
    for item in matches[:MAX_ITEMS]:
        place = item.row.get("county") or ""
        employer = item.match.employer or "Employer not stated"
        closing = item.row.get("deadline")
        tail = ""
        if closing:
            try:
                tail = f" — closes {_fmt_day(closing)}"
            except ValueError:
                tail = f" — closes {closing}"
        lines.append(f"{item.match.title} · {employer}{tail}")
    if total > MAX_ITEMS:
        lines.append(f"+{total - MAX_ITEMS} more")
    lines.append(f"{root}{_search_path(row)}")
    lines.append(f"Stop these alerts: {root}/search?profile={row['profile_id']}&stop={row['id']}")
    return "\n".join(lines)


def _fmt_day(raw) -> str:
    from datetime import date

    return f"{date.fromisoformat(str(raw)[:10]):%-d %b}"


def _search_path(row: dict) -> str:
    from urllib.parse import urlencode

    pairs = [
        ("profile", row["profile_id"]),
        ("q", row["q"]),
        ("county", row["county"]),
        ("family", row["family"]),
        ("type", row["employment_type"]),
        ("days", row["deadline_days"] or ""),
        ("pay", int(row["pay_floor"]) if row["pay_floor"] else ""),
        ("remote", "1" if row["remote"] else ""),
    ]
    query = urlencode([(key, value) for key, value in pairs if value not in ("", 0, None)])
    return f"/search?{query}" if query else "/search"


def period_key(row: dict, moment: datetime) -> str:
    eat = moment.astimezone(timezone(timedelta(hours=3)))
    if row["cadence"] == "weekly":
        year, week, _ = eat.isocalendar()
        return f"{year}-W{week:02d}"
    return eat.date().isoformat()


def queue_due(
    conn, *, now: datetime | None = None, dry_run: bool = False, base: str | None = None
) -> dict:
    """Compose and enqueue every due saved search. Sends nothing; the tick does."""
    moment = _now(now)
    subscriptions = {item.profile_id: item for item in outbox.active_subscriptions(conn)}
    report = {"considered": 0, "queued": 0, "empty": 0, "already": 0, "searches": []}
    for row in due(conn, now=moment):
        report["considered"] += 1
        matches = new_matches(conn, row, now=moment)
        if not matches:
            report["empty"] += 1
            continue
        body = message(row, matches, base=base)
        entry = {
            "id": row["id"],
            "profile_id": row["profile_id"],
            "label": row["label"],
            "matches": len(matches),
            "characters": len(body),
        }
        if dry_run:
            entry["body"] = body
            report["searches"].append(entry)
            continue
        subscription = subscriptions.get(row["profile_id"])
        if subscription is None:  # pragma: no cover - `due` filters these already
            continue
        added = outbox.enqueue(
            conn,
            Outgoing(
                profile_id=row["profile_id"],
                channel=subscription.channel,
                msisdn=subscription.msisdn,
                body=body,
                idempotency=f"saved-search:{row['id']}:{period_key(row, moment)}",
                kind="search",
            ),
            now=moment,
        )
        if added:
            report["queued"] += 1
            report["searches"].append(entry)
        else:
            report["already"] += 1
        # The watermark advances either way: the message for this period either
        # exists or was already queued, and re-querying would only re-find it.
        conn.execute(
            "UPDATE saved_searches SET last_run_at = ? WHERE id = ?", (_iso(moment), row["id"])
        )
    conn.commit()
    return report
