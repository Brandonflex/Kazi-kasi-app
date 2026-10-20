# Technical Blueprint

**Companion to:** [`00-executive-brief.md`](./00-executive-brief.md) · research draft v0.1 · 2026-10-20

A design we can start building from, not a final architecture. Two principles run through everything:

> **1. Raw first.** Every payload is stored exactly as received, before parsing. If a parser is wrong, we replay; we never re-crawl to recover.
> **2. Deterministic before generative.** Regex, rules, and geography run before an LLM. Models are reserved for genuine ambiguity and for language-facing output.

---

## 1. System shape

```
                        ┌──────────────────────────────────────────────┐
                        │  SOURCE REGISTRY (adapters + policy + quota) │
                        └───────────────┬──────────────────────────────┘
                                        │
   ATS APIs ──┐                  ┌──────▼───────┐
   JSON-LD  ──┼──► FETCHER ────► │  RAW STORE   │  payload + hash + headers + policy decision
   ANOFM    ──┤   (tiered      │  (object     │
   Local    ──┤    scheduler)   │   storage)   │
   Social   ──┤                  └──────┬───────┘
   News     ──┘                         │
                                 ┌──────▼───────┐
                                 │  EXTRACTOR   │  per-provider parser → source record
                                 └──────┬───────┘
                                 ┌──────▼───────┐
                                 │ NORMALISER   │  currency, salary period, geo, occupation,
                                 │              │  work mode, seniority, skills, language
                                 └──────┬───────┘
                                 ┌──────▼───────┐
                                 │  RESOLVER    │  dedupe + entity resolution (company, job)
                                 └──────┬───────┘
                                 ┌──────▼───────┐
                                 │  LIFECYCLE   │  state machine + freshness + ghost score
                                 └──────┬───────┘
                                 ┌──────▼───────┐
                                 │  ENRICHER    │  LLM: summaries, skills, ambiguity; news context
                                 └──────┬───────┘
                                 ┌──────▼───────┐
                                 │  INDEX       │  Postgres + pgvector → search index later
                                 └──────┬───────┘
                                 ┌──────▼───────┐
                                 │  MATCHER     │  constraints → relevance → utility → explanation
                                 └──────┬───────┘
                                        │
                                   API + WEB
```

**Stack recommendation for v1** (boring on purpose):

| Layer | Choice | Why |
|---|---|---|
| Language | Python (ingestion, enrichment) + TypeScript (web) | Ecosystem for parsing/ML; TS for UI |
| DB | PostgreSQL 16 + `pgvector` + PostGIS | One database for relational, vector, and spatial; fewer moving parts |
| Queue/workflow | Temporal (or Arq/Redis as a lighter start) | Durable retries, long-running crawls, per-source rate limits |
| Raw storage | S3-compatible bucket, content-addressed | Replay without re-crawl |
| Search | Postgres FTS + trigram initially → OpenSearch/Typesense at ~1M rows | Don't buy a search cluster before you need it |
| API | FastAPI | Typed, fast to build, good OpenAPI story |
| Web | Next.js | SSR for SEO on job pages, good i18n (RO/EN) |
| Cache | Redis | Hot feed pages, isochrone cache, rate limiting |

Everything here is replaceable. The parts that are *not* replaceable are the schema, the resolver, and the source registry.

---

## 2. Canonical data model

Names are indicative; the *separation of concerns* is the point.

### 2.1 Core entities

