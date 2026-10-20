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

import html
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import hmac as _hmac
from urllib.parse import parse_qs, quote, urlparse

from . import db, digest as digest_module, graph, metrics, outbox, ranking, slo, tracking, webhooks
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
  --ink:#14181f; --muted:#5b6573; --line:#e3e7ee; --bg:#f7f8fa;
  --card:#ffffff; --accent:#0f6b4f; --accent-soft:#e7f4ee;
  --warn:#8a5300; --warn-soft:#fdf1dd; --danger:#a3241c; --danger-soft:#fdeceb;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
header{background:var(--card);border-bottom:1px solid var(--line);padding:14px 20px}
.wrap{max-width:760px;margin:0 auto;padding:0 20px}
.brand{font-weight:700;font-size:19px;letter-spacing:-.01em;display:flex;
  justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
.brand span{color:var(--muted);font-weight:500;font-size:14px}
.brand nav a{margin-left:14px;font-size:14px;color:var(--muted)}
.banner{background:var(--warn-soft);color:var(--warn);border-bottom:1px solid #f0dcbc;
  padding:10px 20px;font-size:14px}
.whobar{background:var(--card);border-bottom:1px solid var(--line);padding:12px 20px;font-size:14px}
.whobar b{font-weight:650}
.whobar .chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.chip{border:1px solid var(--line);border-radius:999px;padding:3px 9px;font-size:13px;color:var(--muted)}
.strip{display:flex;gap:20px;flex-wrap:wrap;padding:18px 0 6px;color:var(--muted);font-size:14px}
.strip b{color:var(--ink);font-size:18px;display:block;line-height:1.2}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0 22px}
.filters a{border:1px solid var(--line);background:var(--card);border-radius:999px;
  padding:6px 12px;font-size:14px;color:var(--muted)}
