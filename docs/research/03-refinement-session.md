# Refinement Session — Decisions, Record & Prompt Pack

**Companion to:** [`00-executive-brief.md`](./00-executive-brief.md) · draft v0.2 · 2026-10-20

This document records what was decided, what was delegated, and what is still open. It also contains the reusable prompt pack for each build phase, so the build always starts from the same context.

---

## 1. Decisions taken in the session

| # | Decision | Answer | Consequence |
|---|---|---|---|
| **D1** | Primary user | **Early-career white-collar, 0–3 years** — across sectors, with graduate schemes, internships and industrial attachments | The whole product optimises for timing, eligibility fit, safety, and commute. Not for seniority breadth |
| **D2** | Wedge segment | **Entry-level + internship/attachment**, with a **secondary "passive watcher" surface (Radar)** | Two surfaces, one engine: Feed for urgency, Radar for intelligence |
| **D2b** | Wedge breadth | **All white-collar entry-level**, not IT only — finance, admin, operations, sales, HR, NGO programme support, graduate schemes | Matches how graduates actually search ("anything I'm eligible for"); costs a noisier `entry_fit` signal, hence eligibility as a first-class field |
| **D3** | v1 boundary | **Delegated → thin vertical slice** (see §2) | ~12–14 weeks to a closed beta, not a 6-month pipeline |
| **D3b** | Radar timing | **Ships after the feed works** | It is the retention product, not the acquisition product; two half-built surfaces is the classic failure mode |
| **D4** | Geography | **Kenya first.** Nairobi metro as the beta. East Africa as the expansion shape | Nairobi-only coverage and routing in v1; adapters designed to carry to Uganda/Tanzania later |
| **D4b** | Kenya coverage | **Nairobi metro only**, including remote-first roles that hire in Kenya | Depth of verification and routing over national breadth; Mombasa/Kisumu in a later stage |
| **D5** | Product surface | **Web feed + WhatsApp digest** | Feed carries provenance, evidence and "why this job"; WhatsApp carries the alert. Each does what it is good at |
| **D7** | Social lane | **None in v1.** No WhatsApp group scraping, no Facebook, no LinkedIn profiles | Removes the largest legal and fraud surface; keeps scope honest |
| **D11** | Business model | **Undecided** — keep the schema open | No employer-paid ranking, ever; B2B data remains architecturally possible |

### Decisions I made on your behalf (D3)

You delegated v1 scope. Here is what I chose and why, so you can overrule it explicitly rather than by accident.

**v1 is a thin vertical slice, not a platform.**

- **One metro:** Nairobi, plus remote-first roles that hire in Kenya.
- **Four source families:** BrighterMonday, Fuzu, MyJobMag, ReliefWeb. *Not* all 47 county boards.
- **One document source:** PSC (or one high-volume county board) — enough to prove the PDF/OCR pipeline works, not enough to drown in it.
- **One surface:** a feed with saved scopes and a WhatsApp digest. No map, no chat, no mobile app.
- **One differentiator, fully built:** verification — `last_seen`, deadlines, `entry_fit`, and scam screening.
- **Geography deferred to Phase 5.** Routing on top of unverified identity is wasted work. It is also the most visible feature, so it lands as the "wow" after the base is trustworthy.

**Why not the broad pipeline:** at Kenya's volume (~a few thousand live roles), breadth is cheap but *quality* is expensive. Six months of pipeline work before a single user sees a card is the classic failure mode — you would be guessing which parts matter. Twelve weeks with real users tells you.

**Why not the data-layer-first option:** it is a real business, but it sells to employers, and you asked for a product for people. Keep the schema open for it; don't start there.

---

## 2. Open decisions (need your input, none blocking Phase 1)

D5 was confirmed after the session (web feed + WhatsApp digest) and is now recorded in §5. What remains:

### D6 · Source depth — recommend: boards + public sector + NGO, no aggregators

| | |
|---|---|
| **Question** | How wide is ingestion in v1? |
| **Options** | (a) Four boards only · (b) + PSC/county + ReliefWeb · (c) + 300 employer pages · (d) + social |
| **Recommendation** | **(b)**, then (c) in Phase 3 |
| **Why** | Global aggregators barely cover Kenya (Adzuna has no KE market), so (d) is worthless. Social is legally and practically out. Boards give volume; public sector and NGO give the roles nobody else aggregates |
| **What it changes** | Adapter count, OCR budget, coverage claims |
| **Your call** | — |

