# Phase 8 — the employer dossier, and your year in the market

Part 16. Two surfaces that turn what we already hold into something a person can
act on: **who is actually hiring** (an employer page built from their own
adverts), and **what the year looked like** (a private recap that refuses to
invent outcomes).

Both exist because a job board's honest limit is that it knows the advert, not
the employer, and knows the application, not the answer. These pages say what we
know, attach the sample size, and name what is missing.

---

## 1. `/employers` — who is hiring now

One row per employer with at least one live advert: how many roles are open, the
median of the minimums they publish, and where they are.

**Ordering is by open roles, then alphabetically.** Never by spend, never by a
"featured" slot, never by a score. If that ever changes it gets a label in the
same type size as the job, and that sentence is in the page's own copy so it can
be checked against the behaviour.

## 2. `/employer/<slug>` — the dossier

Built entirely from adverts already in the corpus:

| block | what it is | the guardrail |
| --- | --- | --- |
| **Open roles** | their live adverts, soonest deadline first | links to the job pages, not a wall |
| **Median advertised minimum** | with `n` on the same line | an employer that never states pay reads *never stated*, not a market average |
| **Median run to deadline** | first seen → closing date, with `n` | measured, not assumed |
| **Families** | what they actually advertise | derived from our corpus, merged upward where thin |
| **What we can check** | adverts seen, own domain used, sources, flagged adverts | facts about the advert, not a trust score |
| **What we cannot tell you** | whether they reply, how many applied, what anyone was offered | stated plainly, on every page |

### Merging is shown, not hidden

`Haba Data Systems` and `Haba Data Systems Ltd` are the same employer. Legal
suffixes, case and punctuation are stripped for the grouping key
(`dossier.normalise`), and **when a page merges more than one spelling it lists
every spelling it merged**. A silent merge would confidently report somebody
else's history. A name that matches nothing is a 404 — we do not fuzzy-match an
employer, because the failure mode is showing a candidate the wrong company's
pay.

### Flagged adverts

The one flagged advert in the demo corpus deliberately **has no employer
identity** — so no employer page can inherit a scam flag from a posting that
never named them. When an employer genuinely does have a flagged advert, the
count appears in "what we can check" rather than being hidden.

### Not for sale

The dossier is candidate-side and free. No employer can pay to change it, and the
page says so. That is deliberately harder to walk back than a policy document.

## 3. `/year` — your year in the market

Reached from `/activity` and the ⌘K palette; **not linked publicly, not in the
sitemap, and `noindex`**. It is one person's page, computed from `apply_events`
and `profile_activity`.

It shows: roles opened, kept, applied to, closed while kept; the months you were
here and the busiest one; **the band you kept choosing** against **the band
around you** today; and *the one you almost took* — saved or opened repeatedly,
never applied to, sorted by how close it came to the deadline.

Three refusals define it:

1. **No outcome fabricated.** No rejection count, no interview rate, no score out
   of ten. We never learn what happened after an application, so any such number
   would be invented. The page says exactly that.
2. **The band is advertised minimums**, in KES a month — never "what you were
   offered", because we do not know.
3. **The shareable card names no employer.** Counts, a month, a band and the
   domain. Sharing an application is not ours to do; the card cannot leak the
   name of a company someone applied to, by construction and by test.

### Counting rules, shared with `/activity`

"Kept" means *on the shortlist and not yet sent*. The activity page shows one row
per job at its furthest state, and the year page counts the same way, so the two
cannot disagree about the same job — a property with a test, not a hope.

## 4. The demo has a past

`demo_connection(history=True)` writes thirteen deterministic events across three
months, so the deployed demo link opens on a populated record rather than an
empty shell. It is opt-in (`history=False` by default), only ever runs against an
in-memory demo database, and writes nothing but `apply_events`.

## 5. Schema

No migration. Both surfaces are read models over `jobs`, `observations` and
`apply_events`; nothing new is stored. That was the reason to build them this way:
the data to answer "does this employer actually hire" was already in the ledger.

---

## Verification

```
779 passed in 26.04s
```

`tests/test_dossier.py` — 37 tests: normalisation and slug safety, merge
disclosure, unknown-employer 404, sample sizes on every median, the no-pay
employer, closing times, the flagged-advert count, index ordering (including the
tie-break), the sitemap containing employers and excluding `/year`, the year's
counts agreeing with `/activity`, the busiest month, the band's `n`, "the one you
almost took" never being an applied job, the card naming no employer, `noindex`,
the empty-year copy, and the demo history being opt-in and deterministic.

Smoke through the WSGI shim: `/employers`, `/employer/haba-data-systems` (200),
`/employer/nope` (404), `/year`, `/activity`, `/sitemap.xml` (200), with the
deployed demo `history=True`.
