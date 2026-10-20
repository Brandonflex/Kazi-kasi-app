# Kazi-Kasi — Executive Brief

**Status:** research draft v0.1 · 2026-10-20
**Scope of this round:** research and framing only. No product code yet.
**Read this first, then:** [`01-source-landscape.md`](./01-source-landscape.md) → [`02-technical-blueprint.md`](./02-technical-blueprint.md) → [`03-refinement-session.md`](./03-refinement-session.md)

---

## 1. The problem, said plainly

A job seeker in Bucharest does not have a "not enough jobs" problem. They have four other problems:

1. **Fragmentation.** The same role lives on eJobs, BestJobs, Hipo, ANOFM, LinkedIn, the employer's own careers page, and a recruiter's repost — six versions, three of them stale.
2. **Distance that lies.** A posting says "București". That can mean Pipera at 08:15, or Militari at 06:00, or a fully remote role tagged with the HQ city. "Nearby" is not the same as "reachable from my life".
3. **Staleness and ghosts.** Boards re-date postings, roles get filled and left up, aggregators keep expired copies. A large share of any raw feed is not a real opening. Industry estimates put ghost/filled-but-listed postings in the 15–22% range, and cross-source duplication in the 40–60% range once you merge boards.
4. **No explanation.** Existing tools give a score with no reason, or a list with no prioritisation. The user cannot tell *why* something is a fit, or whether it is worth an hour of their evening.

**Kazi-Kasi's job is to collapse all four into one quiet, trustworthy answer: what is actually open, actually reachable, and actually worth applying to — today, near me.**

---

## 2. The one idea

> **Kazi-Kasi is a geo-anchored hiring radar.** It continuously watches the hiring internet, resolves every posting into one live, deduplicated, provenance-tracked job graph, and tells a single person — in their own language and their own travel reality — which roles are real, reachable, and worth their time.

Three commitments define the product. Everything else is negotiable.

| Commitment | What it means concretely | Why it is the moat |
|---|---|---|
| **Live, not listed** | Every job carries `first_seen`, `last_seen`, `closed_at`, `proof[]` and a ghost score with *named* criteria. We show our evidence. | Cheap to say, expensive to build. Requires continuous re-verification, per-source lifecycle logic, and entity resolution. This is plumbing, not prompt engineering — which is exactly why competitors skip it. |
| **Reachable, not nearby** | Geo scope is travel time from the user's anchors (home, second anchor), by mode, at the hour that matters — not a radius in kilometres. | Nobody in the consumer space does this properly. The research on local labour markets is unambiguous: job attractiveness decays sharply with commute distance, and administrative boundaries badly mis-measure real labour markets. |
| **Explained, not scored** | Every match shows its factors: skills overlap, pay vs. local median, commute minutes, freshness, seniority gap, language requirement. User can re-weight. | Explainability is now also a legal direction of travel (GDPR Art. 22 today; EU AI Act Art. 86 explanation rights for high-risk systems from Dec 2027). Building it in early is cheaper than retrofitting. |

### The compressed thesis

**Own one metro end-to-end before touching a second one.** Depth beats breadth. A verified, live, travel-time-aware graph of Bucharest is worth more than a thin global index of 8 million rows, because the thin index is exactly what already exists and is free.

Expansion path: **Bucharest → Cluj-Napoca / Timișoara / Iași / Brașov → Romania → CEE (Bulgaria, Hungary, Serbia, Moldova)**. Each step reuses the pipeline; only source adapters and geo data change.

---

## 3. What the market already does

Four clusters. None of them occupy the position above.

| Cluster | Examples | Strength | Structural gap |
|---|---|---|---|
| **Legacy aggregators** | Indeed, LinkedIn, Jooble, Careerjet, Adzuna, Talent.com, eJobs, BestJobs, Hipo | Volume, SEO, employer relationships | Query-shaped access, snippets instead of records, no cross-source identity, no lifecycle, re-dated listings, no geography beyond a string |
| **Public employment** | ANOFM (RO), EURES (EU) | Legally authoritative in Romania — employers must register vacancies; COR codes; salary in RON; contact details | Poor UX, no dedupe, no reachability, no matching |
| **AI-native job search** | HiringCafe, Jobright, Simplify, Teal, Welcome to the Jungle (Otta), LoopCV, LazyApply | Real-time indexing, match scoring, autofill, tailoring, ghost-job filtering | Almost entirely US-first; matching is resume-similarity; geo is a filter, not a model; sourcing sits in a ToS grey zone; the product ends at "apply faster", not "choose better" |
| **B2B labour-market data** | Lightcast, LinkUp, JobsPikr, Coresignal, Revelio | Clean feeds, APIs, enterprise buyers | Sold to companies and analysts; the individual worker is not the customer; no personal travel reality |