```sql
-- One observation from one source. Never mutated after write.
job_source_record (
  id                 uuid primary key,
  source_id          text not null,          -- 'greenhouse', 'anofm', 'ejobs'
  source_job_id      text not null,          -- provider's stable id
  source_url         text not null,
  fetched_at         timestamptz not null,
  raw_payload_ref    text not null,          -- object storage key
  raw_hash           text not null,          -- sha256 of payload; change detection
  parsed             jsonb not null,         -- provider-specific parse
  parser_version     text not null,
  unique (source_id, source_job_id)
);

-- The canonical job. Many source records → one job.
job (
  id                 uuid primary key,
  company_id         uuid references company(id),
  title              text not null,
  title_normalized   text not null,
  description_md     text,
  seniority          text,                   -- intern|junior|mid|senior|lead|principal|exec
  employment_type    text,                   -- full_time|part_time|contract|internship|temporary
  work_mode          text,                   -- onsite|hybrid|remote|unknown
  work_mode_source   text,                   -- 'ats'|'jsonld'|'inferred'|'user_reported'
  occupation_code    text,                   -- ISCO-08
  cor_code           text,                   -- Romanian COR
  first_seen_at      timestamptz not null,
  last_seen_at       timestamptz not null,
  date_posted_claimed date,
  date_posted_effective date,                -- min(claimed, first_seen) — never trust the board
  status             text not null,          -- see §5 state machine
  closed_at          timestamptz,
  closed_reason      text,                   -- expired|gone|removed|filled|unknown
  ghost_level        text,                   -- null | possible | likely
  ghost_criteria     text[],                 -- named evidence only, never an unexplained score
  confidence         numeric,                -- merge confidence
  index_embedding    vector(1536)
);

job_location (
  job_id             uuid,
  h3_r9              text,                   -- ~0.1 km² cell
  h3_r7              text,                   -- ~5 km² cell
  city               text,
  county             text,                   -- județ
  siruta_code        text,
  country            text,
  lat                double precision,
  lng                double precision,
  geocode_confidence numeric,
  is_primary         boolean
);

job_salary (
  job_id             uuid,
  min_amount         numeric,
  max_amount         numeric,
  currency           char(3),
  period             text,                   -- hour|day|month|year
  gross_net          text,                   -- gross|net|unknown
  source             text,                   -- 'employer_stated'|'parsed'|'estimated'
  confidence         numeric
);

job_provenance (                              -- shown in the UI; the trust artefact
  job_id             uuid,
  source_id          text,
  source_url         text,
  first_seen_at      timestamptz,
  last_seen_at       timestamptz,
  is_primary_source  boolean,
  agrees_with        text[]                  -- other sources confirming the same role
);
```

### 2.2 Why these specific fields

- `date_posted_claimed` vs `date_posted_effective` — boards re-date postings to look fresh. We keep the claim and publish the *effective* date (earliest sighting anywhere). This single field is what makes "posted 2 days ago" honest.
- `ghost_criteria[]` — never show a ghost flag without naming the reason. A false accusation is a trust-destroying event, and an unexplained score is not defensible under Art. 86.
- `work_mode_source` — "remote" inferred from the word "remote" in a description is a different claim from an ATS `workplaceType` field. The user deserves to know which.
- `job_provenance` — the UI can say "seen on 3 sources, last verified 14 minutes ago". That is the product.

---

## 3. Ingestion: the source registry

Every source is an adapter with a manifest, so policy and code live together.

```yaml
id: greenhouse
enabled: true
access: public_json           # public_json | jsonld_crawl | licensed_api | public_registry | signal
requires_auth: false
robots_reviewed_at: 2026-10-18
terms_reviewed_at: 2026-10-18
rate_limit: { requests: 60, per: minute }
tier: hot                     # hot | warm | cold | signal
cadence_minutes: 30
supports: [full_description, structured_salary, stable_id, close_detection]
discovery: { method: url_pattern, pattern: "boards\\.greenhouse\\.io/([^/]+)" }
```

Benefits: a per-source kill switch, an auditable legal posture, per-source health and freshness metrics, and a coverage report ("we have 412 Romanian Greenhouse boards, 87 Lever, 23 Ashby").

### 3.1 Scheduling

- **Tiered polling** with jitter; never synchronous full-refresh across all sources.
- **Budgeted concurrency** per source and globally; backpressure when downstream lags.
- **Conditional requests** (`ETag`, `If-Modified-Since`) wherever supported.
- **Circuit breaker** per source: 5 consecutive failures → exponential backoff → alert; a broken source must never stall the pipeline.
- **Drift detection**: if a parser's field-fill rate for a required field drops by more than X% week-over-week, raise a schema-drift alarm. Silent nulls are how job datasets rot.

