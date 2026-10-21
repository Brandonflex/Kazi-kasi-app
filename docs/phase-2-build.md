# Phase 2 — the job graph

**Status:** built and tested (155 tests, all offline) · **Network required:** no
**Depends on:** [Phase 1](./phase-1-build.md) — extraction, raw store, replay, canary

Phase 1 turned pages into candidates. Phase 2 answers the questions that make a
feed trustworthy:

- *Is this the same job as that one?*
- *Is it still real?*
- *What does the whole market look like right now?*

---

## 1. What runs today

```bash
python -m pytest                                   # 155 tests, no network

kazikasi init   --db ./data/kazi.db                # create / migrate
kazikasi load   --db ./data/kazi.db --demo         # synthetic corpus (31 candidates)
kazikasi load   --db ./data/kazi.db --from ./data/jobs.jsonl
kazikasi stats  --db ./data/kazi.db                # coverage + health
kazikasi review --db ./data/kazi.db                # ambiguous pairs
kazikasi serve  --db ./data/kazi.db --demo         # read-only feed on :8765
```

`kazikasi ingest --source … --db ./data/kazi.db` now writes straight into the
graph, so the whole path is `fetch → store → parse → observations → jobs → feed`.

## 2. The model

Six tables, and the separation between them is the point.

| Table | Holds | Why it exists |
|---|---|---|
| `observations` | one thing one source said, at one time, with a parser version and an interpretation fingerprint | re-parsing is a no-op; a changed page is a new row |
| `jobs` | what a user sees, denormalised | the feed is read far more than written |
| `job_keys` | every identity key that resolves to a job | keys are how a second source finds an existing job |
| `job_members` | observation → job, with `match_reason` and confidence | every merge is explainable after the fact |
| `job_events` | append-only history (`opened`, `source_added`, `stale`, `reopened`, `closed`, `merged`) | "when did this first appear?" must not depend on the current row |
| `review_queue` | near-duplicate pairs a human should decide | a wrong merge hides a vacancy |

SQLite is the development backend because it needs no server. The schema avoids
SQLite-only types so the Postgres port is mechanical: `AUTOINCREMENT` →
`GENERATED … AS IDENTITY`, `TEXT` timestamps → `timestamptz`, and the queries are
plain SQL with no triggers.

## 3. Identity: what a key is allowed to prove

The first implementation of this was **wrong in a way worth recording**. It used
`apply_target` — reference, email, ATS id, or URL — as proof of identity. The
synthetic corpus immediately produced this:

```
Accounts Assistant   → merged into  Human Resources Officer
Junior Data Analyst  → merged into  Software Support Analyst
Nurse                → merged into  Human Resources Officer
```

Every one of those is a real, separate vacancy. They merged because they shared
`careers@company.co.ke`. A careers inbox is an **employer** signal, not a job id,
and a large employer posts twenty roles pointing at one inbox.

So keys are now tagged with what they may prove:

| Key | Exclusive? | Effect |
|---|---|---|
| reference number (`V/No`, county ref) | **yes** | merges |
| ATS requisition (Greenhouse / Lever / Ashby) | **yes** | merges |
| cultural key: employer + normalised title + county + deadline | **yes** | merges |
| careers inbox | no | merges only if titles agree **and** county and deadline do not contradict |
| apply URL / source URL | no | same rule as inbox |
| fuzzy title (Jaccard) inside the same employer block | no | ≥ 0.75 merges; 0.45–0.75 goes to review |

Hard separators, never normalised away:

- **Grade markers.** "Analyst" and "Analyst II" are different posts.
- **Deadlines.** Different closing dates are different posts — in the public
  sector this is usually "one advert, N posts", not a duplicate.
- **County.** Same title in Nairobi and Mombasa is two jobs.

Two more properties:

- **Idempotent.** Re-ingesting the same candidate returns `duplicate` and counts
  nothing twice. The unique constraint is the interpretation fingerprint.
- **Explainable.** Every row in `job_members` carries the reason
  (`key_dedupe`, `key_ref`, `shared_email+title`, `employer_title_county`, `new`).

## 4. Liveness: closed only by evidence

```
seen today ──► stale (3 days unseen) ──► suspect_closed (7 days) ──► closed
                    ▲                           │
                    └──── a sighting reopens ───┘

deadline + 2 days ──► closed (always)
```

- A passed deadline closes a job after a **two-day grace period**, because boards
  lag their own closing dates.
- A job with missing fields (`needs_review`) is a *data* problem, not a freshness
  problem: it stays visible until its deadline or a human decides.
- `scam_flags` never expire with time; a flagged posting is excluded from the
  feed entirely rather than shown with a warning.

Every transition writes a `job_events` row with the age that caused it.

## 5. Metrics

`kazikasi stats` over the synthetic corpus (31 candidates):

```
live jobs           28  (of 29 jobs)
observations        31  → duplication rate 6%
closing in 7 days    4
open to freshers    39% of live jobs
review queue         2 open
counties            Nairobi 23, Machakos 1, Kiambu 1, Kajiado 1, unresolved 2
```

Two of these are the ones to watch in production:

- **duplication rate.** Research says MyJobMag and BrighterMonday overlap by
  40–60%. A rate near zero on real data means dedupe is broken, not clean.
- **entry-fit share.** If most live jobs are `experienced`, the sources are wrong
  for the audience — not the filter.

`kazikasi review` lists the pairs that were close but not close enough. Both
current pairs are correct to be there: a title variant of the same role at the
same employer, and "Analyst II" against "Analyst".

## 6. The feed (internal)

`kazikasi serve` renders the graph as HTML with no framework, no build step and no
client-side state. It is **not** the product's feed — the real surface (web +
WhatsApp digest) is a Phase 3 decision. This one exists so the pipeline can be
judged by eye.

- `/` — live jobs, soonest deadline first, with county / eligibility / stale filters
- `/job/<id>` — the card, the quoted eligibility evidence, every source that
  carried it and how it matched, plus the event history
- `/review` — the ambiguous pairs
- `/api/jobs` — the same feed as JSON

The banner says **synthetic demo data**, because it is, and a job feed that
launders fake listings into a demo is not a good habit to build.

## 7. Deliberately not built

- **No Postgres yet.** SQLite is enough for a few thousand live jobs and zero ops.
  The migration is the first task when the feed has real users.
- **No scheduler.** `apply_liveness` is a function, not a cron job.
- **No ranking (D9).** The feed sorts by deadline. Constraints → relevance →
  utility needs real candidate data to tune against.
- **No apply tracking (D10)**, no WhatsApp, no notifications.
- **No probabilistic clustering.** Stage 3 stays unbuilt until there is a labelled
  golden set to evaluate it against; the deterministic layer plus `review_queue`
  is the honest interim.

## 8. Next

Done in [Phase 3](./phase-3-build.md): PSC and Nairobi City County, via the
document lane — the "one advert, N posts" rule now runs on real bulletin shapes.

Still to do: run the canary against the live sources for a week, add a second
county, and read the duplication rate on real data. Postgres + a scheduler come
when a feed has returning users.
