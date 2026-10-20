# Source Landscape, Market Map & Legal Posture

**Companion to:** [`00-executive-brief.md`](./00-executive-brief.md) · research draft v0.1 · 2026-10-20

This document answers three questions: *what exists*, *what can we legally and technically take*, and *what does it cost*.

---

## 1. Method and confidence

Desk research across vendor documentation, regulatory summaries, industry benchmarks, and public technical write-ups, October 2026. Three confidence levels are used throughout:

- **Verified** — documented by the vendor/regulator, or reproduced by multiple independent technical sources.
- **Reported** — stated by one credible source; treat as a hypothesis to test.
- **Inferred** — our reasoning. Not a fact.

Every quantitative claim in the tables is tagged. Anything marked *Reported* gets validated in Phase 1 before it drives a design decision.

---

## 2. The market, mapped

### 2.1 Legacy aggregators

| Player | Model | What we can take | What hurts |
|---|---|---|---|
| **Indeed / LinkedIn** | Direct employer + syndicated | Nothing directly. LinkedIn: link-out only, no profile scraping | ToS prohibits scraping; LinkedIn is the most-litigated target in the category |
| **Jooble** | Feed + crawl, 60–70 countries | Free API key on request; snippet + source name + link | Snippets only, no source attribution you can query, no lifecycle, no firehose |
| **Careerjet** | Crawl, 90 countries, ~58k sites scanned | Documented search API | Key per publisher site; every call must carry the *end user's* IP and user agent; paging ceiling ~1,100 per query — structurally unusable for dataset building |
| **Adzuna** | Feed-driven aggregator, 16–20 countries | Free tier (2,500 calls/month, 250/day), salary histogram/geodata endpoints, institutional credibility (UK ONS uses it) | Thin per-job records; commercial use needs a licence after a 14-day trial; prohibits redistribution of derived aggregates |
| **Talent.com / SimplyHired** | Aggregators | Little | Partner-only access |
| **eJobs (RO)** | Largest RO board, ~15k live ads *Reported* | Public JSON endpoint, no key *Reported*; rich fields (company verified flag, positions, counties, expiry) | No published API terms; must confirm permission or use a licensed data provider |
| **BestJobs (RO)** | General + IT board, ~1.45M monthly views *Reported* | Salary ranges, estimated salary, remote/hybrid flags, apply URLs | Publishes no posting dates *Reported*; no API; scraping terms unclear |
| **Hipo (RO)** | IT / graduate / internship | Structured categories, cities, seniority | Niche; no API |
| **ANOFM / mediere (RO)** | **Public employment service** | The authoritative registry: employers must legally declare vacancies. COR occupation code, RON salary (gross/net), county, employer CIF, contact details, EURES flag, start/expiry dates | No official API; portal UX is poor; scraping must be gentle and permitted |

**Verdict:** aggregator APIs are coverage *rental*. They are useful for benchmarking our own coverage and for filling gaps early, but never as the foundation. The foundation is employer-direct.

### 2.2 AI-native job search

| Product | Position | Evidence | Gap we exploit |
|---|---|---|---|
| **HiringCafe** | Search engine over employer career pages; claims ~5.7M live jobs, up to 4× legacy boards; aggressive ghost-job filtering; raised $6.8M | Reported (company + press, Sep 2026) | US-centric; not geo-reasoning; no Romania |
| **Jobright** | ~8M listings, ~400K added daily; match scoring, tailoring, referral discovery, autofill | Reported (vendor + reviews) | US-only per its own FAQ; no pay-vs-local-cost or commute logic; "apply more" optimisation |
| **Simplify** | Autofill + tracker + matches; free core, ~$39.99/mo premium | Reported (reviews) | Utility layer, not a discovery product |
| **Teal** | Tracker + resume + match score; generous free tier | Reported | Organises what you already found |
| **Welcome to the Jungle (ex-Otta)** | Curated tech roles, salary up front, 6–7k vetted companies | Reported | Curated by humans, limited scale, no commute model |
| **LoopCV / LazyApply / JobCopilot** | Auto-apply volume | Reported | Optimises applications sent, which is the metric that produces ghost-job fatigue |

**The pattern:** the category has converged on *matching + tailoring + autofill*. Those are now commodities with many vendors and falling prices. What is not commoditised is **verified liveness** and **geographic realism**. That is where a new entrant can win without out-spending anyone.

### 2.3 B2B labour-market data (the "sell the pipe" alternative)

