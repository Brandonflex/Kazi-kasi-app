# Phase 1 — the ingestion spine

**Status:** built and tested · **Commit series:** see PR #2 · **Network required:** no, except `kazikasi canary` and `kazikasi ingest`

Phase 1 is deliberately the least exciting part of the product: turn four Kenyan
sources into clean, evidence-carrying job records, with every fetched page kept so
that anything we get wrong can be re-derived instead of re-crawled.

No database. No scheduler. No LLM. No UI. Those are Phase 2 and later, and each
gets its own PR.

---

## 1. What runs today

```bash
python -m pip install --break-system-packages -e ".[dev]"   # or: pip install -e ".[dev]"
python -m pytest                                            # 101 tests, no network

# list registered sources and their legal/cadence manifests
kazikasi sources

# fetch one source (or all), store raw payloads, parse, write JSONL
kazikasi ingest --source brightermonday --store ./data/raw --out ./data/jobs.jsonl --limit 20

# re-parse everything already stored. No network. This is the recovery path.
kazikasi replay --source brightermonday --store ./data/raw --report ./data/replay.json

# daily shape check against the live sites. Alerts when a board redesigns.
kazikasi canary --source all
```

`RELIEFWEB_APPNAME` must be set to an appname approved by ReliefWeb before the
ReliefWeb adapter can call the API. Without it the API returns 403; v1 is gone and
returns 410.

## 2. Module map

| Module | Role | Network |
| --- | --- | --- |
| `kazikasi/models.py` | `JobCandidate` (normalised job), `RawRef`, `SourceRecord`, enums as plain string sets | no |
| `kazikasi/extract.py` | All deterministic parsing: dates, pay, location/county, entry fit, employment type, work mode, seniority, JSON-LD, emails, references, scam criteria | no |
| `kazikasi/identity.py` | Cross-source identity: canonical URLs, employer keys, apply-target keys, stage-1 equality | no |
| `kazikasi/rawstore.py` | Content-addressed payload store + fetch log (filesystem and in-memory) | no |
| `kazikasi/sources/base.py` | `Manifest` (access, cadence, terms-review date) + `Adapter` contract | no |
| `kazikasi/sources/boards.py` | BrighterMonday, Fuzu, MyJobMag: JSON-LD first, CSS fallback second | no |
| `kazikasi/sources/reliefweb.py` | ReliefWeb API v2 records → candidates | no (mapping is pure) |
| `kazikasi/pipeline.py` | listing → details → store → parse → verify; HTTP client with a named UA and per-host throttle | yes |
| `kazikasi/replay.py` | Re-parse stored payloads; report field-fill rates | no |
| `kazikasi/canary.py` | Is the source still shaped the way we think? | yes |
| `kazikasi/cli.py` | `sources`, `ingest`, `replay`, `canary` | — |

## 3. Acceptance criteria, and how each is met

| Criterion | Implementation | Test |
| --- | --- | --- |
| **Deterministic extraction only; no model calls in the critical path** | `extract.py` is regex/rules/arithmetic; nothing in `pipeline.py` calls a model | `tests/test_extract.py` (49 cases) |
| **Uncertain fields report confidence or evidence, never a guess** | `entry_fit` returns `(label, quoted evidence, confidence)`; `JobPay.source` + `confidence`; `work_mode_source` distinguishes posting text from `inferred_from_location`; unknown stays `unknown` | `TestEntryFit`, `TestWorkModeAndEmployment`, `TestParsePay` |
| **Adapters emit `SourceRecord` then `JobCandidate`** | Every fetch is stored as a `RawRef` before `parse_detail` runs; the parsed dict is what a `SourceRecord` carries, the normalised job is a separate object | `test_every_payload_is_stored_before_parsing` |
| **Raw payloads content-addressed; replay needs no network** | `FileRawStore` writes `sha256`-named blobs plus a fetch log; `replay()` takes no fetcher at all | `test_replay_needs_no_fetcher_at_all` |
| **Tests run entirely off recorded fixtures** | `FixtureFetcher` raises `KeyError` on any URL it does not have, so a stray network call fails a test | `TestIngest`, `TestCanary` |
| **`entry_fit` must quote evidence** | Evidence is the surrounding text of the matched phrase, capped at ~120 chars | `test_explicit_fresher_language_quotes_evidence` |
| **Scam flags are named criteria with quoted text** | `detect_scam_flags` returns `(flags, evidence)`; `scam_level` needs two independent criteria or a direct request for money | `TestScamSignals`, `TestSuspiciousPosting` |

