"""A read-only feed over the job graph.

This is the thinnest possible proof that the data is usable: server-rendered
HTML, no build step, no framework, no client-side state. It is **internal** —
the real feed is a Phase 3 decision (web + WhatsApp digest), and this exists so
the pipeline can be judged by eye rather than by test assertions alone.

Routes:

    /                feed, with county / entry-fit / stale filters
    /job/<id>        one job, with evidence, sources and event history
    /review          the pairs a human should decide on
    /api/jobs        the same feed as JSON
    /healthz         liveness probe for the process, not the data
"""

from __future__ import annotations

import html
import json
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import db, graph, metrics

ENTRY_FIT_LABEL = {
    "open_to_freshers": "Open to freshers",
    "some_experience": "1–2 years",
    "experienced": "3+ years",
    "unknown": "Eligibility unstated",
}

ENTRY_FIT_TONE = {
    "open_to_freshers": "good",
    "some_experience": "warn",
    "experienced": "muted",
    "unknown": "muted",
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
header{background:var(--card);border-bottom:1px solid var(--line);padding:16px 20px}
.wrap{max-width:760px;margin:0 auto;padding:0 20px}
.brand{font-weight:700;font-size:19px;letter-spacing:-.01em}
.brand span{color:var(--muted);font-weight:500;font-size:14px;margin-left:8px}
.banner{background:var(--warn-soft);color:var(--warn);border-bottom:1px solid #f0dcbc;
  padding:10px 20px;font-size:14px}
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
.foot{display:flex;gap:14px;flex-wrap:wrap;font-size:13px;color:var(--muted);margin-top:10px}
h1{font-size:22px;letter-spacing:-.02em;margin:24px 0 6px}
dl{display:grid;grid-template-columns:150px 1fr;gap:8px 16px;margin:18px 0;font-size:15px}
dt{color:var(--muted)}
dd{margin:0}
.sources{list-style:none;padding:0;margin:0;font-size:14px}
.sources li{padding:8px 0;border-bottom:1px solid var(--line)}
.sources li:last-child{border-bottom:none}
.small{font-size:13px;color:var(--muted)}
footer{padding:28px 0 40px;font-size:13px;color:var(--muted)}
@media (max-width:520px){dl{grid-template-columns:1fr;gap:2px}dt{margin-top:10px}}
"""


def _e(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _page(title: str, body: str, *, demo: bool = False) -> str:
    banner = (
        '<div class="banner">Synthetic demo data — no real vacancies are shown on this page.</div>'
        if demo
        else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)}</title><style>{STYLE}</style></head>
<body>
<header><div class="wrap"><div class="brand">Kazi-Kasi <span>Nairobi metro · early career</span></div></div></header>
{banner}
<div class="wrap">{body}</div>
<footer class="wrap">Every card shows when the source was last checked. Jobs are linked out, never
applied to here. Eligibility labels quote the advert, and unstated means unstated.</footer>
</body></html>"""


def render_feed(
    conn: sqlite3.Connection,
    *,
    county: str | None = None,
    entry_fit: str | None = None,
    include_stale: bool = False,
    now: datetime | None = None,
    demo: bool = False,
) -> str:
    now = now or datetime.now(timezone.utc)
    rows = graph.feed(conn, county=county, entry_fit=entry_fit, include_stale=include_stale, limit=60)
    summary = metrics.stats(conn, now=now)
    counties = [c["county"] for c in summary["counties"] if c["county"] != "unresolved"][:5]

    def chip(label: str, href: str, active: bool) -> str:
        return f'<a class="{"on" if active else ""}" href="{href}">{_e(label)}</a>'

    def qs(**params) -> str:
        parts = [f"{key}={quote(str(value))}" for key, value in params.items() if value]
        return "/" + ("?" + "&".join(parts) if parts else "")

    filters = [chip("All live", qs(), not county and not entry_fit and not include_stale)]
    for name in counties:
        filters.append(chip(name, qs(county=name), county == name))
    filters.append(chip("Open to freshers", qs(entry_fit="open_to_freshers"), entry_fit == "open_to_freshers"))
    filters.append(chip("Include stale", qs(include_stale=1), include_stale))

    cards = []
    for row in rows:
        badges = [
            f'<span class="badge {ENTRY_FIT_TONE.get(row["entry_fit"], "muted")}">'
            f'{_e(ENTRY_FIT_LABEL.get(row["entry_fit"], row["entry_fit"]))}</span>'
        ]
        if row["county"]:
            place = row["county"] if not row["sub_county"] else f'{row["sub_county"]}, {row["county"]}'
            badges.append(f'<span class="badge">{_e(place)}</span>')
        else:
            badges.append('<span class="badge">Location unstated</span>')
        if row["work_mode"] in ("remote", "hybrid"):
            badges.append(f'<span class="badge good">{_e(row["work_mode"].title())}</span>')
        deadline = graph.deadline_band(row, now=now)
        if deadline:
            tone = "warn" if deadline.startswith("closes in") or deadline in ("closes today", "closes tomorrow") else ""
            badges.append(f'<span class="badge {tone}">{_e(deadline)}</span>')
        if row["source_count"] > 1:
            badges.append(f'<span class="badge good">on {row["source_count"]} sources</span>')
        if row["status"] == "stale":
            badges.append('<span class="badge warn">not re-checked recently</span>')

        cards.append(
            f"""<article class="card">
  <h2><a href="/job/{_e(row['id'])}">{_e(row['title'])}</a></h2>
  <div class="employer">{_e(row['employer_name'] or 'Employer not stated')}</div>
  <div class="badges">{''.join(badges)}</div>
  <div class="foot"><span>{_e(graph.freshness_band(row, now=now))}</span></div>
</article>"""
        )

    if not cards:
        cards.append('<div class="card"><p>No live jobs match this filter right now.</p></div>')

    strip = f"""<div class="strip">
  <div><b>{summary['live_jobs']}</b>live jobs</div>
  <div><b>{summary['closing_within_7_days']}</b>closing in 7 days</div>
  <div><b>{summary['entry_fit_share_open_to_freshers']:.0%}</b>open to freshers</div>
  <div><b>{summary['cross_source_jobs']}</b>seen on 2+ sources</div>
</div>"""

    body = f"""{strip}
<div class="filters">{''.join(filters)}</div>
{''.join(cards)}"""
    return _page("Kazi-Kasi — live jobs", body, demo=demo)


def render_job(
    conn: sqlite3.Connection, job_id: str, *, now: datetime | None = None, demo: bool = False
) -> str | None:
    now = now or datetime.now(timezone.utc)
    row = graph.job_row(conn, job_id)
    if row is None:
        return None

    sources = graph.job_sources(conn, job_id)
    events = graph.job_events(conn, job_id)
    observation = conn.execute(
        "SELECT payload FROM observations WHERE id = ?", (row["primary_observation_id"],)
    ).fetchone()
    payload = json.loads(observation["payload"]) if observation else {}
    evidence = payload.get("entry_fit_evidence")
    description = (payload.get("description_md") or "").strip()

    rows = [
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
        f'<li><a href="{_e(source["source_url"])}" rel="nofollow noopener" target="_blank">'
        f'{_e(source["source_id"])}</a> · matched by {_e(source["match_reason"])}'
        f'<div class="small">checked {_e(source["fetched_at"][:16].replace("T", " "))}</div></li>'
        for source in sources
    )
    event_items = "".join(
        f'<li>{_e(event["kind"].replace("_", " "))} · {_e(event["at"][:10])}</li>' for event in events
    )
    flags = json.loads(row["scam_flags"])
    warning = ""
    if flags:
        warning = (
            '<div class="badge danger">Flagged: '
            + _e(", ".join(flag.replace("_", " ") for flag in flags))
            + "</div>"
        )

    evidence_block = (
        f'<div class="evidence">“{_e(evidence)}”</div>' if evidence else ""
    )
    description_block = (
        f'<h1>About the role</h1><p>{_e(description[:1200])}</p>' if description else ""
    )

    body = f"""
<p class="small"><a href="/">← back to the feed</a></p>
<h1>{_e(row['title'])}</h1>
<div class="employer">{_e(row['employer_name'] or 'Employer not stated')}</div>
<div class="badges">{warning}</div>
{evidence_block}
<dl>{''.join(f'<dt>{_e(label)}</dt><dd>{_e(value)}</dd>' for label, value in rows)}</dl>
{description_block}
<h1>Where this came from</h1>
<ul class="sources">{source_items}</ul>
<h1>History</h1>
<ul class="sources">{event_items}</ul>
<p class="small">Eligibility is read from the advert text, not inferred from the title.
If it says nothing, it says nothing.</p>
"""
    return _page(f"{row['title']} — Kazi-Kasi", body, demo=demo)


def render_review(conn: sqlite3.Connection, *, now: datetime | None = None, demo: bool = False) -> str:
    now = now or datetime.now(timezone.utc)
    pairs = graph.open_reviews(conn)
    if not pairs:
        body = "<h1>Review queue</h1><p>Nothing to decide.</p>"
        return _page("Review queue — Kazi-Kasi", body, demo=demo)
    items = "".join(
        f"""<article class="card">
  <h2>{_e(pair['incoming_title'])} <span class="small">vs</span> {_e(pair['job_title'])}</h2>
  <div class="employer">{_e(pair['incoming_employer'])} · similarity {pair['score']:.2f}</div>
  <div class="foot"><span>incoming: {_e(pair['incoming_source'])}</span>
  <span>existing job: <a href="/job/{_e(pair['candidate_job_id'])}">open</a></span></div>
</article>"""
        for pair in pairs
    )
    body = f"<h1>Review queue</h1><p class='small'>Pairs that were close but not close enough to merge automatically.</p>{items}"
    return _page("Review queue — Kazi-Kasi", body, demo=demo)


class _Handler(BaseHTTPRequestHandler):
    db_path = ":memory:"
    demo = False
    server_version = "kazikasi-feed/0.1"

    def _send(self, status: int, body: str, content_type: str = "text/html; charset=utf-8") -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

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
                rows = graph.feed(
                    conn,
                    county=(query.get("county") or [None])[0],
                    entry_fit=(query.get("entry_fit") or [None])[0],
                    include_stale=bool(query.get("include_stale")),
                )
                self._send(200, json.dumps(rows, indent=2), "application/json; charset=utf-8")
                return
            if parsed.path == "/review":
                self._send(200, render_review(conn, now=now, demo=self.demo))
                return
            if parsed.path.startswith("/job/"):
                page = render_job(conn, parsed.path.rsplit("/", 1)[-1], now=now, demo=self.demo)
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
                        county=(query.get("county") or [None])[0],
                        entry_fit=(query.get("entry_fit") or [None])[0],
                        include_stale=bool(query.get("include_stale")),
                        now=now,
                        demo=self.demo,
                    ),
                )
                return
            self._send(404, _page("Not found", "<h1>Not found</h1>", demo=self.demo))
        finally:
            conn.close()

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
    handler = type("KazikasiHandler", (_Handler,), {"db_path": str(db_path), "demo": demo})
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