Firms such as Lightcast, LinkUp, JobsPikr, Coresignal and Revelio sell normalised job-posting feeds and labour-market analytics to enterprises, universities and investors. *Inferred:* this is a real business with real margins, and it is the natural monetisation if the consumer product stalls. It also implies a strategic option worth keeping open — **the same pipeline can serve both**, if the canonical schema is designed properly from day one (which is why provenance and confidence fields are non-negotiable in §4).

### 2.4 Public employment infrastructure (the underrated asset)

- **ANOFM / mediere.anofm.ro** — in Romania, employers are legally required to declare vacancies to the public employment service. That makes it the **most complete single registry of formal openings in the country**, with COR codes and RON salaries. *Reported* by EURES and by practitioners who scrape it.
- **EURES** — EU cross-border portal, publishes labour-market information per country and carries EURES-flagged RO vacancies. API availability to be verified in Phase 1.
- **INS / TEMPO** — earnings by county, activity, sex; monthly averages; vacancy series. *Verified* (INS releases): national average net earnings RON 5,734 in June 2026; IT/programming sector average net RON 13,474; Bucharest above RON 7,000; lowest counties below RON 4,100.

**Why this matters for the product:** it gives us a free, defensible **local pay baseline**. "RON 9,000 for this role in Iași" is meaningless without the county median; with it, it becomes a decision.

---

## 3. Source inventory — the buildable list

Scored on: **access** (1 = hard, 5 = trivial), **data quality**, **freshness**, **cost**, **legal risk** (5 = low risk), **effort**. Priority = whether it belongs in the first 90 days.

### Lane A — Public ATS APIs (the spine)

All unauthenticated, JSON, documented by the vendor or by the endpoint the vendor's own career site uses.

| ATS | Endpoint | Coverage / quirks | Priority |
|---|---|---|---|
| **Greenhouse** | `GET boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` | Whole board in one call; HTML description (double-encoded); departments, offices, `updated_at`, `absolute_url`. ~7,500 companies use Greenhouse *Reported* | **P0** |
| **Lever** | `GET api.lever.co/v0/postings/{site}?mode=json` (EU: `api.eu.lever.co`) | Bare array; `descriptionPlain`, `lists[]`, `categories{team,department,location,commitment,allLocations}`, `workplaceType`, `country`, `createdAt` (ms), `hostedUrl`, `salaryRange?`. `mode=json` must be explicit | **P0** |
| **Ashby** | `GET api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true` | Structured compensation for the large majority of postings *Reported*; `isRemote`, `employmentType`, `descriptionPlain` | **P0** |
| **Workday** | `POST {tenant}.{wdN}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` | Paginated, max 20/page; list is thin (`locationsText` can be the literal `"2 Locations"`); real location/date/description require one detail call per job; `postedOn` is human text ("Posted 3 Days Ago"). No derivable slug — must be discovered from career URLs | **P1** (expensive, but many large RO employers) |
| **SmartRecruiters** | `careers.smartrecruiters.com/{company}` public postings API | Uses **microdata**, not JSON-LD — needs a second extractor | **P1** |
| **Workable** | `apply.workable.com/api/v1/widget/accounts/{slug}?details=true` | Simple, low volume | P1 |
| **Recruitee / Personio / Breezy / Teamtailor / Rippling** | Various public board endpoints | Long tail; implement when a target employer uses them | P2 |

**The board-discovery problem** — the real work in this lane:

1. Start from a seed list of employers (Romanian company registry, ANOFM employer CIFs, VC portfolios, top-employer lists).
2. For each domain, fetch `/careers`, `/jobs`, `/cariere`, `/locuri-de-munca`, follow redirects.
3. Detect ATS from URL patterns (`boards.greenhouse.io`, `jobs.lever.co`, `jobs.ashbyhq.com`, `*.myworkdayjobs.com`, `apply.workable.com`).
4. Fall back to search-engine queries (`site:boards.greenhouse.io "Romania"`) and to sitemap harvesting.
5. Cache the resolved `(provider, tenant, site)` triple — it does not change often.
6. Re-run discovery weekly; ATS migrations are common and silent.

*Inferred but strongly supported by practitioner write-ups:* this discovery index is the single most valuable proprietary asset in the whole system. It is tedious, unglamorous, and hard to copy.

### Lane B — Structured web (`schema.org/JobPosting`)