### D8 · Freshness promise — recommend: published per-source SLO

| | |
|---|---|
| **Question** | What do we promise about liveness? |
| **Options** | (a) "Updated continuously" (vague) · (b) "Last checked X min ago" per card + a per-source SLO page · (c) "Real-time" |
| **Recommendation** | **(b)**. Never (a) — everybody says it and it is unfalsifiable |
| **Why** | It is the one claim a competitor cannot copy quickly, and it is the reason a user trusts the feed over a board they already know |
| **What it changes** | Scheduler tiers, observability, marketing copy, card design |
| **Your call** | — |

### D9 · Matching philosophy — recommend: constraints → relevance → utility

| | |
|---|---|
| **Question** | What does "best match" optimise? |
| **Options** | (a) Skills similarity · (b) Eligibility + relevance + utility (pay, commute, employer signal) · (c) Predicted application success |
| **Recommendation** | **(b)** |
| **Why** | (a) is what BrighterMonday and Fuzu already do, and it recommends jobs the user cannot legally or practically take. (c) needs data we will not have for a year |
| **What it changes** | Ranking service, explanation UI, metrics |
| **Your call** | — |

### D10 · Apply flow — recommend: link out + track

| | |
|---|---|
| **Question** | How far do we go on application assistance? |
| **Options** | (a) Link out only · (b) Save/track + link out · (c) Autofill · (d) Auto-apply |
| **Recommendation** | **(b)**. Never (d) |
| **Why** | Auto-apply turns a decision product into a volume product, worsens the 200–500-applications-per-role pathology, and invites platform hostility. (c) is a possible later feature if retention demands it |
| **What it changes** | Scope, legal posture, positioning |
| **Your call** | — |

### D12 · Brand — recommend: keep Kazi-Kasi, but check the name first

| | |
|---|---|
| **Question** | Do we build on "Kazi-Kasi"? |
| **Options** | (a) Keep, with a trademark/domain check · (b) Rename before launch · (c) Keep for beta, rename for market |
| **Recommendation** | **(a)** — but the check is not optional |
| **Why** | "Kazi" (work) + "kasi" (speed/rate) is a strong, locally legible name. But at least four Kenyan products already use the prefix — **KaziChat, KaziKit, KaziNest, SwiftKazi**. Confusion is a real risk in a market this small |
| **What it changes** | Domain, social handles, trademark filing, all copy |
| **Your call** | — |

---

## 3. Assumptions still load-bearing

Correct me if any is wrong:

1. **The product is for jobseekers, not employers** — at least through beta.
2. **Free through beta.** No paywall, no employer-paid placement.
3. **Solo or very small team**, so the system must be operable by one or two people. This is why the blueprint avoids microservices, Kafka, and a search cluster.
4. **Budget in the low hundreds of USD per month**, excluding engineering time and legal review.
5. **Web + WhatsApp before native app.** PWA, pages under 1MB, usable on a KES 8,000 phone.
6. **English first, Kiswahili second** — not a translation afterthought, but not a v1 blocker. Job text will be mixed regardless.
7. **Nairobi metro is enough of a market to matter**, even though "Africa" is the ambition.

---

## 4. Kill criteria

Write these down before building, so the decision to stop is a judgement, not a mood.

| Signal | Threshold | Interpretation |
|---|---|---|
| Coverage vs. BrighterMonday+MyJobMag union | < 85% after Phase 2 | The completeness thesis is wrong |
| Verified-live rate at 7 days | < 85% | The verification thesis is wrong |
| Feed precision at position 10 | < 0.5 after two tuning cycles | The matching thesis is wrong |
| Beta W4 retention | < 15% | It is a novelty, not a habit |
| Users cannot explain the difference from BrighterMonday in one sentence | > 50% of interviews | Positioning has failed |
| Scam-flag precision | < 0.9 | We are causing harm; pause the feature |
| Cost per active user | > $0.50/month with no path to monetisation | Unit economics do not close |

---

## 5. Decision record