### 3.2 Change detection

Hash the normalised parsed record, not the raw bytes (HTML whitespace and tracking params churn constantly). Only changed records proceed to enrichment. Typically 90%+ of a re-poll is unchanged; without this, LLM costs explode.

---

## 4. Entity resolution

The hardest and most valuable component. Research benchmarks suggest **40–60% duplication in multi-source job data**, and that naive similarity retrieval alone is insufficient — one study found only ~40% of retrieved near-duplicate pairs were true duplicates, which is why an LLM adjudication stage materially improves precision (reported F1 ~95% for GPT-4o-class models, ~92.6% for a small efficient model, on 50k postings).

### 4.1 Two-stage matching

**Stage 1 — deterministic keys (cheap, high precision).** In order:
1. `(source_id, source_job_id)` — never merge two different records from the same source.
2. **Canonical apply URL** — extract ATS requisition ID from `boards.greenhouse.io/{co}/jobs/{id}`, `jobs.lever.co/{co}/{uuid}`, `jobs.ashbyhq.com/{co}/{uuid}`, Workday `externalPath`. *This is the single strongest signal in practice* — the same requisition across boards carries the same ATS id.
3. `(company_id, normalized_title, primary_city)` exact triple.

**Stage 2 — probabilistic merge (only for what stage 1 missed).**
- **Blocking** to avoid O(n²): same `company_id` (or fuzzy company) AND same `h3_r7` (or both remote) AND posting window within ±45 days.
- **Signals, weighted:**
  - title token overlap (Jaccard on normalised tokens, seniority tokens preserved),
  - description 5-word shingle overlap (a threshold around 0.85 is used in practitioner systems),
  - salary range equality/overlap,
  - same `date_posted` window,
  - embedding cosine similarity of title+first 1,000 chars.
- **Decision bands:** ≥ 0.95 auto-merge · 0.80–0.95 → LLM adjudication · 0.60–0.80 → human review queue · < 0.60 distinct.
- **Hard conflicts override similarity:** different employment type, incompatible seniority (intern vs. director), different city with both on-site, different salary currency/period with disjoint ranges → never merge.

**Never destructive.** A merge creates a `job_cluster` link and a canonical pointer. Source records stay. Un-merging must be a one-line operation, because it will be needed.

### 4.2 Company resolution

Company identity is a prerequisite for dedupe and for employer context. Signals, in order of precision:
1. Romanian CIF / tax code (ANOFM supplies it) — near-exact.
2. Employer domain from `hiringOrganization.sameAs` or the apply URL — high precision.
3. ATS tenant token (`greenhouse:stripe`) — high precision.
4. Normalised legal name with suffixes stripped (SRL, SA, S.A., S.R.L., GmbH, Ltd) + fuzzy match at ratio ≥ 0.92 and length ≥ 4.
5. Human review for the remainder.

Reported benchmarks put hybrid matching (fuzzy + URL + ML) at ~90–95% accuracy with false merges under 1%. That is the target; it must be *measured*, not assumed.

### 4.3 Evaluation before launch

Build a **golden set of 500 postings** spanning sources and languages, hand-labelled:
- 150 known-duplicate pairs, 150 known-distinct near-miss pairs (same company, different role; same title, different city).
- 100 postings with hand-verified close dates.
- 100 with hand-verified salary normalisation.

Report per-batch: pairwise precision/recall, cluster purity, company-match accuracy, salary field F1. No resolver change ships without the golden set.

---

## 5. Lifecycle and freshness

```
discovered ──► verified ──► open ──► suspect_closed ──► closed ──► archived
                   │           │             │
                   │           └── reopened ─┘
                   └── invalid (spam/404 on first fetch)
```

**Transitions**
| From → To | Trigger |
|---|---|
| discovered → verified | ≥1 authoritative fetch (ATS/JSON-LD/registry) with required fields present |
| verified → open | published and not expired |
| open → suspect_closed | absent from a full board fetch, or `validThrough` passed, or 2 consecutive 404/410s, or soft-404 detected |
| suspect_closed → closed | confirmed on a second check or after N hours |
| closed → open | re-appears with the same identity (counts as a *repost*, not a new job) |