### The two competitors worth studying closely

- **HiringCafe** — the closest analogue to our indexing ambition: it bypasses aggregators and indexes employer career pages directly, claims ~5.7M live roles, raised $6.8M, and markets itself explicitly against ghost jobs. Its weakness is our opening: it is a US-centric search engine, not a geo-reasoning companion.
- **Jobright** — the closest analogue to our matching ambition: ~8M listings, ~400K added daily, match scoring plus tailoring plus referral discovery. Its weakness: US-only coverage, no local pay/commute realism, and the value proposition collapses into "apply more".

**Conclusion: the differentiation is not "AI job matching" — that is now table stakes. The differentiation is a verifiable, geo-grounded data layer and a product that optimises for *fewer, better, provably-live* roles.**

---

## 4. What we can actually ingest (summary)

Full detail and feasibility scoring in [`01-source-landscape.md`](./01-source-landscape.md).

| Lane | Best sources | Access | Quality | Verdict |
|---|---|---|---|---|
| **ATS public boards** | Greenhouse, Lever, Ashby, Workday (CXS), SmartRecruiters, Workable, Recruitee, Personio | Free, no auth, JSON | Highest: full descriptions, structured pay, stable IDs, real close events | **Build first.** This is the spine. |
| **Structured web** | Any page publishing `schema.org/JobPosting` JSON-LD (~100K–1M domains) | Free, polite crawl | High; survives redesigns; includes employer-direct URLs | **Build second.** Covers the long tail of career pages. |
| **Aggregator APIs** | Adzuna, Jooble, JSearch, JobsPipe-class vendors | Free tiers / cheap | Medium: snippets, duplicates, weak lifecycle | **Borrow, don't depend.** Use for coverage gaps and benchmarking. |
| **Romanian public + local** | ANOFM/mediere (mandatory vacancy registry), eJobs, BestJobs, Hipo | Scrape / partner | High local relevance, COR codes, RON salaries | **Build, with legal care.** ANOFM is the authoritative RO baseline. |
| **Social / informal** | Bluesky firehose, HN "Who is hiring", Telegram public channels; Reddit is closing | Free–cheap | Noisy, personal-data-heavy | **Signal lane only.** Never canonical until corroborated by an employer source. |
| **News / editorial** | RSS, GDELT, local business press | Free | Context, not records | **Enrichment.** Hiring momentum, expansions, layoffs, funding. |

**The single most important engineering insight from the research:** the hard part is not fetching. It is **identity** — deciding that six observations are one job, that this job is closed, and that this employer is that company. Get that right and everything else is presentation.

---

## 5. Legal posture (EU/Romania), in one page

Full treatment in [`01-source-landscape.md` §6](./01-source-landscape.md).

- **Public ≠ free to use.** Under GDPR, a public profile or post containing personal data is still personal data. The French CNIL fined KASPR €240,000 over LinkedIn-derived personal data and closed the injunction only after the database was erased and collection stopped. "It was public" is not a lawful basis.
- **Logged-in scraping is the losing pattern.** *hiQ v. LinkedIn* won the CFAA argument and still lost on contract, paid $500K, and was enjoined and shut down. *Meta v. Bright Data* (2024) went the other way precisely because the collection was logged-out and public. Design rule: **no accounts, no credentials, no fake users, ever.**
- **Terms of service still bind.** In the EU, *Ryanair v. PR Aviation* confirms contract terms can restrict extraction even where database rights do not apply. Respect `robots.txt`; prefer official/public JSON endpoints; identify the crawler; honour rate limits.
- **The AI Act is not a 2027 problem.** Article 50 transparency has applied since 2 Aug 2026. The Annex III high-risk regime for recruitment (which includes *candidate ranking* and *targeted job advertising*) now applies from **2 Dec 2027** under Regulation (EU) 2026/1744. Profiling candidates is always high-risk; there is no narrow-task escape hatch for it. GDPR Art. 22 (no solely-automated significant decisions) applies **today**.
- **Our design answers:** user is the controller of their own profile; consent + contract as bases; no recruiter-side sale of candidate data in v1; no automated rejection or outreach; full export/delete; DPIA before launch; visible "why am I seeing this"; human decides, always.

This is not legal advice. Before public launch we need a Romanian/EU DPO review — budget for it explicitly.

---

## 6. What "constant update 24/7" should actually mean

"Real time" is a cost decision, not a slogan. Proposed freshness contract, by source class:

| Class | Examples | Re-check cadence | Why |
|---|---|---|---|
| **Hot** | ATS boards of target employers; user's saved/search companies | 10–30 min | Close events are the product. |
| **Warm** | Long-tail ATS boards, ANOFM, major local boards | 1–6 h | Volume without urgency. |
| **Cold** | JSON-LD career pages, niche boards | 24 h | Cheap discovery, slow drift. |
| **Signal** | Bluesky, HN, news | streaming / 15 min | Early warning, not truth. |

