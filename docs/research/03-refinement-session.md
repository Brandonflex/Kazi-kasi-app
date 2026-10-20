# Prompt Refinement Session — Agenda & Decision Log

**Companion to:** [`00-executive-brief.md`](./00-executive-brief.md) · draft v0.1 · 2026-10-20

This is the working document for the session. It is deliberately opinionated: every open question comes with a recommendation and the reasoning behind it, so the conversation is about *disagreeing with something specific* rather than starting from a blank page.

**How to use it:** read the brief first (10 minutes), then answer the twelve decisions below. Each answer changes the build. Anything left unanswered defaults to my recommendation, clearly marked.

---

## 0. The three decisions that actually matter

If you only settle three things, settle these. The other nine can be deferred without blocking the first commit.

| # | Decision | Why it dominates | My recommendation |
|---|---|---|---|
| **D1** | **Who is the user?** Active searcher, passive watcher, or career switcher | Determines cadence (push vs. pull), UI (feed vs. digest), and what "good" means | **Active searcher, 25–40, Romania, mid-level** — highest pain, clearest willingness to switch tools, fastest feedback loop |
| **D2** | **Which segment is the wedge?** IT/white-collar, blue-collar/local, or early-career | Determines which sources matter, which competitors matter, and whether ANOFM/Telegram are core or irrelevant | **IT + adjacent white-collar in Bucharest/Cluj** — ATS-dense (so our spine works immediately), English-friendly, and the users who will tolerate a beta |
| **D3** | **What is v1 allowed to be?** A thin vertical slice or a broad pipeline | Determines whether we ship in 6 weeks or 6 months | **Thin slice: one city, five ATS families, one feed, honest freshness labels.** No map, no chat, no mobile |

Everything else in this document is downstream of these three.

---

## 1. Decision log

Fill the **Your call** column during the session. `—` means "accept the recommendation".

### D4 · Geography model

| | |
|---|---|
| **Question** | Is geo scope a *filter* (radius/city) or a *model* (travel time from anchors)? |
| **Options** | (a) City + radius, ship fast · (b) PostGIS radius + H3, model travel time in v2 · (c) Travel-time isochrones from day one |
| **Recommendation** | **(b)** — radius/H3 now, isochrones behind a feature flag in the same release |
| **Why** | Travel time is the differentiator, but routing data (especially Bucharest GTFS) is the riskiest dependency. Building the schema for it now costs little; blocking the launch on it costs everything. |
| **What it changes** | Schema (`job_location` with `h3_r7`/`h3_r9`, `commute_confidence`), the feed API contract, and whether we need OSRM/Valhalla in Phase 1. |
| **Your call** | — |

### D5 · Product surface

| | |
|---|---|
| **Question** | What is the primary interface? |
| **Options** | (a) Feed with filters · (b) Map-first ("jobs around me") · (c) Chat/agent ("find me…") · (d) Email/Telegram digest only |
| **Recommendation** | **(a)**, with a deliberately plain list. Digest in week 2 of beta; map after geo is trustworthy; chat never as the primary surface |
| **Why** | Chat hides the data quality problem behind prose, which is the opposite of what a trust product needs. A feed with visible freshness/provenance lets users audit us. Maps are seductive but poor for scanning 40 roles. |
| **What it changes** | Frontend scope, SEO strategy (job detail pages are the acquisition channel), instrumentation. |
| **Your call** | — |

### D6 · Source policy for v1

| | |
|---|---|
| **Question** | How aggressive is ingestion in the first release? |
| **Options** | (a) ATS + JSON-LD only · (b) + ANOFM + one licensed local board · (c) + aggregator APIs for coverage · (d) + social signals |
| **Recommendation** | **(b)** — and add (c) only as a coverage benchmark, never as canonical |
| **Why** | (a) alone under-covers Romanian SMEs, who mostly hire through ANOFM and local boards. (d) adds legal and quality risk before we have any trust capital. This gives depth in one metro rather than breadth everywhere. |
| **What it changes** | Adapter count, legal review scope, initial coverage numbers, cost. |
| **Your call** | — |

### D7 · Social and informal signals

