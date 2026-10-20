"""The feed: a tailored, explained, link-out job feed over the job graph.

Server-rendered HTML, no build step, no framework, no client-side state. It is
still an **internal** surface — the v1 product decision is web feed + WhatsApp
digest (D5) and WhatsApp is not built — but it is no longer a debug view: it is
the thing the ranking, the freshness promise and the apply tracking are for.

Routes:

    /                 ranked feed for a profile (defaults to the first profile)
    /job/<id>         one job: the card, the evidence, every source, the history
    /slo              the freshness promise, measured per source (D8)
    /review           the duplicate pairs a human should decide
    /digest           the WhatsApp digest, exactly as it would arrive (D5)
    /webhooks/whatsapp  inbound replies and delivery receipts (Meta Cloud API)
    /webhooks/sms       inbound SMS and delivery reports (Africa's Talking)
    /api/jobs         the same ranked feed as JSON
    /healthz          liveness of the process, not of the data
"""

from __future__ import annotations

import hmac as _hmac
import html
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import db, digest as digest_module, graph, metrics, outbox, ranking, slo, tracking, webhooks
from .corpus import load_corpus
from .profile import DEMO_PROFILES, list_profiles, seed_profiles

ENTRY_FIT_LABEL = ranking.ENTRY_FIT_LABEL
ENTRY_FIT_TONE = {
    "open_to_freshers": "good",
    "some_experience": "warn",
    "experienced": "muted",
    "unknown": "muted",
}
SLO_TONE = {"on_time": "good", "late": "warn", "stale": "danger", "never_fetched": "muted"}
SLO_LABEL = {
    "on_time": "on time",
    "late": "late",
    "stale": "stale",
    "never_fetched": "never fetched",
}

