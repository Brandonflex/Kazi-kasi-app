# Technical Blueprint (Kenya)

**Companion to:** [`00-executive-brief.md`](./00-executive-brief.md) · draft v0.2 · 2026-10-20

A design we can start building from. Three principles run through everything, and the third is new to this market:

> **1. Raw first.** Every payload — HTML, PDF, JSON, image — is stored exactly as received before parsing. If a parser is wrong, we replay; we never re-crawl to recover.
> **2. Deterministic before generative.** Regex, rules, layout parsing, and geography run before an LLM. Models handle genuine ambiguity and language-facing output only.
> **3. Verify, don't trust.** A listing is a claim, not a fact. Every job carries evidence, a last-verified timestamp, and an explicit confidence.

---

## 1. System shape

```
   BrighterMonday ─┐
   Fuzu ───────────┤
   MyJobMag ───────┤   ┌────────────┐   ┌────────────┐   ┌────────────┐
   PSC / counties ─┼──►│  FETCHER   │──►│ RAW STORE  │──►│ EXTRACTOR  │
   ReliefWeb API ──┤   │ (tiered,   │   │ (payload + │   │ HTML / JSON│
   Employer pages ─┤   │  polite)   │   │  hash +    │   │ / PDF / OCR│
   News / RSS ─────┘   └────────────┘   │  headers)  │   └─────┬──────┘
                                        └────────────┘         │
   ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────▼──────┐
   │  MATCHER   │◄──│   INDEX    │◄──│  LIFECYCLE │◄──│  NORMALISER   │
   │ constraints│   │ Postgres + │   │ + VERIFY + │   │ KES, county,  │
   │ →relevance │   │ pgvector   │   │ SCAM SCREEN│   │ entry_fit, geo│
   │ →utility    │   └────────────┘   └─────▲──────┘   └──────┬────────┘
   └─────┬──────┘                             │                 │
         │                            ┌───────┴──────┐   ┌──────▼──────┐
         │                            │  RESOLVER    │◄──│  ENRICHER   │
         │                            │ dedupe + ER  │   │ LLM, geocode│
         │                            └──────────────┘   └─────────────┘
         ▼
   ┌──────────────────────────────────────────────────┐
   │  API  →  Web (PWA)  +  WhatsApp digest  +  SMS   │
   └──────────────────────────────────────────────────┘
```

**Stack for v1** — boring, cheap, and operable by one or two people:

| Layer | Choice | Why |
|---|---|---|
| Language | Python (ingest, extract, enrich) + TypeScript (web) | Best parsing/OCR ecosystem; TS for UI |
| DB | PostgreSQL 16 + `pgvector` + PostGIS | One database for relational, vector, spatial |
| Queue | Redis + Arq (or Celery) | Simple, sufficient at this volume |
| Raw store | S3-compatible, content-addressed, **hosted in Kenya** | Replay + DPA s.50 |
| OCR | Tesseract (pidgin/eng) → PaddleOCR fallback | Free; PDF volume is the driver |
| Search | Postgres FTS + trigram | Not enough volume to justify a search cluster |
| API | FastAPI | Typed, fast, good OpenAPI |
| Web | Next.js PWA, server-rendered, <1MB pages | Data cost is a real UX constraint |
| Messaging | WhatsApp Business API (Meta) + Africa's Talking SMS fallback | How Kenya actually communicates |
| Geo | OSRM (self-hosted) + Digital Matatus GTFS + H3 | Matatu routing is open and free |

---

## 2. Canonical data model