| | |
|---|---|
| **Question** | Does v1 include any social lane? |
| **Options** | (a) None · (b) Bluesky + HN + news, signals only (never canonical) · (c) Add Telegram public channels for RO blue-collar · (d) Buy licensed social data |
| **Recommendation** | **(b)**, with (c) as a research spike only if D2 flips to blue-collar |
| **Why** | Reddit's public API dies by March 2027, LinkedIn is off-limits, and Facebook is login-gated. Bluesky is free and open, HN is high-signal, news is safe. Everything else is either a dependency time bomb or a GDPR problem. |
| **What it changes** | Legal exposure, whether we need a DPIA before launch or after, and whether "demand signals" is a v1 feature or a v2 story. |
| **Your call** | — |

### D8 · Freshness promise

| | |
|---|---|
| **Question** | What do we promise users about liveness? |
| **Options** | (a) "Updated continuously" (vague) · (b) Public per-job "last verified" + per-source SLO page · (c) Real-time claim (< 15 min) |
| **Recommendation** | **(b)**. Never (a) — it is what everyone says and it is unfalsifiable |
| **Why** | Freshness is our one honest, measurable claim. If we publish the SLO and miss it, we lose; if we meet it, no competitor can copy it quickly. (c) is a cost trap. |
| **What it changes** | Scheduler tiers, observability requirements, marketing copy, and the "proof" block on every card. |
| **Your call** | — |

### D9 · Matching philosophy

| | |
|---|---|
| **Question** | What does "best match" optimise? |
| **Options** | (a) Skills similarity · (b) Constraints → relevance → utility (pay, commute, stability) · (c) Application likelihood (learned) |
| **Recommendation** | **(b)** |
| **Why** | (a) produces "you're a perfect fit" for jobs that pay badly or are two hours away — the exact failure users complain about. (c) requires data we will not have for a year, and is the version most exposed to AI Act scrutiny. |
| **What it changes** | Ranking service design, the explanation UI, and the metrics we track. |
| **Your call** | — |

### D10 · Apply flow

| | |
|---|---|
| **Question** | How far do we go on application assistance? |
| **Options** | (a) Link out only · (b) Save/track + link out · (c) Autofill on employer sites · (d) Auto-apply |
| **Recommendation** | **(b)**. Revisit (c) only if retention demands it; never (d) |
| **Why** | Auto-apply converts a decision product into a volume product, degrades the data (mass applications → ghost jobs), invites platform hostility, and pushes us into high-risk AI territory for no strategic gain. |
| **What it changes** | Scope, legal posture, and the positioning ("fewer, better" vs. "more, faster"). |
| **Your call** | — |

### D11 · Business model

| | |
|---|---|
| **Question** | Who pays? |
| **Options** | (a) Free consumer, monetise later · (b) Consumer subscription (alerts, scopes, insights) · (c) B2B data/API · (d) Employer-side (job ads / sourcing) |
| **Recommendation** | **(a) now, with (c) kept architecturally open.** Explicitly not (d) in v1 |
| **Why** | (d) creates a conflict of interest with the core promise ("fewer, better roles") and turns the user into inventory. (c) is a natural second act *if* the canonical schema keeps provenance and confidence from day one — which is why §2 of the blueprint insists on it. |
| **What it changes** | Schema (public vs. private fields), privacy notice, and whether we ever need a sales motion. |
| **Your call** | — |

### D12 · Identity and language

| | |
|---|---|
| **Question** | Brand and language posture? |
| **Options** | (a) Kazi-Kasi, Romanian-first · (b) Kazi-Kasi, bilingual RO/EN · (c) Different brand for RO market · (d) English-first |
| **Recommendation** | **(b)** |
| **Why** | "Kazi" (work) + "kasi" (speed/rate) reads as "work, fast" — a decent radar metaphor and short enough to be a domain. Romanian-first builds local trust; English keeps the door open to CEE expansion and to the developer audience. Dual-language from the start is cheap; retrofitting i18n is not. |
| **What it changes** | UI copy, SEO, source parsing (diacritics!), and the data model's text fields. |
| **Your call** | — |

---

## 2. Assumptions I am making until told otherwise

State these back if any are wrong — they are load-bearing.