| # | Decision | Chosen | Rationale | Date |
|---|---|---|---|---|
| D1 | Primary user | Early-career white-collar, 0–3 yrs | Session | 2026-10-20 |
| D2 | Wedge + secondary surface | Entry-level/internships + Radar for passive watchers | Session | 2026-10-20 |
| D2b | Wedge breadth | All white-collar entry-level, not IT only | Matches how graduates search; eligibility becomes a first-class field | 2026-10-20 |
| D3 | v1 boundary | Thin vertical slice (my call) | Speed to feedback; quality over breadth | 2026-10-20 |
| D3b | Radar timing | After the feed works | Retention product, not acquisition product | 2026-10-20 |
| D4 | Geography | Kenya first, Nairobi metro beta; EAC expansion | Session | 2026-10-20 |
| D4b | Kenya coverage | Nairobi metro only (+ Kenya-hiring remote roles) | Verification depth over national breadth | 2026-10-20 |
| D5 | Surface | Web feed + WhatsApp digest | Each does what it is good at | 2026-10-20 |
| D6 | Sources | 4 boards + PSC/county + ReliefWeb | Pending confirmation | — |
| D7 | Social lane | None in v1 | Session (implied by scope) | 2026-10-20 |
| D8 | Freshness | Per-card "last checked" + SLO page | Pending confirmation | — |
| D9 | Matching | Constraints → relevance → utility | Pending confirmation | — |
| D10 | Apply | Link out + track | Pending confirmation | — |
| D11 | Revenue | Undecided; schema kept open | Session | 2026-10-20 |
| D12 | Brand | Kazi-Kasi, pending IP check | Pending check | — |

---

## 6. The prompt pack

Standing context to give the build at the start of every phase.

### 6.1 Project context

```text
PROJECT: Kazi-Kasi — a geo-anchored hiring radar for Kenya.

THESIS
Every formal vacancy advertised in Kenya is a few thousand roles at any moment —
small enough to enumerate, verify and become the definitive record of. We index
them continuously, resolve them into one live, deduplicated, provenance-tracked
job graph, and tell one early-career jobseeker in Nairobi which roles are real,
reachable, safe and worth their time.

DECIDED
- User:              early-career white-collar, 0-3 years, all sectors
                     (IT/digital, finance, admin, operations, sales, HR,
                     NGO programme support), plus internships and attachments
- Secondary surface: Radar — passive watchers (target employers, pay movement);
                     ships after the feed works
- Market:            Kenya; Nairobi metro in beta; EAC expansion shape
- Surface:           web feed + WhatsApp digest (+ opt-in SMS fallback)
- v1:                thin vertical slice — 4 sources, one feed, verification built
- Social:            none in v1
- Revenue:           undecided; schema kept open

INVARIANTS (do not violate without asking)
1. Raw payload stored before parsing. Parsers are replayable.
2. Deterministic before generative. No LLM in the ingestion critical path.
3. No logged-in scraping, no fake accounts, no WhatsApp/Facebook groups.
4. We store jobs and employers. We never build a database of people.
5. Every job carries provenance: source, first_seen, last_seen, verified_at.
6. Never show a scam flag without naming the evidence. Flag the posting, not the person.
7. No automated decisions about a person. Rank and explain; the human decides.
8. No protected attributes or proxies in matching. Audit county-level leakage.
9. Every merge is reversible; source records are never destroyed.
10. Personal data stays on a server in Kenya (DPA 2019 s.50).
11. Every page must work on a mid-range Android phone on a metered connection.
12. No metric reported without its sample size.

NON-GOALS FOR v1
Informal-economy coverage, auto-apply, CV builder, recruiter CRM, native app,
chat UI, map UI, all 47 counties, social scraping.
```

### 6.2 Phase prompts

Each phase is its own PR. Keep them small enough to review.

**Phase 1 — Spine**
```text
Build the ingestion spine.
- source_registry table + adapter interface with a YAML manifest.
- Adapters: BrighterMonday, Fuzu, MyJobMag (HTML), ReliefWeb (JSON API v2,
  requires a pre-approved appname via env var).
- Raw store, content-addressed, storing payload + headers + fetch metadata.
- Canonical schema + migrations (job, job_source_record, job_location, job_pay,
  employer, job_provenance).
- Replay tool: re-parse a date range from raw without re-crawling.
- Golden-set harness; seed 30 postings manually to start.
Acceptance: 1,000 real Kenyan postings ingested and replayable; field-fill report
per source; zero network calls in the test suite (recorded fixtures only).
```