```sql
-- One observation from one source. Immutable after write.
job_source_record (
  id               uuid primary key,
  source_id        text not null,        -- 'brightermonday' | 'fuzu' | 'psc' | 'reliefweb'
  source_job_id    text not null,        -- board id, PSC V/No, county ref
  source_url       text not null,
  fetched_at       timestamptz not null,
  raw_ref          text not null,        -- object key
  raw_hash         text not null,        -- sha256; change detection
  content_type     text not null,        -- html | json | pdf | image
  parser_version   text not null,
  parsed           jsonb not null,
  unique (source_id, source_job_id)
);

-- The canonical job. Many source records → one job.
job (
  id                 uuid primary key,
  employer_id        uuid references employer(id),
  title              text not null,
  title_normalized   text not null,
  description_md     text,
  description_source text,               -- 'html' | 'pdf_text' | 'ocr' | 'llm'
  extraction_confidence numeric,

  seniority          text,               -- intern | attachment | graduate | junior | mid | senior
  entry_fit          text,               -- open_to_freshers | some_experience | experienced | unknown
  entry_fit_evidence text,               -- the quoted phrase that decided it
  employment_type    text,               -- full_time | part_time | contract | internship | attachment
  work_mode          text,               -- onsite | hybrid | remote | unknown
  work_mode_source   text,               -- 'posting' | 'inferred'

  occupation_code    text,               -- ISCO-08
  sector             text,

  first_seen_at      timestamptz not null,
  last_seen_at       timestamptz not null,
  date_posted_claimed date,
  date_posted_effective date,            -- earliest sighting anywhere
  deadline           date,               -- Kenyan adverts almost always state one
  status             text not null,
  closed_at          timestamptz,
  closed_reason      text,                -- deadline_passed | gone | filled | withdrawn

  scam_level         text,               -- null | suspicious | likely_scam
  scam_flags         text[],             -- named evidence only
  scam_checked_at    timestamptz,

  merge_confidence   numeric,
  index_embedding    vector(1536)
);

job_location (
  job_id        uuid,
  h3_r9         text,       -- ~0.1 km²
  h3_r7         text,       -- ~5 km²
  county        text,       -- e.g. 'Nairobi'
  sub_county    text,       -- e.g. 'Westlands'
  town          text,
  lat           double precision,
  lng           double precision,
  geocode_confidence numeric,
  is_primary    boolean
);

job_pay (
  job_id      uuid,
  min_amount  numeric,
  max_amount  numeric,
  currency    char(3) default 'KES',
  period      text,        -- month | year | day | hour
  gross_net   text,        -- gross | net | unknown
  source      text,        -- 'stated' | 'parsed' | 'estimated_from_grade' | 'unknown'
  confidence  numeric
);

employer (
  id            uuid primary key,
  name          text,
  name_norm     text,
  domain        text,
  county        text,
  is_verified   boolean default false,   -- confirmed by us, not by the board
  verified_at   timestamptz,
  scam_history_count int default 0
);

job_provenance (            -- the artefact the UI renders
  job_id        uuid,
  source_id     text,
  source_url    text,
  first_seen_at timestamptz,
  last_seen_at  timestamptz,
  is_primary    boolean,
  agrees_with   text[]
);
```

### Why these specific fields exist

- **`date_posted_claimed` vs `date_posted_effective`** — boards re-date. We keep the claim, publish the earliest sighting anywhere.
- **`deadline`** — a genuine local advantage: Kenyan adverts almost always state a closing date. It gives us a hard close signal that most sources in mature markets lack.
- **`entry_fit` + `entry_fit_evidence`** — the single most useful derived field for this user. "Fresh graduates encouraged" and "minimum 3 years" are the difference between an hour of the user's evening and a wasted one. Always show the quoted evidence.
- **`description_source`** — OCR text is not the same claim as clean HTML. The user deserves to know which.
- **`scam_flags[]`** — never a score. Named criteria, always inspectable.
- **`employer.is_verified`** — verified by *us*, not by a board's paid badge.

---

## 3. Ingestion

### 3.1 Source registry

Each adapter carries its own manifest, so policy and code travel together:

```yaml
id: brightermonday
enabled: true
access: public_html          # public_html | pdf | public_json_api | partner_api | signal
requires_auth: false
terms_reviewed_at: 2026-10-20
rate_limit: { requests: 30, per: minute }
tier: hot                    # hot | warm | cold | burst | signal
cadence_minutes: 15
supports: [full_description, deadline, jsonld_detail, stable_id]
discovery: { method: listing_pages, max_depth: 40 }
```

Gives us: a per-source kill switch, an auditable legal posture, per-source health and freshness, and a coverage number we can publish.

### 3.2 Scheduling

- Tiered polling with jitter. Never one giant synchronous sweep.
- Per-source budgets and global backpressure.
- Conditional requests (`ETag`, `If-Modified-Since`) where supported.
- Circuit breaker per source: 5 consecutive failures → exponential backoff → alert.
- **Burst handling** for PSC and county drives: hundreds of adverts can appear in an hour. These go to a separate queue so they cannot starve the hot lane.
- **Schema-drift alarm:** if a required field's fill rate drops more than X% week-over-week, raise it. Silent nulls are how job datasets rot.

