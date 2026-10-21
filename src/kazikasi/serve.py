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

import base64
import hashlib
import re
import hmac as _hmac
import html
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse

from . import (
    accounts,
    autofill,
    brief as brief_module,
    bundle as bundle_module,
    db,
    digest as digest_module,
    dossier,
    employer,
    graph,
    recap,
    metrics,
    momentum,
    channels,
    outbox,
    pulse,
    ranking,
    scheduler,
    search as search_module,
    searches as searches_module,
    setup as setup_module,
    shortlist,
    slo,
    tracking,
    webhooks,
    wildcard,
)
from .corpus import load_corpus
from .profile import DEMO_PROFILES, list_profiles, seed_profiles

ENTRY_FIT_LABEL = ranking.ENTRY_FIT_LABEL
ENTRY_FIT_TONE = {
    "open_to_freshers": "good",
    "some_experience": "warn",
    "experienced": "muted",
    "unknown": "muted",
}
SLO_TONE = {"on_time": "good", "late": "warn", "stale": "danger", "never_fetched": "muted",
            "not_enabled": "muted"}
SLO_LABEL = {
    "on_time": "on time",
    "late": "late",
    "stale": "stale",
    "never_fetched": "never fetched",
    "not_enabled": "not enabled",
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
  --radius:16px; --radius-sm:10px; --radius-pill:999px;
  --shadow:0 1px 2px rgba(18,22,28,.04),0 10px 30px rgba(18,22,28,.05);
  --shadow-lift:0 2px 4px rgba(18,22,28,.05),0 18px 44px rgba(18,22,28,.09);
  --focus:0 0 0 3px #B9D4C1, 0 0 0 1px #14532D;
  --font-sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --font-display:Georgia,"Iowan Old Style","Times New Roman",serif;
  --font-mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 var(--font-sans);
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:var(--forest);text-decoration:none}
a:hover{text-decoration:underline;text-underline-offset:2px}
:focus-visible{outline:none;box-shadow:var(--focus);border-radius:8px}
::selection{background:var(--forest-soft);color:var(--ink)}
a{-webkit-tap-highlight-color:transparent}

/* ---- the masthead -------------------------------------------------- */
header{position:sticky;top:0;z-index:20;background:rgba(251,248,242,.93);
  border-bottom:1px solid var(--line);backdrop-filter:saturate(140%) blur(10px)}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
.brand{display:flex;justify-content:space-between;align-items:center;gap:16px;
  padding:14px 0;flex-wrap:wrap}
.lockup{display:flex;align-items:center;gap:10px;min-width:0}
.lockup svg{width:30px;height:30px;color:var(--forest);flex:none}
.lockup .word{font-size:21px;font-weight:700;letter-spacing:-.025em;line-height:1}
.lockup .tag{display:block;color:var(--muted);font-size:10.5px;letter-spacing:.1em;
  text-transform:uppercase;font-weight:600;margin-top:5px}
.brand nav{display:flex;gap:2px;flex-wrap:wrap;align-items:center}
.brand nav a{font-size:11px;letter-spacing:.09em;text-transform:uppercase;font-weight:650;
  color:var(--ink-2);padding:9px 10px;border-radius:8px}