STYLE = """
:root{
  /* design tokens — see docs/design/01-visual-system.md */
  --paper:#FBF8F2; --card:#FFFFFF; --sunken:#F3EEE5; --line:#E3DCCF;
  --ink:#12161C; --ink-2:#3D4653; --muted:#5C6675;
  --forest:#14532D; --forest-soft:#E7F0E8;
  --amber:#9A4E00; --amber-soft:#FBEEDC;
  --risk:#A3241C; --risk-soft:#FBEAE8;
  --live:#15803D;
  --accent:var(--forest); --accent-soft:var(--forest-soft);
  --warn:var(--amber); --warn-soft:var(--amber-soft);
  --danger:var(--risk); --danger-soft:var(--risk-soft);
  --bg:var(--paper);
  --radius:14px; --radius-sm:10px; --radius-pill:999px;
  --focus:0 0 0 3px #B9D4C1, 0 0 0 1px #14532D;
  --font-sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --font-mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 var(--font-sans);
  -webkit-font-smoothing:antialiased}
a{color:var(--forest);text-decoration:none}
a:hover{text-decoration:underline}
:focus-visible{outline:none;box-shadow:var(--focus);border-radius:6px}
header{background:var(--card);border-bottom:1px solid var(--line);padding:12px 20px}
.wrap{max-width:760px;margin:0 auto;padding:0 20px}
.brand{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.lockup{display:flex;align-items:center;gap:9px;min-width:0}
.lockup svg{width:26px;height:26px;color:var(--forest);flex:none}
.lockup .word{font-size:19px;font-weight:700;letter-spacing:-.02em;line-height:1.1}
.lockup .tag{display:block;color:var(--muted);font-weight:500;font-size:12.5px;letter-spacing:.01em}
.brand nav{display:flex;gap:4px;flex-wrap:wrap}
.brand nav a{font-size:14px;color:var(--ink-2);padding:7px 10px;border-radius:var(--radius-sm)}
.brand nav a:hover{background:var(--sunken);text-decoration:none}
.brand nav a.on{background:var(--forest-soft);color:var(--forest);font-weight:600}
.banner{background:var(--amber-soft);color:var(--amber);border-bottom:1px solid #EBD6B4;padding:10px 20px;font-size:14px}
.whobar{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:14px 16px;margin:18px 0 0;font-size:14px}
.whobar b{font-weight:650}
.whobar .chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.chip{border:1px solid var(--line);border-radius:var(--radius-pill);padding:3px 10px;
  font-size:13px;color:var(--ink-2);background:var(--card)}
.strip{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;padding:18px 0 4px;
  color:var(--muted);font-size:13px}
.strip b{color:var(--ink);font-size:20px;line-height:1.15;display:block;
  font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 6px}
.filters a{border:1px solid var(--line);background:var(--card);border-radius:var(--radius-pill);
  padding:7px 14px;font-size:14px;color:var(--ink-2);min-height:36px;display:inline-flex;align-items:center}
.filters a.on{border-color:var(--forest);color:var(--forest);background:var(--forest-soft);font-weight:600}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:16px 18px;margin-bottom:12px}
.card h2{margin:0 0 3px;font-size:18px;line-height:1.3;letter-spacing:-.015em;font-weight:650}
.card h2 a{color:var(--ink)}
.card h2 a:hover{color:var(--forest)}
.employer{color:var(--ink-2);font-size:14px;margin-bottom:10px}
.badges{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
.badge{font-size:12px;border-radius:var(--radius-pill);padding:3px 10px;border:1px solid var(--line);
  color:var(--ink-2);background:var(--sunken);white-space:nowrap}
.badge.good{background:var(--forest-soft);border-color:#CFE3D4;color:var(--forest);font-weight:600}
.badge.warn{background:var(--amber-soft);border-color:#EBD6B4;color:var(--amber);font-weight:600}
.badge.danger{background:var(--risk-soft);border-color:#EBC5C0;color:var(--risk);font-weight:600}
.badge.muted{background:var(--sunken);border-color:var(--line);color:var(--ink-2)}
.evidence{font-size:13.5px;color:var(--ink-2);border-left:2px solid var(--line);
  padding-left:12px;margin:10px 0 4px}
.whythat{font-size:13px;color:var(--muted);margin:8px 0 0;padding:0;list-style:none;
  display:flex;gap:6px;flex-wrap:wrap}
.whythat li{background:var(--sunken);border-radius:6px;padding:2px 8px}
.foot{display:flex;gap:14px;flex-wrap:wrap;font-size:13px;color:var(--muted);
  margin-top:12px;align-items:center;border-top:1px solid var(--line);padding-top:10px}
.foot form{display:inline;margin:0}
.foot button{font:inherit;font-size:13px;background:none;border:none;color:var(--muted);
  cursor:pointer;padding:8px 0;text-decoration:underline}
.foot .apply{border:1px solid var(--forest);color:#fff;border-radius:var(--radius-pill);
  padding:9px 16px;font-size:14px;font-weight:600;background:var(--forest);min-height:40px;
  display:inline-flex;align-items:center}
.foot .apply:hover{background:#0F3F22;text-decoration:none}
h1{font-size:28px;line-height:1.15;letter-spacing:-.02em;margin:26px 0 6px}
h2{font-size:18px;letter-spacing:-.01em;margin:24px 0 4px}
p{margin:8px 0}
table{width:100%;border-collapse:collapse;font-size:14px;background:var(--card);
  border:1px solid var(--line);border-radius:var(--radius-sm);overflow:hidden;
  font-variant-numeric:tabular-nums}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:12.5px;background:var(--paper)}
tr:last-child td{border-bottom:none}
dl{display:grid;grid-template-columns:150px 1fr;gap:8px 16px;margin:18px 0;font-size:15px}
dt{color:var(--muted)}
dd{margin:0}
.sources{list-style:none;padding:0;margin:0;font-size:14px}
.sources li{padding:8px 0;border-bottom:1px solid var(--line)}
.sources li:last-child{border-bottom:none}
.small{font-size:13px;color:var(--muted)}
.msg{white-space:pre-wrap;word-break:break-word;background:var(--forest-soft);
  border:1px solid #CFE3D4;border-radius:var(--radius);padding:14px 16px;
  font:14px/1.6 var(--font-mono);margin:12px 0;color:var(--ink)}
.msg.sms{background:var(--sunken);border-color:var(--line)}
.subform{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 18px}
.subform input{flex:1 1 220px;padding:11px 13px;border:1px solid var(--line);
  border-radius:var(--radius-sm);font-size:16px;font-family:inherit;background:var(--card)}
.subform button{padding:11px 18px;border:0;border-radius:var(--radius-sm);background:var(--forest);
  color:#fff;font-size:15px;font-weight:600;cursor:pointer;min-height:44px}
.subform button:hover{background:#0F3F22}
.subform button.ghost{background:var(--card);color:var(--ink-2);border:1px solid var(--line);font-weight:500}
footer{padding:30px 0 44px;font-size:13px;color:var(--muted)}
@media (max-width:520px){
  h1{font-size:24px}
  .strip{grid-template-columns:repeat(2,1fr);gap:10px}
  dl{grid-template-columns:1fr;gap:2px}dt{margin-top:10px}
  .foot .apply{width:100%;justify-content:center}
  .brand nav a{padding:7px 8px}
}
/* --- craft layer -------------------------------------------------------
   Premium here is mostly restraint: one hairline that warms on hover, 1px of
   lift, a 160ms ease-out, tabular figures, and a focus ring that is the only
   thing allowed to shout. Nothing bounces, nothing loops, nothing decorates. */
::selection{background:var(--forest-soft);color:var(--ink)}
a{-webkit-tap-highlight-color:transparent}
.card,.filters a,.badge,.foot .apply,.subform button,header,nav a{
  transition:border-color .16s ease-out,background-color .16s ease-out,
             color .16s ease-out,transform .16s ease-out,box-shadow .16s ease-out}
.card:hover{border-color:#D8CBB6;transform:translateY(-1px)}
.card:focus-within{border-color:var(--forest)}
.card h2 a{text-underline-offset:2px;text-decoration-thickness:.06em}
.filters a:hover{border-color:#CFC3AE;color:var(--ink)}
.foot .apply:hover{transform:translateY(-1px)}
.ledger{display:flex;gap:8px;flex-wrap:wrap;align-items:baseline;margin:16px 0 0;
  padding:10px 0;border-bottom:1px solid var(--line);font-size:13.5px;color:var(--ink-2)}
.ledger b{color:var(--ink);font-weight:650}
.ledger .quiet{color:var(--muted)}
.strip b,.ledger b,table td{font-variant-numeric:tabular-nums}
.small,.badge{font-variant-numeric:tabular-nums}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""


def _constant_time_equal(left: str, right: str) -> bool:
    return _hmac.compare_digest((left or "").encode(), (right or "").encode())


# --------------------------------------------------------------------------
# The ledger: what changed since this visitor last looked.
#
# The single most valuable thing this product can say is a diff. It needs one
# fact — when the person was last here — and it must not become an identity:
# the value is a timestamp, signed so it cannot be forged into "you last looked
# in 1970", and readable by nothing but us.
# --------------------------------------------------------------------------

SEEN_COOKIE = "kazi_seen"
SEEN_MAX_AGE = 60 * 60 * 24 * 30


def _ledger_key() -> bytes:
    return (os.environ.get("KAZIKASI_SECRET") or "kazi-kasi-demo").encode()


def _sign_seen(stamp: str) -> str:
    return _hmac.new(_ledger_key(), stamp.encode(), "sha256").hexdigest()[:20]


def seen_cookie(now: datetime) -> str:
    """The cookie that makes tomorrow's feed able to say what changed."""
    stamp = now.replace(microsecond=0).isoformat()
    return (
        f"{SEEN_COOKIE}={stamp}.{_sign_seen(stamp)}; Path=/; "
        f"Max-Age={SEEN_MAX_AGE}; HttpOnly; SameSite=Lax"
    )