.filters a.on{border-color:var(--accent);color:var(--accent);background:var(--accent-soft)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:16px 18px;margin-bottom:12px}
.card h2{margin:0 0 4px;font-size:17px;letter-spacing:-.01em}
.employer{color:var(--muted);font-size:14px;margin-bottom:10px}
.badges{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
.badge{font-size:12px;border-radius:999px;padding:3px 9px;border:1px solid var(--line);color:var(--muted)}
.badge.good{background:var(--accent-soft);border-color:#c9e6d9;color:var(--accent)}
.badge.warn{background:var(--warn-soft);border-color:#f0dcbc;color:var(--warn)}
.badge.danger{background:var(--danger-soft);border-color:#f6cfcb;color:var(--danger)}
.evidence{font-size:13px;color:var(--muted);border-left:2px solid var(--line);
  padding-left:10px;margin:8px 0 4px}
.whythat{font-size:13px;color:var(--muted);margin:8px 0 0;padding-left:0;list-style:none;
  display:flex;gap:6px;flex-wrap:wrap}
.whythat li{background:#f2f4f7;border-radius:6px;padding:2px 8px}
.foot{display:flex;gap:14px;flex-wrap:wrap;font-size:13px;color:var(--muted);
  margin-top:12px;align-items:center}
.foot form{display:inline;margin:0}
.foot button{font:inherit;font-size:13px;background:none;border:none;color:var(--muted);
  cursor:pointer;padding:0;text-decoration:underline}
.foot .apply{border:1px solid var(--accent);color:var(--accent);border-radius:999px;
  padding:5px 12px;font-size:14px;background:var(--accent-soft)}
h1{font-size:22px;letter-spacing:-.02em;margin:24px 0 6px}
table{width:100%;border-collapse:collapse;font-size:14px;background:var(--card);
  border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;font-size:13px;background:#fbfcfd}
tr:last-child td{border-bottom:none}
dl{display:grid;grid-template-columns:150px 1fr;gap:8px 16px;margin:18px 0;font-size:15px}
dt{color:var(--muted)}
dd{margin:0}
.sources{list-style:none;padding:0;margin:0;font-size:14px}
.sources li{padding:8px 0;border-bottom:1px solid var(--line)}
.sources li:last-child{border-bottom:none}
.small{font-size:13px;color:var(--muted)}
.msg{white-space:pre-wrap;word-break:break-word;background:#e8f5ee;border:1px solid var(--line);
  border-radius:14px;padding:14px 16px;font:14px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;margin:12px 0}
.msg.sms{background:#f3f5f8}
.subform{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 18px}
.subform input{flex:1 1 220px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;font-size:15px}
.subform button{padding:10px 16px;border:0;border-radius:10px;background:var(--accent);color:#fff;font-size:15px;font-weight:600}
.subform button.ghost{background:#fff;color:var(--muted);border:1px solid var(--line);font-weight:500}
footer{padding:28px 0 40px;font-size:13px;color:var(--muted)}
@media (max-width:520px){dl{grid-template-columns:1fr;gap:2px}dt{margin-top:10px}}
"""


def _constant_time_equal(left: str, right: str) -> bool:
    return _hmac.compare_digest((left or "").encode(), (right or "").encode())


def _e(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _page(title: str, body: str, *, demo: bool = False, nav: str = "") -> str:
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
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)}</title><style>{STYLE}</style></head>
<body>
<header><div class="wrap"><div class="brand">Kazi-Kasi
<span>Nairobi metro · early career</span>
<nav>{links}</nav></div></div></header>
{banner}
<div class="wrap">{body}</div>
<footer class="wrap">Every card says when it was last checked and why it was shown.
Eligibility labels quote the advert. Applications happen on the employer's site, never here.</footer>
</body></html>"""


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
) -> str:
    now = now or datetime.now(timezone.utc)
    profile = _profile_or_default(conn, profile_id)
    matches, acted = _ranked(conn, profile, now=now, limit=limit)
    summary = metrics.stats(conn, now=now)

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
        badges.append(f'<span class="badge">{_e(place or "Location unstated")}</span>')
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
        if row.get("id") in acted:
            badges.append('<span class="badge">you applied</span>')

        reasons = "".join(f"<li>{_e(reason)}</li>" for reason in match.reasons[:4])
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
  <ul class="whythat">{reasons}</ul>
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
    return _page(f"{row['title']} — Kazi-Kasi", body, demo=demo)


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


class _Handler(BaseHTTPRequestHandler):
    db_path = ":memory:"
    demo = False
    limiter = _RateLimiter()
    server_version = "kazikasi-feed/0.5"

    def _send(self, status: int, body: str, content_type: str = "text/html; charset=utf-8", headers=None) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        now = datetime.now(timezone.utc)
        conn = db.connect(self.db_path)
        try:
            if parsed.path == "/healthz":
                self._send(200, "ok", "text/plain; charset=utf-8")
                return
            if parsed.path == "/api/jobs":
                profile = _profile_or_default(conn, (query.get("profile") or [None])[0])
                matches, _ = _ranked(conn, profile, now=now, limit=int((query.get("limit") or [40])[0]))
                payload = {"profile": profile.to_dict(), "matches": [match.to_dict() for match in matches]}
                self._send(200, json.dumps(payload, indent=2, default=str), "application/json; charset=utf-8")
                return
            if parsed.path == "/go":
                profile_id = (query.get("profile") or [""])[0]
                job_id = (query.get("job") or [""])[0]
                row = graph.job_row(conn, job_id)
                source = graph.primary_source(conn, job_id)
                if row is None or source is None:
                    self._send(404, _page("Not found", "<h1>Job not found</h1>", demo=self.demo))
                    return
                tracking.record(conn, profile_id, job_id, "clicked_through", detail=source["source_id"])
                self._redirect(source["source_url"])
                return
            if parsed.path == "/slo":
                self._send(200, render_slo(conn, now=now, demo=self.demo))
                return
            if parsed.path == "/review":
                self._send(200, render_review(conn, now=now, demo=self.demo))
                return
            if parsed.path == "/webhooks/whatsapp":
                challenge = webhooks.verify_challenge(
                    {key: (values or [""])[0] for key, values in query.items()},
                    os.environ.get("WHATSAPP_VERIFY_TOKEN"),
                )
                if challenge is None:
                    self._send(403, "verification failed", "text/plain; charset=utf-8")
                else:
                    self._send(200, challenge, "text/plain; charset=utf-8")
                return
            if parsed.path == "/digest":
                self._send(
                    200,
                    render_digest(
                        conn,
                        profile_id=(query.get("profile") or [None])[0],
                        now=now,
                        demo=self.demo,
                        error=(query.get("error") or [""])[0],
                    ),
                )
                return
            if parsed.path.startswith("/job/"):
                page = render_job(
                    conn,
                    parsed.path.rsplit("/", 1)[-1],
                    profile_id=(query.get("profile") or [None])[0],
                    now=now,
                    demo=self.demo,
                )
                if page is None:
                    self._send(404, _page("Not found", "<h1>Job not found</h1>", demo=self.demo))
                else:
                    self._send(200, page)
                return
            if parsed.path in ("/", "/index.html"):
                self._send(
                    200,
                    render_feed(
                        conn,
                        profile_id=(query.get("profile") or [None])[0],
                        now=now,
                        demo=self.demo,
                    ),
                )
                return
            self._send(404, _page("Not found", "<h1>Not found</h1>", demo=self.demo))
        finally:
            conn.close()

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        parsed = urlparse(self.path)
        if parsed.path in ("/webhooks/whatsapp", "/webhooks/sms"):
            self._webhook(parsed)
            return
        if parsed.path in ("/digest/subscribe", "/digest/unsubscribe"):
            self._consent(parsed.path)
            return
        if parsed.path != "/action":
            self._send(404, "not found", "text/plain; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(body)
        profile_id = (form.get("profile") or [""])[0]
        job_id = (form.get("job") or [""])[0]
        kind = (form.get("kind") or [""])[0]

        conn = db.connect(self.db_path)
        try:
            if profile_id and job_id and kind in tracking.KINDS:
                try:
                    tracking.record(conn, profile_id, job_id, kind)
                except ValueError:
                    pass
        finally:
            conn.close()

        if self.headers.get("Accept", "").startswith("application/json"):
            self._send(200, json.dumps({"ok": True}), "application/json; charset=utf-8")
            return
        self._redirect(f"/?profile={quote(profile_id)}" if profile_id else "/")

    def _client_key(self) -> str:
        return str(self.client_address[0] if self.client_address else "unknown")

    def _limited(self) -> bool:
        if self.limiter.allow(self._client_key()):
            return False
        self._send(429, "too many requests", "text/plain; charset=utf-8")
        return True

    def _webhook(self, parsed) -> None:
        """Inbound replies and receipts. Fails closed on an unverified sender."""
        if self._limited():
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(min(length, 512 * 1024))

        conn = db.connect(self.db_path)
        try:
            if parsed.path == "/webhooks/whatsapp":
                secret = os.environ.get("WHATSAPP_APP_SECRET")
                signature = self.headers.get(webhooks.SIGNATURE_HEADER)
                if secret:
                    if not webhooks.verify_signature(raw, signature, secret):
                        self._send(403, "bad signature", "text/plain; charset=utf-8")
                        return
                elif not self.demo:
                    # No secret and not a demo: we cannot tell Meta from anyone.
                    self._send(503, "webhook not configured", "text/plain; charset=utf-8")
                    return
                payload = webhooks.parse_json(raw)
                result = webhooks.handle_meta(conn, payload)
            else:
                token = (parse_qs(parsed.query).get("token") or [""])[0]
                expected = os.environ.get("AT_WEBHOOK_TOKEN")
                if expected and not _constant_time_equal(token, expected):
                    self._send(403, "bad token", "text/plain; charset=utf-8")
                    return
                if not expected and not self.demo:
                    self._send(503, "webhook not configured", "text/plain; charset=utf-8")
                    return
                form = {
                    key: (values or [""])[0]
                    for key, values in parse_qs(raw.decode("utf-8", errors="replace")).items()
                }
                result = webhooks.handle_africas_talking(conn, form)
        finally:
            conn.close()

        self._send(200, json.dumps(result, default=str), "application/json; charset=utf-8")

    def _consent(self, path: str) -> None:
        """Subscribe or opt out from the digest page. Always redirects back."""
        if self._limited():
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(body)
        profile_id = (form.get("profile") or [""])[0]
        msisdn = (form.get("msisdn") or [""])[0]

        conn = db.connect(self.db_path)
        error = ""
        try:
            if path.endswith("/unsubscribe"):
                outbox.unsubscribe(conn, profile_id, reason="web")
            else:
                try:
                    outbox.subscribe(conn, profile_id, msisdn, source="web")
                except ValueError as exc:
                    error = str(exc)
        finally:
            conn.close()

        target = f"/digest?profile={quote(profile_id)}"
        if error:
            target += f"&error={quote(error)}"
        self._redirect(target)

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