### 3.3 Change detection

Hash the normalised parsed record, not raw bytes — HTML whitespace and tracking parameters churn constantly. Typically >90% of a re-poll is unchanged; without this, OCR and LLM costs explode.

### 3.4 Document pipeline (the hard part)

```
PDF ──► text layer? ──yes──► layout parse ──► structured blocks
          │
          no
          ▼
       render to image ──► OCR (Tesseract) ──► confidence per block
          │
          ▼
   LLM structured extraction (schema-constrained, quote-grounded)
          │
          ▼
   confidence < 0.75 ──► human review queue
```

Rules:
- The LLM may only output fields present in the text. Missing → `null`. **No guessing.**
- Every extracted field keeps its source span, so a human can audit it in one click.
- PSC/county adverts usually contain *many* posts in one document — this is **one document → N jobs**, not one job per URL. Model it explicitly: a `document` entity with a `post[]` array.
- Cache by `raw_hash`; a re-parse must be free.

### 3.5 ReliefWeb adapter

- API v2, free, but requires a **pre-approved `appname`**; without one you get 403/410. Apply early — it is a single form, but it is a gate.
- Filter by country = Kenya; respect their requested attribution and rate norms.

---

## 4. Entity resolution

Kenyan boards duplicate each other aggressively: MyJobMag republishes BrighterMonday, county adverts get copied to aggregators, and one PSC drive can produce 20 near-identical "Office Administrative Assistant II" postings that are genuinely *different* posts.

### 4.1 Two-stage matching

**Stage 1 — deterministic (cheap, high precision).**
1. `(source_id, source_job_id)` — never merge two records from the same source.
2. **Canonical apply target** — the email address, portal URL, or reference number (`V/No`, county ref) is the strongest cross-source key in this market. Two adverts pointing at `recruitment@sameemployer.co.ke` with the same reference are the same job.
3. `(employer_id, normalized_title, county, deadline)` exact triple.

**Stage 2 — probabilistic (only what stage 1 missed).**
- **Blocking:** same employer (or fuzzy employer) AND same county AND deadline within ±14 days.
- **Signals:** title token Jaccard, description 5-word shingle overlap, identical deadline, identical salary band, embedding cosine.
- **Bands:** ≥ 0.95 auto-merge · 0.80–0.95 LLM adjudication · 0.60–0.80 human review · < 0.60 distinct.
- **Hard conflicts override:** different reference numbers, different counties with both on-site, different employers, different deadlines >14 days apart.

**Critical Kenyan exception:** multiple identical job titles in one public-sector advert are **separate posts**, not duplicates. If they share a document and reference series but have distinct post numbers, they stay separate and are linked as a `post_group`.

**Never destructive.** Merges create links; source records survive; un-merging is one operation.

### 4.2 Employer resolution

Order of precision:
1. Employer domain from the apply URL or careers page.
2. Exact registered name (once we have a company registry match; note: Kenyan names often include "Kenya", "Ltd", "PLC", "Sacco", "County Government of…").
3. Normalised name + county + sector.
4. Fuzzy at ratio ≥ 0.92, length ≥ 4.
5. Human review for the remainder.

Target: ≥ 93% accuracy, < 1% false merges — **measured on a labelled set, not assumed.**

### 4.3 Evaluation before launch

Golden set of **300 postings**:
- 100 known-duplicate pairs (cross-board republication),
- 50 known-distinct near-misses (same title, different county or post number),
- 75 public-sector documents with hand-verified extracted fields (including at least 25 OCR-only),
- 75 with hand-verified salary or `entry_fit`.

No resolver or extractor change ships without re-running it.

---

## 5. Lifecycle, verification and scam screening

### 5.1 State machine

```
discovered ──► extracted ──► verified ──► open ──► suspect_closed ──► closed ──► archived
                    │                        │            │
                    └── needs_review         └── reopened ┘
```

| Transition | Trigger |
|---|---|
| discovered → extracted | parse succeeded above confidence threshold |
| extracted → verified | ≥1 authoritative fetch with required fields present |
| verified → open | published, deadline not passed |
| open → suspect_closed | gone from a full source sweep, or deadline passed, or 2× 404 |
| suspect_closed → closed | confirmed on a second check, or deadline passed |
| closed → open | reappears with same identity (counts as a *repost*) |