def read_seen(headers: dict | None) -> datetime | None:
    """Parse and verify the last-look timestamp. Anything doubtful is ignored."""
    raw = ""
    for key, value in (headers or {}).items():
        if str(key).lower() != "cookie":
            continue
        for part in str(value).split(";"):
            name, _, val = part.strip().partition("=")
            if name == SEEN_COOKIE:
                raw = val
    stamp, _, signature = raw.rpartition(".")
    if not stamp or not signature:
        return None
    if not _hmac.compare_digest(signature, _sign_seen(stamp)):
        return None
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _as_dt(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


SCOPE_MARK = """<svg viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
  <circle cx="12" cy="13" r="3.2" stroke="currentColor" stroke-width="1.8"/>
  <path d="M6.4 17.6a7.6 7.6 0 0 1 0-9.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
  <path d="M17.6 8a7.6 7.6 0 0 1 0 9.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
  <path d="M3.6 20.2a12 12 0 0 1 0-13.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" opacity=".55"/>
  <path d="M20.4 6.8a12 12 0 0 1 0 13.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" opacity=".55"/>
  <path d="M1.5 20.9h21" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" opacity=".35"/>
</svg>"""


def _e(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _page(title: str, body: str, *, demo: bool = False, nav: str = "", head: str = "") -> str:
    banner = (
        '<div class="banner">Synthetic demo data — no real vacancies are shown on this page.</div>'
        if demo
        else ""
    )
    links = nav or (
        '<a href="/">Feed</a><a href="/digest">WhatsApp</a>'
        '<a href="/slo">Freshness</a><a href="/review">Review</a>'
    )
    return f"""<!doctype html>
<html lang="en-KE"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#FBF8F2">
<meta name="description" content="Kazi-Kasi — jobs you can reach, checked today.">
<title>{_e(title)}</title>{head}<style>{STYLE}</style></head>
<body>
<header><div class="wrap"><div class="brand">
<a class="lockup" href="/" aria-label="Kazi-Kasi — jobs you can reach">
{SCOPE_MARK}
<span><span class="word">Kazi-Kasi</span>
<span class="tag">Nairobi metro · early career</span></span>
</a>
<nav>{links}</nav></div></div></header>
{banner}
<div class="wrap">{body}</div>
<footer class="wrap">Every card says when it was last checked and why it was shown.
Eligibility labels quote the advert. Applications happen on the employer's site, never here.</footer>
</body></html>"""


# --------------------------------------------------------------------------
# Structured data
# --------------------------------------------------------------------------

_EMPLOYMENT_TYPE = {
    "full_time": "FULL_TIME",
    "part_time": "PART_TIME",
    "contract": "CONTRACTOR",
    "internship": "INTERN",
    "temporary": "TEMPORARY",
    "volunteer": "VOLUNTEER",
}
_PAY_UNIT = {"hour": "HOUR", "day": "DAY", "week": "WEEK", "month": "MONTH", "year": "YEAR"}


def _job_posting(row, description: str) -> str:
    """One schema.org JobPosting for a job page, or nothing at all.

    Google's rules are unusually concrete: exactly one block per page, on the
    page that shows that job, with a description that is more than the title,
    and no markup for a job that has no way to apply. We emit nothing rather
    than emit something thin — a page that lies in its markup is worse than a
    page that is simply not rich.

    `directApply` is false on purpose: the application happens on the employer's
    site, and Google asks for the honest answer.
    """
    text = (description or "").strip()
    if len(text) < 80 or not row["title"]:
        return ""

    posting: dict = {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": row["title"],
        "description": text,
        "datePosted": str(row["first_seen_at"])[:10],
        "directApply": False,
        "identifier": {"@type": "PropertyValue", "name": "Kazi-Kasi", "value": row["id"]},
        "hiringOrganization": {
            "@type": "Organization",
            "name": row["employer_name"] or "Employer not stated",
        },
    }
    if row["deadline"]:
        posting["validThrough"] = f'{row["deadline"]}T23:59+03:00'
    if row["county"]:
        posting["jobLocation"] = {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": row["sub_county"] or row["county"],
                "addressRegion": row["county"],
                "addressCountry": "KE",
            },
        }
    if row["work_mode"] == "remote":
        posting["jobLocationType"] = "TELECOMMUTE"
        posting["applicantLocationRequirements"] = {"@type": "Country", "name": "Kenya"}
    kind = _EMPLOYMENT_TYPE.get(row["employment_type"])
    if kind:
        posting["employmentType"] = kind
    unit = _PAY_UNIT.get(str(row["pay_period"] or "").lower())
    if row["pay_min"] and unit:
        value: dict = {"@type": "QuantitativeValue", "unitText": unit, "minValue": row["pay_min"]}
        if row["pay_max"] and row["pay_max"] != row["pay_min"]:
            value["maxValue"] = row["pay_max"]
        posting["baseSalary"] = {"@type": "MonetaryAmount", "currency": "KES", "value": value}

    payload = json.dumps(posting, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{payload}</script>'


# --------------------------------------------------------------------------
# Feed
# --------------------------------------------------------------------------


def _profiles(conn) -> list:
    profiles = list_profiles(conn)
    if not profiles:
        seed_profiles(conn)
        profiles = list_profiles(conn)
    return profiles


def _profile_or_default(conn, profile_id: str | None):
    profiles = _profiles(conn)
    if not profiles:
        return DEMO_PROFILES[0]
    if profile_id:
        for profile in profiles:
            if profile.id == profile_id:
                return profile
    return profiles[0]


def _ranked(conn, profile, *, now, limit=40, include_blocked=False):
    # Stale jobs stay visible, carrying their age. Hiding them would be tidier
    # and less honest; the card is supposed to tell you it is old.
    rows = graph.feed(conn, limit=500, include_stale=True)
    dismissed = tracking.dismissed_job_ids(conn, profile.id)
    rows = [row for row in rows if row["id"] not in dismissed]
    matches = ranking.rank(rows, profile, now=now, limit=limit, include_blocked=include_blocked)
    acted = tracking.applied_job_ids(conn, profile.id)
    return matches, acted


def render_feed(
    conn: sqlite3.Connection,
    *,
    profile_id: str | None = None,
    now: datetime | None = None,
    demo: bool = False,
    limit: int = 40,
    since: datetime | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    profile = _profile_or_default(conn, profile_id)
    matches, acted = _ranked(conn, profile, now=now, limit=limit)
    summary = metrics.stats(conn, now=now)
    clock = (now + timedelta(hours=3)).strftime("%H:%M")
    if since is None:
        ledger = (
            '<p class="ledger"><b>First look.</b> We keep what you saw, so next '
            "time we can tell you exactly what changed.</p>"
        )
    else:
        # Compare at second resolution: the cookie is stored to the second, so a
        # job first seen in the same second as the visit is not "new".
        boundary = since.replace(microsecond=0)
        new_count = sum(
            1 for match in matches
            if (
                (_as_dt((match.row or {}).get("first_seen_at")) or boundary)
                .replace(microsecond=0)
                > boundary
            )
        )
        when = (
            "earlier today"
            if since.astimezone(timezone.utc).date() == now.astimezone(timezone.utc).date()
            else f"{since:%a} {since.day} {since:%b}"
        )
        lead = f"<b>{new_count} new</b> since {when}" if new_count else f"<b>Nothing new</b> since {when}"
        ledger = (
            f'<p class="ledger">{lead} · {summary["closing_within_7_days"]} closing this week · '
            f"checked {clock} EAT</p>"
        )

    chips = "".join(
        f'<span class="chip">{_e(family)}</span>' for family in profile.role_families
    ) or '<span class="chip">any role type</span>'
    limit_chip = (
        f'<span class="chip">≤ {profile.max_commute_km:g} km from {_e(profile.home_area or profile.home_county)}</span>'
        if profile.max_commute_km
        else '<span class="chip">no distance limit</span>'
    )
    pay_chip = (
        f'<span class="chip">≥ KES {profile.min_monthly_pay:,.0f}/month</span>'
        if profile.min_monthly_pay
        else ""
    )

    switcher = " ".join(
        f'<a class="{"on" if other.id == profile.id else ""}" href="/?profile={quote(other.id)}">{_e(other.name.split(" — ")[0])}</a>'
        for other in _profiles(conn)
    )

    cards = []
    for match in matches:
        row = match.row or {}
        entry_tone = ENTRY_FIT_TONE.get(row.get("entry_fit"), "muted")
        entry_label = ENTRY_FIT_LABEL.get(row.get("entry_fit"), "eligibility unstated")
        badges = [f'<span class="badge {entry_tone}">{_e(entry_label)}</span>']
        place = row.get("county") if not row.get("sub_county") else f'{row["sub_county"]}, {row["county"]}'
        badges.append(f'<span class="badge muted">{_e(place or "Location unstated")}</span>')
        if row.get("work_mode") in ("remote", "hybrid"):
            badges.append(f'<span class="badge good">{_e(row["work_mode"].title())}</span>')
        deadline = graph.deadline_band(row, now=now)
        if deadline:
            tone = "warn" if deadline.startswith("closes in") or "today" in deadline or "tomorrow" in deadline else ""
            badges.append(f'<span class="badge {tone}">{_e(deadline)}</span>')
        if row.get("source_count", 1) > 1:
            badges.append(f'<span class="badge good">on {row["source_count"]} sources</span>')
        if row.get("status") == "stale":
            badges.append('<span class="badge warn">not re-checked recently</span>')
        else:
            badges.append('<span class="badge good">live</span>')
        if row.get("id") in acted:
            badges.append('<span class="badge">you applied</span>')

        # The deadline is already a badge; a reason that repeats it is noise.
        # Keep at least one reason so every card still says why it is here.
        shown_reasons = [reason for reason in match.reasons if not reason.startswith("closes")]
        if not shown_reasons:
            shown_reasons = match.reasons[:1]
        reasons = " · ".join(_e(reason) for reason in shown_reasons[:3])
        source = graph.primary_source(conn, match.job_id)

        apply_html = ""
        if source:
            apply_html = (
                f'<a class="apply" href="/go?profile={quote(profile.id)}&job={quote(match.job_id)}"'
                f' rel="nofollow noopener" target="_blank">Apply on {_e(source["source_id"])}</a>'
            )

        cards.append(
            f"""<article class="card">
  <h2><a href="/job/{_e(match.job_id)}?profile={quote(profile.id)}">{_e(match.title)}</a></h2>
  <div class="employer">{_e(match.employer or "Employer not stated")}</div>
  <div class="badges">{''.join(badges)}</div>
  <p class="whythat">{reasons}</p>
  <div class="foot">
    <span title="match score">{match.score:.2f}</span>
    <span>{_e(graph.freshness_band(row, now=now))}</span>
    {apply_html}
    <form method="post" action="/action">
      <input type="hidden" name="profile" value="{_e(profile.id)}">
      <input type="hidden" name="job" value="{_e(match.job_id)}">
      <input type="hidden" name="kind" value="dismissed">
      <button type="submit">Not for me</button>
    </form>
  </div>
</article>"""
        )

    if not cards:
        cards.append('<div class="card"><p>Nothing matches this profile right now. Loosen a constraint, or check back after the next sweep.</p></div>')

    strip = f"""<div class="strip">
  <div><b>{summary['live_jobs']}</b>live jobs</div>
  <div><b>{summary['closing_within_7_days']}</b>closing in 7 days</div>
  <div><b>{len(matches)}</b>match this profile</div>
  <div><b>{len(acted)}</b>applied</div>
</div>"""

    body = f"""
<div class="whobar">
  <div><b>{_e(profile.name)}</b> <span class="small">— the constraints this feed was ranked against</span></div>
  <div class="chips">{limit_chip}{pay_chip}{chips}</div>
</div>
<div class="filters">{switcher}</div>
{ledger}
{strip}
{''.join(cards)}"""
    return _page("Kazi-Kasi — jobs for you", body, demo=demo)


def render_job(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    profile_id: str | None = None,
    now: datetime | None = None,
    demo: bool = False,
) -> str | None:
    now = now or datetime.now(timezone.utc)
    row = graph.job_row(conn, job_id)
    if row is None:
        return None

    profile = _profile_or_default(conn, profile_id)
    match = ranking.score_job(dict(row), profile, now)
    sources = graph.job_sources(conn, job_id)
    events = graph.job_events(conn, job_id)
    observation = conn.execute(
        "SELECT payload FROM observations WHERE id = ?", (row["primary_observation_id"],)
    ).fetchone()
    payload = json.loads(observation["payload"]) if observation else {}
    evidence = payload.get("entry_fit_evidence")
    description = (payload.get("description_md") or "").strip()
    source = graph.primary_source(conn, job_id)

    facts = [
        ("Employer", row["employer_name"] or "Not stated"),
        (
            "Location",
            f'{row["sub_county"]}, {row["county"]}' if row["sub_county"] and row["county"]
            else (row["county"] or "Not stated"),
        ),
        ("Eligibility", ENTRY_FIT_LABEL.get(row["entry_fit"], row["entry_fit"])),
        ("Type", (row["employment_type"] or "unknown").replace("_", " ").title()),
        ("Work mode", (row["work_mode"] or "unknown").title()),
        ("Deadline", row["deadline"] or "Not stated"),
        (
            "Pay",
            f'KES {row["pay_min"]:,.0f}–{row["pay_max"]:,.0f} per {row["pay_period"]}'
            if row["pay_min"] and row["pay_max"] and row["pay_min"] != row["pay_max"]
            else (f'KES {row["pay_min"]:,.0f} per {row["pay_period"]}' if row["pay_min"] else "Not stated"),
        ),
        ("Last checked", graph.freshness_band(row, now=now)),
        ("Status", row["status"].replace("_", " ")),
    ]

    source_items = "".join(
        f'<li><a href="{_e(item["source_url"])}" rel="nofollow noopener" target="_blank">'
        f'{_e(item["source_id"])}</a> · matched by {_e(item["match_reason"])}'
        f'<div class="small">checked {_e(item["fetched_at"][:16].replace("T", " "))}</div></li>'
        for item in sources
    )
    event_items = "".join(
        f'<li>{_e(event["kind"].replace("_", " "))} · {_e(event["at"][:10])}</li>' for event in events
    )
    structured = _job_posting(row, description)
    flags = json.loads(row["scam_flags"])
    warning = (
        '<div class="badge danger">Flagged: '
        + _e(", ".join(flag.replace("_", " ") for flag in flags))
        + "</div>"
        if flags
        else ""
    )

    if match.eligible:
        why = "".join(f"<li>{_e(reason)}</li>" for reason in match.reasons)
        why_block = f'<h1>Why this is in your feed</h1><ul class="whythat">{why}</ul>'
    else:
        why_block = (
            "<h1>Why this is not in your feed</h1>"
            + "".join(f'<div class="badge warn">{_e(blocker)}</div>' for blocker in match.blockers)
        )

    apply_html = ""
    if source:
        apply_html = (
            f'<p><a class="apply" href="/go?profile={quote(profile.id)}&job={quote(job_id)}"'
            f' rel="nofollow noopener" target="_blank">Apply on {_e(source["source_id"])}</a></p>'
        )

    body = f"""
<p class="small"><a href="/?profile={quote(profile.id)}">← back to the feed</a></p>
<h1>{_e(row['title'])}</h1>
<div class="employer">{_e(row['employer_name'] or 'Employer not stated')}</div>
<div class="badges">{warning}</div>
{apply_html}
<dl>{''.join(f'<dt>{_e(label)}</dt><dd>{_e(value)}</dd>' for label, value in facts)}</dl>
{why_block}
{f'<div class="evidence">“{_e(evidence)}”</div>' if evidence else ''}
{f'<h1>About the role</h1><p>{_e(description[:1200])}</p>' if description else ''}
<h1>Where this came from</h1>
<ul class="sources">{source_items}</ul>
<h1>History</h1>
<ul class="sources">{event_items}</ul>
<p class="small">Eligibility is read from the advert text, not inferred from the title.
Distance is straight-line between approximate area centres, not a route.</p>
"""
    return _page(f"{row['title']} — Kazi-Kasi", body, demo=demo, head=structured)


# --------------------------------------------------------------------------
# Freshness (D8)
# --------------------------------------------------------------------------


def render_slo(conn, *, now: datetime | None = None, demo: bool = False) -> str:
    now = now or datetime.now(timezone.utc)
    payload = slo.report(conn, now=now)
    rows = []
    for source in payload["sources"]:
        age = "—" if source["age_minutes"] is None else f'{source["age_minutes"]:.0f} min'
        rows.append(
            f"""<tr>
  <td>{_e(source['label'])}</td>
  <td><span class="badge {SLO_TONE.get(source['state'], 'muted')}">{_e(SLO_LABEL.get(source['state'], source['state']))}</span></td>
  <td>{_e(age)}</td>
  <td>{source['target_minutes']} min</td>
  <td>{source['observations']}</td>
</tr>"""
        )

    feed_age = payload["feed_age_minutes"]
    headline = (
        f"Feed last updated {feed_age:.0f} minutes ago."
        if feed_age is not None
        else "The feed has not been updated yet."
    )
    body = f"""
<h1>Freshness</h1>
<p>{_e(headline)} {payload['sources_meeting_slo']} of {payload['sources_reporting']}
reporting sources are within their target cadence.</p>
<p class="small">This page exists because "constant update" is a claim. If a source is late,
it says so here rather than on a marketing page.</p>
<table>
<tr><th>Source</th><th>State</th><th>Since last fetch</th><th>Target</th><th>Observations</th></tr>
{''.join(rows)}
</table>"""
    return _page("Freshness — Kazi-Kasi", body, demo=demo)


def render_digest(
    conn: sqlite3.Connection,
    *,
    profile_id: str | None = None,
    now: datetime | None = None,
    demo: bool = False,
    link_base: str = "https://kazikasi.app",
    error: str = "",
) -> str:
    """The digest as it will actually arrive, plus what it left out and why.

    This is the honest version of a WhatsApp preview: the body is generated by
    the same code the transport would send, so what you read here is the
    message, not a mock-up of it.
    """
    now = now or datetime.now(timezone.utc)
    if not profile_id:
        # Open on someone who actually receives a digest, not alphabetically first.
        for candidate in outbox.active_subscriptions(conn):
            profile_id = candidate.profile_id
            break
    profile = _profile_or_default(conn, profile_id)
    subscription = outbox.load_subscription(conn, profile.id)

    digest = outbox.compose(conn, profile.id, now=now)
    channel = subscription.channel if subscription else "whatsapp"
    msisdn = subscription.msisdn if subscription else "+254700000000"
    messages = digest_module.build_messages(
        digest, channel=channel, msisdn=msisdn, link_base=link_base
    )
    sms_preview = digest_module.render_sms(digest)

    if subscription and subscription.active:
        consent = (
            f'<p>Subscribed on {_e((subscription.consented_at or "")[:10])} via '
            f'{_e(subscription.consent_source)} to {_e(digest_module.mask_msisdn(subscription.msisdn))}. '
            f'Daily, {_e(subscription.window_start)}–{_e(subscription.window_end)} EAT, '
            f'up to {subscription.max_items} jobs.</p>'
            f'<form class="subform" method="post" action="/digest/unsubscribe">'
            f'<input type="hidden" name="profile" value="{_e(profile.id)}">'
            f'<button class="ghost" type="submit">Stop these messages</button></form>'
        )
    elif subscription:
        consent = (
            f'<p>Opted out on {_e((subscription.unsubscribed_at or "")[:10])}. '
            f'Consent is recorded, not deleted — a re-subscribe re-dates it.</p>'
            f'<form class="subform" method="post" action="/digest/subscribe">'
            f'<input type="hidden" name="profile" value="{_e(profile.id)}">'
            f'<input name="msisdn" inputmode="tel" placeholder="07xx xxx xxx" required>'
            f'<button type="submit">Start the daily digest</button></form>'
        )
    else:
        consent = (
            '<p>No number on file for this profile, so nothing is queued. A digest needs an '
            'explicit opt-in: who agreed, to what, and when.</p>'
            f'<form class="subform" method="post" action="/digest/subscribe">'
            f'<input type="hidden" name="profile" value="{_e(profile.id)}">'
            f'<input name="msisdn" inputmode="tel" placeholder="07xx xxx xxx" required>'
            f'<button type="submit">Start the daily digest</button></form>'
        )

    if messages:
        body = messages[0].body
        shown = f'<pre class="msg">{_e(body)}</pre>'
        if len(messages) > 1:
            shown += f'<p class="small">Split into {len(messages)} messages at card boundaries (WhatsApp caps a text at {digest_module.WHATSAPP_TEXT_LIMIT} characters).</p>'
    else:
        shown = (
            '<div class="card"><p>Nothing to send today: every job that fits has already been '
            'in a digest, applied to, or dismissed. An empty digest is silence, not a '
            '"no jobs" message.</p></div>'
        )

    skipped = digest.skipped or {}
    skip_labels = {
        "already_sent": "already sent in an earlier digest",
        "acted_on": "you already applied",
        "dismissed": "you dismissed",
        "flagged": "flagged as risky",
        "closed": "closed or out of reach",
    }
    skipped_html = "".join(
        f'<li>{skipped[key]} {_e(label)}</li>' for key, label in skip_labels.items() if skipped.get(key)
    )
    skipped_block = f'<h2>Left out</h2><ul class="sources">{skipped_html}</ul>' if skipped_html else ""

    log_rows = "".join(
        f"<tr><td>{_e(row['channel'])}</td><td>{_e(row['state'])}</td>"
        f"<td>{row['attempts']}</td><td>{_e((row['created_at'] or '')[:16].replace('T', ' '))}</td>"
        f"<td class='small'>{_e(row['last_error'] or '')}</td></tr>"
        for row in outbox.messages_for(conn, profile.id, limit=10)
    )
    log_block = (
        f"<h2>Delivery log</h2><table><tr><th>Channel</th><th>State</th><th>Attempts</th>"
        f"<th>Queued</th><th>Last error</th></tr>{log_rows}</table>"
        if log_rows
        else "<h2>Delivery log</h2><p class='small'>Nothing queued yet for this profile.</p>"
    )

    switcher = " ".join(
        f'<a class="{"on" if other.id == profile.id else ""}" '
        f'href="/digest?profile={quote(other.id)}">{_e(other.name.split(" — ")[0])}</a>'
        for other in _profiles(conn)
    )

    body_html = f"""
<h1>WhatsApp digest</h1>
<p class="small">One message a day, five jobs at most, closing soonest first, and never the same
job twice. The body below is produced by the same code that would send it.</p>
<div class="filters">{switcher}</div>
<div class="whobar"><div><b>{_e(profile.name)}</b></div></div>
{f'<div class="banner" role="alert">{_e(error)}</div>' if error else ""}
{consent}
{shown}
<h2>If WhatsApp fails</h2>
<p class="small">After three attempts the message falls back to one SMS segment:</p>
<pre class="msg sms">{_e(sms_preview)}</pre>
{skipped_block}
{log_block}"""
    return _page("WhatsApp digest — Kazi-Kasi", body_html, demo=demo)


def render_review(conn: sqlite3.Connection, *, now: datetime | None = None, demo: bool = False) -> str:
    pairs = graph.open_reviews(conn)
    if not pairs:
        return _page("Review queue — Kazi-Kasi", "<h1>Review queue</h1><p>Nothing to decide.</p>", demo=demo)
    items = "".join(
        f"""<article class="card">
  <h2>{_e(pair['incoming_title'])} <span class="small">vs</span> {_e(pair['job_title'])}</h2>
  <div class="employer">{_e(pair['incoming_employer'])} · similarity {pair['score']:.2f} · {_e(pair['reason'])}</div>
  <div class="foot"><span>incoming: {_e(pair['incoming_source'])}</span>
  <span>existing job: <a href="/job/{_e(pair['candidate_job_id'])}">open</a></span></div>
</article>"""
        for pair in pairs
    )
    body = (
        "<h1>Review queue</h1><p class='small'>Pairs that were close but not close enough to "
        f"merge automatically.</p>{items}"
    )
    return _page("Review queue — Kazi-Kasi", body, demo=demo)


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


#: Requests per window per client, for the endpoints that change consent.
RATE_LIMIT = 30
RATE_WINDOW_SECONDS = 60


class _RateLimiter:
    """A tiny in-process token bucket.

    Not a replacement for a real edge limiter — it exists so a loop cannot
    enumerate numbers through the subscribe form on a single node. It is
    deliberately forgiving and per-process.
    """

    def __init__(self, limit: int = RATE_LIMIT, window: int = RATE_WINDOW_SECONDS) -> None:
        self.limit = limit
        self.window = window
        self.hits: dict[str, list[float]] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        moment = now if now is not None else time.monotonic()
        recent = [hit for hit in self.hits.get(key, []) if moment - hit < self.window]
        recent.append(moment)
        self.hits[key] = recent
        return len(recent) <= self.limit

    def reset(self) -> None:
        self.hits.clear()


def demo_connection(*, thread_safe: bool = False, now: datetime | None = None) -> sqlite3.Connection:
    """An in-memory database with the synthetic corpus and the demo profiles.

    This is what a serverless deployment serves: no file to mount, no write to
    a read-only filesystem, and nothing real to leak. State lives as long as the
    instance does, which for a testing link is the right trade.
    """
    conn = db.connect(":memory:", check_same_thread=not thread_safe)
    load_corpus(conn, now=now or datetime.now(timezone.utc))
    seed_profiles(conn)
    return conn


# --------------------------------------------------------------------------
# One router, two transports
#
# Everything below the HTTP layer is a pure function of (connection, method,
# path, query, body). That is what lets the same app run behind the stdlib
# server here and behind a serverless function on Vercel — and it is why the
# two cannot drift apart.
# --------------------------------------------------------------------------


@dataclass
class Response:
    status: int = 200
    body: str = ""
    content_type: str = "text/html; charset=utf-8"
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def is_redirect(self) -> bool:
        return self.status in (301, 302, 303, 307, 308)


def _query_one(query: dict, key: str, default: str = "") -> str:
    values = query.get(key) or [default]
    return values[0] if values else default


def handle(
    conn: sqlite3.Connection,
    method: str,
    path: str,
    query: dict,
    *,
    body: bytes = b"",
    headers: dict | None = None,
    demo: bool = False,
    limiter: "_RateLimiter | None" = None,
    client: str = "unknown",
    now: datetime | None = None,
) -> Response:
    """The whole app, minus the socket.

    ``headers`` keys are matched case-insensitively. ``body`` is the raw request
    body, because a webhook signature is computed over bytes, not over a parsed
    form.
    """
    now = now or datetime.now(timezone.utc)
    header_map = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
    method = method.upper()

    if method == "GET":
        return _handle_get(conn, path, query, demo=demo, now=now, headers=header_map)
    if method != "POST":
        return Response(405, "method not allowed", "text/plain; charset=utf-8")

    # Consent and webhook endpoints change state; they are throttled.
    throttled = ("/digest/subscribe", "/digest/unsubscribe", "/webhooks/whatsapp", "/webhooks/sms")
    if path in throttled and limiter is not None and not limiter.allow(client):
        return Response(429, "too many requests", "text/plain; charset=utf-8")

    if path in ("/webhooks/whatsapp", "/webhooks/sms"):
        return _handle_webhook(conn, path, query, body, header_map, demo=demo)
    if path in ("/digest/subscribe", "/digest/unsubscribe"):
        return _handle_consent(conn, path, body)
    if path == "/action":
        return _handle_action(conn, body, header_map)
    return Response(404, "not found", "text/plain; charset=utf-8")


def _handle_get(
    conn, path: str, query: dict, *, demo: bool, now: datetime, headers: dict | None = None
) -> Response:
    if path == "/healthz":
        return Response(200, "ok", "text/plain; charset=utf-8")

    if path == "/api/health":
        summary = metrics.stats(conn, now=now)
        return Response(
            200,
            json.dumps(
                {
                    "ok": True,
                    "schema": db.SCHEMA_VERSION,
                    "live_jobs": summary["live_jobs"],
                    "sources_reporting": len(summary["jobs_per_source"]),
                    "as_of": summary["as_of"],
                    "demo": demo,
                },
                indent=2,
                default=str,
            ),
            "application/json; charset=utf-8",
        )

    if path == "/api/jobs":
        profile = _profile_or_default(conn, _query_one(query, "profile") or None)
        limit = int(_query_one(query, "limit", "40") or 40)
        matches, _ = _ranked(conn, profile, now=now, limit=limit)
        payload = {"profile": profile.to_dict(), "matches": [match.to_dict() for match in matches]}
        return Response(200, json.dumps(payload, indent=2, default=str), "application/json; charset=utf-8")

    if path == "/go":
        profile_id = _query_one(query, "profile")
        job_id = _query_one(query, "job")
        row = graph.job_row(conn, job_id)
        source = graph.primary_source(conn, job_id)
        if row is None or source is None:
            return Response(404, _page("Not found", "<h1>Job not found</h1>", demo=demo))
        tracking.record(conn, profile_id, job_id, "clicked_through", detail=source["source_id"])
        return Response(303, "", headers={"Location": source["source_url"]})

    if path == "/slo":
        return Response(200, render_slo(conn, now=now, demo=demo))

    if path == "/review":
        return Response(200, render_review(conn, now=now, demo=demo))

    if path == "/webhooks/whatsapp":
        challenge = webhooks.verify_challenge(
            {key: _query_one(query, key) for key in query},
            os.environ.get("WHATSAPP_VERIFY_TOKEN"),
        )
        if challenge is None:
            return Response(403, "verification failed", "text/plain; charset=utf-8")
        return Response(200, challenge, "text/plain; charset=utf-8")

    if path == "/digest":
        return Response(
            200,
            render_digest(
                conn,
                profile_id=_query_one(query, "profile") or None,
                now=now,
                demo=demo,
                error=_query_one(query, "error"),
            ),
        )

    if path.startswith("/job/"):
        page = render_job(
            conn,
            path.rsplit("/", 1)[-1],
            profile_id=_query_one(query, "profile") or None,
            now=now,
            demo=demo,
        )
        if page is None:
            return Response(404, _page("Not found", "<h1>Job not found</h1>", demo=demo))
        return Response(200, page)

    if path in ("/", "/index.html"):
        seen = read_seen(headers)
        page = render_feed(
            conn,
            profile_id=_query_one(query, "profile") or None,
            now=now,
            demo=demo,
            since=seen,
        )
        return Response(200, page, headers={"Set-Cookie": seen_cookie(now)})

    return Response(404, _page("Not found", "<h1>Not found</h1>", demo=demo))


def _handle_webhook(conn, path: str, query: dict, raw: bytes, headers: dict, *, demo: bool) -> Response:
    """Inbound replies and receipts. Fails closed on an unverified sender."""
    if path == "/webhooks/whatsapp":
        secret = os.environ.get("WHATSAPP_APP_SECRET")
        signature = headers.get(webhooks.SIGNATURE_HEADER.lower())
        if secret:
            if not webhooks.verify_signature(raw, signature, secret):
                return Response(403, "bad signature", "text/plain; charset=utf-8")
        elif not demo:
            # No secret and not a demo: we cannot tell Meta from anyone.
            return Response(503, "webhook not configured", "text/plain; charset=utf-8")
        result = webhooks.handle_meta(conn, webhooks.parse_json(raw))
        return Response(200, json.dumps(result, default=str), "application/json; charset=utf-8")

    token = _query_one(query, "token")
    expected = os.environ.get("AT_WEBHOOK_TOKEN")
    if expected and not _constant_time_equal(token, expected):
        return Response(403, "bad token", "text/plain; charset=utf-8")
    if not expected and not demo:
        return Response(503, "webhook not configured", "text/plain; charset=utf-8")
    form = {
        key: (values or [""])[0]
        for key, values in parse_qs(raw.decode("utf-8", errors="replace")).items()
    }
    result = webhooks.handle_africas_talking(conn, form)
    return Response(200, json.dumps(result, default=str), "application/json; charset=utf-8")


def _handle_consent(conn, path: str, body: bytes) -> Response:
    """Subscribe or opt out from the digest page. Always redirects back."""
    form = parse_qs(body.decode("utf-8", errors="replace"))
    profile_id = _query_one(form, "profile")
    msisdn = _query_one(form, "msisdn")
    error = ""
    if path.endswith("/unsubscribe"):
        outbox.unsubscribe(conn, profile_id, reason="web")
    else:
        try:
            outbox.subscribe(conn, profile_id, msisdn, source="web")
        except ValueError as exc:
            error = str(exc)

    target = f"/digest?profile={quote(profile_id)}"
    if error:
        target += f"&error={quote(error)}"
    return Response(303, "", headers={"Location": target})


def _handle_action(conn, body: bytes, headers: dict) -> Response:
    form = parse_qs(body.decode("utf-8", errors="replace"))
    profile_id = _query_one(form, "profile")
    job_id = _query_one(form, "job")
    kind = _query_one(form, "kind")

    if profile_id and job_id and kind in tracking.KINDS:
        try:
            tracking.record(conn, profile_id, job_id, kind)
        except ValueError:
            pass

    if headers.get("accept", "").startswith("application/json"):
        return Response(200, json.dumps({"ok": True}), "application/json; charset=utf-8")
    return Response(303, "", headers={"Location": f"/?profile={quote(profile_id)}" if profile_id else "/"})


class _Handler(BaseHTTPRequestHandler):
    db_path = ":memory:"
    demo = False
    limiter = _RateLimiter()
    server_version = "kazikasi-feed/0.6"

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(min(length, 512 * 1024)) if length else b""

    def _respond(self, response: Response) -> None:
        if response.is_redirect:
            self.send_response(response.status)
            for key, value in response.headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        payload = response.body.encode("utf-8")
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in response.headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def _client_key(self) -> str:
        return str(self.client_address[0] if self.client_address else "unknown")

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        body = self._read_body() if method == "POST" else b""
        headers = {key: value for key, value in self.headers.items()}

        conn = db.connect(self.db_path)
        try:
            response = handle(
                conn,
                method,
                parsed.path,
                query,
                body=body,
                headers=headers,
                demo=self.demo,
                limiter=self.limiter,
                client=self._client_key(),
            )
        except Exception as exc:  # noqa: BLE001 - a 500 with a reason beats a dropped socket
            response = Response(
                500,
                _page("Error", f"<h1>Something broke</h1><p class=\"small\">{_e(exc)}</p>", demo=self.demo),
            )
        finally:
            conn.close()
        self._respond(response)

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        self._dispatch("POST")

    def log_message(self, fmt: str, *args) -> None:  # keep the console readable
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(fmt, *args)


def make_server(
    db_path: str | Path,
    *,
    host: str = "0.0.0.0",
    port: int = 8765,
    demo: bool = False,
) -> ThreadingHTTPServer:
    handler = type(
        "KazikasiHandler",
        (_Handler,),
        {"db_path": str(db_path), "demo": demo, "limiter": _RateLimiter()},
    )
    return ThreadingHTTPServer((host, port), handler)


def serve(db_path: str | Path, *, host: str = "0.0.0.0", port: int = 8765, demo: bool = False) -> None:
    httpd = make_server(db_path, host=host, port=port, demo=demo)
    print(f"Kazi-Kasi feed on http://{host}:{port} (db={db_path})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