**Freshness fields surfaced to users:** `first_seen`, `last_seen`, `verified_at`, `source_count`, `repost_count`.

**Ghost scoring — evidence, not vibes.** Each criterion is a named boolean:

| Criterion | Definition |
|---|---|
| `evergreen` | Open continuously > 90 days across re-checks |
| `ats_absent` | Gone from the employer's own board but still live on an aggregator |
| `re_dated` | `date_posted_claimed` moved forward by > 14 days while `first_seen` stayed put |
| `mass_posting` | Same requisition replicated across > 5 locations simultaneously |
| `no_apply_path` | No working application URL |
| `repost_loop` | Same identity closed and reopened ≥ 3 times |

Display `ghost_level` only when ≥1 criterion holds, and always list the criteria. Never show a percentage.

---

## 6. Geography: from "near me" to "reachable from my life"

### 6.1 The model

A user does not have a location. They have **anchors** and **constraints**:

```
anchor:   home | second_anchor (partner's work, school, family)
modes:    walk | transit | car | bike
budget:   max_minutes per mode, and arrival window (e.g. "in office by 09:15")
tolerance: days per week on-site (0 for fully remote)
```

**Reachability** for a job = does any of its locations fall inside the user's travel-time polygon for an accepted mode, on a representative weekday?

### 6.2 Implementation

1. **Geocode** every job location. Normalise Romanian address noise ("Sector 2", "Șos.", "Bd.", diacritics, missing numbers). Keep `geocode_confidence`; if < threshold, fall back to city centroid and *label it*.
2. **Index** with H3: `h3_r9` for precision, `h3_r7` for fast joins and market analytics.
3. **Precompute isochrones** per H3 cell per mode per time band (AM peak, PM peak, off-peak). Cache aggressively — there are only so many cells in a metro, and they don't change intraday.
4. **Query**: `jobs JOIN reachable_cells(user) ON h3_r7`, then refine with exact travel time for the top N results.
5. **Fallback ladder** when routing data is missing: transit → car isochrone → straight-line with distance decay. Always expose a `commute_confidence` label.
6. **Remote handling**: a remote job has no commute, but it does have a *time-zone and jurisdiction* constraint. Model `remote_scope` (worldwide / EU / RO / city) and `timezone_overlap_hours`.

### 6.3 Why this is defensible

The empirical literature is consistent: job attractiveness decays sharply with commute distance (one UK estimate: ~4.5× less attractive at +5 km, roughly exponential at ~0.3/km), and administrative boundaries mis-measure real labour markets — travel times or commuting flows do better. Practitioners in staffing already rank candidates by commute burden rather than straight-line distance. No consumer job product does this well. It is a genuine product idea, not a feature.

### 6.4 The "geo scope" as a first-class product object

Rather than a filter, let the user *draw* their scope:

- **Commute scope** — "≤ 35 min door-to-door by transit, Tue–Thu".
- **Relocation scope** — "Cluj, if pay ≥ +25% and rent-adjusted".
- **Remote scope** — "EU time zones, ±2h".
- **Watch scope** — "any employer within 3 km of home, even if not hiring yet" (signals lane).

Save scopes, name them, switch between them. This is the differentiator made tangible.

---

## 7. Matching and explanation

Three layers, in order. Cheap and hard-constrained first.

**Layer 1 — constraints (boolean, explainable, no model).**
Work authorisation, required language level (RO/EN), licence/certification, shift availability, minimum pay floor, on-site days tolerance, travel-time budget. Fail → excluded, with a stated reason ("requires C1 German", "on-site 5 days, your limit is 2").

**Layer 2 — relevance (retrieval + model).**
- Candidate representation: structured profile (roles, skills with years, domains, tools, languages, education) + a derived embedding.
- Job representation: title + normalised skills + seniority + domain + description embedding.
- Candidate generation: BM25/trigram over title+skills, plus pgvector ANN, plus a "same company, adjacent role" source.
- Scoring: must-have skill coverage, nice-to-have overlap, seniority distance, domain adjacency, recency of the skill in the user's history.
- **Hard rule:** never use protected attributes or their proxies (name, gender, age, nationality, photo, address beyond coarse geo). Audit for proxy leakage — postal code is a well-known ethnicity proxy.