Pair this with a **freshness SLO** (e.g. p95 time-to-detect-close < 2 h for hot sources, < 24 h for warm) and a public "last verified" stamp on every card. That stamp is the trust product.

---

## 7. Non-goals for v1 (deliberate)

We are not building, in the first release:

- an **auto-apply bot** — legally messy, ethically poor, and it optimises the wrong metric;
- a **resume factory** — commodity, and it pulls focus from the data layer;
- a **recruiter CRM / candidate marketplace** — different buyer, different compliance surface, and it turns the user into inventory;
- **global coverage** — thin global coverage is a solved, free commodity;
- **a social scraper at scale** — the platforms are actively closing (Reddit's public API dies by March 2027; LinkedIn is off-limits), so a dependency there is a time bomb.

---

## 8. What success looks like

North star: **verified, reachable, relevant roles surfaced per active user per week** — with the user's own judgement as the check ("saved" or "applied"), not clicks.

Leading indicators:
- % of feed items still live at 7 days (target > 95% for hot sources)
- duplicate rate in feed (target < 1%)
- median "why this job" agreement rate in user interviews (target > 80%)
- p95 commute estimate error vs. a manual routing check (target < 15%)
- feed precision at position 10, human-labelled (target > 0.7)

Guardrails:
- ghost false-positive rate (flagging a real job as ghost) — must stay low; a false accusation is a trust event
- adverse-impact ratio across gender/age proxies in ranking
- source concentration (no single source > 35% of served roles)

---

## 9. Risks, ranked

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Identity/dedupe quality is worse than expected | High | High | Golden set of 500 hand-labelled postings before launch; measure precision/recall per source; human review queue for low-confidence merges |
| 2 | Source access revoked or priced up | High | High | Adapter abstraction; never >35% concentration; community/public sources prioritised; no ToS-hostile collection |
| 3 | GDPR/DPIA exposure from social sourcing | Medium | High | Signal lane corroboration rule; no personal profiles stored; DPO review before launch |
| 4 | Cold-start: not enough local coverage to feel useful | Medium | High | Anchor the first release on ATS + ANOFM + one local board partnership; publish honest coverage stats |
| 5 | LLM cost/latency on enrichment | Medium | Medium | Deterministic-first parsing; content-hash caching; cheap-model triage, expensive model only on ambiguity |
| 6 | Ranking skew / discrimination | Medium | High | Exclude protected attributes; monitor adverse impact; explainability; no automated decisions |
| 7 | Commute data unavailable (GTFS gaps in RO) | Medium | Medium | Start with drive/walk isochrones + straight-line damping; add transit per-city as data permits; label confidence |
| 8 | Founders' attention spread across too many surfaces | High | Medium | One metro, one feed, one map, one metric |

---

## 10. Recommended 90-day shape

Not a commitment — an input to the refinement session.

| Phase | Weeks | Output |
|---|---|---|
| **0 — Decisions** | 1 | This brief argued through; the 12 decisions in [`03`](./03-refinement-session.md) locked |
| **1 — Spine** | 2–5 | 5 ATS adapters + raw ELT store + canonical schema + golden set; ingesting ~5k live RO-relevant roles |
| **2 — Identity** | 5–8 | Dedupe/ER with measured precision/recall; lifecycle state machine; freshness + ghost scoring |
| **3 — Geography** | 8–10 | Geocoding, H3 indexing, isochrone cache, travel-time scope for Bucharest |
| **4 — Feed** | 10–13 | Explainable matching, feed UI, "why this job", save/hide feedback loop; closed beta (50–100 users) |
| **5 — Trust** | 13+ | Public freshness stats, DPIA, privacy notice, export/delete, source-health dashboard |

---

## 11. Open questions for the session

These are not rhetorical. Each one changes the build:

1. Who is the user — the **active searcher** (urgency, applications), the **passive watcher** (curiosity, alerts), or the **career switcher** (long horizon)? The product shape differs substantially.
2. Is the wedge **white-collar Bucharest**, **blue-collar/local** (where ANOFM and Telegram signals are strongest and competition is weakest), or **early-career** (where Hipo and internships dominate)?
3. Is this **consumer-first** (free, grow, monetise later) or **B2B-first** (sell the data layer, consumer as demo)?
4. How far do we go on **social signals** in v1 — none, or a single corroborated lane?
5. Is "Kazi-Kasi" the brand we build on, and does the Romania-first hypothesis hold?

My working answers are in [`03-refinement-session.md`](./03-refinement-session.md), with the reasoning for each. Disagree with them there, not in the abstract.