- **Scale:** schema.org reports `JobPosting` usage in the 100K–1M domains range *Reported*.
- **Format:** JSON-LD preferred by Google; microdata and RDFa also valid. Parse `script[type="application/ld+json"]`, handle both a single object and an array, and recurse into `@graph`.
- **Core fields:** `title`, `description`, `datePosted`, `validThrough`, `hiringOrganization`, `jobLocation`, `baseSalary`, `employmentType`, `identifier`, `directApply`, `jobLocationType`, `applicantLocationRequirements`, `experienceRequirements`, `educationRequirements`.
- **Why it's high value:** full descriptions, employer-direct apply URLs, stable `identifier`, and — critically — `validThrough`, which gives us a free close signal.
- **Failure modes:** markup that does not match visible content; one-JobPosting-per-URL violations on listing pages; silent schema drift; pages that render the JSON-LD only via JavaScript (needs a headless fallback, used sparingly).
- **Crawl politeness:** `robots.txt`, `Crawl-delay`, sitemaps, conditional requests (`If-Modified-Since`, `ETag`), a truthful user agent with a contact URL.

### Lane C — Aggregator APIs (borrow, verify, don't depend)

| Source | Free tier | Countries | Record depth | Lifecycle | Legal note |
|---|---|---|---|---|---|
| Adzuna | 2,500 calls/mo (250/day) | 16–20, strongest UK/EU | Snippets; strong aggregate/salary endpoints | Created date only | Commercial licence required after trial; no redistribution of aggregates |
| Jooble | Free key on request | 60–70 | Snippet + source name + link | None | No published limits or pricing; attribution terms |
| Careerjet | Free, publisher key | 90 | Fragments | None | Must pass end-user IP/UA → not usable for a dataset |
| JSearch (RapidAPI) | 200 req/mo; $25/mo for 10k | Global-ish, US-weighted | Google for Jobs SERP copy; duplicates per board | None | Wrapper-of-a-wrapper; freshness lag 24–48h *Reported* |
| JobsPipe-class unified APIs | Free credits, ~$49/mo | NA/EU/India | Full record, `status`, `closed_at`, `ghost_score`, webhooks | Yes | Best "buy" option — worth a paid benchmark month to calibrate our own dedupe against theirs |

**Decision rule:** use aggregators to (a) measure our coverage gap, (b) backfill thin geographies during beta, and (c) sanity-check our dedupe. Do not let them into the canonical graph as a primary source of truth.

### Lane D — Social and informal signals (handle with tongs)

| Source | Access | Signal value | Status | Verdict |
|---|---|---|---|---|
| **Bluesky / AT Protocol** | Free public firehose (Jetstream), 5,000 points/hour *Reported* | Early chatter, "we're hiring" posts, layoffs | Open and stable | **Only social source in scope for v1 research** |
| **Reddit** | New public API requests stop **31 Oct 2026**; RSS ends **13 Nov 2026**; public API ends **March 2027** | Strong for local/industry chatter | Actively closing | **Do not build a dependency.** If needed, license via a provider |
| **X / Twitter** | Paid, restrictive | Same as above | Closed | Out of scope |
| **LinkedIn** | ToS prohibits scraping; logged-in collection is the pattern that loses in court | Job posts, "we're hiring" | Hostile | **Link-out only. No profile collection. No logged-in access.** |
| **Telegram (public channels)** | MTProto / bot API on public channels | High for RO blue-collar, gig, hospitality, construction | Fragmentary | P2 — strong local signal, but personal data and no structure |
| **Hacker News "Who is hiring"** | Algolia HN API | High-quality remote tech roles, monthly thread | Open | Cheap win; P2 |
| **Mastodon** | Open APIs | Small | Open | Ignore for now |
| **Facebook groups** | Login-gated | High for RO local work | ToS + login | **Out of scope** |

**The corroboration rule (non-negotiable):** a social signal is never a job. It becomes a candidate job only when backed by (a) an employer-controlled URL or ATS requisition, **and** (b) at least one independent confirmation. Otherwise it lives in the signal lane and powers *demand intelligence* — "this company is about to hire" — not the feed.

### Lane E — News and editorial

RSS, Google News RSS, GDELT, and Romanian business press (Profit.ro, ZF, Economica.net, StartupCafe). Use for:
- hiring momentum ("X opens Bucharest engineering hub"),
- funding, expansion, layoffs,
- employer context on the job card ("12 roles open, 3 closed this week, raised €4M in June").