1. **Romania-first**, Bucharest as the first metro. *(Not stated by you; inferred from your location and from the choice of ANOFM-adjacent sources. If the intent is a global product from day one, say so and D2 changes completely.)*
2. **Consumer product**, one person looking for work, not a recruiter tool.
3. **Solo/small team**, so the architecture must be operable by one or two people. This is why the blueprint avoids microservices and Kafka.
4. **Budget in the hundreds of euros per month**, not thousands, during validation.
5. **Mobile web before native app.**
6. **No employer relationships at launch** — so no "featured jobs" inventory, which is also why the feed can stay honest.

---

## 3. What I need from you in the session

Answer in whatever order. Short is fine.

1. Who is the person you are picturing? Describe one real user, not a persona.
2. Which of D1–D3 do you want to argue about first?
3. Is the Romania-first assumption right, or is this meant to be borderless from the start?
4. What does "accurate" mean to you — *no duplicates*, *no dead listings*, *right pay*, or *reachable*? Rank them.
5. What is the smallest version of this you would be proud to show someone?
6. What would make you abandon this idea? (Useful for designing the kill criteria.)
7. Do you have access to any of these: an eJobs/BestJobs partnership, a company/employer list, a data provider contract, or a legal reviewer?
8. What is the timeline pressure — demo, launch, fundraise, or "when it's good"?

---

## 4. The prompt pack (for after the session)

Once the decisions are settled, this is the brief we hand to the build. It is written to be reusable at every phase, so the agent always has the same context.

### 4.1 Standing context prompt

```text
PROJECT: Kazi-Kasi — a geo-anchored hiring radar for Romania.

THESIS
We index the hiring internet continuously, resolve every posting into one live,
deduplicated, provenance-tracked job graph, and tell one person which roles are
real, reachable, and worth their time.

DECIDED (fill in after the session)
- User:              <D1>
- Wedge segment:     <D2>
- v1 boundary:       <D3>
- Geo model:         <D4>
- Product surface:   <D5>
- Sources in v1:     <D6>
- Social lane:       <D7>
- Freshness promise: <D8>
- Matching:          <D9>
- Apply flow:        <D10>
- Business model:    <D11>
- Brand/language:    <D12>

INVARIANTS (do not violate without asking)
1. Raw payload is stored before any parsing. Parsers are replayable.
2. Deterministic before generative. No LLM in the ingestion critical path.
3. No logged-in scraping, no fake accounts, no ToS-hostile collection.
4. No personal-data harvesting. We store jobs, employers, and the user's own profile.
5. Every job carries provenance: source, first_seen, last_seen, verified_at.
6. Never show a ghost flag without naming the criteria.
7. No automated decisions about a person. Rank and explain; the human decides.
8. No protected attributes or proxies in matching. Audit postal-code leakage.
9. Every merge is reversible; source records are never destroyed.
10. No metric reported without its sample size.

NON-GOALS FOR v1
Auto-apply, resume generation, recruiter CRM, mobile app, chat-first UI,
global coverage, social scraping at scale.
```

### 4.2 Phase prompts

Each phase gets its own PR. Each PR stays small enough to review.

**Phase 1 — Spine**
```text
Build the ingestion spine.
- `source_registry` table + adapter interface with a YAML manifest.
- Five adapters: Greenhouse, Lever, Ashby, Workday, SmartRecruiters. Contract
  tests against recorded fixtures; no live network in tests.
- Raw store: content-addressed, stores payload + headers + fetch metadata.
- Canonical schema + migrations (job, job_source_record, job_location,
  job_salary, company, job_provenance).
- Replay tool: re-parse a date range from raw without re-crawling.
- Golden-set harness: 500 labelled postings, but start with 50 seeded manually.
Acceptance: 1,000 real Romanian postings ingested and replayable; field-fill
rate report per source; zero network calls in the test suite.
```

**Phase 2 — Identity**
```text
Build entity resolution.
- Stage 1 deterministic keys incl. ATS requisition extraction from apply URLs.
- Stage 2 blocking + weighted signals + confidence bands.
- LLM adjudication only for 0.80–0.95, cached by pair hash.
- Company resolver with CIF/domain/tenant priority.
- Golden-set evaluation CLI that prints precision/recall per band.
Acceptance: precision >= 0.97, recall >= 0.90 on the labelled pairs;
every merge reversible; no source record mutated.
```