**Phase 2 — Identity**
```text
Build entity resolution.
- Stage 1 deterministic keys, including apply-target extraction (email address,
  portal URL, PSC V/No, county reference) and the deadline in the composite key.
- Stage 2 blocking + weighted signals + confidence bands.
- LLM adjudication only for 0.80-0.95, cached by pair hash.
- Employer resolver: domain, registered name normalisation, county, fuzzy >=0.92.
- Handle the public-sector exception: identical titles inside one advert are
  separate posts, not duplicates; link them as a post_group.
Acceptance: precision >=0.97, recall >=0.90 on the labelled pairs; every merge
reversible; source records never mutated.
```

**Phase 3 — Documents and trust**
```text
Build the document pipeline and verification.
- PDF text extraction -> OCR fallback (Tesseract) -> layout parse -> LLM
  structured extraction, schema-constrained and quote-grounded.
- One document may contain N posts: model document -> post[] explicitly.
- Per-field confidence and a human review queue below 0.75.
- Lifecycle state machine with deadline-driven closure.
- Scam screening: named criteria, evidence spans, two-criteria threshold,
  report and appeal path.
Acceptance: on 75 documents (25 OCR-only), field F1 >=0.85 and date F1 >=0.90;
on 100 labelled postings, scam precision >=0.95.
```

**Phase 4 — Feed**
```text
Build the feed, explanation and WhatsApp digest.
- Feed API: cursor pagination, saved scopes, hide/report, entry_fit filter.
- Matching: constraints -> relevance -> utility, returning every factor as data.
- Card UI: title, employer, entry_fit with quoted evidence, pay vs. baseline,
  deadline, freshness proof, scam status.
- "Why this job" panel rendered from factor data, never generated prose.
- WhatsApp digest via Business API: batched, 5-8 roles max, deep links, opt-in,
  quiet hours, one-tap unsubscribe. SMS fallback for feature phones.
Acceptance: 50-user beta; every card auditable without opening a database;
digest < 20KB of data per send.
```

**Phase 5 — Geography**
```text
Build reachability.
- Kenyan address normaliser (estates, "off <road>", P.O. Box, missing numbers).
- Geocoding with confidence, plus a manual override table.
- H3 r7/r9 + PostGIS.
- Load Digital Matatus GTFS into a router; precompute isochrones for one city,
  three time bands.
- Fallback ladder with explicit commute_confidence; fare estimates labelled.
Acceptance: p95 error <15% vs. 50 manual checks; every top-100 card shows a
commute number or an honest "distance only" label.
```

**Phase 6 — Trust surface**
```text
Build the trust surface.
- Per-source health dashboard: last success, error rate, fill-rate drift,
  OCR confidence distribution.
- Public freshness page generated from real metrics.
- Privacy: export, delete, plain-language notice in English and Kiswahili,
  retention jobs, Kenyan-hosted primary store.
- DPIA draft and a data-flow diagram suitable for a Kenyan lawyer's review.
Acceptance: a stranger can answer "how fresh is this?" and "why am I seeing
this?" from the UI alone.
```

---

## 7. What I need from you next

Short answers are fine.

1. **Do you have any of these:** a BrighterMonday/MyJobMag contact, a Kenyan lawyer, a hosting account in Kenya, or beta users lined up? Any one of them changes the first month.
2. **D6:** confirm the source set — 4 boards + PSC/one county + ReliefWeb. (Recommendation: yes.)
3. **D8–D10:** confirm published freshness, constraints→relevance→utility matching, and link-out apply. (Recommendation: yes to all three.)
4. **D12:** want me to draft the IP and domain check list for the brand, and a shortlist of fallback names?
5. **Anything in §3 assumptions** you want to overrule — especially "free through beta" and "no native app"?

---

## 8. Immediate next actions

1. Confirm D6, D8–D10 and D12 — or accept the recommendations and I will record them.
2. Start ODPC registration and pick a Kenyan host (one afternoon, unblocks Phase 1).
3. Apply for a ReliefWeb `appname` (a single form, but it gates one whole lane).
4. Read the BrighterMonday and MyJobMag terms; email both about partnership.
5. Open the Phase 1 PR: schema + two adapters + replay tool. Nothing else.