Never for job records. Always attributed, never paywalled content reproduced.

### Lane F — Geo and macro data

| Need | Source | Notes |
|---|---|---|
| Geocoding | Nominatim / Photon (OSM), plus manual overrides | Romanian addresses are messy; sector + street + number needs a normaliser |
| Routing / isochrones | OSRM, Valhalla, OpenRouteService | Self-host OSRM for cost; ORS/Valhalla for isochrone polygons |
| Public transit | GTFS per city (Bucharest STB/Metrorex availability to verify) | *Reported* as patchy; plan a fallback |
| Spatial index | H3 (res 7 ≈ 5 km², res 9 ≈ 0.1 km²) | Pre-compute reachability bands per H3 cell |
| Admin geography | SIRUTA codes, 41 județe + București, sectors | Needed for county-level pay baselines and ANOFM joins |
| Occupations | ISCO-08 (EU) + COR (RO) | Cross-walk table required; COR is what ANOFM publishes |
| Pay baselines | INS/TEMPO, ANOFM, EURES LMI | County × activity × month |

**Research support for the geography model:** spatial job-search literature finds the utility of a job offer decays roughly exponentially with distance (order of ~0.3 per km in one UK estimate), and that a job 5 km further away can be ~4.5× less attractive. Administrative units badly mis-measure real labour markets; travel time or commuting flows are better. This is the academic justification for making travel time a first-class field rather than a filter.

---

## 4. Field-level reality check

What sources actually return, versus what the product needs. This table drives the canonical schema in [`02`](./02-technical-blueprint.md).

| Field | ATS | JSON-LD | ANOFM | Local boards | Aggregators | Coverage verdict |
|---|---|---|---|---|---|---|
| Title | ✅ | ✅ | ✅ | ✅ | ✅ | Universal |
| Employer | ✅ (GH only named) | ✅ | ✅ (+ CIF) | ✅ | ✅ | Universal, needs normalisation |
| Full description | ✅ | ✅ | Partial | ✅ | ❌ snippet | **ATS + JSON-LD only** |
| Stable source ID | ✅ | ✅ (`identifier`) | ✅ | ✅ | ✅ | Universal |
| Posted date | ✅ | ✅ | ✅ | Varies | ✅ (board-claimed) | Needs `first_seen` to be trustworthy |
| Close event | ✅ (absence) | ✅ (`validThrough`) | ✅ (expiry) | Varies | ❌ | **Our differentiator** |
| Structured salary | Ashby ✅, Lever ~, GH ❌ | ~ | ✅ RON gross/net | BestJobs ~ | ❌ free text | Biggest data gap; needs parsing + local baseline |
| Work mode | Lever/Ashby ✅ | ✅ (`jobLocationType`) | ❌ | ~ | ~ | Needs inference + user-visible confidence |
| Coordinates | ❌ | Place only | ❌ (city/county) | Some (eJobs GPS *Reported*) | ❌ | **Must geocode ourselves** |
| Multi-location | ✅ (Lever `allLocations`) | Partial | ❌ | ~ | ❌ | Needs explicit modelling |
| Occupations | ❌ | ❌ | ✅ COR | ~ | ~ | Build a COR/ISCO cross-walk |
| Employer identity | Partial | `sameAs` | ✅ CIF | company ID | Weak | Build the company entity resolver |

---

## 5. Cost envelope (order of magnitude)

*Inferred from published pricing and typical token costs; validate in Phase 1.*

| Item | Monthly | Notes |
|---|---|---|
| Compute + Postgres + object storage (small) | €40–120 | A single 4–8 vCPU node plus managed Postgres is enough for Phase 1–2 |
| LLM enrichment | €30–250 | Only on new/changed postings; deterministic parsing first; ~5–15k new RO-relevant postings/day assumed |
| Routing / isochrones | €0–100 | Self-hosted OSRM ≈ free; hosted ORS if needed |
| Aggregator API benchmarks | €0–60 | Adzuna free tier; one paid month for calibration |
| Proxy / crawl infrastructure | €0–150 | Only if polite crawling is insufficient; avoid aggressive scraping |
| **Total** | **≈ €100–700/mo** | Comfortably bootstrappable; the constraint is engineering time, not infrastructure |

---

## 6. Legal and compliance posture

> Not legal advice. Before public launch we need a Romanian/EU DPO review and a DPIA. Budget for both explicitly.

### 6.1 Collection