## 4. Decisions worth defending

**Store before parse, always.** A parser bug is the most likely bug we will ship.
Storing the payload first makes the fix a `replay`, not a re-crawl — and a re-crawl
of a Kenyan job board is exactly the moment a page changes underneath us.

**A fetch log, separate from the blob store.** Two URLs can return identical bytes
(a shared template, a syndicated copy). Content addressing would then silently lose
the fact that two URLs were seen. The `_index.jsonl` fetch log keeps one record per
fetch; replay walks the log, not the blobs.

**Deadlines come from labelled text only.** `find_deadline` requires a
"deadline / closing date / applications close" label before it will parse a date.
An unlabelled date on a job page is usually the *posting* date, and promoting it to
a deadline silently closes a live job — the single worst failure a job feed can
have.

**The dedupe key includes the deadline.** Same employer + same title + same county
+ a different closing date is, in the Kenyan public sector, usually two different
posts. Merging them would hide a real vacancy. The key is conservative by design:
missing a duplicate costs a repeated card, a false merge costs a job.

**Schema.org first, selectors second, prose third.** JSON-LD is structural and
survives redesigns; selectors are brittle; prose heuristics are needed anyway for
entry fit, pay and deadlines, because Kenyan adverts put those in sentences.

**`work_mode` is inferred, and says so.** If a posting names a physical place and
never says otherwise, we record `onsite` with source
`inferred_from_location` — not `unknown`, and not a claim about the posting's own
words.

**Canary over try/except.** The dangerous failure is a page that parses *cleanly*
into a hollow job. `kazikasi canary` asserts that a detail page still yields a
title, an employer and a place, and fails the run when it does not.

## 5. Deliberately not built in Phase 1

- **No persistence beyond the raw store.** No Postgres, no migrations, no query
  layer. That is Phase 2, together with the identity/cluster tables.
- **No scheduler or worker.** Cadence lives in each source's `Manifest` as data;
  wiring it to a runner is Phase 2.
- **No probabilistic dedupe.** Stage-1 identity is deterministic equality. Fuzzy
  matching needs a labelled golden set before it can merge anything, and merging
  wrongly is worse than not merging.
- **No LLM enrichment.** A model may later propose `entry_fit` on hard cases, but
  it must be shadowed against the deterministic label first.
- **No WhatsApp, no web feed, no notifications.** Phase 3.
- **No scraping of sources whose terms have not been reviewed** — the manifest's
  `terms_reviewed_at` exists so this stays visible rather than assumed.

## 6. Fixtures are synthetic on purpose

`tests/fixtures/` contains hand-written markup modelled on what the boards publish,
not copies of real postings. That keeps third-party copyrighted content out of the
repository while still exercising the same structural paths. When a real page
contradicts a fixture, add a new fixture beside it — do not edit the old one, or the
regression it encodes is lost.

## 7. Next

1. Persist candidates and clusters (Postgres), with the identity keys from
   `identity.py` as indexes.
2. Add PSC Kenya and one county government source — the public-sector lane is the
   least crowded and the most deadline-driven.
3. Measure: density per county, entry-fit share, dedupe rate between MyJobMag and
   BrighterMonday (research expectation: 40–60% cross-source duplication).
4. Only then: the web feed.
