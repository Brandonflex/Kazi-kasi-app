# Phase 4 — constraints, ranking, and the freshness promise

**Status:** built and tested (286 tests, all offline) · **Network required:** no
**Depends on:** [Phase 1](./phase-1-build.md) ingestion, [Phase 2](./phase-2-build.md) graph, [Phase 3](./phase-3-build.md) documents

Phases 1–3 produced a job graph that knows what is real and what is current.
Phase 4 turns it into the thing the research actually promised: **a short,
explained list of jobs that one specific person can take, reach, and act on
today.**

It closes the three decisions that were still open in the refinement session —
**D8** (freshness), **D9** (matching), **D10** (apply) — in code rather than in
prose.

---

## 1. What runs today

```bash
python -m pytest                                              # 286 tests, no network

kazikasi profiles --db ./data/kazi.db --seed                  # the demo constraints
kazikasi match    --db ./data/kazi.db --profile demo-two-years # ranked, explained
kazikasi match    --db ./data/kazi.db --include-blocked         # and why jobs were excluded
kazikasi apply    --db ./data/kazi.db --profile demo-fresher --job <id> --applied
kazikasi slo      --db ./data/kazi.db                         # the freshness promise, measured
kazikasi serve    --db ./data/kazi.db --demo                  # /, /job/<id>, /slo, /review
```

`kazikasi match` on the synthetic corpus:

```
Otieno — finance, 2 years
  Finance Assistant (0.61): matches finance · closes in 6 days · pays above your KES 40,000 floor · 3 km away (walkable, approximate)
  Operations Assistant (0.55): matches operations · pays above your KES 40,000 floor · 4 km away (one matatu, approximate)
  Accounts Intern (0.52): matches finance · internship — entry route · 0 km away (walkable, approximate)
```

## 2. D9 — constraints, then relevance, then utility

Three stages, **in this order**, because they answer different questions and
blending them is how a feed ends up showing an impossible job at 4%.

| Stage | Question | Output |
|---|---|---|
| **Constraints** | Can this person take the job at all? | a list of blockers, or nothing |
| **Relevance** | Is it the kind of work they asked for? | 0–1 + a reason |
| **Utility** | Is it worth acting on *today*? | 0–1 + reasons |

**Gates, not scores.** Wrong eligibility, wrong work mode, wrong contract type,
outside the commute cap, outside the deadline window — excluded, with the
sentence that excluded them. A gate is binary because the underlying fact is.

Three deliberate exceptions:

- **Unknown eligibility is not disqualifying.** "not stated" is a gap in the
  advert, not a verdict about the candidate.
- **Unknown location is not a blocker.** No location means *unknown distance*,
  which is different from *far away*.
- **A pay floor never hides a job.** Most Kenyan adverts state no pay at all;
  using a floor as a filter would quietly delete half the market. It reorders.

**Weights** (relevance 0.45, utility 0.40, distance 0.15): relevance leads
because a well-timed job you cannot do is still the wrong job.

**Utility** is deadline urgency (35%), freshness (30%), source corroboration
(15%), and pay (10%), minus 0.25 for a flagged posting. Scam flags subtract
rather than gate: a flag is evidence for a human, and a wrongly hidden real job
is the worse error.

**Every number is a sentence.** No component contributes silently.

## 3. Distance without pretending to route

`geo.py` computes straight-line distance between **approximate** area centroids,
decays utility as `exp(-0.3 × km)` (the research's figure: ~4.5× less attractive
at +5 km), and shows the user a *band* — walkable, one matatu, long commute,
across the metro — rather than a decimal.

- Coordinates are labelled approximate everywhere they surface (they are good to
  a couple of km, not to a street).
- Only areas we actually know are resolved; anything else falls back to county,
  then to `None`.
- `commute_utility(None)` is **0.5** — unknown, not zero. Punishing a missing
  field teaches the ranking to prefer well-published employers over good jobs.
- The GTFS matatu data in the research pack is the upgrade path: same interface,
  real travel times.

## 4. D8 — the freshness promise, as a number

The claim is "current data, constant update". `slo.py` makes it checkable:

- each source's **target cadence** comes from its `Manifest`;
- its state is computed from the **last observed fetch**:
  `on_time` → `late` (1 missed cycle) → `stale` (3);
- `/slo` publishes `x of y sources within target` — **including when it is bad**.

A source that has never been fetched says `never_fetched` rather than being
quietly omitted. On the demo database, three board sources show as `late`
because the data was loaded 24 minutes ago and their targets are 15–20 minutes:
that is the page working, not the page breaking.

## 5. D10 — link out, remember, never apply

- The apply button goes to **`/go`**, which records `clicked_through` and
  redirects to the **original advert**. Applications happen on the employer's
  site.
- `applied` is only ever set because the user said so. Nothing is inferred from
  a page view.
- `dismissed` ("Not for me") removes a job from that profile's feed and is the
  strongest signal the product collects.

`tracking.source_yield()` then answers the question volume cannot: which sources
produce jobs people **act on**, not just jobs.

## 6. Schema v3, and upgrading in place

Two new tables — `profiles` (constraints, stored not inferred) and `apply_events`
(append-only). `migrate()` now applies pending versions in order instead of
assuming a fresh database, and a test starts from a v2 file and upgrades it.

## 7. What this phase deliberately does not do

- **No CV parsing, no embeddings, no LLM ranking.** The ranking is arithmetic a
  person can read and argue with. If it is wrong, it is wrong in a way that can
  be fixed in a test.
- **No WhatsApp digest.** D5 says web feed + WhatsApp; at the time of this phase
  WhatsApp was not built, and this feed was still internal (banner included).
  [Phase 5](./phase-5-build.md) builds the digest.
- **No accounts or auth.** Profiles are local rows; the demo profiles are seeded.
- **No application forms, no auto-apply.** Never.
- **No commute routing.** Bands from straight lines, labelled approximate.

## 8. Next

1. **Run the canary against the live sources for a week.** This sandbox has no
   route to them (only GitHub and PyPI are proxied), so the adapters remain
   proven against synthetic fixtures, not live pages.
2. **Persist real profiles from a sign-up**, then measure the funnel on real
   users — `clicked_through / viewed` is the first honest product metric.
3. **WhatsApp digest (D5's second half)** — built in [Phase 5](./phase-5-build.md).