.brand nav a:hover{background:var(--sunken);text-decoration:none;color:var(--ink)}
.brand nav .nav-signin{background:var(--forest);color:#fff;padding:9px 16px}
.brand nav .nav-signin:hover{background:#0e3d1f;color:#fff;text-decoration:none}
.banner{background:var(--amber-soft);color:var(--amber);border-bottom:1px solid #EBD6B4;
  padding:9px 24px;font-size:12.5px;letter-spacing:.01em}

/* ---- the page ------------------------------------------------------ */
main{padding-bottom:40px}
.masthead{padding:44px 0 0}
.kicker{margin:0;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;
  font-weight:700;color:var(--muted)}
.display{font-family:var(--font-display);font-weight:400;font-size:50px;line-height:1.02;
  letter-spacing:-.025em;margin:12px 0 8px;color:var(--ink)}
.scopeline{margin:0;color:var(--ink-2);font-size:15px;max-width:60ch}
.cmdk{font:inherit;font-size:11px;letter-spacing:.09em;text-transform:uppercase;
  font-weight:650;color:var(--ink-2);background:none;border:1px solid var(--line);
  border-radius:8px;padding:7px 10px;cursor:pointer;display:inline-flex;gap:7px;
  align-items:center;transition:border-color .14s,color .14s}
.cmdk:hover{border-color:var(--forest);color:var(--forest)}
.cmdk kbd{font:inherit;font-size:10px;color:var(--muted);border:1px solid var(--line);
  border-radius:4px;padding:1px 4px}
.palette{position:fixed;inset:0;z-index:60;background:rgba(18,22,28,.35);
  display:flex;align-items:flex-start;justify-content:center;padding:12vh 16px 16px}
.palette[hidden]{display:none}
.palette-box{width:min(560px,100%);background:var(--card);border:1px solid var(--line);
  border-radius:var(--radius);box-shadow:var(--shadow-lift);overflow:hidden}
.palette input{width:100%;border:0;border-bottom:1px solid var(--line);padding:16px 18px;
  font:16px/1.4 var(--font-sans);background:var(--card);color:var(--ink);outline:none}
.palette ul{list-style:none;margin:0;padding:6px;max-height:52vh;overflow:auto}
.palette li a{display:flex;justify-content:space-between;gap:14px;align-items:baseline;
  padding:10px 12px;border-radius:8px;color:var(--ink)}
.palette li a:hover,.palette li.on a{background:var(--forest-soft);text-decoration:none}
.palette li b{font-weight:600;font-size:14px}
.palette li span{color:var(--muted);font-size:12px;white-space:nowrap}
.palette .none{padding:14px 12px;color:var(--muted);font-size:14px}
.palette .hint{border-top:1px solid var(--line);padding:9px 16px;font-size:11.5px;color:var(--muted)}
.wildcard{border:1px dashed #CFC3AE;background:var(--sunken)}
.wildcard .tagline{font-size:10px;letter-spacing:.13em;text-transform:uppercase;
  color:var(--amber);font-weight:700;margin:0 0 8px}
.momentum{display:flex;align-items:center;gap:10px;margin-top:4px}
.marks{display:flex;gap:4px}
.marks i{width:9px;height:9px;border-radius:2px;background:var(--line);display:block}
.marks i.on{background:var(--forest)}
.ledger{display:flex;gap:8px;flex-wrap:wrap;align-items:baseline;margin:24px 0 0;
  padding:12px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);
  font-size:13px;color:var(--ink-2)}
.ledger b{color:var(--ink);font-weight:650}

/* ---- the four numbers ---------------------------------------------- */
.strip{display:grid;grid-template-columns:repeat(4,1fr);margin:0}
.strip div{padding:18px 20px 16px 0;border-bottom:1px solid var(--line)}
.strip b{display:block;font-family:var(--font-display);font-weight:400;font-size:34px;
  line-height:1;font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.strip span{display:block;margin-top:7px;font-size:10.5px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted);font-weight:650}

/* ---- layout -------------------------------------------------------- */
.layout{display:grid;grid-template-columns:minmax(0,1fr) 296px;gap:36px;
  padding:28px 0 0;align-items:start}
.feedcol{min-width:0}
.section{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
  margin:0 0 14px;font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;
  color:var(--muted);font-weight:700}
.section em{font-style:normal;color:var(--ink-2);letter-spacing:.04em}
.endnote{color:var(--muted);font-size:13px;padding:6px 0 0}

/* ---- the card ------------------------------------------------------ */
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:20px 22px 16px;margin-bottom:14px;box-shadow:var(--shadow);
  transition:border-color .18s ease-out,transform .18s ease-out,box-shadow .18s ease-out}
.card:hover{border-color:#D5C7B0;transform:translateY(-2px);box-shadow:var(--shadow-lift)}
.card:focus-within{border-color:var(--forest)}
.card-top{display:flex;gap:20px;justify-content:space-between;align-items:flex-start}
.card h2{margin:0 0 5px;font-family:var(--font-sans);font-size:19px;line-height:1.26;
  letter-spacing:-.018em;font-weight:650}
.card h2 a{color:var(--ink)}
.card h2 a:hover{color:var(--forest);text-decoration:none}
.employer{color:var(--muted);font-size:13.5px}
.deadline{flex:none;text-align:right;padding-top:3px}
.dl-label{display:block;font-size:9.5px;letter-spacing:.13em;text-transform:uppercase;
  color:var(--muted);font-weight:700}
.dl-date{display:block;font-family:var(--font-display);font-size:18px;line-height:1.2;
  color:var(--ink);white-space:nowrap;font-variant-numeric:tabular-nums}
.deadline.soon .dl-date{color:var(--amber)}
.deadline.gone .dl-date{color:var(--muted);text-decoration:line-through}
.badges{display:flex;gap:6px;flex-wrap:wrap;margin:14px 0 0}
.badge{font-size:11.5px;border-radius:var(--radius-pill);padding:3px 10px;
  border:1px solid var(--line);color:var(--ink-2);background:var(--sunken);white-space:nowrap}
.badge.good{background:var(--forest-soft);border-color:#CFE3D4;color:var(--forest);font-weight:600}
.badge.warn{background:var(--amber-soft);border-color:#EBD6B4;color:var(--amber);font-weight:600}
.badge.danger{background:var(--risk-soft);border-color:#EBC5C0;color:var(--risk);font-weight:600}
.badge.muted{background:var(--sunken);border-color:var(--line);color:var(--ink-2)}
.whythat{font-size:12.5px;color:var(--muted);margin:12px 0 0;padding:0;list-style:none;
  display:flex;gap:6px;flex-wrap:wrap}
.whythat li{border:1px solid var(--line);border-radius:var(--radius-pill);padding:2px 9px;
  background:transparent}
.foot{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-top:14px;
  padding-top:12px;border-top:1px solid var(--line);font-size:12.5px;color:var(--muted)}
.foot .score{font-variant-numeric:tabular-nums;letter-spacing:.02em;color:var(--ink-2)}
.foot form{display:inline;margin:0}
.foot button{font:inherit;font-size:12.5px;background:none;border:none;color:var(--muted);
  cursor:pointer;padding:8px 0;border-bottom:1px solid transparent;transition:color .14s,border-color .14s}
.foot button:hover{color:var(--ink);border-bottom-color:var(--line)}
.foot button.on{color:var(--forest);font-weight:650}
.foot .apply{margin-left:auto;border:1px solid var(--forest);color:#fff;
  border-radius:var(--radius-pill);padding:0 18px;font-size:13.5px;font-weight:600;
  background:var(--forest);min-height:40px;display:inline-flex;align-items:center;
  transition:background .16s ease-out,transform .16s ease-out}
.foot .apply:hover{background:#0F3F22;text-decoration:none;transform:translateY(-1px)}

/* ---- the rail ------------------------------------------------------ */
.rail{position:sticky;top:88px}
.rail-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:16px 18px;margin-bottom:14px}
.rail-card h3{margin:0 0 10px;font-size:10px;letter-spacing:.13em;text-transform:uppercase;
  color:var(--muted);font-weight:700}
.rail-card .chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{border:1px solid var(--line);border-radius:var(--radius-pill);padding:3px 10px;
  font-size:12px;color:var(--ink-2);background:var(--sunken);white-space:nowrap}
.filters a.chip{padding:6px 12px;min-height:32px;background:transparent}
.filters a.chip.on{border-color:var(--forest);color:var(--forest);background:var(--forest-soft)}
.filters a.chip .num{color:var(--ink-3);font-variant-numeric:tabular-nums;margin-left:2px}
.searchform{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:12px;
  margin:22px 0 0;align-items:end}
.searchform label{display:flex;flex-direction:column;gap:5px;font-size:10.5px;
  letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3);font-weight:650}
.searchform input,.searchform select{font:inherit;font-size:14px;padding:10px 11px;width:100%;
  border:1px solid var(--line);border-radius:10px;background:#fff;color:var(--ink);
  min-height:42px;appearance:none}
.searchform input:focus,.searchform select:focus{outline:2px solid var(--forest);
  outline-offset:1px;border-color:var(--forest)}
.searchform label.check{flex-direction:row;align-items:center;gap:8px;font-size:12.5px;
  letter-spacing:0;text-transform:none;color:var(--ink-2);font-weight:400;min-height:42px}
.searchform label.check input{width:16px;height:16px;min-height:0;margin:0}
.searchform button{font:inherit;font-size:13.5px;font-weight:650;padding:11px 18px;
  border-radius:10px;border:1px solid var(--forest);background:var(--forest);
  color:#FBF8F2;min-height:42px;cursor:pointer}
.searchform button:hover{background:#0F3F22}
.paste{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0}
.paste input{flex:1 1 260px;min-width:0;font:13px/1.4 var(--font-mono);padding:9px 10px;
  border:1px solid var(--line);border-radius:8px;background:var(--sunken);color:var(--ink)}
.copy{font:inherit;font-size:12.5px;padding:8px 12px;border:1px solid var(--line);
  border-radius:8px;background:var(--card);color:var(--ink-2);cursor:pointer;min-height:36px}
.copy:hover{border-color:#CFC3AE;color:var(--ink)}
code.key{font:12px/1.4 var(--font-mono);background:var(--sunken);border:1px solid var(--line);
  border-radius:6px;padding:1px 6px;margin-right:4px;white-space:nowrap}
.step .employer{max-width:62ch}
.step.done{opacity:.72;padding:14px 18px}
.step.done h2{font-size:15px;margin:0}
.stepnum{display:inline-block;min-width:1.4em}
.trouble li{margin-bottom:14px;line-height:1.5}
.trouble .small{display:block}
p.mono{font-family:var(--font-mono);font-size:12px}
@media (max-width:640px){.searchform{grid-template-columns:1fr 1fr}
  .searchform label:first-of-type{grid-column:1/-1}}
.mini{display:flex;justify-content:space-between;gap:12px;padding:9px 0;
  border-bottom:1px solid var(--line);font-size:13px;line-height:1.35}
.mini:last-of-type{border-bottom:none}
.mini a{color:var(--ink)}
.mini .when{color:var(--amber);white-space:nowrap;font-variant-numeric:tabular-nums;font-size:12px}
.rail-card .more{display:inline-block;margin-top:10px;font-size:12.5px;font-weight:650}
.rail-note{color:var(--muted);font-size:12px;margin:6px 0 0}

/* ---- profile switcher --------------------------------------------- */
.mt0{margin-top:0}.mt6{margin-top:6px}.mt10{margin-top:10px}.mt12{margin-top:12px}
.mt18{margin-top:18px}.mt26{margin-top:26px}.mt28{margin-top:28px}.mt32{margin-top:32px}
.flush{margin:0}.inline{display:inline}.inline-ml{display:inline;margin-left:10px}
.stack{flex-direction:column;align-items:stretch}
.codebox{font:14px/1.5 var(--font-mono);padding:12px;border:1px solid var(--line);
  border-radius:var(--radius-sm);background:var(--card);color:var(--ink);width:100%}
.filters{display:flex;gap:6px;flex-wrap:wrap;margin:18px 0 0}
.filters a{border:1px solid var(--line);background:transparent;border-radius:var(--radius-pill);
  padding:6px 13px;font-size:12.5px;color:var(--ink-2);min-height:34px;
  display:inline-flex;align-items:center;transition:border-color .14s,background .14s,color .14s}
.filters a:hover{border-color:#CFC3AE;color:var(--ink);text-decoration:none}
.filters a.on{border-color:var(--forest);color:var(--forest);background:var(--forest-soft);
  font-weight:650}

/* ---- employer and year pages --------------------------------------- */
.two{display:grid;grid-template-columns:1fr 1fr;gap:26px;align-items:start;margin-bottom:8px}
.two .tablewrap{margin:0}
.fig{font-family:var(--font-display);font-size:32px;line-height:1;margin:6px 0 8px;
  font-variant-numeric:tabular-nums}
pre.msg{white-space:pre-wrap;font:13.5px/1.6 var(--font-mono);background:var(--sunken);
  border:1px solid var(--line);border-radius:var(--radius-sm);padding:14px 16px;margin:0 0 8px}
@media (max-width:900px){.two{grid-template-columns:1fr;gap:14px}}

/* ---- panels used by the ops pages --------------------------------- */
.whobar{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:16px 18px;margin:20px 0 0;font-size:14px;box-shadow:var(--shadow)}
.whobar b{font-weight:650}
.whobar .chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.whobar button.ghost{font:inherit;font-size:13.5px;font-weight:650;background:var(--card);
  color:var(--forest);border:1px solid var(--forest);border-radius:var(--radius-pill);
  padding:9px 16px;cursor:pointer;min-height:40px}
.whobar button.ghost:hover{background:var(--forest-soft)}


/* Sign-in providers. These classes existed in the markup but were never defined —
   a stylesheet rewrite dropped them, and the buttons rendered as unstyled inline
   text. tests/test_css_coverage.py now fails if markup names a class the sheet
   does not define. */
.provider{display:flex;align-items:center;gap:12px;margin-bottom:10px;
  padding:4px;border-radius:calc(var(--radius) + 4px)}
.provider-button{flex:1;display:flex;flex-direction:column;align-items:flex-start;gap:3px;
  font:inherit;text-align:left;cursor:pointer;background:var(--card);
  border:1px solid var(--line);border-radius:var(--radius);padding:13px 16px;
  color:var(--ink);min-height:52px;
  transition:border-color .18s ease-out,box-shadow .18s ease-out,transform .18s ease-out}
.provider-button b{font-size:14.5px;font-weight:650}
.provider-button span{font-size:12.5px;color:var(--muted);line-height:1.35}
.provider-button:hover{border-color:var(--forest);box-shadow:var(--shadow);
  transform:translateY(-1px)}
.provider-button:focus-visible{outline:2px solid var(--forest);outline-offset:2px}
.provider-button.off{background:var(--sunken);color:var(--muted);cursor:not-allowed;
  border-style:dashed;opacity:.85}
.provider-button.off:hover{border-color:var(--line);box-shadow:none;transform:none}
.provider-state{font-size:11.5px;border-radius:var(--radius-pill);padding:3px 10px;
  border:1px solid var(--line);background:var(--sunken);color:var(--muted);
  white-space:nowrap;flex:none}
.provider-state.ready{background:var(--forest-soft);border-color:var(--forest);color:var(--forest)}

/* The numbered verification list on the go-live page. */
.trial{list-style:none;padding:0;margin:0;counter-reset:trial}
.trial li{padding:11px 0 11px 34px;border-bottom:1px solid var(--line);position:relative;
  font-size:13.5px;counter-increment:trial}
.trial li:last-child{border-bottom:none}
.trial li::before{content:counter(trial);position:absolute;left:0;top:11px;
  width:22px;height:22px;border-radius:50%;background:var(--sunken);
  border:1px solid var(--line);color:var(--ink-2);font-size:11.5px;font-weight:700;
  display:flex;align-items:center;justify-content:center}
.trial li .small{display:block;margin-top:3px}
/* ---- Sign-in page ------------------------------------------------------ */
.signin-wrap{display:flex;align-items:flex-start;justify-content:center;
  padding:60px 20px 40px;min-height:60vh}
.signin-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:36px 40px 32px;max-width:440px;width:100%;box-shadow:var(--shadow)}
.signin-card .kicker{margin:0 0 18px}
.signin-headline{font-family:var(--font-display);font-weight:400;font-size:34px;
  line-height:1.1;letter-spacing:-.02em;margin:0 0 10px;color:var(--ink)}
.signin-sub{margin:0 0 24px;font-size:14.5px;color:var(--ink-2);line-height:1.45}
.signin-primary{margin-bottom:14px}
.signin-primary-btn{display:flex;flex-direction:column;align-items:flex-start;gap:4px;
  width:100%;background:var(--forest);color:#fff;border:none;border-radius:10px;
  padding:18px 22px;cursor:pointer;text-align:left;font:inherit;
  transition:background .14s,transform .14s}
.signin-primary-btn:hover{background:#0e3d1f;transform:translateY(-1px)}
.signin-primary-btn:focus-visible{outline:2px solid var(--forest);outline-offset:2px}
.signin-provider-name{font-size:17px;font-weight:650}
.signin-provider-why{font-size:12.5px;opacity:.85;line-height:1.3}
.signin-secondary{display:flex;gap:8px;margin-bottom:8px}
.signin-secondary-btn{flex:1;font:inherit;font-size:14px;font-weight:600;
  background:var(--card);color:var(--ink);border:1px solid var(--line);
  border-radius:8px;padding:12px 14px;cursor:pointer;
  transition:border-color .14s,box-shadow .14s}
.signin-secondary-btn:hover{border-color:var(--forest);box-shadow:var(--shadow)}
.signin-guest{margin-top:20px;padding-top:18px;border-top:1px solid var(--line)}
.signin-guest-btn{width:100%;font:inherit;font-size:13.5px;font-weight:600;
  background:transparent;color:var(--ink-2);border:none;border-radius:8px;
  padding:11px;cursor:pointer;transition:color .14s,background .14s}
.signin-guest-btn:hover{color:var(--ink);background:var(--sunken)}
.signin-privacy{margin:18px 0 0;font-size:11.5px;color:var(--muted);line-height:1.5}
.signin-notice{margin:0 0 14px;font-size:12.5px;color:var(--muted)}
.signin-notice a{color:var(--forest)}
.evidence{font-size:13.5px;color:var(--ink-2);border-left:2px solid var(--line);
  padding-left:12px;margin:12px 0 4px}
h1{font-family:var(--font-display);font-weight:400;font-size:38px;line-height:1.08;
  letter-spacing:-.02em;margin:34px 0 8px}
h2{font-size:18px;letter-spacing:-.01em;margin:26px 0 4px}
p{margin:8px 0}
table{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--card);
  border:1px solid var(--line);border-radius:var(--radius-sm);overflow:hidden;
  font-variant-numeric:tabular-nums}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:650;font-size:11px;letter-spacing:.06em;
  text-transform:uppercase;background:var(--paper)}
tr:last-child td{border-bottom:none}
.tablewrap{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:6px 0 4px}
.tablewrap table{min-width:520px}
.tablewrap th a{color:var(--ink);font-weight:650}
dl{display:grid;grid-template-columns:150px 1fr;gap:8px 16px;margin:18px 0;font-size:15px}
dt{color:var(--muted)}
dd{margin:0}
.sources{list-style:none;padding:0;margin:0;font-size:13.5px}
.sources li{padding:9px 0;border-bottom:1px solid var(--line)}
.sources li:last-child{border-bottom:none}
.small{font-size:12.5px;color:var(--muted)}
.msg{white-space:pre-wrap;word-break:break-word;background:var(--forest-soft);
  border:1px solid #CFE3D4;border-radius:var(--radius-sm);padding:14px 16px;
  font:13.5px/1.65 var(--font-mono);margin:12px 0;color:var(--ink)}
.msg.sms{background:var(--sunken);border-color:var(--line)}
.subform{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 18px}
.subform input{flex:1 1 220px;padding:11px 13px;border:1px solid var(--line);
  border-radius:var(--radius-sm);font-size:16px;font-family:inherit;background:var(--card)}
.subform button{padding:11px 18px;border:0;border-radius:var(--radius-sm);background:var(--forest);
  color:#fff;font-size:15px;font-weight:600;cursor:pointer;min-height:44px}
.subform button:hover{background:#0F3F22}
.subform button.ghost{background:var(--card);color:var(--ink-2);border:1px solid var(--line);font-weight:500}
footer{padding:34px 0 46px;font-size:12.5px;color:var(--muted);border-top:1px solid var(--line)}
footer p{margin:0;max-width:70ch}

@media (max-width:900px){
  .layout{grid-template-columns:1fr;gap:10px}
  .rail{position:static;order:2;margin-top:6px}
  .display{font-size:40px}
}
@media (max-width:520px){
  .wrap{padding:0 18px}
  main{overflow-x:hidden}
  .masthead{padding-top:30px}
  .display{font-size:34px}
  .strip{grid-template-columns:repeat(2,1fr);gap:10px 0}
  .strip b{font-size:28px}
  .strip div{padding:14px 0 12px}
  dl{grid-template-columns:1fr;gap:2px}
  dt{margin-top:10px}
  .foot .apply{width:100%;justify-content:center;margin-left:0}
  .brand nav a{padding:8px 8px}
  .card{padding:17px 16px 14px}
  .card-top{flex-wrap:wrap;gap:6px}
  .deadline{text-align:left;padding-top:0}
  .dl-date{font-size:16px}
}
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


def _page(
    title: str,
    body: str,
    *,
    demo: bool = False,
    nav: str = "",
    head: str = "",
    palette: list | None = None,
) -> str:
    build = (os.environ.get("VERCEL_GIT_COMMIT_SHA") or "")[:7] or "dev"
    notice = bundle_module.notice()
    if demo:
        banner = (
            '<div class="banner">Synthetic demo data — no real vacancies are shown on this page.</div>'
        )
    elif notice:
        banner = f'<div class="banner">{_e(notice)}</div>'
    else:
        banner = ""
    demo_line = f'<div class="small mt6">demo build {_e(build)}</div>' if demo else ""
    palette_html = _palette_markup(palette or [])
    links = nav or (
        '<a href="/">Feed</a><a href="/shortlist">Shortlist</a>'
        '<a href="/brief">Brief</a><a href="/pulse">Pulse</a><a href="/digest">WhatsApp</a>'
        '<button type="button" class="cmdk" data-cmdk aria-haspopup="dialog">'
        'Jump <kbd>⌘K</kbd></button>'
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
<main class="wrap">{body}</main>
{palette_html}
<footer class="wrap"><p>Every card says when it was last checked and why it was shown.
Eligibility labels quote the advert. Applications happen on the employer's site, never here.</p>
<p class="ops">Ops: <a href="/slo">freshness</a> · <a href="/review">review queue</a> ·
<a href="/salaries">advertised pay</a> · <a href="/setup">go-live</a></p>
{demo_line}</footer>
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


def _deadline_view(row, now: datetime) -> tuple[str, str, str]:
    """Label, date, tone. The deadline is the decision field; it gets the corner."""
    raw = row.get("deadline")
    if not raw:
        return "no deadline", "—", ""
    try:
        day = date.fromisoformat(str(raw)[:10])
    except ValueError:
        return "no deadline", "—", ""
    stamp = f"{day.day:02d} {day:%b}"
    # Constructed rather than `datetime.combine(day, time(23, 59))`: importing
    # `time` from datetime here would shadow the stdlib module the rate limiter
    # needs, and that mistake costs an afternoon of 500s.
    end = datetime(day.year, day.month, day.day, 23, 59, tzinfo=timezone(timedelta(hours=3)))
    if end < now:
        return "closed", stamp, "gone"
    hours = (end - now).total_seconds() / 3600
    return "closes", stamp, "soon" if hours <= 72 else ""


def render_feed(
    conn: sqlite3.Connection,
    *,
    profile_id: str | None = None,
    now: datetime | None = None,
    demo: bool = False,
    limit: int = 40,
    since: datetime | None = None,
    headers: dict | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    profile = _profile_or_default(conn, profile_id)
    matches, acted = _ranked(conn, profile, now=now, limit=limit)
    saved = shortlist.saved_job_ids(conn, profile.id)
    momentum.check_in(conn, profile.id, now=now)
    state = momentum.status(conn, profile.id, now=now)
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
        lead = (
            f"<b>{new_count} new</b> since {when}"
            if new_count
            else f"<b>Nothing new</b> since {when}"
        )
        ledger = (
            f'<p class="ledger">{lead} · {summary["closing_within_7_days"]} closing this week · '
            f"checked {clock} EAT</p>"
        )

    name, _, tagline = profile.name.partition(" — ")
    subtitle = tagline.strip() or "the scope this feed was ranked against"

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
        else '<span class="chip">no pay floor</span>'
    )

    switcher = " ".join(
        f'<a class="{"on" if other.id == profile.id else ""}" href="/?profile={quote(other.id)}">{_e(other.name.split(" — ")[0])}</a>'
        for other in _profiles(conn)
    )

    feed_path = f"/?profile={quote(profile.id)}"

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
        if row.get("source_count", 1) > 1:
            badges.append(f'<span class="badge good">on {row["source_count"]} sources</span>')
        if row.get("status") == "stale":
            badges.append('<span class="badge warn">not re-checked recently</span>')
        else:
            badges.append('<span class="badge good">live</span>')
        if row.get("id") in acted:
            badges.append('<span class="badge">you applied</span>')
        if row.get("id") in saved:
            badges.append('<span class="badge good">saved</span>')

        # The deadline now lives in the corner; a reason that repeats it is noise.
        shown_reasons = [reason for reason in match.reasons if not reason.startswith("closes")]
        if not shown_reasons:
            shown_reasons = match.reasons[:1]
        reasons = "".join(f"<li>{_e(reason)}</li>" for reason in shown_reasons[:3])
        source = graph.primary_source(conn, match.job_id)
        label, stamp, tone = _deadline_view(row, now)

        apply_html = ""
        if source:
            apply_html = (
                f'<a class="apply" href="/go?profile={quote(profile.id)}&job={quote(match.job_id)}"'
                f' rel="nofollow noopener" target="_blank">Apply on {_e(source["source_id"])}</a>'
            )

        cards.append(
            f"""<article class="card">
  <div class="card-top">
    <div>
      <h2><a href="/job/{_e(match.job_id)}?profile={quote(profile.id)}">{_e(match.title)}</a></h2>
      <div class="employer">{_e(match.employer or "Employer not stated")}</div>
    </div>
    <div class="deadline {tone}"><span class="dl-label">{_e(label)}</span><span class="dl-date">{_e(stamp)}</span></div>
  </div>
  <div class="badges">{''.join(badges)}</div>
  <ul class="whythat">{reasons}</ul>
  <div class="foot">
    <span class="score" title="match score">{match.score:.2f}</span>
    <span>{_e(graph.freshness_band(row, now=now))}</span>
    <form method="post" action="/action">
      <input type="hidden" name="profile" value="{_e(profile.id)}">
      <input type="hidden" name="job" value="{_e(match.job_id)}">
      <input type="hidden" name="kind" value="{'unsaved' if match.job_id in saved else 'saved'}">
      <input type="hidden" name="next" value="{_e(feed_path)}">
      <button type="submit" class="{'on' if match.job_id in saved else ''}">
        {'Save' if match.job_id not in saved else 'Saved'}
      </button>
    </form>
    <form method="post" action="/action">
      <input type="hidden" name="profile" value="{_e(profile.id)}">
      <input type="hidden" name="job" value="{_e(match.job_id)}">
      <input type="hidden" name="kind" value="dismissed">
      <input type="hidden" name="next" value="{_e(feed_path)}">
      <button type="submit">Not for me</button>
    </form>
    {apply_html}
  </div>
</article>"""
        )

    if not cards:
        cards.append(
            '<div class="card"><h2>Nothing matches this scope right now</h2>'
            "<p>Loosen a constraint, or check back after the next sweep. We will not "
            "fill the space with jobs that do not fit.</p></div>"
        )

    soon = []
    for match in matches:
        row = match.row or {}
        if _deadline_view(row, now)[2] == "soon":
            soon.append(
                f'<div class="mini"><a href="/job/{_e(match.job_id)}?profile={quote(profile.id)}">'
                f"{_e(match.title)}</a>"
                f'<span class="when">{_e(_deadline_view(row, now)[1])}</span></div>'
            )
        if len(soon) == 3:
            break

    strip = f"""<div class="strip">
  <div><b>{len(matches)}</b><span>match this profile</span></div>
  <div><b>{summary['live_jobs']}</b><span>live jobs</span></div>
  <div><b>{summary['closing_within_7_days']}</b><span>closing in 7 days</span></div>
  <div><b>{len(acted)}</b><span>applied</span></div>
</div>"""

    body = f"""
<div class="masthead">
  <p class="kicker">Nairobi metro · early career</p>
  <h1 class="display">{_e(name)}</h1>
  <p class="scopeline">{_e(subtitle)}</p>
  <div class="filters">{switcher}</div>
  {ledger}
</div>
{strip}
<div class="layout">
  <div class="feedcol">
    <div class="section"><span>The feed</span><em>{len(matches)} roles</em></div>
    <p class="small"><a href="/search?profile={quote(profile.id)}">Search every live role →</a>
    — words, county, pay floor, deadline horizon.</p>
    {''.join(cards)}
    <p class="endnote">That's all of them. We will tell you when that changes.</p>
    {_wildcard_html(conn, profile, now=now)}
  </div>
  <aside class="rail">
    <div class="rail-card">
      <h3>Your scope</h3>
      <div class="chips">{limit_chip}{pay_chip}{chips}</div>
      <p class="rail-note">This is the argument for why the feed looks like this.</p>
    </div>
    <div class="rail-card">
      <h3>Closing this week</h3>
      {''.join(soon) or '<p class="rail-note">Nothing closes in the next seven days.</p>'}
    </div>
    <div class="rail-card">
      <h3>Momentum</h3>
      {_momentum_html(state)}
      <p class="rail-note">Weeks, not days. One missed week is forgiven, once.</p>
    </div>
    <div class="rail-card">
      <h3>Shortlist</h3>
      <p class="rail-note">{len(saved)} saved — kept for you, never sent to an employer.</p>
      <a class="more" href="/shortlist?profile={quote(profile.id)}">Open the shortlist →</a>
      <a class="more" href="/year?profile={quote(profile.id)}">Your year in the market →</a>
    </div>
  </aside>
</div>"""
    return _page(
        "Kazi-Kasi — jobs for you",
        body,
        demo=demo,
        nav=_nav_for(_account_for(conn, headers), profile.id),
        palette=palette_index(conn, profile, now=now),
    )


def render_shortlist(
    conn: sqlite3.Connection,
    *,
    profile_id: str | None = None,
    now: datetime | None = None,
    demo: bool = False,
    headers: dict | None = None,
) -> str:
    """Saved jobs, the comparison, and the one reminder a save earns.

    This page is the product's answer to "why would I come back?". The answer is
    not a notification stream: it is the thing the person already said they
    wanted, still open, with its deadline in view.
    """
    now = now or datetime.now(timezone.utc)
    profile = _profile_or_default(conn, profile_id)
    rows = shortlist.entries(conn, profile.id, now=now)
    path = f"/shortlist?profile={quote(profile.id)}"
    feed_path = f"/?profile={quote(profile.id)}"
    due = shortlist.reminders_due(conn, profile.id, now=now)

    reminder_block = ""
    if not due and rows:
        upcoming = next(
            (
                row
                for row in rows
                if (shortlist.deadline_at(row) and shortlist.deadline_at(row) > now)
            ),
            None,
        )
        if upcoming is not None:
            deadline = shortlist.deadline_at(upcoming)
            reminder_block = (
                f'<p class="small">No reminder due. Next: {_e(upcoming["title"])} closes '
                f"{deadline:%a %-d %b} — one message, {shortlist.REMINDER_HOURS} hours before.</p>"
            )
    if due:
        item = due[0]
        subscription = outbox.load_subscription(conn, profile.id)
        delivers = bool(subscription and subscription.active)
        if delivers:
            delivery_note = (
                f'Queued for your {_e(subscription.channel)} '
                f'({_e(subscription.msisdn)}) at the next daily tick — once per job, per deadline.'
            )
        else:
            delivery_note = (
                'No message is queued: closing alerts need a subscription. '
                f'<a href="/digest?profile={quote(profile.id)}">Turn on WhatsApp</a> '
                'and this text sends itself.'
            )
        reminder_block = f"""
<div class="whobar">
  <div><b>{len(due)} reminder{'s' if len(due) != 1 else ''} due now</b>
    <span class="small">— saved jobs closing within {shortlist.REMINDER_HOURS} hours.</span></div>
  <div class="msg">{_e(item['text'])}</div>
  <p class="small">{delivery_note}</p>
</div>"""

    if rows:
        cards = []
        for row in rows:
            deadline = shortlist.deadline_at(row)
            if deadline is None:
                when, tone = "no deadline stated", ""
            elif deadline < now:
                when, tone = f"closed {deadline:%a %-d %b}", "muted"
            else:
                when = f"closes {deadline:%a %-d %b}"
                tone = "warn" if deadline - now <= timedelta(hours=shortlist.REMINDER_HOURS) else ""
            source = graph.primary_source(conn, row["id"])
            apply_html = (
                f'<a class="apply" href="/go?profile={quote(profile.id)}&job={quote(row["id"])}"'
                ' rel="nofollow noopener" target="_blank">Apply</a>'
                if source
                else ""
            )
            cards.append(
                f"""<article class="card">
  <h2><a href="/job/{_e(row['id'])}?profile={quote(profile.id)}">{_e(row['title'])}</a></h2>
  <div class="employer">{_e(row.get('employer_name') or 'Employer not stated')}</div>
  <div class="badges">
    <span class="badge {tone}">{_e(when)}</span>
    <span class="badge muted">{_e(row.get('county') or 'Location unstated')}</span>
    <span class="badge">{_e((row.get('entry_fit') or 'unknown').replace('_', ' '))}</span>
    {'' if row.get('status') in ('open', 'stale') else '<span class="badge warn">not verified yet</span>'}
  </div>
  <div class="foot">
    {apply_html}
    <form method="post" action="/action">
      <input type="hidden" name="profile" value="{_e(profile.id)}">
      <input type="hidden" name="job" value="{_e(row['id'])}">
      <input type="hidden" name="kind" value="unsaved">
      <input type="hidden" name="next" value="{_e(path)}">
      <button type="submit">Remove</button>
    </form>
  </div>
</article>"""
            )

        compare = rows[:4]
        table = ""
        if len(compare) > 1:
            head = "".join(
                f'<th><a href="/job/{_e(row["id"])}?profile={quote(profile.id)}">'
                f"{_e(row['title'])}</a></th>"
                for row in compare
            )
            body_rows = "".join(
                f"<tr><td>{_e(label)}</td>"
                + "".join(f"<td>{_e(cell)}</td>" for cell in cells)
                + "</tr>"
                for label, cells in shortlist.compare_fields(compare)
            )
            note = (
                f'<p class="small">Comparing the {len(compare)} closing soonest.</p>'
                if len(rows) > 4
                else ""
            )
            table = f"""
<h2>Side by side</h2>
<div class="tablewrap"><table><tr><th></th>{head}</tr>{body_rows}</table></div>
{note}"""

        body = f"""
<h1>Shortlist</h1>
<p class="small">Jobs you saved, soonest deadline first. Nothing here is shared
with an employer, and a save is never sold as a lead.</p>
{reminder_block}
{''.join(cards)}
{''.join([table])}
<p class="small"><a href="{_e(feed_path)}">← back to the feed</a></p>"""
    else:
        body = f"""
<h1>Shortlist</h1>
<div class="card">
  <h2>Nothing saved yet</h2>
  <p>Save a job from the feed and it waits here with its deadline — and earns
  one reminder before it closes. That is the whole feature: your intent, kept for
  you, mentioned once.</p>
  <p><a class="apply" href="{_e(feed_path)}">Back to the feed</a></p>
</div>"""

    return _page(
        "Shortlist — Kazi-Kasi",
        body,
        demo=demo,
        nav=_nav_for(_account_for(conn, headers), profile.id),
    )



# --------------------------------------------------------------------------
# The public market pages
# --------------------------------------------------------------------------


def synthetic_build() -> bool:
    """Is the data on this instance synthetic?

    True until a real store — or a published bundle — is configured
    (`DATABASE_URL` / `KAZIKASI_BUNDLE`). Deliberately
    independent of `KAZIKASI_DEMO`, which governs session strictness: turning on
    real secret hygiene must never un-label synthetic vacancies, because the
    banner is the one thing standing between a demo corpus and a lie.
    """
    return not any(
        (os.environ.get(name) or "").strip() for name in ("DATABASE_URL", "KAZIKASI_BUNDLE")
    )


def _request_host(headers) -> str:
    """The Host the browser actually used, so the page can catch a base-URL mismatch."""
    for key, value in (headers or {}).items():
        if str(key).lower() == "host":
            return str(value)
    return ""


def _base_url() -> str:
    return (os.environ.get("KAZIKASI_BASE_URL") or "https://kazi-kasi-app.vercel.app").rstrip("/")


def _band_line(band: dict | None, *, prefix: str = "KES ") -> str:
    if not band:
        return "not stated in enough adverts"
    if band["p25"] == band["p75"]:
        return f"{prefix}{band['median']:,.0f}"
    return f"{prefix}{band['p25']:,.0f}–{band['p75']:,.0f}"


def _n(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"



# --------------------------------------------------------------------------
# ⌘K — one entry point, invisible until it is wanted
# --------------------------------------------------------------------------

PALETTE_JS = """
(function(){
  var dialog=document.getElementById('kazi-palette');
  if(!dialog) return;
  var input=document.getElementById('kazi-q'), list=document.getElementById('kazi-results'),
      raw=document.getElementById('kazi-index'), data=[], shown=[], active=0;
  try { data=JSON.parse(raw.textContent||'[]'); } catch(e) { data=[]; }

  function paint(){
    list.textContent='';
    if(!shown.length){
      var none=document.createElement('li'); none.className='none';
      none.textContent='Nothing matches that.'; list.appendChild(none); return;
    }
    shown.forEach(function(item, index){
      var li=document.createElement('li');
      if(index===active) li.className='on';
      var a=document.createElement('a'); a.href=item.href;
      var b=document.createElement('b'); b.textContent=item.label;
      var s=document.createElement('span'); s.textContent=item.meta||'';
      a.appendChild(b); a.appendChild(s); li.appendChild(a); list.appendChild(li);
    });
  }
  function filter(){
    var q=(input.value||'').toLowerCase().trim();
    shown=data.filter(function(item){
      if(!q) return true;
      return ((item.label+' '+(item.meta||''))||'').toLowerCase().indexOf(q)>-1;
    }).slice(0,8);
    active=0; paint();
  }
  function open(){
    if(!dialog.hidden) return;
    dialog.hidden=false; input.value=''; filter();
    setTimeout(function(){ input.focus(); },0);
  }
  function close(){ dialog.hidden=true; }
  function go(){
    if(shown[active]){ window.location.href=shown[active].href; return; }
    var q=(input.value||'').trim();
    if(q){ window.location.href='/search?q='+encodeURIComponent(q); }
  }

  document.addEventListener('keydown', function(event){
    var key=event.key;
    if((event.metaKey||event.ctrlKey) && key.toLowerCase()==='k'){
      event.preventDefault(); dialog.hidden?open():close(); return;
    }
    if(dialog.hidden) return;
    if(key==='Escape'){ close(); }
    else if(key==='ArrowDown'){ event.preventDefault(); active=Math.min(active+1, shown.length-1); paint(); }
    else if(key==='ArrowUp'){ event.preventDefault(); active=Math.max(active-1, 0); paint(); }
    else if(key==='Enter'){ event.preventDefault(); go(); }
  });
  Array.prototype.forEach.call(document.querySelectorAll('[data-cmdk]'), function(button){
    button.addEventListener('click', open);
  });
  dialog.addEventListener('click', function(event){ if(event.target===dialog) close(); });
  input.addEventListener('input', filter);
})();
"""


COPY_JS = """(function(){
  document.addEventListener('click', function(event){
    var target = event.target;
    var button = target && target.closest ? target.closest('[data-copy]') : null;
    if(!button) return;
    var value = button.getAttribute('data-copy') || '';
    var original = button.textContent;
    function say(word){ button.textContent = word; setTimeout(function(){ button.textContent = original; }, 1200); }
    if(navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(value).then(function(){ say('Copied'); }, function(){ say('Select it'); });
    } else {
      say('Select it');
    }
  });
})();"""

# --------------------------------------------------------------------------
# Response policy
# --------------------------------------------------------------------------

def _inline_hash(source: str) -> str:
    """sha256 of an inline block, in the form a CSP accepts.

    The style sheet and the one script are the only inline assets on the site.
    Hashing them means the policy can say `'none'` for everything else and still
    let the page work — which is the difference between a header that is present
    and a header that is doing something.
    """
    digest = hashlib.sha256(source.encode("utf-8")).digest()
    return "sha256-" + base64.b64encode(digest).decode("ascii")


ERROR_STYLE = """body{font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
background:#FBF8F2;color:#12161C;margin:0;padding:32px}
h1{font-size:24px;margin:0 0 8px}
.mut{color:#5C6675;margin:0 0 16px}
pre{background:#fff;border:1px solid #E3DCCF;border-radius:14px;padding:16px;
white-space:pre-wrap;font:13px/1.6 ui-monospace,Menlo,monospace}"""

STYLE_HASH = _inline_hash(STYLE)
SCRIPT_HASH = _inline_hash(PALETTE_JS)
COPY_HASH = _inline_hash(COPY_JS)
ERROR_STYLE_HASH = _inline_hash(ERROR_STYLE)


def security_headers(*, https: bool | None = None) -> dict[str, str]:
    """The whole policy for a response, in one place.

    Both transports (the stdlib server here, the serverless adapter on Vercel)
    call this, so a header cannot exist on one path and be missing on the other.
    `frame-ancestors 'none'` and `X-Frame-Options: DENY` say the same thing twice
    on purpose: the older header is what some scanners still read.
    """
    headers = {
        "Content-Security-Policy": "; ".join(
            [
                "default-src 'none'",
                f"style-src '{STYLE_HASH}' '{ERROR_STYLE_HASH}'",
                # The palette's index is a JSON data block, not a program; the
                # only executable inline script is PALETTE_JS.
                f"script-src '{SCRIPT_HASH}' '{COPY_HASH}'",
                "img-src 'self' data:",
                "font-src 'self'",
                "connect-src 'self'",
                "form-action 'self'",
                "base-uri 'none'",
                "frame-ancestors 'none'",
                "object-src 'none'",
            ]
        ),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
    }
    if https is None:
        https = _base_url().startswith("https://")
    if https:
        headers["Strict-Transport-Security"] = "max-age=15552000; includeSubDomains"
    return headers


def _palette_markup(index: list) -> str:
    """The dialog, its data and its script. Absent when there is nothing to jump to."""
    if not index:
        return ""
    payload = (
        json.dumps(index, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    return f"""
<div class="palette" id="kazi-palette" hidden>
  <div class="palette-box" role="dialog" aria-modal="true" aria-label="Jump to a job, county or page">
    <input id="kazi-q" type="search" placeholder="Jump to a job, county or page"
           aria-label="Search jobs, counties and pages" autocomplete="off" spellcheck="false">
    <ul id="kazi-results"></ul>
    <div class="hint">↑ ↓ to move · Enter to open · Esc to close</div>
  </div>
</div>
<script type="application/json" id="kazi-index">{payload}</script>
<script>{PALETTE_JS}</script>
"""


def palette_index(conn, profile, *, now: datetime) -> list:
    """Jobs, then counties, then pages — the order people look for things in."""
    index = []
    seen = set()
    for match in _ranked(conn, profile, now=now, limit=25)[0]:
        index.append(
            {
                "label": match.title,
                "meta": "job · " + (match.employer or "employer not stated"),
                "href": f"/job/{quote(match.job_id)}?profile={quote(profile.id)}",
            }
        )
        seen.add(match.job_id)
    hidden = tracking.dismissed_job_ids(conn, profile.id)
    for row in pulse.live_rows(conn):
        if row["id"] in seen or row["id"] in hidden:
            continue
        if len(index) >= 60:
            break
        index.append(
            {
                "label": row["title"],
                "meta": "job · " + (row.get("county") or "county not stated"),
                "href": f"/job/{quote(row['id'])}?profile={quote(profile.id)}",
            }
        )
    for item in pulse.overview(conn, now=now)["counties"]:
        index.append(
            {
                "label": item["county"],
                "meta": f"county · {item['live']} live",
                "href": f"/county/{pulse.slug(item['county'])}",
            }
        )
    index.append(
        {
            "label": "Search every live role",
            "meta": "page · words, county, pay, deadline",
            "href": f"/search?profile={quote(profile.id)}",
        }
    )
    for entry in dossier.index(conn, now=now, limit=8):
        index.append(
            {
                "label": entry["name"],
                "meta": f"employer · {entry['live']} live",
                "href": f"/employer/{quote(entry['slug'])}",
            }
        )
    index.extend(
        [
            {"label": "The feed", "meta": "page", "href": f"/?profile={quote(profile.id)}"},
            {"label": "Shortlist", "meta": "page", "href": f"/shortlist?profile={quote(profile.id)}"},
            {"label": "Weekly brief", "meta": "page", "href": f"/brief?profile={quote(profile.id)}"},
            {"label": "Market pulse", "meta": "page", "href": "/pulse"},
            {"label": "Advertised pay", "meta": "page", "href": "/salaries"},
            {"label": "Employers hiring now", "meta": "page", "href": "/employers"},
            {"label": "Your year", "meta": "page", "href": f"/year?profile={quote(profile.id)}"},
            {"label": "Your record", "meta": "page", "href": f"/activity?profile={quote(profile.id)}"},
            {"label": "WhatsApp digest", "meta": "page", "href": f"/digest?profile={quote(profile.id)}"},
        ]
    )
    return index


def _momentum_html(state: dict) -> str:
    marks = "".join(f'<i class="{"on" if on else ""}"></i>' for on in state["marks"])
    return (
        f'<div class="momentum"><span class="marks" aria-hidden="true">{marks}</span>'
        f'<span class="rail-note">{_e(momentum.line(state))}</span></div>'
    )


def _wildcard_html(conn, profile, *, now: datetime) -> str:
    """One exception a week, labelled as one."""
    item = wildcard.pick(conn, profile, now=now)
    if item is None:
        return ""
    href = f"/job/{quote(item['job_id'])}?profile={quote(profile.id)}"
    feed_path = f"/?profile={quote(profile.id)}"
    return f"""<article class="card wildcard">
  <p class="tagline">Outside your scope · this week only</p>
  <div class="card-top">
    <div>
      <h2><a href="{href}">{_e(item['title'])}</a></h2>
      <div class="employer">{_e(item['employer'] or 'Employer not stated')}</div>
    </div>
    <div class="deadline"><span class="dl-label">score</span>
      <span class="dl-date">{item['match'].score:.2f}</span></div>
  </div>
  <div class="badges"><span class="badge warn">{_e(item['blocker'])}</span>
    <span class="badge muted">{_e(item['row'].get('county') or 'location unstated')}</span></div>
  <ul class="whythat">{''.join(f'<li>{_e(reason)}</li>' for reason in item['match'].reasons[:2])}</ul>
  <div class="foot">
    <span class="small">{_e(wildcard.sentence(item, profile))}</span>
    <form method="post" action="/action">
      <input type="hidden" name="profile" value="{_e(profile.id)}">
      <input type="hidden" name="job" value="{_e(item['job_id'])}">
      <input type="hidden" name="kind" value="dismissed">
      <input type="hidden" name="next" value="{_e(feed_path)}">
      <button type="submit">Not for me</button>
    </form>
    <a class="apply" href="{href}">Look at it</a>
  </div>
</article>"""



# --------------------------------------------------------------------------
# Accounts, the CV, and the application kit
# --------------------------------------------------------------------------


def _account_for(conn, headers: dict | None) -> dict | None:
    account_id = accounts.read_session(headers)
    if not account_id:
        return None
    return accounts.account(conn, account_id)


def _first_name(account: dict | None) -> str:
    if not account:
        return ""
    name = (account.get("name") or "").strip()
    return name.split()[0].title() if name else ""


def _public_nav(conn, headers: dict | None) -> str:
    """The same nav for pages that are not tied to one saved scope."""
    return _nav_for(_account_for(conn, headers), _profile_or_default(conn, None).id)


def _nav_for(account: dict | None, profile_id: str) -> str:
    who = _first_name(account)
    if account:
        # Signed in — show name, links to /account
        label = who or "Account"
        account_link = f'<a href="/account">{_e(label)}</a>'
    else:
        # Not signed in — prominent "Sign in" button first, no guest label
        account_link = '<a href="/signin" class="nav-signin">Sign in</a>'
    return (
        account_link
        + '<a href="/?profile=' + quote(profile_id) + '">Feed</a>'
        + '<a href="/shortlist?profile=' + quote(profile_id) + '">Shortlist</a>'
        + '<a href="/brief?profile=' + quote(profile_id) + '">Brief</a>'
        + '<a href="/activity?profile=' + quote(profile_id) + '">Activity</a>'
        + '<a href="/pulse">Pulse</a>'
        + '<button type="button" class="cmdk" data-cmdk aria-haspopup="dialog">'
        + "Jump <kbd>⌘K</kbd></button>"
    )


def _notice(kind: str, message: str) -> str:
    if not message:
        return ""
    tone = {"good": "good", "warn": "warn", "bad": "danger"}.get(kind, "")
    return f'<div class="whobar"><span class="badge {tone}">{_e(message)}</span></div>'



# --------------------------------------------------------------------------
# Employers and the year
# --------------------------------------------------------------------------


def _pay_cell(pay: dict) -> str:
    if not pay.get("median"):
        return "never stated"
    return f"{pay['median']:,.0f}"


def _handle_saved_search(conn, path: str, body: bytes) -> Response:
    """Save or stop a search. A POST, because both change state."""
    form = parse_qs(body.decode("utf-8", errors="replace"))

    def field(name: str) -> str:
        return _query_one(form, name)

    profile_id = field("profile")
    back = f"/search?profile={quote(profile_id)}" if profile_id else "/search"
    if path == "/search/stop":
        if profile_id and field("id"):
            searches_module.stop(conn, profile_id, int(field("id")) if field("id").isdigit() else 0)
        return _redirect(back)

    result = searches_module.watch(
        conn,
        profile_id,
        q=field("q"),
        county=field("county"),
        family=field("family"),
        employment_type=field("type"),
        deadline_days=int(field("days")) if field("days").isdigit() else None,
        pay_floor=float(field("pay")) if field("pay").replace(".", "", 1).isdigit() else None,
        remote=field("remote") in ("1", "on", "true"),
    )
    if not result.get("saved"):
        return _redirect(f"/digest?profile={quote(profile_id)}")
    return _redirect(back + "#saved-searches")


def _handle_search(conn, query: dict, *, demo: bool, now: datetime, headers: dict | None) -> Response:
    """Query-string in, HTML out. Every filter is a plain GET parameter."""

    def one(key: str, default: str = "") -> str:
        return (_query_one(query, key) or default).strip()

    def number(key: str):
        raw = one(key).replace(",", "").replace("_", "")
        try:
            value = float(raw)
        except ValueError:
            return None
        return int(value) if value.is_integer() and key == "days" else value

    days = number("days")
    pay = number("pay")
    html = render_search(
        conn,
        profile_id=one("profile") or None,
        query=one("q"),
        county=one("county"),
        family=one("family"),
        employment_type=one("type"),
        deadline_days=int(days) if isinstance(days, int) and days >= 0 else None,
        pay_floor=pay if isinstance(pay, float) and pay > 0 else None,
        remote=one("remote") in ("1", "on", "true"),
        include_blocked=one("blocked") in ("1", "on", "true"),
        stop_request=one("stop"),
        now=now,
        demo=demo,
        headers=headers,
    )
    return Response(200, html, "text/html; charset=utf-8")


def render_employers(conn, *, now: datetime | None = None, demo: bool = False, headers: dict | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    rows = dossier.index(conn, now=now)
    live = sum(row["live"] for row in rows)
    paid = [row["median_pay"] for row in rows if row["median_pay"]]
    lines = []
    for row in rows:
        counties = ", ".join(row["counties"][:2]) or "county not stated"
        lines.append(
            f"""<tr>
  <td><a href="/employer/{_e(row['slug'])}">{_e(row['name'])}</a></td>
  <td>{row['live']}</td>
  <td>{f"{row['median_pay']:,.0f}" if row['median_pay'] else "never stated"}</td>
  <td class="small">{_e(counties)}</td>
</tr>"""
        )
    body = f"""
<div class="masthead">
  <p class="kicker">Employers · {len(rows)} hiring now</p>
  <h1 class="display">Who is actually hiring</h1>
  <p class="scopeline">Every employer with a live advert, and what their own
  adverts say about pay. Ranked by open roles, then alphabetically — never by
  anything an employer can buy.</p>
</div>
<div class="strip">
  <div><b>{len(rows)}</b><span>employers with live adverts</span></div>
  <div><b>{live}</b><span>open roles between them</span></div>
  <div><b>{f"{round(sum(paid) / len(paid)):,.0f}" if paid else "—"}</b><span>median of employer medians (n={len(paid)})</span></div>
</div>
<div class="tablewrap mt26"><table>
  <tr><th>Employer</th><th>Open now</th><th>Median advertised minimum (KES)</th><th>Where</th></tr>
  {''.join(lines)}
</table></div>
<p class="small">An employer page shows what we have seen them advertise, how often
they publish pay, and how long they leave an advert open. It is a record, not a
rating, and it is not for sale. <a href="/search">Search every live role →</a></p>"""
    return _page(
        "Employers hiring now — Kazi-Kasi",
        body,
        demo=demo,
        nav=_public_nav(conn, headers),
    )


def render_employer(
    conn,
    key: str,
    *,
    profile_id: str | None = None,
    now: datetime | None = None,
    demo: bool = False,
    headers: dict | None = None,
) -> str | None:
    now = now or datetime.now(timezone.utc)
    profile = _profile_or_default(conn, profile_id)
    data = dossier.report(conn, key, now=now)
    if data is None:
        return None

    pay, closing = data.pay, data.closing
    jobs = "".join(
        f"""<tr>
  <td><a href="/job/{_e(job['id'])}?profile={quote(profile.id)}">{_e(job['title'])}</a></td>
  <td>{_e(job['county'] or '—')}</td>
  <td>{_e(job['deadline'] or '—')}</td>
  <td>{f"KES {job['pay_min']:,.0f}" if job.get('pay_min') else 'not stated'}</td>
</tr>"""
        for job in data.jobs
    )
    families = "".join(
        f'<tr><td>{_e(family.replace("_", " "))}</td><td>{count}</td></tr>'
        for family, count in data.families
    )
    counties = "".join(f"<li>{_e(name)} · {count}</li>" for name, count in data.counties)
    checks = "".join(
        f'<tr><td>{_e(check["label"])}</td><td>{_e(check["value"])}</td>'
        f'<td class="small">{"" if check["ok"] else "worth a second look"}</td></tr>'
        for check in data.checks
    )
    merged = ""
    if len(data.variants) > 1:
        merged = (
            '<p class="small">This page merges the names '
            + _e(", ".join(data.variants))
            + ", because they normalise to the same employer. If that is wrong, "
            "tell us and it gets split.</p>"
        )
    cadence = (
        f"a new advert roughly every {data.cadence_days:g} days"
        if data.cadence_days
        else "too few adverts to see a rhythm"
    )

    body = f"""
<div class="masthead">
  <p class="kicker">Employer · last checked {(now + timedelta(hours=3)).strftime('%d %b, %H:%M')} EAT</p>
  <h1 class="display">{_e(data.name)}</h1>
  <p class="scopeline">{_e(dossier.line(data))}. Everything below is read from their
  own adverts, with the sample size attached.</p>
</div>
<div class="strip">
  <div><b>{data.live}</b><span>open now</span></div>
  <div><b>{data.total}</b><span>adverts we have seen</span></div>
  <div><b>{_pay_cell(pay)}</b><span>median advertised minimum (n={pay['stated']})</span></div>
  <div><b>{f"{closing['median_days']} days" if closing['median_days'] is not None else "—"}</b><span>median run to deadline (n={closing['n']})</span></div>
</div>
{merged}
<h2>Open roles</h2>
{
    f'<div class="tablewrap"><table><tr><th>Role</th><th>Where</th><th>Closes</th><th>Pay</th></tr>{jobs}</table></div>'
    if jobs
    else '<p>No live adverts from this employer right now. Their history is below.</p>'
}
<h2>What they advertise</h2>
<div class="two">
  <div class="tablewrap"><table><tr><th>Family</th><th>Adverts</th></tr>{families or '<tr><td>—</td><td>0</td></tr>'}</table></div>
  <div>
    <p class="small">Where these roles are:</p>
    <ul class="sources">{counties or '<li>county not stated</li>'}</ul>
    <p class="small">{_e(cadence)}.</p>
  </div>
</div>
<h2>What we can check</h2>
<div class="tablewrap"><table><tr><th>Check</th><th>Result</th><th></th></tr>{checks}</table></div>
<h2>What we cannot tell you</h2>
<p>Whether they reply, how many people applied, or what they offered anyone. We do
not have that data and will not estimate it. {"They never state pay, so the median above is a market figure only if it says so." if not pay["stated"] else f"Pay is stated in {pay['stated']} of {data.total} adverts."}</p>
<p class="small">This dossier is candidate-side and free. Employers cannot pay to
change it, and no ordering on Kazi-Kasi is for sale. If that ever changes it will
be labelled in the same type size as the job.</p>
<p class="small"><a href="/employers">← all employers hiring now</a></p>"""
    return _page(
        f"{data.name} — Kazi-Kasi",
        body,
        demo=demo,
        nav=_nav_for(_account_for(conn, headers), profile.id),
        head='<meta name="robots" content="noindex">' if False else "",
    )


def render_year(
    conn,
    *,
    profile_id: str | None = None,
    now: datetime | None = None,
    demo: bool = False,
    headers: dict | None = None,
    year: int | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    profile = _profile_or_default(conn, profile_id)
    data = recap.build(conn, profile, now=now, year=year)
    card = recap.card_lines(data)
    months = " ".join(
        f'<span class="chip">{_e(recap._month_name(int(month[5:7]))[:3])} {count}</span>'
        for month, count in data.months
    )
    almost = ""
    if data.almost:
        almost = f"""
<div class="card">
  <p class="tagline">{"Closed without an application" if data.almost["closed"] else "Still open — still unapplied"}</p>
  <h2><a href="/job/{_e(data.almost['job_id'])}?profile={quote(profile.id)}">{_e(data.almost['title'])}</a></h2>
  <p class="small">{_e(data.almost['employer'] or 'employer not stated')} · closes
  {_e(data.almost['deadline'] or 'no deadline stated')} ·
  {("you opened it " + str(data.almost["opened"]) + (" times" if data.almost["opened"] != 1 else " time")) if data.almost["opened"] else "you kept it and never sent anything"}</p>
</div>"""
    bands = ""
    if data.band_aimed or data.band_in_scope:
        bands = f"""
<h2>The band</h2>
<div class="two">
  <div class="rail-card flush">
    <p class="small">Band you kept choosing</p>
    <p class="fig">{f"{data.band_aimed:,.0f}" if data.band_aimed else "—"}</p>
    <p class="small">median advertised minimum across {data.band_aimed_n} role{'s' if data.band_aimed_n != 1 else ''} you kept or applied to</p>
  </div>
  <div class="rail-card flush">
    <p class="small">Band around you today</p>
    <p class="fig">{f"{data.band_in_scope:,.0f}" if data.band_in_scope else "—"}</p>
    <p class="small">median across {data.band_in_scope_n} role{'s' if data.band_in_scope_n != 1 else ''} inside your scope</p>
  </div>
</div>
<p class="small">Both are advertised minimums, in KES a month. We never learn what
anyone was offered, so this is not an outcome comparison — it is the range you
were looking at, next to the range that was looking at you.</p>"""
    share = ""
    if card:
        share = f"""
<h2>One card you can share</h2>
<pre id="yearcard" class="msg">{_e(chr(10).join(card))}</pre>
<p class="small">Counts, a month and a band. No employer you applied to is named on
it, and no outcome is claimed. <a href="/activity?profile={quote(profile.id)}">See the
whole record →</a></p>"""

    body = f"""
<div class="masthead">
  <p class="kicker">Your year · {data.year} · private</p>
  <h1 class="display">{_e(recap.headline(data))}</h1>
  <p class="scopeline">{_e(recap.note(data))}</p>
</div>
<div class="strip">
  <div><b>{data.seen}</b><span>roles you opened</span></div>
  <div><b>{data.saved}</b><span>kept</span></div>
  <div><b>{data.applied}</b><span>applied to</span></div>
  <div><b>{data.closed_while_saved}</b><span>closed while kept</span></div>
</div>
{f'<p class="small mt10">Months you were here: {months}</p>' if months else ''}
{almost}
{bands}
{share}
<h2>What this page will never say</h2>
<p>No rejection count, no interview rate, no score out of ten. We do not ask what
happened after you applied, so any number like that would be invented — and a year
review is the last place to invent a number about someone's life.</p>
<p class="small">This page is not linked from anywhere public, is not in the
sitemap and asks search engines to ignore it. <a href="/activity?profile={quote(profile.id)}">Your
record →</a></p>"""
    return _page(
        f"Your {data.year} in the market — Kazi-Kasi",
        body,
        demo=demo,
        nav=_nav_for(_account_for(conn, headers), profile.id),
        head='<meta name="robots" content="noindex">',
    )


def render_signin(conn, *, demo: bool = False, notice: str = "", tone: str = "warn") -> str:
    """Sign-in page: primary action first, explanation minimal.

    The user came here to sign in. Don't argue with them. Show the button,
    tell them what you'll store, get out of the way.
    """
    configured = {key: provider.configured for key, provider in accounts.PROVIDERS.items()}
    any_configured = any(configured.values())

    # Primary button: the first configured provider. On production this is
    # Google. Shown as the big green card — the one action the page wants.
    primary = None
    for key, provider in accounts.PROVIDERS.items():
        if configured[key]:
            primary = (key, provider)
            break

    # Secondary buttons: the other configured providers, smaller.
    secondaries = [
        (key, provider)
        for key, provider in accounts.PROVIDERS.items()
        if configured[key] and (primary is None or key != primary[0])
    ]

    # Unconfigured providers are not shown at all. Showing a disabled button
    # that says "Google is not configured" when Google IS configured would be
    # confusing, and showing one that says "Apple is not configured" when Apple
    # was never asked to be is just noise.
    unconfigured = [key for key, v in configured.items() if not v]
    unconfigured_note = ""
    if unconfigured and not any_configured:
        # Nothing is set. Show a small notice pointing at /setup.
        unconfigured_note = (
            '<p class="signin-notice">No sign-in provider is configured on this '
            'deployment. <a href="/setup">The go-live page</a> names each '
            'variable.</p>'
        )

    notice_html = _notice(tone, notice)

    primary_html = ""
    if primary:
        key, provider = primary
        primary_html = (
            f'<form method="post" action="/auth/start" class="signin-primary">'
            f'<input type="hidden" name="provider" value="{key}">'
            f'<button type="submit" class="signin-primary-btn">'
            f'<span class="signin-provider-name">Continue with {_e(provider.label)}</span>'
            f'<span class="signin-provider-why">{_e(accounts.WHY[key])}</span>'
            f"</button></form>"
        )

    secondary_html = ""
    if secondaries:
        buttons = []
        for key, provider in secondaries:
            buttons.append(
                f'<form method="post" action=\"/auth/start\" class="signin-secondary">'
                f'<input type="hidden" name="provider" value=\"{key}\">'
                f'<button type=\"submit\" class=\"signin-secondary-btn\">'
                f'Continue with {_e(provider.label)}</button></form>'
            )
        secondary_html = "".join(buttons)

    body = f"""
<div class=\"signin-wrap\">
  <div class=\"signin-card\">
    <p class=\"kicker\">Sign in</p>
    <h1 class=\"signin-headline\">One account, every job in Kenya.</h1>
    <p class=\"signin-sub\">Your shortlist follows you across devices, and the
    application kit fills employer forms from your CV — that's the whole deal.</p>
    {notice_html}
    {primary_html}
    {secondary_html}
    <form method=\"post\" action=\"/auth/guest\" class=\"signin-guest\">
      <input type=\"hidden\" name=\"next\" value=\"/account?guest=1\">
      <button type=\"submit\" class=\"signin-guest-btn\">Continue without an account</button>
    </form>
    {unconfigured_note}
    <p class=\"signin-privacy\">We store your name, your email, and the fields
    on your CV. We do not read your contacts or your connections, and deleting
    your account deletes everything in one click.</p>
  </div>
</div>"""
    return _page("Sign in — Kazi-Kasi", body, demo=demo)


def _cv_summary(cv: dict | None) -> str:
    if not cv:
        return ""
    fields = cv.get("fields") or {}
    rows = []
    labels = {
        "name": "Name", "email": "Email", "phone": "Phone", "location": "Location",
        "experience": "Experience", "education": "Education", "links": "Links",
        "skills": "Skills", "referees": "Referees",
    }
    for key, label in labels.items():
        field = fields.get(key) or {}
        value = field.get("value")
        if not value:
            continue
        if isinstance(value, list):
            value = ", ".join(value)
        rows.append(
            f"<tr><td>{_e(label)}</td><td>{_e(value)}</td>"
            f'<td class="small">{_e(field.get("evidence") or "")}</td></tr>'
        )
    if not rows:
        return '<p class="small">We could not find any of the usual fields in that text.</p>'
    return (
        "<table><tr><th>Field</th><th>Read as</th><th>From your CV</th></tr>"
        + "".join(rows)
        + "</table>"
    )


def render_account(
    conn,
    account: dict | None,
    *,
    profile,
    demo: bool = False,
    notice: str = "",
    tone: str = "good",
) -> str:
    cv = accounts.latest_cv(conn, account["id"]) if account else None
    suggestions = autofill.profile_suggestions(cv.get("fields", {})) if cv else {}
    gaps = autofill.missing(cv.get("fields", {})) if cv else ["Full name", "Email", "Phone number"]

    who = (account or {}).get("name") or ("Guest" if account else "Not signed in")
    kind = (account or {}).get("kind") or "none"
    provider = (account or {}).get("provider")
    provider_label = accounts.PROVIDERS[provider].label if provider in accounts.PROVIDERS else None

    identity = []
    if account is None:
        identity.append(
            '<p>You are browsing as a guest without a session. <a href="/signin">Sign in</a>'
            " to keep a shortlist across devices.</p>"
        )
    else:
        identity.append(
            f"<p><b>{_e(who)}</b> — "
            + ("a guest account" if kind == "guest" else f"signed in with {_e(provider_label or 'a provider')}")
            + (f", {_e(account.get('email'))}" if account.get("email") else "")
            + ".</p>"
        )
        if kind == "guest":
            identity.append(
                '<p class="small">A guest account lives in this browser. <a href="/signin">'
                "Sign in</a> and the shortlist and this CV move with you.</p>"
            )

    suggestion_html = ""
    if suggestions:
        bits = []
        if suggestions.get("home_county"):
            bits.append(f"county {_e(suggestions['home_county'])}")
        if suggestions.get("role_families"):
            bits.append("role families " + _e(", ".join(suggestions["role_families"])))
        if suggestions.get("entry_fits"):
            levels = ", ".join(suggestions["entry_fits"]).replace("_", " ")
            bits.append("entry level " + _e(levels))
        suggestion_html = (
            '<div class="whobar"><b>From your CV, we would suggest:</b> '
            + " · ".join(bits)
            + '. <span class="small">Suggestions only — nothing about your scope changed.</span></div>'
        )

    delete_form = ""
    if account:
        delete_form = (
            '<form method="post" action="/account/forget" class="inline-ml"'
            ' onsubmit="return confirm(&quot;Delete your account, CV and identity? This cannot be undone.&quot;)">'
            '<button type="submit" class="ghost">Delete everything</button></form>'
        )

    body = f"""
<div class="masthead">
  <p class="kicker">Account</p>
  <h1 class="display">You</h1>
  <p class="scopeline">What we hold, where it came from, and how to make applying
  take five minutes instead of forty.</p>
</div>
{_notice(tone, notice)}
<div class="layout">
  <div class="feedcol">
    <div class="section"><span>Identity</span></div>
    {''.join(identity) if account else '<p>Not signed in. <a href="/signin">Sign in</a> or continue as a guest.</p>'}

    <div class="section mt26"><span>Your CV</span>
      <em>{'read ' + _e(cv['created_at'][:10]) if cv else 'not uploaded'}</em></div>
    <p class="small">Paste the text of your CV, or upload a .txt, .md or .pdf file.
    We read it here, store the fields it states with the line each came from, and
    nothing else. It is never shown to an employer from our side.</p>
    <form method="post" action="/account/cv" enctype="multipart/form-data" class="subform stack">
      <input type="file" name="cv_file" accept=".txt,.md,.pdf" aria-label="CV file">
      <textarea name="cv_text" rows="7" placeholder="…or paste your CV text here"
        class="codebox"></textarea>
      <button type="submit">Read my CV</button>
    </form>
    {_cv_summary(cv)}
    {suggestion_html}
    <p class="small">Missing for forms: {_e(', '.join(gaps))}. A gap here is the
    document's gap, not yours — the kit will tell you what to type rather than make
    something up.</p>

    <div class="section mt26"><span>Your data</span></div>
    <form method="post" action="/auth/signout" class="inline">
      <button type="submit" class="ghost">Sign out</button>
    </form>
{delete_form}
    <p class="small">Deleting removes the CV outright, blanks your name and email, and
    keeps an anonymous tombstone so the same sign-in cannot silently recreate a
    profile behind your back.</p>
  </div>
  <aside class="rail">
    <div class="rail-card">
      <h3>Why a CV</h3>
      <p class="rail-note">So that the “fill this form” step stops being
      forty fields of retyping. It does not change your ranking, and no employer
      receives it.</p>
    </div>
    <div class="rail-card">
      <h3>Your scope</h3>
      <div class="chips">
        <span class="chip">{_e(profile.name.split(' — ')[0])}</span>
        <span class="chip">{_e(profile.home_area or profile.home_county or 'no home area')}</span>
        <span class="chip">{'≤ %g km' % profile.max_commute_km if profile.max_commute_km else 'no limit'}</span>
      </div>
      <a class="more" href="/?profile={quote(profile.id)}">Open the feed →</a>
    </div>
  </aside>
</div>"""
    return _page("You — Kazi-Kasi", body, demo=demo)


def render_activity(
    conn,
    *,
    profile,
    now: datetime | None = None,
    demo: bool = False,
    tab: str = "all",
    headers: dict | None = None,
) -> str:
    """Everything the person has done here: saved, applied, visited, dismissed."""
    now = now or datetime.now(timezone.utc)
    tabs = [("all", "Everything"), ("saved", "Saved"), ("applied", "Applied"), ("visited", "Visited")]
    counts = {key: 0 for key, _ in tabs}

    events = conn.execute(
        """SELECT e.*, j.title, j.employer_name, j.status, j.deadline
             FROM apply_events e JOIN jobs j ON j.id = e.job_id
            WHERE e.profile_id = ? AND e.kind IN ('saved','unsaved','clicked_through','applied','viewed','dismissed')
            ORDER BY e.at DESC LIMIT 400""",
        (profile.id,),
    ).fetchall()

    # One row per job, showing the furthest thing you did with it. A job you
    # saved, opened and applied to is one line, not three. "Unsaved" is a
    # transition, not a state: it clears the save and leaves the rest.
    # Oldest first, so the most recent save/unsave wins.
    per_job: dict[str, dict] = {}
    for event in reversed(events):
        state = per_job.setdefault(
            event["job_id"], {"row": dict(event), "saved": False, "applied": False,
                              "clicked": False, "dismissed": False}
        )
        state["row"] = dict(event) if event["at"] >= state["row"]["at"] else state["row"]
        if event["kind"] == "saved":
            state["saved"] = True
        elif event["kind"] == "unsaved":
            state["saved"] = False
        elif event["kind"] == "applied":
            state["applied"] = True
        elif event["kind"] == "clicked_through":
            state["clicked"] = True
        elif event["kind"] == "dismissed":
            state["dismissed"] = True

    rows = []
    for job_id, state in per_job.items():
        if state["applied"]:
            group, label = "applied", "you applied"
        elif state["clicked"]:
            group, label = "applied", "opened the application"
        elif state["saved"]:
            group, label = "saved", "on your shortlist"
        elif state["dismissed"]:
            group, label = "visited", "dismissed"
        elif state["row"]["kind"] == "viewed":
            group, label = "visited", "visited"
        else:
            continue
        row = state["row"]
        closed = (row.get("deadline") or "9999") < now.date().isoformat()
        if group == "visited" and label == "visited" and closed:
            label = "closed since"
        rows.append(dict(row, group=group, label=label, closed=closed))
        counts["all"] += 1
        counts[group] += 1
    rows.sort(key=lambda row: row["at"], reverse=True)
    if tab in ("saved", "applied", "visited"):
        rows = [row for row in rows if row["group"] == tab]

    def status(row) -> str:
        tone = {
            "you applied": "good",
            "on your shortlist": "good",
            "opened the application": "",
            "visited": "",
            "dismissed": "muted",
            "closed since": "warn",
        }[row["label"]]
        return f'<span class="badge {tone}">{_e(row["label"])}</span>'

    items = []
    for row in rows:
        when = row["at"][:16].replace("T", " ")
        items.append(
            '<tr>'
            f'<td><a href="/job/{_e(row["job_id"])}?profile={quote(profile.id)}">'
            f'{_e(row["title"])}</a><div class="small">{_e(row["employer_name"] or "")}</div></td>'
            f"<td>{status(row)}</td>"
            f'<td class="small">{_e(when)}</td>'
            f'<td class="small">{_e((row.get("deadline") or "—"))}</td>'
            "</tr>"
        )

    tabs_html = "".join(
        f'<a class="{"on" if tab == key else ""}" href="/activity?profile={quote(profile.id)}&tab={key}">'
        f"{_e(label)} <span class=\"count\">{counts[key]}</span></a>"
        for key, label in tabs
    )

    body = f"""
<div class="masthead">
  <p class="kicker">Activity · {counts['all']} jobs touched</p>
  <h1 class="display">Where you have been</h1>
  <p class="scopeline">Saved, applied, visited and dismissed — the same record that
  powers the ledger on your feed. Nothing here is shared with an employer.</p>
  <div class="filters">{tabs_html}</div>
</div>
<div class="layout">
  <div class="feedcol">
    <div class="section"><span>{_e(dict(tabs).get(tab, 'Everything'))}</span>
      <em>{len(rows)} items</em></div>
    {
        '<div class="tablewrap"><table><tr><th>Job</th><th>State</th><th>When</th><th>Closes</th></tr>'
        + "".join(items) + "</table></div>"
        if items
        else '<div class="card"><h2>Nothing here yet</h2><p>Open a role, save one, or tell us '
             'you applied, and it appears in this record.</p></div>'
    }
  </div>
  <aside class="rail">
    <div class="rail-card">
      <h3>Why keep this</h3>
      <p class="rail-note">A job hunt is thirty open tabs and a notebook. This is the
      notebook: what you looked at, what you kept, and what you already did.</p>
    </div>
    <div class="rail-card">
      <h3>Saved jobs close</h3>
      <p class="rail-note">Anything still open on your shortlist earns one reminder
      48 hours before its deadline.</p>
      <a class="more" href="/shortlist?profile={quote(profile.id)}">Open the shortlist →</a>
      <a class="more" href="/year?profile={quote(profile.id)}">Your year in the market →</a>
    </div>
  </aside>
</div>"""
    return _page(
        "Activity — Kazi-Kasi",
        body,
        demo=demo,
        nav=_nav_for(_account_for(conn, headers), profile.id),
    )


def _dossier_block(conn, row, payload: dict) -> str:
    row = dict(row)
    dossier = employer.read(
        payload.get("description_md"),
        source_id=(graph.primary_source(conn, row["id"]) or {}).get("source_id"),
        employer_domain=row.get("employer_domain"),
    )
    contacts = "".join(
        f'<li><b>{_e(contact.kind)}</b> · {_e(contact.value)}'
        f'<div class="small">“{_e(contact.evidence)}”</div></li>'
        for contact in dossier.contacts
    ) or '<li class="small">The advert names nobody and gives no contact.</li>'
    missing = "".join(f"<li>{_e(item)}</li>" for item in dossier.missing)
    opens = employer.opens(conn, row["id"])
    return f"""
<h1>Who you would be dealing with</h1>
<p>Apply {_e("by email" if dossier.channel == "email" else "through " + dossier.channel)}. That is what the advert says, not a
guess — applying the wrong way is a silent rejection.</p>
{f'<div class="evidence">{_e(dossier.instructions)}</div>' if dossier.instructions else ''}
<ul class="sources">{contacts}</ul>
{f'<p class="small">What the advert does not tell you:</p><ul class="sources">{missing}</ul>' if missing else ''}
<p class="small">Connects: we do not have your network and will not scrape one. If you
know someone at {_e(row.get('employer_name') or 'this employer')}, ask them for the
name on the advert — a referral beats a cover letter here.
{f'{opens} people opened this page here.' if opens else 'You are the first to open this page.'}</p>
"""


def _kit_block(account: dict | None, cv: dict | None, profile, row, payload: dict) -> str:
    row = dict(row)
    if not account:
        return """
<h1>Fill this form in five minutes</h1>
<p class="small">Sign in — or continue as a guest — and add your CV. We will prepare
every field the employer's form asks for, with your own words, ready to paste.</p>
<p><a class="apply" href="/signin">Set up the application kit</a></p>"""

    fields = (cv or {}).get("fields") or {}
    rows = autofill.kit(profile, fields, dict(row))
    note = autofill.cover_note(profile, fields, dict(row))
    missing = autofill.missing(fields)

    cells = []
    for item in rows:
        value = item["value"]
        if not value:
            cells.append(
                f'<tr><td>{_e(item["label"])}</td>'
                '<td class="small">type this one — your CV does not state it</td>'
                '<td class="small">—</td></tr>'
            )
            continue
        cells.append(
            f'<tr><td>{_e(item["label"])}</td><td>{_e(value)}</td>'
            f'<td class="small">{_e(item["source"])}</td></tr>'
        )

    return f"""
<h1>Fill this form in five minutes</h1>
<p class="small">Every value below comes from your CV or the advert. Copy them into
the employer's form; nothing is submitted from here, and no employer receives your
CV from us.</p>
<div class="tablewrap"><table><tr><th>Field</th><th>Your answer</th><th>Source</th></tr>
{''.join(cells)}</table></div>
{f'<p class="small">Still to type: {_e(", ".join(missing))}.</p>' if missing else ''}
<h2>Cover note, from your own words</h2>
<div class="msg">{_e(note)}</div>
<p class="small">Three sentences, built from the advert and your CV. Edit it — it is a
starting point, not a voice we are putting in your mouth.</p>"""


def render_brief(
    conn,
    *,
    profile_id: str | None = None,
    now: datetime | None = None,
    demo: bool = False,
    headers: dict | None = None,
) -> str:
    """The weekly brief as a page: the same numbers as the message, with the working."""
    now = now or datetime.now(timezone.utc)
    profile = _profile_or_default(conn, profile_id)
    data = brief_module.overview(conn, profile, now=now)
    state = data["momentum"]
    text_version = brief_module.message(data, profile)
    move = data["move"]
    feed_profile = quote(profile.id)

    if move:
        move_html = f"""<article class="card">
  <h2><a href="/job/{_e(move['job_id'])}?profile={feed_profile}">{_e(move['title'])}</a></h2>
  <div class="employer">{_e(move['employer'] or 'Employer not stated')}</div>
  <ul class="whythat"><li>{_e(move['reason'])}</li></ul>
  <div class="foot"><a class="apply" href="/job/{_e(move['job_id'])}?profile={feed_profile}">Open it</a></div>
</article>"""
    else:
        move_html = """<div class="card"><h2>No move this week</h2>
  <p>Nothing new cleared the bar. The honest thing is to wait for the next sweep
  rather than lower your standards.</p></div>"""

    families = " · ".join(
        f"{_e(name)} <span class='small'>{count}</span>" for name, count in data["families"]
    )
    band_text = brief_module.band_line(data)
    band_value = f"{data['band_this_week']:,}" if data["band_this_week"] else "—"
    delta_value = f"{data['delta_pct']:+d}%" if data["delta_pct"] is not None else "—"
    distance = "≤ %g km" % profile.max_commute_km if profile.max_commute_km else "no distance limit"
    pay = f"≥ KES {profile.min_monthly_pay:,.0f}" if profile.min_monthly_pay else "no pay floor"

    body = f"""
<div class="masthead">
  <p class="kicker">Weekly brief · week {data['week'].split('-W')[1]} · {data['days']}-day window</p>
  <h1 class="display">What moved</h1>
  <p class="scopeline">{_e(brief_module.headline(data, profile))}</p>
  <p class="ledger"><b>{data['in_scope']} in scope</b> · {data['new']} new ·
  {data['closing']} closing · updated {(now + timedelta(hours=3)).strftime('%a %H:%M')} EAT</p>
</div>
<div class="strip">
  <div><b>{data['new']}</b><span>new this week</span></div>
  <div><b>{data['closing']}</b><span>closing this week</span></div>
  <div><b>{band_value}</b><span>median advertised minimum</span></div>
  <div><b>{delta_value}</b><span>vs last week</span></div>
</div>
<div class="layout">
  <div class="feedcol">
    <div class="section"><span>The move</span><em>one per week, never two</em></div>
    {move_html}
    <div class="section mt28"><span>What the numbers mean</span></div>
    <p>{_e(band_text)}</p>
    <p class="small">Computed from live, unflagged adverts in your scope, first seen in the
    last {data['days']} days against the {data['days']} before. The sample size is printed
    because a median of three is a rumour with a decimal point.</p>
    <div class="section mt28"><span>Role families in scope</span></div>
    <p>{families or '<span class="small">none resolved yet</span>'}</p>
    <div class="section mt28"><span>Exactly what we would send</span></div>
    <div class="msg">{_e(text_version)}</div>
    <p class="small">The same brief goes out on WhatsApp once a week, and only when it has
    something to say.</p>
  </div>
  <aside class="rail">
    <div class="rail-card">
      <h3>Momentum</h3>
      {_momentum_html(state)}
      <p class="rail-note">Weeks, not days. Opening the brief counts; one missed week is
      forgiven, once.</p>
    </div>
    <div class="rail-card">
      <h3>Your scope</h3>
      <div class="chips">
        <span class="chip">{_e(profile.home_area or profile.home_county or 'no home area')}</span>
        <span class="chip">{_e(distance)}</span>
        <span class="chip">{_e(pay)}</span>
      </div>
    </div>
  </aside>
</div>"""
    return _page(
        "Weekly brief — Kazi-Kasi",
        body,
        demo=demo,
        palette=palette_index(conn, profile, now=now),
        nav=_nav_for(_account_for(conn, headers), profile.id),
    )


def render_pulse(conn, *, now: datetime | None = None, demo: bool = False, headers: dict | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    data = pulse.overview(conn, now=now)
    stamp = (now + timedelta(hours=3)).strftime("%H:%M")

    rows = "".join(
        f"""<tr>
  <td><a href="/county/{pulse.slug(item['county'])}">{_e(item['county'])}</a></td>
  <td>{item['live']}</td>
  <td>{item['closing']}</td>
  <td>{_e(_band_line(item['band'], prefix=''))}</td>
  <td>{item['band']['n'] if item['band'] else 0}</td>
</tr>"""
        for item in data["counties"]
    )

    employers = " · ".join(
        f"{_e(name)} <span class='small'>{count}</span>" for name, count in data["employers"]
    ) or '<span class="small">none yet</span>'

    sources = "".join(
        f"<tr><td>{_e(name)}</td><td>{count}</td></tr>" for name, count in data["sources"].items()
    )

    body = f"""
<div class="masthead">
  <p class="kicker">Market pulse · counted, not estimated</p>
  <h1 class="display">What Nairobi is hiring</h1>
  <p class="scopeline">Every number on this page comes from adverts we have checked
  ourselves. Nothing here is a forecast, a survey or an extrapolation.</p>
  <p class="ledger"><b>Updated {stamp} EAT</b> · window: last {data['window_days']} days</p>
</div>
<div class="strip">
  <div><b>{data['live']}</b><span>live adverts</span></div>
  <div><b>{data['new']}</b><span>new this week</span></div>
  <div><b>{data['closing']}</b><span>closing this week</span></div>
  <div><b>{f"{data['band']['median']:,.0f}" if data['band'] else "—"}</b><span>median advertised minimum (KES)</span></div>
</div>
<div class="layout">
  <div class="feedcol">
    <div class="section"><span>By county</span><em>{len(data['counties'])} counties</em></div>
    <div class="tablewrap"><table>
      <tr><th>County</th><th>Live</th><th>Closing</th><th>Middle half (KES/month)</th><th>n</th></tr>
      {rows}
    </table></div>
    <p class="rail-note">The middle half is the 25th–75th percentile of monthly minimums
    stated in adverts; <b>n</b> is how many adverts stated one. A band built from four
    adverts is four adverts, and it says so.</p>

    <div class="section mt32"><span>Employers hiring most</span></div>
    <p>{employers}</p>

    <div class="section mt32"><span>Sources</span><em>live adverts contributed</em></div>
    <div class="tablewrap"><table><tr><th>Source</th><th>Live adverts</th></tr>{sources}</table></div>
    <p class="small">Flagged adverts are excluded from every figure on this page. They stay
    in the corpus for the review queue, not for the statistic.</p>
  </div>
  <aside class="rail">
    <div class="rail-card">
      <h3>How to read this</h3>
      <p class="rail-note">“Live” means an advert we have checked and that has not passed
      its deadline. A job seen once is not live; it is unconfirmed.</p>
    </div>
    <div class="rail-card">
      <h3>Early career</h3>
      <p class="rail-note">{data['fresher_share'] if data['fresher_share'] is not None else 0}% of live
      adverts say they are open to people with no experience.</p>
    </div>
    <div class="rail-card">
      <h3>Your turn</h3>
      <p class="rail-note">A count is not a shortlist.</p>
      <a class="more" href="/">See what fits you →</a>
      <a class="more" href="/employers">Who is hiring now →</a>
    </div>
  </aside>
</div>"""
    return _page(
        "Market pulse — Kazi-Kasi",
        body,
        demo=demo,
        nav=_public_nav(conn, headers),
    )


def render_salaries(conn, *, now: datetime | None = None, demo: bool = False, headers: dict | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    data = pulse.overview(conn, now=now)
    rows = "".join(
        f"""<tr>
  <td><a href="/county/{pulse.slug(item['county'])}">{_e(item['county'])}</a></td>
  <td>{_e(_band_line(item['band'], prefix=''))}</td>
  <td>{item['band']['median']:,.0f}</td>
  <td>{item['band']['n']}</td>
  <td>{item['live']}</td>
</tr>"""
        for item in data["counties"]
        if item["band"]
    )
    body = f"""
<div class="masthead">
  <p class="kicker">Advertised pay</p>
  <h1 class="display">What the adverts actually say</h1>
  <p class="scopeline">Monthly minimums, as stated in live adverts. Not an estimate,
  not a survey, and never a number we filled in ourselves.</p>
  <p class="ledger"><b>{data['live']} live adverts</b> · {data['band']['n'] if data['band'] else 0}
  stated a monthly salary · updated {(now + timedelta(hours=3)).strftime('%d %b, %H:%M')} EAT</p>
</div>
<div class="layout">
  <div class="feedcol">
    <div class="tablewrap"><table>
      <tr><th>County</th><th>Middle half</th><th>Median</th><th>n</th><th>Live adverts</th></tr>
      {rows or '<tr><td colspan="5">Not enough adverts have stated a salary yet.</td></tr>'}
    </table></div>
    <p class="rail-note">An advert that does not state pay is not a data point. The gap
    is the advert's, not yours — and we would rather show four honest numbers than
    forty invented ones.</p>
    <h2>Why this page exists</h2>
    <p>Salary information in Kenya is scattered across adverts, rumours and
    recruiters. This is the smallest honest version of the answer: the middle half
    of what adverts stated, with the sample size attached, updated as the corpus
    changes.</p>
  </div>
  <aside class="rail">
    <div class="rail-card">
      <h3>Every figure</h3>
      <p class="rail-note">Computed from live, unflagged adverts only. Sample size on
      every row, because a median of three is a rumour with a decimal point.</p>
    </div>
  </aside>
</div>"""
    return _page(
        "Advertised pay — Kazi-Kasi",
        body,
        demo=demo,
        nav=_public_nav(conn, headers),
    )


def render_county(
    conn,
    key: str,
    *,
    now: datetime | None = None,
    demo: bool = False,
    headers: dict | None = None,
) -> str | None:
    """A county by slug ("nairobi") or by name ("Nairobi"). 404 when we have never seen it."""
    now = now or datetime.now(timezone.utc)
    data = pulse.county(conn, key, now=now) or pulse.by_slug(conn, key.lower(), now=now)
    if data is None:
        return None
    name = data["county"]

    def pay(row) -> str:
        low, high = row.get("pay_min"), row.get("pay_max")
        if low and high and low != high:
            return f"KES {low:,.0f}–{high:,.0f}"
        if low:
            return f"KES {low:,.0f}"
        return "not stated"

    rows = "".join(
        f"""<tr>
  <td><a href="/job/{_e(row['id'])}">{_e(row['title'])}</a></td>
  <td>{_e(row.get('employer_name') or 'not stated')}</td>
  <td>{_e(row.get('deadline') or '—')}</td>
  <td>{pay(row)}</td>
</tr>"""
        for row in data["jobs"]
    )
    body = f"""
<div class="masthead">
  <p class="kicker">County view</p>
  <h1 class="display">{_e(name)}</h1>
  <p class="scopeline">Live adverts in {_e(name)}, soonest deadline first.</p>
  <p class="ledger"><b>{data['live']} live</b> · {data['new']} new this week ·
  {data['closing']} closing this week · updated
  {(now + timedelta(hours=3)).strftime('%H:%M')} EAT</p>
</div>
<div class="strip">
  <div><b>{data['live']}</b><span>live adverts</span></div>
  <div><b>{data['new']}</b><span>new this week</span></div>
  <div><b>{data['closing']}</b><span>closing this week</span></div>
  <div><b>{f"{data['band']['median']:,.0f}" if data['band'] else "—"}</b><span>median advertised minimum (KES)</span></div>
</div>
<div class="tablewrap mt26"><table>
  <tr><th>Role</th><th>Employer</th><th>Closes</th><th>Pay</th></tr>
  {rows}
</table></div>
<p class="small">Pay is what the advert stated. “Not stated” is the advert's gap,
not a judgement about the job. <a href="/salaries">Advertised pay by county →</a> ·
<a href="/search?county={quote(name)}">Search within {_e(name)} →</a></p>"""
    return _page(
        f"{name} — jobs — Kazi-Kasi",
        body,
        demo=demo,
        nav=_public_nav(conn, headers),
    )


def _search_href(
    profile_id: str,
    *,
    query: str = "",
    county: str = "",
    family: str = "",
    employment_type: str = "",
    deadline_days: int | None = None,
    pay_floor: float | None = None,
    remote: bool = False,
    include_blocked: bool = False,
    **overrides,
) -> str:
    """A search URL that keeps every filter. Facet links must not reset the query."""
    values = {
        "profile": profile_id,
        "q": query,
        "county": county,
        "family": family,
        "type": employment_type,
        "days": deadline_days,
        "pay": int(pay_floor) if pay_floor else "",
        "remote": "1" if remote else "",
        "blocked": "1" if include_blocked else "",
    }
    values.update(overrides)
    pairs = [(key, value) for key, value in values.items() if value not in ("", None, 0, False)]
    return "/search" + ("?" + urlencode(pairs) if pairs else "")


def _pay_text(row) -> str:
    low, high = row.get("pay_min"), row.get("pay_max")
    if low and high and low != high:
        return f"KES {low:,.0f}–{high:,.0f}"
    if low:
        return f"KES {low:,.0f}"
    return "pay not stated"


def _search_card(item, profile, *, now: datetime, back: str) -> str:
    match, row = item.match, item.row
    place = row.get("sub_county") or row.get("county") or "location unstated"
    label, stamp, tone = _deadline_view(row, now)
    badges = [f'<span class="badge muted">{_e(place)}</span>']
    entry = ENTRY_FIT_LABEL.get(row.get("entry_fit"), "")
    if entry:
        badges.append(f'<span class="badge {ENTRY_FIT_TONE.get(row.get("entry_fit"), "muted")}">{_e(entry)}</span>')
    if row.get("work_mode") in ("remote", "hybrid"):
        badges.append(f'<span class="badge good">{_e(row["work_mode"].title())}</span>')
    if row.get("status") == "stale":
        badges.append('<span class="badge warn">not re-checked recently</span>')
    if item.applied:
        badges.append('<span class="badge">you applied</span>')
    if item.saved:
        badges.append('<span class="badge good">saved</span>')
    if item.blocked:
        badges.append('<span class="badge warn">outside your scope</span>')

    why = "".join(f"<li>{_e(reason)}</li>" for reason in (match.reasons or [])[:2])
    blockers = ""
    if item.blocked and match.blockers:
        blockers = (
            '<p class="small">Out of reach because: '
            + "; ".join(_e(blocker) for blocker in match.blockers)
            + ".</p>"
        )
    return f"""<article class="card">
  <div class="card-top">
    <div>
      <h2><a href="/job/{_e(match.job_id)}?profile={quote(profile.id)}">{_e(match.title)}</a></h2>
      <div class="employer">{_e(match.employer or "Employer not stated")}</div>
    </div>
    <div class="deadline {tone}"><span class="dl-label">{_e(label)}</span><span class="dl-date">{_e(stamp)}</span></div>
  </div>
  <div class="badges">{''.join(badges)}</div>
  {f'<ul class="whythat">{why}</ul>' if why else ''}
  {blockers}
  <div class="foot">
    <span>{_e(_pay_text(row))}</span>
    <span>{_e(graph.freshness_band(row, now=now))}</span>
    <form method="post" action="/action">
      <input type="hidden" name="profile" value="{_e(profile.id)}">
      <input type="hidden" name="job" value="{_e(match.job_id)}">
      <input type="hidden" name="kind" value="{'unsaved' if item.saved else 'saved'}">
      <input type="hidden" name="next" value="{_e(back)}">
      <button type="submit" class="{'on' if item.saved else ''}">{'Saved' if item.saved else 'Save'}</button>
    </form>
    <form method="post" action="/action">
      <input type="hidden" name="profile" value="{_e(profile.id)}">
      <input type="hidden" name="job" value="{_e(match.job_id)}">
      <input type="hidden" name="kind" value="dismissed">
      <input type="hidden" name="next" value="{_e(back)}">
      <button type="submit">Not for me</button>
    </form>
  </div>
</article>"""


def _watch_query(row: dict) -> str:
    """The query string that reproduces a saved search, without the profile."""
    pairs = [
        ("q", row.get("q") or ""),
        ("county", row.get("county") or ""),
        ("family", row.get("family") or ""),
        ("type", row.get("employment_type") or ""),
        ("days", row.get("deadline_days") or ""),
        ("pay", int(row["pay_floor"]) if row.get("pay_floor") else ""),
        ("remote", "1" if row.get("remote") else ""),
    ]
    query = urlencode([(key, value) for key, value in pairs if value not in ("", 0, None)])
    return f"&{query}" if query else ""


def _saved_search_html(
    conn,
    profile,
    *,
    query: str,
    county: str,
    family: str,
    employment_type: str,
    deadline_days: int | None,
    pay_floor: float | None,
    remote: bool,
    stop_request: str = "",
) -> str:
    """The "keep this search" form, the saved list, and the stop confirmation.

    Consent lives here on purpose: the form is only offered to someone with an
    active subscription, and without one the page explains the rule instead of
    collecting an address it cannot legally message.
    """
    subscription = outbox.load_subscription(conn, profile.id)
    watching = searches_module.for_profile(conn, profile.id)
    pid = quote(profile.id)
    blocks: list[str] = []

    stop_id = str(stop_request or "").strip()
    if stop_id:
        target = next((item for item in watching if str(item["id"]) == stop_id), None)
        if target is not None:
            blocks.append(
                '<div class="whobar"><div><b>Stop alerts for “'
                + _e(target["label"])
                + '”?</b> <span class="small">The search stays on this page; only the'
                " messages stop.</span></div>"
                '<form method="post" action="/search/stop">'
                f'<input type="hidden" name="profile" value="{_e(profile.id)}">'
                f'<input type="hidden" name="id" value="{target["id"]}">'
                "<button type=\"submit\">Stop alerts</button></form></div>"
            )

    if subscription is not None and subscription.active:
        channel = _e(subscription.channel)
        blocks.append(
            '<div class="whobar"><div><b>Keep this search</b> '
            f'<span class="small">— we send you a message when something new matches, at most '
            f"once a day, and only while your {channel} subscription is on.</span></div>"
            '<form method="post" action="/search/save">'
            f'<input type="hidden" name="profile" value="{_e(profile.id)}">'
            f'<input type="hidden" name="q" value="{_e(query)}">'
            f'<input type="hidden" name="county" value="{_e(county)}">'
            f'<input type="hidden" name="family" value="{_e(family)}">'
            f'<input type="hidden" name="type" value="{_e(employment_type)}">'
            f'<input type="hidden" name="days" value="{deadline_days or ""}">'
            f'<input type="hidden" name="pay" value="{int(pay_floor) if pay_floor else ""}">'
            f'<input type="hidden" name="remote" value="{"1" if remote else ""}">'
            '<button type="submit">Keep this search</button></form></div>'
        )
    elif query or county or family or employment_type or deadline_days or pay_floor or remote:
        blocks.append(
            '<div class="whobar"><div><b>Want this search to message you?</b> '
            '<span class="small">Saved searches send messages, so they need a subscription '
            "first — that is the consent rule, not a paywall.</span></div>"
            f'<a class="chip" href="/digest?profile={pid}">Turn on WhatsApp</a></div>'
        )

    if watching:
        items = []
        for item in watching:
            when = (
                f"last checked {item['last_run_at'][:10]}"
                if item.get("last_run_at")
                else "not run yet"
            )
            items.append(
                f'<li><a href="/search?profile={pid}{_watch_query(item)}">{_e(item["label"])}</a> '
                f'<span class="small">— {_e(item["cadence"])}, {_e(when)}</span> '
                '<form method="post" action="/search/stop" class="inline">'
                f'<input type="hidden" name="profile" value="{_e(profile.id)}">'
                f'<input type="hidden" name="id" value="{item["id"]}">'
                "<button type=\"submit\">Stop</button></form></li>"
            )
        blocks.append(
            f'<div class="section mt26"><span>Saved searches</span>'
            f"<em>{len(watching)}</em></div>"
            f'<ul class="whythat">{"".join(items)}</ul>'
        )

    return "\n".join(blocks)


def render_search(
    conn: sqlite3.Connection,
    *,
    profile_id: str | None = None,
    query: str = "",
    county: str = "",
    family: str = "",
    employment_type: str = "",
    deadline_days: int | None = None,
    pay_floor: float | None = None,
    remote: bool = False,
    include_blocked: bool = False,
    stop_request: str = "",
    now: datetime | None = None,
    demo: bool = False,
    headers: dict | None = None,
) -> str:
    """Every live role, narrowed by hand. Server-rendered; works without JS."""
    now = now or datetime.now(timezone.utc)
    profile = _profile_or_default(conn, profile_id)
    found = search_module.run(
        conn,
        profile,
        query=query,
        county=county,
        family=family,
        employment_type=employment_type,
        deadline_days=deadline_days,
        pay_floor=pay_floor,
        remote=remote,
        include_blocked=include_blocked,
        now=now,
    )

    def keep(**overrides) -> str:
        params = {
            "query": query,
            "county": county,
            "family": family,
            "employment_type": employment_type,
            "deadline_days": deadline_days,
            "pay_floor": pay_floor,
            "remote": remote,
            "include_blocked": include_blocked,
        }
        params.update(overrides)
        return _search_href(profile.id, **params)

    back = keep()
    county_options = "".join(
        f'<option value="{_e(name)}"{" selected" if county.lower() == name.lower() else ""}>'
        f"{_e(name)} ({count})</option>"
        for name, count in found.counties
    )
    family_options = "".join(
        f'<option value="{_e(name)}"{" selected" if family == name else ""}>'
        f"{_e(name)} ({count})</option>"
        for name, count in found.families
    )
    types = sorted(
        {item.row.get("employment_type") for item in found.matches if item.row.get("employment_type")}
    )
    type_options = "".join(
        f'<option value="{_e(kind)}"{" selected" if employment_type == kind else ""}>'
        f"{_e(kind.replace('_', ' ').title())}</option>"
        for kind in types
    )

    chips = []
    for name, count, label, key in (
        *[(name, count, name, "county") for name, count in found.counties[:6]],
        *[(name, count, name, "family") for name, count in found.families[:6]],
    ):
        active = county.lower() == name.lower() if key == "county" else family == name
        if active:
            chips.append(
                f'<a class="chip on" href="{_e(keep(**{key: ""}))}">{_e(label)} ×</a>'
            )
        else:
            chips.append(
                f'<a class="chip" href="{_e(keep(**{key: name}))}">{_e(label)} '
                f'<span class="num">{count}</span></a>'
            )
    if remote:
        chips.append(f'<a class="chip on" href="{_e(keep(remote=False))}">remote or hybrid ×</a>')
    if deadline_days:
        chips.append(
            f'<a class="chip on" href="{_e(keep(deadline_days=None))}">'
            f"closes within {deadline_days} days ×</a>"
        )
    if pay_floor:
        chips.append(
            f'<a class="chip on" href="{_e(keep(pay_floor=None))}">≥ KES {pay_floor:,.0f} ×</a>'
        )
    if found.is_filtered:
        chips.append(f'<a class="chip" href="/search?profile={quote(profile.id)}">clear all</a>')

    saved_html = _saved_search_html(
        conn,
        profile,
        query=query,
        county=county,
        family=family,
        employment_type=employment_type,
        deadline_days=deadline_days,
        pay_floor=pay_floor,
        remote=remote,
        stop_request=stop_request,
    )
    watched_html = ""

    cards = "".join(_search_card(item, profile, now=now, back=back) for item in found.matches)

    if found.is_empty:
        suggestions = []
        for name, count in found.counties[:3]:
            suggestions.append(
                f'<a href="{_e(keep(county=name, query=""))}">every live role in {_e(name)} ({count})</a>'
            )
        for name, count in found.families[:3]:
            suggestions.append(
                f'<a href="{_e(keep(family=name, query=""))}">{_e(name)} roles ({count})</a>'
            )
        if deadline_days:
            suggestions.append(
                f'<a href="{_e(keep(deadline_days=None))}">drop the {deadline_days}-day horizon</a>'
            )
        if pay_floor:
            suggestions.append(f'<a href="{_e(keep(pay_floor=None))}">drop the pay floor</a>')
        cards = f"""<div class="card">
  <h2>Nothing matches that</h2>
  <p>Every word has to appear, and every filter has to hold. This corpus is small
  enough that a narrow search is often empty — that is a fact about the market,
  not a reason to fill the page with roles that do not fit.</p>
  <ul class="whythat">{''.join(f'<li>{item}</li>' for item in suggestions)}</ul>
</div>"""

    blocked_html = ""
    if include_blocked and found.blocked:
        blocked_cards = "".join(
            _search_card(item, profile, now=now, back=back) for item in found.blocked
        )
        blocked_html = f"""
<div class="section"><span>Outside your constraints</span><em>{len(found.blocked)} roles</em></div>
<p class="small">These advertised roles fail something in your profile — the years asked
for, the distance, or the pay floor. They are here because seeing the edge of the market
is useful; they are never mixed into the feed.</p>
{blocked_cards}"""

    toggle = keep(include_blocked=not include_blocked)
    toggle_label = (
        "Hide roles outside my constraints"
        if include_blocked
        else f"Show {found.blocked_count} role{'s' if found.blocked_count != 1 else ''} "
        "outside my constraints"
    )

    unstated_note = (
        f'<p class="small">{found.pay_unstated} of these do not state pay, so the floor '
        "cannot include or exclude them. They are shown, labelled.</p>"
        if found.pay_unstated
        else ""
    )

    body = f"""
<div class="masthead">
  <p class="kicker">Search · {_e(profile.name.split(' — ')[0])}</p>
  <h1 class="display">Find the role you meant</h1>
  <p class="scopeline">Every live advert in the graph, narrowed by your words and your
  filters — ranked by the same scorer as the feed.</p>
  <form method="get" action="/search" class="searchform">
    <input type="hidden" name="profile" value="{_e(profile.id)}">
    <label>Words <input type="search" name="q" value="{_e(query)}"
      placeholder="software nairobi" autocomplete="off"></label>
    <label>County <select name="county"><option value="">any</option>{county_options}</select></label>
    <label>Family <select name="family"><option value="">any</option>{family_options}</select></label>
    <label>Type <select name="type"><option value="">any</option>{type_options}</select></label>
    <label>Closes in <input type="number" name="days" min="0" max="365" step="1"
      value="{deadline_days if deadline_days else ''}" placeholder="any"></label>
    <label>Pay at least <input type="number" name="pay" min="0" step="1000"
      value="{int(pay_floor) if pay_floor else ''}" placeholder="any"></label>
    <label class="check"><input type="checkbox" name="remote" value="1"
      {'checked' if remote else ''}> remote or hybrid</label>
    <label class="check"><input type="checkbox" name="blocked" value="1"
      {'checked' if include_blocked else ''}> include roles outside my scope</label>
    <button type="submit">Search</button>
  </form>
  <div class="filters">{''.join(chips)}</div>
  <p class="ledger"><b>{found.narrowed}</b> of {found.considered} live roles match ·
    {len(found.matches)} in your scope · {found.blocked_count} outside it
    · checked {(now + timedelta(hours=3)).strftime('%H:%M')} EAT</p>
</div>
{unstated_note}
{saved_html}
{cards}
<div class="filters mt18">
  <a class="chip" href="{_e(toggle)}">{_e(toggle_label)}</a>
  <a class="chip" href="/?profile={quote(profile.id)}">Back to the feed</a>
  <a class="chip" href="/employers">Employers hiring now</a>
</div>
{blocked_html}
{watched_html}"""
    return _page(
        f"Search — Kazi-Kasi",
        body,
        demo=demo,
        nav=_nav_for(_account_for(conn, headers), profile.id),
        head='<meta name="robots" content="noindex">',
        palette=palette_index(conn, profile, now=now),
    )




def _setup_step_html(step, *, number: int | None = None) -> str:
    """One step. A **done** step never shows instructions.

    That distinction is the whole page. An earlier version rendered the "here is
    how you set this variable" note on completed steps too — so the first card on
    the page told you to set something you had already set, and read like step one
    of a to-do list. A checklist that keeps instructing you after you are finished
    is a checklist you stop trusting.
    """
    tone = setup_module.STATE_TONE.get(step.state, "muted")
    label = setup_module.STATE_LABEL.get(step.state, step.state)
    badge = f'<span class="badge {tone}">{_e(label)}</span>'

    if step.state == "done":
        names = ", ".join(step.env) if step.env else "no variables"
        return f"""<article class="card step done">
  <div class="card-top">
    <div><h2>{_e(step.title)}</h2>
      <div class="small mono">{_e(step.detail or names)} · nothing to do</div></div>
    <div class="deadline">{badge}</div>
  </div>
</article>"""

    head = f'<span class="kicker stepnum">{number}.</span> ' if number is not None else ""
    rows = []
    if step.env:
        rows.append(
            '<div class="small">Variables: '
            + " ".join(f'<code class="key">{_e(name)}</code>' for name in step.env)
            + "</div>"
        )
    for item in step.paste:
        rows.append(
            '<div class="paste"><span class="small">' + _e(item.label) + "</span>"
            f'<input readonly value="{_e(item.value)}" aria-label="{_e(item.label)}">'
            f'<button type="button" class="copy" data-copy="{_e(item.value)}">Copy</button></div>'
        )
    if step.detail:
        rows.append(f'<p class="small mono">{_e(step.detail)}</p>')
    if step.link:
        rows.append(f'<p class="small"><a href="{_e(step.link[1])}">{_e(step.link[0])} →</a></p>')
    if step.note:
        rows.append(f'<p class="small">{_e(step.note)}</p>')
    return f"""<article class="card step">
  <div class="card-top">
    <div><h2>{head}{_e(step.title)}</h2>
      <div class="employer">{_e(step.why)}</div></div>
    <div class="deadline">{badge}</div>
  </div>
  {''.join(rows)}
</article>"""


def render_setup(
    conn,
    *,
    now: datetime | None = None,
    demo: bool = False,
    headers: dict | None = None,
) -> str:
    """The go-live page: derived from this process, never from a to-do list."""
    now = now or datetime.now(timezone.utc)
    plan = setup_module.plan(
        conn,
        now=now,
        synthetic=synthetic_build(),
        strict=accounts.strict_mode(),
        base_url=_base_url(),
        host=_request_host(headers),
    )
    instance = plan.instance
    tick = instance["tick"]
    corpus_tone = "good" if instance["corpus"]["source"] == "bundle" else "warn"

    # Grouped by what to do about it, not by an internal id order. A flat numbered
    # list mixes "already finished" with "do this next" and reads like a to-do list
    # that never shrinks — which is precisely how the previous version was misread.
    todo = [step for step in plan.steps if step.state == "missing"]
    optional = [step for step in plan.steps if step.state == "optional"]
    deferred = [step for step in plan.steps if step.state == "deferred"]
    done = [step for step in plan.steps if step.state == "done"]

    def section(title: str, meta: str, html: str) -> str:
        if not html:
            return ""
        return f'<div class="section mt26"><span>{title}</span><em>{meta}</em></div>{html}'

    if todo:
        todo_html = section(
            "Do these, in this order",
            f"{len(todo)} to go",
            "".join(_setup_step_html(step, number=index) for index, step in enumerate(todo, 1)),
        )
    else:
        todo_html = (
            '<div class="whobar"><div><b>Nothing required is missing.</b> '
            '<span class="small">Sign-in, sessions and storage are all configured — '
            "whichever optional steps you take from here are improvements, not repairs.</span></div></div>"
        )
    optional_html = section(
        "Optional, when you want a second channel",
        f"{len(optional)}",
        "".join(_setup_step_html(step) for step in optional),
    )
    deferred_html = section(
        "Deliberately not yet",
        f"{len(deferred)}",
        "".join(_setup_step_html(step) for step in deferred),
    )
    done_html = section(
        "Already done — nothing to do here",
        f"{len(done)}",
        "".join(_setup_step_html(step) for step in done),
    )
    cards = todo_html + optional_html + deferred_html + done_html
    trouble = "".join(
        f"""<li><b>{_e(item['symptom'])}</b>
      <span class="small">{_e(item['cause'])}</span>
      <span class="small"><b>Fix:</b> {_e(item['fix'])}</span></li>"""
        for item in plan.troubleshooting
    )
    next_line = (
        "Nothing required is missing. Jump to what is left →"
        if not todo
        else "Next: "
        + todo[0].title
        + (
            " — one step."
            if len(todo) == 1
            else f", then {len(todo) - 1} more."
        )
    )
    host_warning = (
        ""
        if instance["host_matches"]
        else f"""<div class="whobar"><div><b>You are on {_e(instance['served_host'])}, but this build thinks it lives at
  {_e(instance['base_url'])}.</b>
  <span class="small">Every redirect URI below is wrong for the address you are using. Sign-in will
  bounce back with a state-mismatch error. Fix <code class="key">KAZIKASI_BASE_URL</code> in Vercel and
  redeploy — or open the site at the address it names.</span></div></div>"""
    )
    required_done = sum(1 for item in plan.required if item.state == "done")
    optional_open = sum(1 for item in plan.steps if item.state in ("optional", "deferred"))

    body = f"""
<div class="masthead">
  <p class="kicker">Go-live · this deployment</p>
  <h1 class="display">What is left, and what to paste</h1>
  <p class="scopeline">{_e(next_line)}</p>
  <p class="ledger"><b>{required_done} of {len(plan.required)}</b> required steps done ·
    {optional_open} optional · build {_e(instance['build'])} ·
    schema {instance['schema']} · checked {(now + timedelta(hours=3)).strftime('%H:%M')} EAT</p>
</div>
<div class="strip">
  <div><b>{instance['live_jobs']}</b><span>live roles</span></div>
  <div><b>{instance['sources']}</b><span>sources</span></div>
  <div><b>{'synthetic' if instance['synthetic'] else 'real'}</b><span>corpus</span></div>
  <div><b>{'yes' if tick['runs'] else 'no'}</b><span>tick would send</span></div>
</div>
{host_warning}<div class="whobar">
  <div><b>The scheduled tick, right now:</b>
    <span class="small">{_e(tick['answer'])}{(' — needs ' + _e(tick['needs'])) if tick['needs'] else ''}</span></div>
  <div><span class="badge {corpus_tone}">{_e(instance['corpus']['source'])}</span></div>
</div>
{cards}
<div class="section mt26"><span>How to test sign-in</span><em>in this order, two minutes</em></div>
<ol class="whythat trial">
  <li><b>Click Continue with Google</b> on <a href="/signin">the sign-in page</a>.
    <span class="small">If the page says the provider is not connected, the variables are not in
    <em>this</em> build — redeploy first.</span></li>
  <li><b>You should land on Google's account chooser.</b>
    <span class="small">That alone proves the client id is valid and the redirect URI is registered.</span></li>
  <li><b>Pick your account, then look at where you land.</b>
    <span class="small">A page showing your name and email means sign-in works end to end. Your
    address appearing at the top right is the same evidence.</span></li>
  <li><b>If Google says <code class="key">redirect_uri_mismatch</code></b>
    <span class="small">the URI in the Google client differs from the one above by a character —
    usually a trailing slash, http vs https, or www.</span></li>
  <li><b>If Google says <code class="key">invalid_client</code></b>
    <span class="small">the secret is wrong or has a stray newline from the paste. Re-paste it.</span></li>
  <li><b>If you bounce back here with a state error</b>
    <span class="small">the base URL does not match the domain you are on — see the warning above,
    if there is one.</span></li>
</ol>
<div class="section mt26"><span>When a console fights you</span><em>the four that cost hours</em></div>
<ul class="whythat trouble">{trouble}</ul>
<p class="small">Nothing on this page is a secret: it renders booleans and public URLs.
The values themselves live in Vercel and are never read back out.</p>"""
    return _page(
        "Go live — Kazi-Kasi",
        body + f"<script>{COPY_JS}</script>",
        demo=demo,
        nav=_public_nav(conn, headers),
        head='<meta name="robots" content="noindex">',
    )


def render_sitemap(conn, *, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    base = _base_url()
    entries = [
        (f"{base}/", now),
        (f"{base}/pulse", now),
        (f"{base}/salaries", now),
    ]
    for item in dossier.index(conn, now=now):
        entries.append((f"{base}/employer/{item['slug']}", now))
    for item in pulse.overview(conn, now=now)["counties"]:
        entries.append((f"{base}/county/{pulse.slug(item['county'])}", now))
    for row in pulse.live_rows(conn):
        stamp = pulse._as_dt(row.get("last_seen_at")) or now
        entries.append((f"{base}/job/{row['id']}", stamp))

    urls = "".join(
        f"<url><loc>{_e(loc)}</loc><lastmod>{stamp.strftime('%Y-%m-%d')}</lastmod></url>"
        for loc, stamp in entries
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}</urlset>"
    )


def render_robots() -> str:
    base = _base_url()
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /slo",
            "Disallow: /review",
            "Disallow: /digest",
            "Disallow: /action",
            "Disallow: /search",
            "Disallow: /setup",
            "Disallow: /webhooks/",
            "Disallow: /api/",
            "",
            f"Sitemap: {base}/sitemap.xml",
            "",
        ]
    )


def _application_state(conn, profile_id: str, job_id: str) -> dict:
    """What has this person already told us about this job?"""
    rows = conn.execute(
        """SELECT kind FROM apply_events
            WHERE profile_id = ? AND job_id = ? AND kind IN ('saved','unsaved','applied')
            ORDER BY at, id""",
        (profile_id, job_id),
    ).fetchall()
    saved = applied = False
    for row in rows:
        if row["kind"] == "saved":
            saved = True
        elif row["kind"] == "unsaved":
            saved = False
        elif row["kind"] == "applied":
            applied = True
    return {"saved": saved, "applied": applied}


def render_job(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    profile_id: str | None = None,
    now: datetime | None = None,
    demo: bool = False,
    headers: dict | None = None,
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
    account = _account_for(conn, headers)
    cv = accounts.latest_cv(conn, account["id"]) if account else None
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

    state = _application_state(conn, profile.id, job_id)
    actions = [
        '<form method="post" action="/action" class="inline">'
        f'<input type="hidden" name="profile" value="{_e(profile.id)}">'
        f'<input type="hidden" name="job" value="{_e(job_id)}">'
        '<input type="hidden" name="kind" value="'
        + ("unsaved" if state["saved"] else "saved")
        + f'"><input type="hidden" name="next" value="/job/{_e(job_id)}?profile={quote(profile.id)}">'
        f'<button type="submit" class="ghost">{"Saved ✓ — remove" if state["saved"] else "Save for later"}</button>'
        "</form>",
        '<form method="post" action="/action" class="inline-ml">'
        f'<input type="hidden" name="profile" value="{_e(profile.id)}">'
        f'<input type="hidden" name="job" value="{_e(job_id)}">'
        f'<input type="hidden" name="kind" value="{"unsaved" if state["applied"] else "applied"}">'
        f'<input type="hidden" name="next" value="/job/{_e(job_id)}?profile={quote(profile.id)}">'
        '<button type="submit" class="ghost">'
        + ("Applied ✓ — undo" if state["applied"] else "I applied to this")
        + "</button></form>",
    ]
    apply_html = ""
    if source:
        apply_html = (
            f'<p><a class="apply" href="/go?profile={quote(profile.id)}&job={quote(job_id)}"'
            f' rel="nofollow noopener" target="_blank">Apply on {_e(source["source_id"])}</a> '
            + "".join(actions)
            + '</p><p class="small">Applying happens on the employer’s site. '
            "“I applied” is your note to yourself — it is what the tracker counts, "
            "and no employer is told.</p>"
        )

    body = f"""
<p class="small"><a href="/?profile={quote(profile.id)}">← back to the feed</a></p>
<h1>{_e(row['title'])}</h1>
<div class="employer">{_e(row['employer_name'] or 'Employer not stated')}</div>
<div class="badges">{warning}</div>
{apply_html}
<dl>{''.join(f'<dt>{_e(label)}</dt><dd>{_e(value)}</dd>' for label, value in facts)}</dl>
{f'<p class="small"><a href="/employer/{_e(dossier.slug(row["employer_name"]))}">Everything {_e(row["employer_name"])} has advertised →</a></p>' if row["employer_name"] else ''}
{why_block}
{f'<div class="evidence">“{_e(evidence)}”</div>' if evidence else ''}
{f'<h1>About the role</h1><p>{_e(description[:1200])}</p>' if description else ''}
{_dossier_block(conn, row, payload)}
{_kit_block(account, cv, profile, row, payload)}
<h1>Where this came from</h1>
<ul class="sources">{source_items}</ul>
<h1>History</h1>
<ul class="sources">{event_items}</ul>
<p class="small">Eligibility is read from the advert text, not inferred from the title.
Distance is straight-line between approximate area centres, not a route.</p>
"""
    return _page(
        f"{row['title']} — Kazi-Kasi",
        body,
        demo=demo,
        head=structured,
        nav=_nav_for(account, profile.id),
    )


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
#: Search ranks every live row per request; it is the most expensive page here.
SEARCH_RATE_LIMIT = 60
#: A person saving and dismissing quickly is normal; a loop is not.
ACTION_RATE_LIMIT = 120


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


def _spread_first_seen(conn, now: datetime) -> None:
    """Make the demo corpus look accumulated rather than conjured.

    On a serverless cold start every advert is created in the same second, which
    makes "new this week" mean "everything" and the ledger meaningless. The spread
    is derived from the job id, so it is stable across restarts.
    """
    for row in conn.execute("SELECT id FROM jobs").fetchall():
        days = int(hashlib.sha256(row["id"].encode()).hexdigest()[:4], 16) % 14
        stamp = (now - timedelta(days=days, hours=days)).replace(microsecond=0)
        conn.execute("UPDATE jobs SET first_seen_at = ? WHERE id = ?", (stamp.isoformat(), row["id"]))
    conn.commit()


def _seed_demo_history(conn, now: datetime) -> None:
    """Give the demo build a past.

    `/activity` and `/year` are only meaningful with history, and a demo link that
    opens on "nothing here yet" demonstrates nothing. These events are synthetic
    like the rest of the corpus, deterministic (same ids, same days) and only ever
    written into an in-memory demo database — never into a real one.
    """
    rows = conn.execute(
        "SELECT id FROM jobs WHERE status = 'open' ORDER BY id LIMIT 12"
    ).fetchall()
    if len(rows) < 8:
        return
    ids = [row["id"] for row in rows]
    plan = [
        ("demo-fresher", 6, "viewed", 64),
        ("demo-fresher", 0, "saved", 62),
        ("demo-fresher", 2, "viewed", 47),
        ("demo-fresher", 2, "saved", 46),
        ("demo-fresher", 1, "applied", 30),
        ("demo-fresher", 3, "viewed", 22),
        ("demo-fresher", 4, "saved", 21),
        ("demo-fresher", 5, "viewed", 15),
        ("demo-fresher", 0, "applied", 14),
        ("demo-fresher", 5, "dismissed", 9),
        ("demo-fresher", 6, "viewed", 2),
        ("demo-remote", 7, "saved", 12),
        ("demo-remote", 7, "viewed", 11),
    ]
    for profile_id, index, kind, days_ago in plan:
        stamp = (now - timedelta(days=days_ago)).replace(hour=10, minute=0, second=0, microsecond=0)
        conn.execute(
            "INSERT INTO apply_events (profile_id, job_id, kind, at, detail) VALUES (?,?,?,?,?)",
            (profile_id, ids[index], kind, stamp.isoformat(), "demo"),
        )
    conn.commit()


def demo_connection(
    *, thread_safe: bool = False, now: datetime | None = None, history: bool = False
) -> sqlite3.Connection:
    """An in-memory database with the synthetic corpus and the demo profiles.

    This is what a serverless deployment serves: no file to mount, no write to
    a read-only filesystem, and nothing real to leak. State lives as long as the
    instance does, which for a testing link is the right trade.
    """
    conn = db.connect(":memory:", check_same_thread=not thread_safe)
    moment = now or datetime.now(timezone.utc)
    load_corpus(conn, now=moment)
    seed_profiles(conn)
    _spread_first_seen(conn, moment)
    if history:
        _seed_demo_history(conn, moment)
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
    search_limiter: "_RateLimiter | None" = None,
    action_limiter: "_RateLimiter | None" = None,
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
        if path == "/search" and search_limiter is not None and not search_limiter.allow(client):
            return Response(429, "too many searches", "text/plain; charset=utf-8")
        return _handle_get(conn, path, query, demo=demo, now=now, headers=header_map)
    if method != "POST":
        return Response(405, "method not allowed", "text/plain; charset=utf-8")

    # Consent and webhook endpoints change state; they are throttled.
    throttled = ("/digest/subscribe", "/digest/unsubscribe", "/webhooks/whatsapp", "/webhooks/sms")
    if path in throttled and limiter is not None and not limiter.allow(client):
        return Response(429, "too many requests", "text/plain; charset=utf-8")

    if path in ("/webhooks/whatsapp", "/webhooks/sms"):
        return _handle_webhook(
            conn,
            path,
            query,
            body,
            header_map,
            strict=accounts.strict_mode() or not demo,
        )
    if path in ("/digest/subscribe", "/digest/unsubscribe"):
        return _handle_consent(conn, path, body)
    if path in ("/search/save", "/search/stop"):
        if action_limiter is not None and not action_limiter.allow(client):
            return Response(429, "too many actions", "text/plain; charset=utf-8")
        return _handle_saved_search(conn, path, body)
    if path in ("/api/cron/run", "/api/cron"):
        return _handle_cron(conn, header_map, query, now=now, demo=demo)
    if path == "/action":
        if action_limiter is not None and not action_limiter.allow(client):
            return Response(429, "too many actions", "text/plain; charset=utf-8")
        return _handle_action(conn, body, header_map)
    if path == "/auth/start":
        # The sign-in page posts here with the provider in the body. This route did
        # not exist, so every "Continue with ..." button answered 404 — the flow was
        # built, tested through GET /auth/<provider>/start, and unreachable from the
        # only place a person actually clicks it. Provenance is the lesson: test the
        # route the markup posts to, not the route the helper is named after.
        return _handle_auth_start_post(conn, body, demo=demo, now=now)
    if path in ("/auth/guest", "/auth/demo", "/auth/signout", "/account/cv", "/account/forget"):
        return _handle_account_post(conn, path, body, header_map, demo=demo, now=now)
    return Response(404, "not found", "text/plain; charset=utf-8")


def _record_view(conn, profile_id: str, job_id: str, now: datetime) -> None:
    """One "visited" per job per (Nairobi) day — the tracker, not a hit counter.

    The day is stored in ``detail`` and compared there. Comparing the timestamp's
    prefix instead mixes two clocks *and* two timezones: rows are stamped in UTC
    while the day is a Nairobi day, so between 21:00 and 23:59 UTC the same
    Nairobi day spans two UTC dates and the de-duplication silently fails. The
    timestamp fallback stays for rows written before ``detail`` existed.
    """
    day = (now + timedelta(hours=3)).date().isoformat()
    existing = conn.execute(
        """SELECT 1 FROM apply_events
            WHERE profile_id = ? AND job_id = ? AND kind = 'viewed'
              AND (detail = ? OR substr(at, 1, 10) = ?)""",
        (profile_id, job_id, day, day),
    ).fetchone()
    if existing:
        return
    try:
        tracking.record(conn, profile_id, job_id, "viewed", detail=day, now=now)
    except ValueError:
        pass


def _transports_from_env() -> dict:
    """The real senders, if this deployment has credentials for them.

    Missing credentials are not an error at import time — the site must render
    without a WhatsApp account — but they *are* an error for a cron run, which is
    why the cron handler reports 503 rather than pretending to have sent.
    """
    transports = {}
    for name, factory in (("whatsapp", channels.WhatsAppCloudTransport), ("sms", channels.SmsTransport)):
        try:
            transports[name] = factory()
        except RuntimeError:
            continue
    return transports


def _outbox_counts(conn, *, now: datetime) -> dict:
    since = (now - timedelta(hours=24)).isoformat()
    row = conn.execute(
        """SELECT
             SUM(state = 'queued')    AS queued,
             SUM(state = 'sent'   AND updated_at >= ?) AS sent_24h,
             SUM(state = 'failed' AND updated_at >= ?) AS failed_24h,
             SUM(state = 'suppressed') AS suppressed
           FROM messages""",
        (since, since),
    ).fetchone()
    return {key: int(row[key] or 0) for key in ("queued", "sent_24h", "failed_24h", "suppressed")} if row else {}


def _handle_sweep(conn, headers: dict, query: dict, *, now: datetime, demo: bool) -> Response:
    """On-demand sweep: fetch sources and update jobs.

    Gated by CRON_SECRET (same as the tick). Returns a report of what was fetched.
    """
    from . import sweep  # lazy: pulls in pipeline which pulls in httpx

    expected = (os.environ.get("CRON_SECRET") or "").strip()
    supplied = ""
    authorization = str(headers.get("authorization") or "")
    if authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    supplied = supplied or _query_one(query, "token")
    if not expected:
        return _json(503, {"error": "cron not configured", "hint": "set CRON_SECRET"})
    if not _constant_time_equal(supplied, expected):
        return _json(403, {"error": "bad cron token"})

    force = _query_one(query, "force") == "1"
    report = sweep.run_sweep(conn, now=now, force=force)
    return _json(200, report)


def _handle_sources(conn, headers: dict, query: dict, *, now: datetime, demo: bool) -> Response:
    """Source health: which sources are alive, which are dead, when each was last fetched."""
    from . import db as _db
    if not _db._is_postgres(conn) and "source_health" not in [
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    ]:
        return _json(200, {"sources": [], "note": "source_health table not yet created; run the sweep once"})
    
    rows = conn.execute(
        "SELECT source_id, last_seen_at, last_error, status, cadence_minutes FROM source_health ORDER BY source_id"
    ).fetchall()
    sources = [dict(row) for row in rows]
    return _json(200, {"sources": sources, "count": len(sources)})


def _handle_cron(conn, headers: dict, query: dict, *, now: datetime, demo: bool) -> Response:
    """One scheduled tick: compose what is due, then deliver it.

    Three refusals, in order, before anything leaves the building:

    1. **No shared secret, no tick.** `CRON_SECRET` gates the endpoint; Vercel's
       scheduler sends it as a bearer token automatically.
    2. **No synthetic sends.** On an instance serving the demo corpus, a cron run
       would deliver fabricated vacancies to a real phone number. That is the one
       outcome this product must never produce.
    3. **No silent success.** With no transport configured the answer is 503, not
       a cheerful 200 with nothing sent.
    """
    expected = (os.environ.get("CRON_SECRET") or "").strip()
    supplied = ""
    authorization = str(headers.get("authorization") or "")
    if authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    supplied = supplied or _query_one(query, "token")
    if not expected:
        return _json(503, {"error": "cron not configured", "hint": "set CRON_SECRET"})
    if not _constant_time_equal(supplied, expected):
        return _json(403, {"error": "bad cron token"})

    # `demo` is this process's own answer (a `--demo` server, or the serverless
    # shim reading the store); `synthetic_build()` catches a deployment that is
    # configured like production but has no database behind it. Either one means
    # the corpus is invented, and invented vacancies must not reach a phone.
    if (demo or synthetic_build()) and (os.environ.get("KAZIKASI_ALLOW_SYNTHETIC_SEND") or "") != "1":
        return _json(
            409,
            {
                "error": "refusing to send",
                "detail": "This instance serves a synthetic corpus, so a cron run would "
                "text fabricated vacancies to real numbers. Wire a real store first, or "
                "set KAZIKASI_ALLOW_SYNTHETIC_SEND=1 to test against your own number.",
            },
        )

    transports = _transports_from_env()
    if not transports:
        return _json(
            503,
            {
                "error": "no transport configured",
                "needs": ["WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"],
                "fallback": ["AT_USERNAME", "AT_API_KEY"],
            },
        )

    # Sweep first: fetch every source that is due, update the jobs table, so the
    # digest has fresh vacancies to compose from. Without this the digest is
    # composed from whatever happened to be in the database yesterday.
    from . import sweep  # lazy: sweep pulls in pipeline which pulls in httpx
    sweep_report = sweep.run_sweep(conn, now=now)

    report = scheduler.run_due(
        conn, transports, now=now, with_brief=True, with_alerts=True, with_searches=True
    )
    report["sweep"] = sweep_report["totals"]
    report["outbox"] = _outbox_counts(conn, now=now)
    return _json(200, report)


def _json(status: int, payload: dict) -> Response:
    return Response(status, json.dumps(payload, indent=2, default=str), "application/json; charset=utf-8")


def _handle_get(
    conn, path: str, query: dict, *, demo: bool, now: datetime, headers: dict | None = None
) -> Response:
    if path == "/healthz":
        return Response(200, "ok", "text/plain; charset=utf-8")

    if path in ("/api/cron/run", "/api/cron"):
        return _handle_cron(conn, headers or {}, query, now=now, demo=demo)

    if path == "/api/sweep":
        return _handle_sweep(conn, headers or {}, query, now=now, demo=demo)

    if path == "/api/sources":
        return _handle_sources(conn, headers or {}, query, now=now, demo=demo)

    if path == "/api/health":
        summary = metrics.stats(conn, now=now)
        return Response(
            200,
            json.dumps(
                {
                    "ok": True,
                    "schema": db.SCHEMA_VERSION,
                    "outbox": _outbox_counts(conn, now=now),
                    "live_jobs": summary["live_jobs"],
                    "sources_reporting": len(summary["jobs_per_source"]),
                    "as_of": summary["as_of"],
                    # Two different questions, two names: the corpus is synthetic
                    # until a real store exists; whether this is production is
                    # answered by KAZIKASI_DEMO (see /auth/ready).
                    "synthetic": demo,
                    "strict": accounts.strict_mode(),
                    "corpus": {
                        "source": bundle_module.STATE.get("source", "synthetic"),
                        "built_at": bundle_module.STATE.get("built_at"),
                        "count": bundle_module.STATE.get("count", 0),
                        "error": bundle_module.STATE.get("error"),
                    },
                    "build": (os.environ.get("VERCEL_GIT_COMMIT_SHA") or "")[:7] or "dev",
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

    if path == "/brief":
        profile = _profile_or_default(conn, _query_one(query, "profile") or None)
        momentum.check_in(conn, profile.id, now=now)
        return Response(
            200,
            render_brief(
                conn, profile_id=_query_one(query, "profile") or None, now=now, demo=demo
            ),
        )



    if path == "/setup":
        return Response(200, render_setup(conn, demo=demo, now=now, headers=headers), "text/html; charset=utf-8")

    if path == "/api/setup":
        plan = setup_module.plan(
            conn,
            now=now,
            synthetic=synthetic_build(),
            strict=accounts.strict_mode(),
            base_url=_base_url(),
            host=_request_host(headers),
        )
        return Response(
            200, json.dumps(plan.to_dict(), indent=2, default=str), "application/json; charset=utf-8"
        )

    if path == "/search":
        return _handle_search(conn, query, demo=demo, now=now, headers=headers)

    if path == "/employers":
        return Response(200, render_employers(conn, now=now, demo=demo, headers=headers))

    if path.startswith("/employer/"):
        page = render_employer(
            conn,
            path.split("/", 2)[2],
            profile_id=_query_one(query, "profile") or None,
            now=now,
            demo=demo,
            headers=headers,
        )
        if page is None:
            return Response(404, _page("Not found", "<h1>Employer not found</h1>", demo=demo))
        return Response(200, page)

    if path == "/year":
        return Response(
            200,
            render_year(
                conn,
                profile_id=_query_one(query, "profile") or None,
                now=now,
                demo=demo,
                headers=headers,
                year=int(_query_one(query, "year")) if _query_one(query, "year").isdigit() else None,
            ),
        )

    if path == "/auth/ready":
        return Response(
            200,
            json.dumps(accounts.readiness(base_url=_base_url()), indent=2),
            "application/json; charset=utf-8",
        )

    if path == "/signin":
        return Response(
            200,
            render_signin(
                conn,
                demo=demo,
                notice=_query_one(query, "notice"),
                tone=_query_one(query, "tone", "warn"),
            ),
        )

    if path == "/account":
        account = _account_for(conn, headers)
        profile = _profile_or_default(conn, _query_one(query, "profile") or None)
        notice = ""
        tone = "good"
        if _query_one(query, "guest"):
            notice, tone = "Guest session started. Add your CV and the kit will fill itself.", "good"
        if _query_one(query, "saved"):
            notice, tone = "CV read. Check the fields below before you rely on them.", "good"
        if _query_one(query, "error"):
            notice, tone = _query_one(query, "error"), "bad"
        return Response(200, render_account(conn, account, profile=profile, demo=demo, notice=notice, tone=tone))

    if path == "/activity":
        profile = _profile_or_default(conn, _query_one(query, "profile") or None)
        return Response(
            200,
            render_activity(
                conn,
                profile=profile,
                now=now,
                demo=demo,
                tab=_query_one(query, "tab", "all") or "all",
                headers=headers,
            ),
        )

    if path.startswith("/auth/") and path.endswith("/start"):
        provider_key = path.split("/")[2]
        provider = accounts.PROVIDERS.get(provider_key)
        if provider is None:
            return Response(404, _page("Not found", "<h1>Unknown provider</h1>", demo=demo))
        return _auth_start(conn, provider, demo=demo, now=now)

    if path.startswith("/auth/") and path.endswith("/callback"):
        provider_key = path.split("/")[2]
        provider = accounts.PROVIDERS.get(provider_key)
        if provider is None:
            return Response(404, _page("Not found", "<h1>Unknown provider</h1>", demo=demo))
        return _auth_callback(conn, provider, query, demo=demo, now=now)
    if path == "/pulse":
        return Response(200, render_pulse(conn, now=now, demo=demo, headers=headers))

    if path == "/salaries":
        return Response(200, render_salaries(conn, now=now, demo=demo, headers=headers))

    if path == "/sitemap.xml":
        return Response(200, render_sitemap(conn, now=now), "application/xml; charset=utf-8")

    if path == "/robots.txt":
        return Response(200, render_robots(), "text/plain; charset=utf-8")

    if path.startswith("/county/"):
        page = render_county(conn, path.rsplit("/", 1)[-1], now=now, demo=demo, headers=headers)
        if page is None:
            return Response(404, _page("Not found", "<h1>County not found</h1>", demo=demo))
        return Response(200, page)

    if path == "/shortlist":
        return Response(
            200,
            render_shortlist(
                conn,
                profile_id=_query_one(query, "profile") or None,
                now=now,
                demo=demo,
                headers=headers,
            ),
        )

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
            headers=headers,
        )
        if page is None:
            return Response(404, _page("Not found", "<h1>Job not found</h1>", demo=demo))
        _record_view(
            conn,
            _profile_or_default(conn, _query_one(query, "profile") or None).id,
            path.rsplit("/", 1)[-1],
            now,
        )
        return Response(200, page)

    if path in ("/", "/index.html"):
        seen = read_seen(headers)
        page = render_feed(
            conn,
            profile_id=_query_one(query, "profile") or None,
            now=now,
            demo=demo,
            since=seen,
            headers=headers,
        )
        return Response(200, page, headers={"Set-Cookie": seen_cookie(now)})

    return Response(404, _page("Not found", "<h1>Not found</h1>", demo=demo))


def _handle_webhook(conn, path: str, query: dict, raw: bytes, headers: dict, *, strict: bool) -> Response:
    """Inbound replies and receipts. Fails closed on an unverified sender.

    The posture is "production", not "synthetic data": a local `serve` without
    --demo, or a deployment with KAZIKASI_DEMO=0, fails closed when no shared
    secret is configured — otherwise anyone could POST a fake receipt.
    """
    if path == "/webhooks/whatsapp":
        secret = os.environ.get("WHATSAPP_APP_SECRET")
        signature = headers.get(webhooks.SIGNATURE_HEADER.lower())
        if secret:
            if not webhooks.verify_signature(raw, signature, secret):
                return Response(403, "bad signature", "text/plain; charset=utf-8")
        elif strict:
            # No secret and not a demo: we cannot tell Meta from anyone.
            return Response(503, "webhook not configured", "text/plain; charset=utf-8")
        result = webhooks.handle_meta(conn, webhooks.parse_json(raw))
        return Response(200, json.dumps(result, default=str), "application/json; charset=utf-8")

    token = _query_one(query, "token")
    expected = os.environ.get("AT_WEBHOOK_TOKEN")
    if expected and not _constant_time_equal(token, expected):
        return Response(403, "bad token", "text/plain; charset=utf-8")
    if not expected and strict:
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


#: A visitor may trigger these; everything else in `tracking.KINDS` is written
#: by the system (viewed, clicked_through, applied, reminded by the scheduler).
ACTION_KINDS = ("dismissed", "saved", "unsaved", "reminded", "applied")


def _safe_next(value: str) -> str | None:
    """Only same-site paths, so a form cannot be turned into an open redirect."""
    if not value or not value.startswith("/") or value.startswith("//"):
        return None
    return value


def _handle_action(conn, body: bytes, headers: dict) -> Response:
    form = parse_qs(body.decode("utf-8", errors="replace"))
    profile_id = _query_one(form, "profile")
    job_id = _query_one(form, "job")
    kind = _query_one(form, "kind")
    back = _safe_next(_query_one(form, "next"))

    if profile_id and job_id and kind in ACTION_KINDS:
        try:
            tracking.record(conn, profile_id, job_id, kind)
        except ValueError:
            pass

    if headers.get("accept", "").startswith("application/json"):
        return Response(200, json.dumps({"ok": True}), "application/json; charset=utf-8")
    location = back or (f"/?profile={quote(profile_id)}" if profile_id else "/")
    return Response(303, "", headers={"Location": location})



def _handle_auth_start_post(conn, body: bytes, *, demo: bool, now: datetime) -> Response:
    """Turn "Continue with X" into the provider's consent screen.

    Redirects (303, not 307) so a refresh re-enters through the gate rather than
    replaying a POST. The provider must be one we know *and* one this build can
    actually talk to; anything else goes back to the page that offered it, with a
    notice that names the missing variable rather than a dead end.
    """
    form = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
    provider_key = (form.get("provider") or [""])[0].strip().lower()
    provider = accounts.PROVIDERS.get(provider_key)
    if provider is None:
        return _redirect(
            "/signin?notice=" + quote("That sign-in option does not exist.") + "&tone=warn"
        )
    if not provider.configured:
        missing = ", ".join(
            name
            for name, present in (
                (provider.client_id_env, bool(os.environ.get(provider.client_id_env))),
                (provider.client_secret_env, bool(os.environ.get(provider.client_secret_env))),
            )
            if not present
        )
        return _redirect(
            "/signin?notice="
            + quote(f"{provider.label} is not configured in this build. Missing: {missing}.")
            + "&tone=warn"
        )
    return _redirect(f"/auth/{provider.key}/start")


def _redirect(location: str, *, cookie: str | None = None) -> Response:
    headers = {"Location": location}
    if cookie:
        headers["Set-Cookie"] = cookie
    return Response(303, "", headers=headers)


def _auth_start(conn, provider, *, demo: bool, now: datetime, return_to: str = "/account") -> Response:
    if not provider.configured:
        # No client id in this build. Say so, name the variables, and offer the
        # synthetic path so the rest of the flow can still be walked end to end.
        body = f"""
<div class="masthead">
  <p class="kicker">Sign-in · not configured</p>
  <h1 class="display">{_e(provider.label)} is not connected in this build</h1>
  <p class="scopeline">The flow is built; the credentials are not. A deployment needs
  two environment variables before this button can talk to {_e(provider.label)}.</p>
</div>
<div class="whobar">
  <div><b>{_e(provider.client_id_env)}</b> and <b>{_e(provider.client_secret_env)}</b></div>
  <p class="small">Register <code>{_e(_base_url())}/auth/{_e(provider.key)}/callback</code>
  as the redirect URI, then redeploy. Nothing else changes. Run
  <code>kazikasi auth check --base-url {_e(_base_url())}</code> to see every
  provider's state at once, and <a href="/auth/ready">/auth/ready</a> for the JSON.</p>
  <p class="small">The callback verifies the provider's id_token signature against
  their published keys, and checks the issuer, the audience and the lifetime before
  it trusts a single claim.</p>
</div>
{"<form method='post' action='/auth/demo'><input type='hidden' name='provider' value='" + provider.key + "'><button type='submit' class='ghost'>Continue with a synthetic demo account</button></form><p class='small'>This creates a local member account so the flow can be tested. No provider is contacted.</p>" if demo else ""}
<p><a href="/signin">← back</a></p>"""
        return Response(200, _page("Sign in — Kazi-Kasi", body, demo=demo))

    attempt = accounts.start(conn, provider.key, now=now, return_to=return_to)
    url = accounts.authorize_url(
        provider,
        state=attempt["state"],
        challenge=attempt["challenge"],
        redirect_uri=f"{_base_url()}/auth/{provider.key}/callback",
    )
    return _redirect(url)


def _auth_callback(conn, provider, query: dict, *, demo: bool, now: datetime) -> Response:
    code = _query_one(query, "code")
    state = _query_one(query, "state")
    error = _query_one(query, "error")
    if error:
        return _redirect(f"/signin?notice={quote('Sign-in was cancelled: ' + error)}&tone=warn")
    if not code or not state:
        return _redirect(f"/signin?notice={quote('Sign-in came back incomplete.')}&tone=bad")
    try:
        verifier = accounts.claim_state(conn, state, provider.key, now=now)
    except ValueError as exc:
        return _redirect(f"/signin?notice={quote(str(exc))}&tone=warn")
    try:
        identity = accounts.exchange(
            provider,
            code=code,
            verifier=verifier,
            redirect_uri=f"{_base_url()}/auth/{provider.key}/callback",
        )
    except Exception as exc:  # noqa: BLE001 - the provider's error is the message
        return _redirect(f"/signin?notice={quote('Sign-in failed: ' + str(exc)[:120])}&tone=bad")
    account = accounts.sign_in(conn, provider.key, identity, now=now)
    return _redirect("/account", cookie=accounts.session_cookie(account["id"], now))


def _handle_account_post(conn, path: str, body: bytes, header_map: dict, *, demo: bool, now: datetime) -> Response:
    if path == "/auth/guest":
        account = accounts.guest(conn, now=now)
        return _redirect("/account?guest=1", cookie=accounts.session_cookie(account["id"], now))

    if path == "/auth/demo":
        form = parse_qs(body.decode("utf-8", errors="replace"))
        provider_key = _query_one(form, "provider", "google")
        account = accounts.sign_in(
            conn,
            provider_key,
            {
                "subject": "demo-" + provider_key,
                "email": f"demo@{provider_key}.example",
                "email_verified": True,
                "name": "Demo member",
            },
            now=now,
        )
        return _redirect("/account", cookie=accounts.session_cookie(account["id"], now))

    if path == "/auth/signout":
        return _redirect(
            "/",
            cookie="kazi_id=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax",
        )

    account = _account_for(conn, header_map)
    if account is None:
        return _redirect(f"/signin?notice={quote('That needs a session first.')}&tone=warn")

    if path == "/account/forget":
        accounts.forget(conn, account["id"], now=now)
        return _redirect(
            "/signin?notice=Deleted. Your CV is gone and your identity is blank.",
            cookie="kazi_id=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax",
        )

    if path == "/account/cv":
        filename, text = _cv_text(body, header_map.get("content-type", ""))
        if not text.strip():
            return _redirect(f"/account?error={quote('No CV text found — paste the text or upload a .txt, .md or .pdf.')}")
        fields = autofill.parse(text)
        accounts.store_cv(conn, account["id"], filename=filename, text=text, fields=fields, now=now)
        accounts.touch(conn, account["id"], now=now)
        return _redirect("/account?saved=1")

    return Response(404, "not found", "text/plain; charset=utf-8")


def _cv_text(body: bytes, content_type: str) -> tuple[str | None, str]:
    """Either a pasted field or one uploaded file. Returns (filename, text)."""
    if "multipart/form-data" not in (content_type or ""):
        form = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
        return None, _query_one(form, "cv_text")

    boundary = ""
    for part in content_type.split(";"):
        if part.strip().startswith("boundary="):
            boundary = part.strip().split("=", 1)[1].strip('"')
    if not boundary:
        return None, ""

    parts = body.split(b"--" + boundary.encode())
    text_value, filename = "", None
    for part in parts:
        head, _, payload = part.partition(b"\r\n\r\n")
        header_text = head.decode("utf-8", errors="replace")
        if 'name="cv_text"' in header_text:
            text_value = payload.rstrip(b"\r\n-").decode("utf-8", errors="replace")
        elif 'name="cv_file"' in header_text and "filename=" in header_text:
            match = re.search(r'filename="([^"]*)"', header_text)
            filename = match.group(1) if match else "cv"
            raw = payload.rstrip(b"\r\n-")
            if filename.lower().endswith(".pdf"):
                try:
                    from pypdf import PdfReader
                except ImportError:
                    return filename, ""
                import io

                reader = PdfReader(io.BytesIO(raw))
                text_value = "\n".join(page.extract_text() or "" for page in reader.pages)
            else:
                text_value = raw.decode("utf-8", errors="replace")
    return filename, text_value or ""


class _Handler(BaseHTTPRequestHandler):
    db_path = ":memory:"
    demo = False
    limiter = _RateLimiter()
    server_version = "kazikasi-feed/0.6"

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(min(length, 512 * 1024)) if length else b""

    def _respond(self, response: Response) -> None:
        # This server speaks plain HTTP; HSTS belongs on the deployment's edge,
        # where TLS actually terminates (the shim sends it, the base URL decides).
        policy = security_headers(https=False)
        if response.is_redirect:
            self.send_response(response.status)
            for key, value in policy.items():
                self.send_header(key, value)
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
        for key, value in policy.items():
            self.send_header(key, value)
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
                search_limiter=self.search_limiter,
                action_limiter=self.action_limiter,
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
        {
            "db_path": str(db_path),
            "demo": demo,
            "limiter": _RateLimiter(),
            "search_limiter": _RateLimiter(limit=SEARCH_RATE_LIMIT),
            "action_limiter": _RateLimiter(limit=ACTION_RATE_LIMIT),
        },
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
