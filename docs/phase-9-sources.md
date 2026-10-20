# Phase 9 — the fourth source is cheap, and the fifth cannot ship by accident

Coverage is the product. A job feed that knows three boards is a feed that misses
the jobs those boards do not carry — which, in Kenya, is most public-sector and
programme work. But a source is also the most expensive thing in this codebase to
maintain, because every one of them can change its markup on a Tuesday.

This phase attacks both halves of that: **adding a source became configuration**,
and **a source that has never parsed a live page cannot reach the feed**.

---

## 1. `StructuredSource` — a source in twenty lines

`kazikasi/sources/structured.py`. A subclass declares:

```python
class CareerPoint(StructuredSource):
    manifest = Manifest(id="careerpoint", ...)
    detail_pattern = "/job/"
    listing_link_selectors = ("h2 a[href]", "h3 a[href]", "[class*='job'] a[href]")
    employer_selectors = ("[class*='company']",)
    default_employer = None       # only for single-employer sources
```

and inherits the whole parse. The order is the same one the hand-written board
adapters use, and it is the order that matters:

1. **`schema.org/JobPosting` JSON-LD**, including an `ItemList` on a listing page —
   publisher-supplied URLs, already canonical, indifferent to CSS.
2. **Selector fallbacks**, for the sites that never adopted structured data.
3. **Prose heuristics**, for the fields that are always prose (pay, deadline,
   entry fit, scam signals).

Two small behaviours keep it honest: a posting with no title falls back to the
page's `<title>` and records `title_from_page_title`; a source-wide default
employer is used only when the advert is silent and records
`employer_from_manifest`. Provenance stays visible in `parser_notes`, which is
what the canary prints.

## 2. The three P2 sources

| source | id | lane | why it matters |
| --- | --- | --- | --- |
| Career Point Kenya | `careerpoint` | structured HTML | long-tail admin and NGO roles the big boards miss |
| Teachers Service Commission | `tsc` | documents (PDF) | the largest early-career employer in the country, in bursts |
| Ajira Digital | `ajira` | documents + HTML | attachments and short digital-work contracts |

TSC and Ajira reuse the existing `BulletinAdapter` / `documents` lane: a public
sector advert is one PDF, several posts, one closing date, one inbox. TSC's
`exclude_hints` also drop registration guidelines and tenders, which sit in the
same downloads folder as the advert.

## 3. The gate: `status="unverified"`

**None of these three has been run against a live page from this build.** The
sandbox has no route to those hosts, and writing CSS selectors from memory is how
a scraper returns zero rows for a month while everything looks fine.

So:

* the manifests say `status="unverified"` and their notes say so in prose, along
  with "terms not yet reviewed";
* `pipeline.ingest()` raises `UnverifiedSource` for anything not `active`, and the
  error names the exact command that would change it:

  ```
  careerpoint is unverified: it has never parsed a live page. Run
  `kazikasi canary --source careerpoint --live`, read the output, then pass
  allow_unverified=True (CLI: --allow-unverified) if you are deliberately testing it.
  ```

* `--allow-unverified` exists for exactly one purpose: running a candidate source
  against fixtures in CI, or probing it by hand.

### Promotion is a human decision

To move `careerpoint` from `unverified` to `active`:

1. `kazikasi canary --source careerpoint --live` — it must report ≥1 detail link
   and ≥1 candidate with title, employer and description;
2. fill in `terms_reviewed_at` after reading the site's terms and `robots.txt`;
3. flip `status` to `active` in one line, in a commit that says who verified it.

That is deliberately three steps. A source is a long-term obligation, not a
config value.

## 4. What the ops page does with them

`slo.report()` now separates **enabled** from **registered**. An unverified source
reports `state="not_enabled"`, is excluded from `slo_rate`, and never turns the
page amber: a source we have deliberately not switched on is not late, and
counting it would teach everyone to ignore the colour.

---

## Verification

```
803 passed in 25.75s
```

`tests/test_p2_sources.py` — 23 tests: JSON-LD `ItemList` preferred over anchors
and canonicalised (no `utm_`), anchor fallback, empty listing, a 200-anchor page
capped at 60, JSON-LD detail fields (employer, domain, county, deadline), prose
pay marked as prose, title fallback, default employer disclosed, broken markup
does not raise, TSC taking the advert PDF and dropping the guidelines and the
tender, Ajira dropping registration and FAQ, TSC parsing a real advert PDF, the
gate raising with the canary command in the message, the gate opening with the
flag, an adapter written before `status` existed still ingesting, and the CLI
listing status for every source.

Fixtures are synthetic examples of each source's *documented structure*. They
prove the parser handles that structure; they do not claim the live site looks
like that today. That distinction is the reason the gate exists.
