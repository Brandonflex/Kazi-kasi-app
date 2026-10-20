# Phase 12 — search: the feed, narrowed by hand

**Status:** built and tested (901 tests, all offline) · **Network required:** no
**Depends on:** [Phase 4](./phase-4-build.md) ranking, [Phase 8](./phase-8-market.md) employer pages

The feed answers one question well — *what should I look at first?* It answers
every other question badly, because it does not know what you meant. Someone who
wants "internships in Nairobi closing in the next ten days that pay something"
was being asked to read eighteen cards and hold five facts in their head.

Search is that question, spelled out. It is a **server-rendered form with a GET
action**: no JavaScript, no debounce, no client state, and the URL is the query,
so a result can be sent to a friend or opened on a 2G phone.

---

## 1. What you can narrow by

| control | meaning | why it is a fact, not a score |
| --- | --- | --- |
| **Words** | matches title, employer, area, employment type, work mode, entry fit | the things people actually type |
| **County** | exact match on the advert's county | a county is not a preference |
| **Family** | the ranking's own role families (`it`, `admin`, `finance`, …) | one definition, shared with the feed |
| **Type** | `full_time`, `internship`, … | the advert said so |
| **Closes in N days** | deadline inside the horizon | undated adverts cannot satisfy a horizon |
| **Pay at least** | stated `pay_min` ≥ floor | see §3 — the unstated ones stay |
| **Remote or hybrid** | work mode filter | the field exists on the advert |

Words are **AND**-ed: every word has to appear somewhere in the same document.
That is stricter than most job search, and it is why an empty result is common in
a corpus this size — which is honest. "Nothing matches that" is a fact about the
market, not a reason to show something else.

## 2. Order is the feed's order

Results are ranked by the same `ranking.rank()` the feed uses, so a role cannot
be first in search and absent from the feed for different reasons. Search narrows;
it never re-sorts by "relevance" to a keyword, because that is how keyword
matching starts pretending to be judgement.

## 3. The pay floor, and the adverts that do not state pay

Most Kenyan adverts state no pay. A floor that dropped them would hide most of the
market; a floor that passed them off as "≥ KES 80,000" would be a lie.

So they are **kept, labelled "pay not stated", and counted**:

> 6 of these do not state pay, so the floor cannot include or exclude them. They
> are shown, labelled.

That sentence appears only when a floor is set and at least one such advert made
it through the other filters.

## 4. Out of scope is shown, behind a toggle, with the reason

The scorer returns roles the person cannot take — a fresher against an advert
asking two years, a Kasarani candidate against a Limuru commute. Search excludes
them by default and **counts them anyway**:

> 26 of 26 live roles match · 18 in your scope · 8 outside it

Ask for them (`include roles outside my scope`, or `?blocked=1`) and they appear
*after* the in-scope results, under **Outside your constraints**, each carrying
the blocker that failed: `needs 1–2 years`. They are never mixed in, and they
never inflate the in-scope count.

## 5. Facets come from the corpus

County and family chips are counted from live rows, ordered by count then name,
and capped at twelve. No hard-coded county list: if the graph has never seen
Mombasa, the chip does not exist. Clicking a facet keeps every other filter —
the `keep()` helper builds each URL from the current query so a chip cannot
silently reset the words you typed.

## 6. What this phase refuses to do

- **No saved searches / alerts yet.** A saved search is a subscription with a
  query attached, and subscriptions are where the consent rules live. Doing it
  properly means a schema change; doing it quickly means emailing people who did
  not ask.
- **No fuzzy matching or synonyms.** "Developer" will not find "engineer". A
  stemming pass would improve recall and worsen trust: every miss would look like
  an absence.
- **No infinite scroll.** 120 results maximum, with the count telling you the
  truth above them.
- **No indexing.** `/search` is `noindex` and `Disallow`ed in `robots.txt`;
  search-result pages are thin content, and a crawlable infinite filter space is
  how a small site wastes its crawl budget.

## 7. Where it is linked from

The feed ("Search every live role →"), the county page ("Search within Nairobi
→"), the employers index, and **⌘K** — where typing words that match no job now
opens `/search?q=<what you typed>` instead of doing nothing.

## 8. Verification

```
901 passed in 29.24s
```

`tests/test_search.py` — 27 tests: term normalisation (lower-casing,
deduplication, the single-letter floor, the cap); a term matching employer and
area as well as title; two words both having to match; an unknown word returning
nothing; the empty query returning the whole scope; exact county matching;
family filtering against the ranker's own answer; a deadline horizon excluding
undated and distant roles; remote meaning remote *or* hybrid; the pay floor
keeping unstated pay and counting it; employment type; blocked roles excluded by
default, returned separately when asked for, counted either way, and each showing
its blocker; dismissed jobs absent; saved/applied flags travelling with the row;
facets summing to the in-scope count and not changing when out-of-scope rows are
shown; the page rendering a form with no JavaScript; the query echoed back; the
count line; the empty state offering a way out; the unstated-pay note; the scope
toggle; `noindex`; absence from the sitemap and `robots.txt`; and junk numbers in
the query string returning 200 rather than a traceback.