**Deadlines make this much stronger than in mature markets.** A job with a stated closing date can be closed deterministically, and a job that survives its deadline without being reposted is strong evidence of a ghost.

### 5.2 Freshness surfaced to users

`first_seen` · `last_seen` · `verified_at` · `deadline` · `source_count` · `repost_count`

Displayed as plain language: **"Seen on 3 sites · last checked 8 min ago · closes Friday."**

### 5.3 Scam screening (a safety feature, not a growth hack)

Named criteria, each a boolean with evidence:

| Criterion | Definition |
|---|---|
| `fee_requested` | Text asks for payment: "registration", "processing", "interview", "training" fee |
| `personal_number_only` | Application contact is a personal mobile number, no employer domain |
| `no_employer_identity` | No registered name, no domain, no physical address |
| `domain_mismatch` | Apply email domain does not match the named employer |
| `template_match` | Matches a known scam template (e.g. "Send KES 500 to confirm your slot") |
| `whatsapp_only` | Application is solely via a WhatsApp link with no employer presence |
| `copy_of_known_scam` | Duplicate of a previously confirmed fraudulent posting |
| `no_interview_process` | "Immediate start, no interview" combined with a fee |

**Rules:**
- Display `likely_scam` only at ≥ 2 independent criteria, or on any `fee_requested`.
- Always show the criteria and the quoted text.
- Flag the **posting**, not the person; avoid naming individuals.
- Provide a correction/appeal path and a visible "report this job" action.
- Track precision monthly. A false accusation is a trust and legal event.

---

## 6. Geography: reachability in Nairobi

### 6.1 Why this matters more here than almost anywhere

Nairobi's commute is the defining daily cost for the user. Distance is a poor proxy: 6 km in traffic can be 50 minutes, and a matatu route with two transfers can be cheaper but slower than one direct route. "Nairobi" as a location string is almost meaningless — Westlands, Karen, Ruiru, and Kitengela are different lives.

### 6.2 The model

```
anchor:   home | campus | second_anchor
modes:    matatu+walk (primary) | boda | car | walk
budget:   max_minutes, arrival window ("in office by 08:30")
fare:     max_kes_per_day (a real constraint for entry-level workers)
```

**Reachability** = is the job inside the user's travel-time polygon for an accepted mode and fare budget, for a representative weekday peak?

### 6.3 Implementation

1. **Geocode** every job. Normalise Kenyan address noise: "off Thika Road", "Opp. Yaya Centre", "P.O. Box", estate names, missing street numbers. Keep `geocode_confidence`; if low, fall back to sub-county centroid and **label it**.
2. **Index** with H3 (r9 ≈ 0.1 km², r7 ≈ 5 km²).
3. **Transit data:** Digital Matatus GTFS — 135 routes, ~2,500 stops, open and free, in Google Maps since 2015, updated in 2019 with frequency estimates. Load into OpenTripPlanner or a GTFS-aware router.
4. **Precompute** isochrones per H3 cell per mode per time band (AM peak, PM peak, off-peak, Saturday). Cache aggressively.
5. **Query:** join jobs to reachable cells, then refine the top N with exact routing.
6. **Fallback ladder:** matatu GTFS → OSRM drive/boda → straight-line with distance decay. Always expose `commute_confidence`.
7. **Fare:** matatu fares fluctuate and are not in GTFS reliably. Store a per-route estimate table, refresh it from user reports, and label it an estimate.

### 6.4 The "geo scope" as a product object

Let the user *draw* their scope, and save it:

- **Commute** — "≤ 45 min and ≤ KES 150/day by matatu, Mon–Fri".
- **Remote** — "anywhere in EAT ±1h".
- **Relocate** — "Nakuru or Kisumu if pay ≥ +30% rent-adjusted".
- **Watch** — "any employer within 3 km of home, even if not hiring" (Radar).

This is the differentiator made tangible, and it is cheap to build once the GTFS is loaded.

---

## 7. Matching and explanation

Three layers, cheapest first.

**Layer 1 — constraints (boolean, explainable, no model).**
`entry_fit` vs. the user's experience, deadline not passed, commute within budget, language requirement (English/Kiswahili), licence/certification, work authorisation, minimum pay floor. Fail → excluded, with the reason shown: *"asks for 3 years' experience; you have 1"*.