**Phase 3 — Lifecycle**
```text
Build liveness.
- State machine with explicit transitions and a transition log.
- Close detection: absence from full-board fetch, validThrough, HTTP status,
  soft-404 detection.
- Ghost criteria as named booleans; ghost_level derived, never estimated.
- Repost detection (same identity, reopened).
Acceptance: on 100 postings with known fate, liveness precision >= 0.95;
p95 close detection < 2h for hot sources in a simulated 24h run.
```

**Phase 4 — Geography**
```text
Build geo scope.
- Romanian address normaliser (diacritics, Sector, abbreviations).
- Geocoding with confidence scores and a manual override table.
- H3 r7/r9 indexing; PostGIS geometry.
- Isochrone cache: one city, two modes, three time bands.
- Fallback ladder with an explicit `commute_confidence` label.
Acceptance: p95 commute error < 15% vs. 50 manual checks; every job in the
top 100 of a test feed has a geocode confidence >= threshold or a visible label.
```

**Phase 5 — Feed**
```text
Build the feed and the explanation.
- Feed API with cursor pagination, saved scopes, hide/report actions.
- Matching: constraints -> relevance -> utility, each factor returned as data.
- Card UI: title, employer, pay vs. local percentile, commute, freshness proof.
- "Why this job" panel driven by the factor data, not by generated prose.
- Dual language RO/EN from the start.
Acceptance: 50-user closed beta; instrumented save/apply/hide; a human can
audit any card's reasoning without opening a database.
```

**Phase 6 — Trust**
```text
Build the trust surface.
- Per-source health dashboard: last success, error rate, field-fill drift.
- Public freshness page generated from real metrics.
- Privacy: export, delete, plain-language notice (RO/EN), retention jobs.
- DPIA draft and a data-flow diagram suitable for a DPO review.
Acceptance: a stranger can answer "how fresh is this?" and "why am I seeing
this?" from the UI alone.
```

---

## 5. Kill criteria (write these down before we start)

An idea without kill criteria becomes a sunk cost. Proposed:

| Signal | Threshold | Interpretation |
|---|---|---|
| Feed precision at position 10 | < 0.5 after two tuning cycles | The matching thesis is wrong |
| Verified-live rate at 7 days | < 85% on hot sources | The data thesis is wrong |
| Beta weekly retention (W4) | < 15% | The product is a novelty |
| Users cannot articulate the difference from eJobs/LinkedIn in one sentence | > 50% of interviews | The positioning has failed |
| Legal review says the source strategy is untenable | Any | Pivot to licensed data rather than litigate |
| Cost per active user per month | > €3 with no monetisation path | The unit economics don't close |

---

## 6. Decision record (fill during the session)

| # | Decision | Options considered | Chosen | Rationale | Date |
|---|---|---|---|---|---|
| D1 | Primary user | active / passive / switcher | | | |
| D2 | Wedge segment | IT / blue-collar / early-career | | | |
| D3 | v1 boundary | thin slice / broad pipeline | | | |
| D4 | Geo model | filter / H3 / isochrones | | | |
| D5 | Surface | feed / map / chat / digest | | | |
| D6 | Sources | ATS / +local / +aggregators / +social | | | |
| D7 | Social lane | none / Bluesky+HN+news / +Telegram | | | |
| D8 | Freshness | vague / published SLO / real-time | | | |
| D9 | Matching | skills / constraints+utility / learned | | | |
| D10 | Apply | link-out / +track / autofill / auto | | | |
| D11 | Revenue | free / consumer sub / B2B / employer | | | |
| D12 | Brand | RO-first / bilingual / rename | | | |

---

## 7. Next actions after the session

1. Fill §6; commit the completed decision log to this file (or `docs/decisions/0001-scope.md`).
2. Open the Phase 1 PR with the schema and the first two adapters only.
3. Seed the employer list (target: 300 Romanian employers with resolvable ATS boards).
4. Commission the legal review: source policy + DPIA scope, before any public beta.
5. Do not start Phase 4 (geo) until Phase 2's precision numbers are in hand — geo on top of bad identity is wasted work.