| Question | Position | Basis |
|---|---|---|
| Is scraping public pages a crime? | Generally no in the US (CFAA does not reach public pages, *hiQ*), but it is not a free pass | *hiQ v. LinkedIn* (9th Cir. 2022); *Van Buren* (2021) |
| Do terms of service bind? | Yes, if you accepted them. Logged-out public collection was held outside Meta's terms in *Meta v. Bright Data* (N.D. Cal., Jan 2024) | Log-in status is the sharpest line in the case law |
| Can we scrape while logged in? | **No.** This is the fact pattern that destroyed hiQ: fake accounts, contract breach, $500K, injunction, shutdown | *hiQ* consent judgment (Dec 2022) |
| What about EU contract terms? | *Ryanair v. PR Aviation* (CJEU, C-30/14): even where database rights don't apply, the site owner can restrict extraction contractually | EU is stricter than the US here |
| Do database rights apply? | Possibly, for substantial extraction from a protected database | EU Database Directive *sui generis* right |

**Operating rules we adopt:**
1. No accounts, no credentials, no fake users, no paywall bypass.
2. Honour `robots.txt` and rate limits; identify ourselves honestly.
3. Prefer documented/public JSON endpoints over HTML.
4. Log every fetch (URL, timestamp, status, policy decision) for auditability.
5. Maintain a per-source kill switch and a `terms_reviewed_at` field in the adapter registry.
6. Never store personal data from social posts beyond what is strictly necessary; no author profiling.

### 6.2 Personal data (GDPR)

- Publicly available personal data is still personal data. The CNIL fined KASPR €240,000 over LinkedIn-derived data and only closed the injunction after the database was erased and collection ceased *Reported*.
- The EDPB's 2026 guidance on web scraping confirms GDPR applies whenever personal data is involved, and that public posting is not consent.
- **Our boundary:** we store *job* data, employer data, and the user's own profile. We do **not** build a people database. No candidate profiles, no recruiter contact harvesting, no "find the hiring manager's email" feature.
- User-side: consent + contract bases, data minimisation, retention limits, export, delete, and a plain-language notice written in Romanian and English.

### 6.3 AI Act and automated decision-making

| Date | Obligation | Status | Impact on us |
|---|---|---|---|
| 2 Feb 2025 | Article 5 prohibitions (emotion inference at work); AI literacy | In force | We do none of the prohibited practices |
| 2 Aug 2026 | Article 50 transparency (tell people they're interacting with AI) | In force | Label any AI-generated summaries; disclose the matcher |
| **2 Dec 2027** | Annex III high-risk for recruitment, incl. **candidate ranking** and **targeted job advertising** | Deferred from 2 Aug 2026 by Reg. (EU) 2026/1744 | Our ranking engine is in scope. Build oversight, logging, and documentation now |
| Today | GDPR Art. 22 — no solely automated decisions with significant effects | In force | We never auto-reject, auto-apply, or auto-contact. Human decides |

*Key legal detail to design around:* **profiling candidates is always high-risk**; the narrow-task exemption in Art. 6(3) does not open for it. And from Dec 2027, Art. 86 gives an affected person the right to a meaningful explanation of the AI's role in a decision. Our "why this job" panel is therefore both a product feature and a compliance artefact.

### 6.4 Other surfaces

- **DSA** — if we host user-generated content or become an intermediary, notice-and-action duties may attach. Keep v1 read-only for users; no public posting.
- **Consumer protection** — no dark patterns, no fake urgency, no "12 people applied" theatre unless it is true.
- **Pay transparency** — the EU Pay Transparency Directive pushes employers toward disclosing ranges; this is a tailwind for our salary normalisation, not a constraint.
- **Accessibility** — WCAG 2.2 AA from day one; job search is a high-need accessibility category.

---

## 7. What this landscape tells us to build

1. **Employer-direct first.** ATS + JSON-LD gives us the only records with full text, stable identity, and a real close signal.
2. **Aggregators as a measuring stick.** Their coverage gap defines our roadmap; their duplication defines our quality bar.
3. **ANOFM is a local superpower.** No global player will invest in parsing a Romanian public registry with COR codes and CIFs. We should.
4. **Social is seasoning, not substrate.** The platforms are closing; the legal exposure is asymmetric; the signal is real but must be corroborated.
5. **The moat is the boring middle:** board discovery, entity resolution, lifecycle tracking, geocoding, pay baselines. None of it demos well. All of it compounds.