**Layer 2 — relevance (retrieval + model).**
- Candidate representation: structured profile (roles, skills with months of use, tools, education, attachment history) + embedding.
- Job representation: title + normalised skills + seniority + sector + description embedding.
- Candidate generation: BM25/trigram over title+skills, pgvector ANN, plus "same employer, adjacent role".
- Scoring: must-have coverage, nice-to-have overlap, seniority distance, sector adjacency, recency of skill use.

**Layer 3 — utility (the part everyone skips).**
- **Pay vs. local baseline:** KES normalised to monthly gross, compared with the relevant reference (statutory minimum KES 16,113.75 for general labour; sector and grade bands where known; KNBS earnings series). Show the comparison, not just the number.
- **Commute cost:** minutes, transfers, KES/day, and KES/month.
- **Net take-home estimate:** if gross is stated, show approximate net after statutory deductions.
- **Employer signal:** open roles, roles closed in the last 30 days, whether the employer is verified, scam history.

**The explanation contract.** Every card can answer in one sentence and three factors:

> "Open to fresh graduates (posting says so) · 34 min by matatu, 1 transfer, ~KES 100/day · KES 45,000–55,000/month, above the sector median for this grade · checked 9 minutes ago, closes Friday."

If a factor is missing, say so. A blank is honest; a fabricated strength is not.

**Hard rules:** never use protected attributes or proxies (name, gender, ethnicity, religion, disability, exact address). Audit county/sub-county for proxy leakage. Never auto-reject, auto-apply, or auto-contact. The user decides.

---

## 8. "24/7" as an engineering contract

| Concern | Design |
|---|---|
| Uptime | Stateless API; Kenyan-hosted primary DB with PITR; object storage durable |
| Freshness SLO | p95 new hot posting seen < 20 min; p95 close detection < 2h after deadline or removal |
| Backpressure | Queue depth and lag are first-class metrics; shed cold-tier work before hot-tier |
| Burst safety | Separate queue + rate budget for PSC/county drives |
| Idempotency | Writes keyed on `(source_id, source_job_id, raw_hash)`; replays free |
| Dead letters | Per-source DLQ with a replay tool; nothing silently dropped |
| Source health | Last success, error rate, field-fill drift, OCR confidence distribution |
| Cost control | Per-source daily budget for requests, OCR pages, and LLM tokens; hard caps with alerts |
| Data residency | Primary store in Kenya (DPA s.50); document any cross-border replica |
| Secrets | Environment injection only; never in the repo |

---

## 9. Evaluation plan

| What | How | Target |
|---|---|---|
| Extraction — HTML | 100 hand-labelled postings | title/employer/location F1 ≥ 0.95 |
| Extraction — PDF/OCR | 75 documents incl. 25 OCR-only | field F1 ≥ 0.85; date F1 ≥ 0.90 |
| Dedupe | 150 labelled pairs | precision ≥ 0.97, recall ≥ 0.90 |
| Employer resolution | 150 labelled pairs | accuracy ≥ 0.93; false merges < 1% |
| Liveness | 100 postings with known fate | precision ≥ 0.95 |
| Scam screening | 100 labelled postings (30 known scams) | precision ≥ 0.95, recall ≥ 0.70 |
| Geo | 50 addresses vs. manual routing | p95 error < 15% or < 5 min |
| Ranking | NDCG@10 + save/apply in beta | NDCG@10 ≥ 0.7 |
| Fairness | adverse-impact ratio by county/sub-county proxy | 0.8–1.25 |
| User trust | "Was this accurate?" on 200 cards | ≥ 85% positive |

**Two rules:** no metric without its sample size; no ranking change without an offline evaluation and a fairness check.

---

## 10. Build order (spine, not surface)

1. `source_registry` + 3 board adapters (BrighterMonday, Fuzu, MyJobMag) + ReliefWeb.
2. Raw store, content hashing, replay tooling, Kenyan hosting.
3. Canonical schema + migrations.
4. Golden set (300 postings) — **before** the resolver.
5. Resolver stage 1 → measure → stage 2.
6. Document pipeline (PDF/OCR) for PSC + one county; human review queue.
7. Lifecycle + deadlines + scam screening.
8. Feed API + WhatsApp digest.
9. Geocoding + H3 + matatu GTFS routing.
10. Instrumentation for every metric in §9.

Absent by design: LLM in the critical path, vector database, microservices, mobile app, chat interface. All later, and only if the numbers justify them.