**Layer 3 — utility (the part everyone skips).**
- **Pay vs. local baseline**: salary normalised to monthly gross RON, compared with the INS county × activity median. Show the percentile, not just the number.
- **Rent-adjusted**: net pay minus median rent for a 1-bedroom in the job's city (source: INS / local listings — to be selected).
- **Commute cost**: minutes and estimated monthly cost.
- **Employer signal**: open roles, roles closed in the last 30 days, funding/expansion news, response signals if we ever have them.

**The explanation contract.** Every card can answer, in one sentence and three factors:
> "Strong skills match (8 of 10 must-haves) · pay is 78th percentile for Cluj · 24 min by tram from your saved home · verified 11 minutes ago on the employer's own board."

If any factor is missing, say so. A blank is honest; a fabricated strength is not.

**Human-in-the-loop by design.** We rank and explain. The user decides. No auto-apply, no auto-reject, no automated outreach. This is both an ethical stance and the cleanest path through GDPR Art. 22 and the AI Act's high-risk regime.

---

## 8. "24/7" as an engineering contract

| Concern | Design |
|---|---|
| Uptime | Stateless API behind a load balancer; DB with PITR; object storage durable |
| Freshness SLO | p95 close-detection < 2h (hot), < 24h (warm); publish actuals internally and, later, publicly |
| Backpressure | Queue depth and consumer lag are first-class metrics; shed cold-tier work before hot-tier work |
| Idempotency | Every write keyed on `(source_id, source_job_id, raw_hash)`; replays are free |
| Dead letters | Per-source DLQ with a replay tool; nothing is silently dropped |
| Source health | Per-source dashboard: last success, error rate, field-fill rates, parse drift |
| Cost control | Per-source daily budget (requests + LLM tokens); hard caps with alerts |
| Observability | Structured logs with `source_id` and `job_id`; traces across fetch → parse → resolve → index |
| Secrets | No credentials in the repo; environment injection; rotate |

---

## 9. Evaluation plan

| What | How | Target |
|---|---|---|
| Extraction quality | Golden set, field-level F1 vs. human labels | title/company/location ≥ 0.95; salary ≥ 0.85 |
| Dedupe | Pairwise precision/recall on 300 labelled pairs | precision ≥ 0.97, recall ≥ 0.90 |
| Company resolution | 200 labelled employer pairs | accuracy ≥ 0.93, false-merge rate < 1% |
| Liveness | 100 postings with known fate | precision ≥ 0.95, recall ≥ 0.85 |
| Geo | 50 addresses vs. manual routing | p95 error < 15% or < 5 min |
| Ranking | NDCG@10 + user save/apply rate in beta | NDCG@10 ≥ 0.7; save rate improving week-over-week |
| Fairness | Adverse-impact ratio by proxy groups | within 0.8–1.25 |
| User trust | "Was this accurate?" thumbs on 200 cards | ≥ 85% positive |

Two rules: **no metric is reported without its sample size**, and **no ranking change ships without an offline evaluation and a fairness check**.

---

## 10. What to build first (spine, not surface)

1. `source_registry` table + 5 ATS adapters (Greenhouse, Lever, Ashby, Workday, SmartRecruiters).
2. Raw store + content-addressed hashing + replay tooling.
3. Canonical schema + migrations.
4. Board discovery for Romanian employers (the seed list is the work).
5. Golden set (500 postings) — *before* the resolver, not after.
6. Resolver stage 1 (deterministic) → measure → stage 2.
7. Lifecycle state machine + freshness/ghost criteria.
8. Geocoding + H3 + one city's isochrones.
9. Feeds API + a deliberately plain UI.
10. Instrumentation for every metric in §9.

Notice what is absent: no LLM in the critical path, no vector database, no microservices, no mobile app. Those are all later, and only if the numbers justify them.
