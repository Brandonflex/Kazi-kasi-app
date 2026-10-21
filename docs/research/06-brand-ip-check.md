# Brand, IP and domain check — decision D12

**Status:** draft for confirmation · **Prepared:** 20 October 2026 · **Not legal advice**

This note answers one question: *can we put "Kazi-Kasi" on a product, a domain and
an app store listing without walking into someone else's mark?* It records what
was found, what it costs to be sure, and the decision we recommend.

---

## 1. What the name means in this market

"Kazi" is Swahili for *work*. In Kenya it is not a brand word — it is the category
word. That has two consequences that pull in opposite directions:

- **Good:** instant comprehension. No explanation needed for what the product does.
- **Bad:** a mark that is descriptive of the service is the weakest kind of mark.
  It is hard to register, hard to defend, and easy for the next entrant to
  approach without infringing.

"Kazi-Kasi" (reduplication) is a coinage, which helps — a coined compound is
registrable where the bare word is not — but it does not escape the crowding,
because every search a user runs will surface the other Kazis first.

## 2. What is already using the name

Findings from a web and app-store sweep, October 2026.

| Name | What it is | Overlap with us | Risk |
| --- | --- | --- | --- |
| **KaziNow** (kazinow.ke, Kazi Now Limited) | Kenyan job platform; MTN App of the Year 2021 | **Direct** — Kenyan jobs product, same three syllables | **High** |
| **Kazi** (kaziapp.co.ke, est. 2017) | Kenyan jobs app | Direct, same category | High |
| **KaziSasa** | Kenyan jobs/opportunities app | Direct, near-identical construction (Kazi + Swahili time word) | High |
| **KaziConnect** | Kenyan professional networking | Adjacent | Medium |
| **kaziscout** (GitHub, swiftkimani) | Open-source job-search agent, described as "deepest in Africa" | Adjacent in method, not a registered brand | Medium |
| **kazi.odana.design** | African design-jobs board | Adjacent, same category | Medium |
| **KaziChat, KaziKit, KaziNest, SwiftKazi** | Various apps/services | Low direct overlap, high search noise | Low–medium |
| All Across Africa "Kazi" brand | Consumer goods | Different class | Low |
| Global "Kazi" apps (several) | Unrelated categories | Jurisdiction/class separation | Low |

**Reading of this:** we would not be entering a clear field. We would be the
* seventh or eighth* Kazi in Kenyan job search, next to at least three direct
competitors, one of which won a national app award under that name.

## 3. Trademark position (Kenya, KIPI)

- **Relevant classes.** Nice class **35** (advertising, business services,
  employment agency services — this is where job boards sit) and class **42**
  (SaaS, platform services). Class 9 (downloadable software) if a mobile app ships.
- **Registrability of "Kazi-Kasi".** Likely registrable as a word mark, because a
  coined compound is not purely descriptive. Enforcement value would be weak: the
  distinctive element is thin, and an examiner may cite earlier "Kazi" marks in
  class 35 during examination.
- **Indicative cost at KIPI** (per class, quoted 2026): search KES 1,000 + filing
  KES 3,000 + examination KES 20,000 + publication KES 1,000 ≈ **KES 25,000–40,000**
  per class, 10-year term. A compliance search plus a filed application in classes
  35 and 42 is therefore roughly **KES 50,000–80,000** — negligible next to the
  cost of being forced to rename after launch, and non-trivial for a pre-revenue
  beta.
- **Business name registration** (Companies Act, via the Business Registration
  Service) is separate from a trademark: it reserves a trading name, it does not
  stop anyone else using a similar mark.
- **Common-law position.** Kenya recognises passing off and prior use. The
  practical test is confusion in the market, and "Kazi-Kasi" beside "KaziNow" and
  "KaziSasa" in the same category is exactly the fact pattern that invites a
  complaint.

## 4. Domain and handle position

Nothing here is asserted as available; availability changes daily and must be
checked at the registrar at the moment of purchase.

| Asset | Priority | Notes |
| --- | --- | --- |
| `kazikasi.co.ke` | **Required** | `.co.ke` is the trust signal in Kenya; use KENIC-accredited registrars |
| `kazikasi.ke` | Nice to have | Second-level `.ke` restrictions vary; check registry rules |
| `kazikasi.com` | Defensive | Redirect only |
| `kazikasi.app` | Recommended | Cheap, unambiguous for the product name |
| App store display name | Check before launch | Must be unique; "Kazi-Kasi" as a display name sits beside KaziNow and KaziSasa |
| `@kazikasi` on X, Instagram, TikTok, LinkedIn, Facebook | Defensive | Squatting on handles for a Kenyan job product is plausible |

## 5. Recommendation

**Ship the code and the beta under "Kazi-Kasi" as a working name, but do not spend
on brand assets yet, and run a compliance search before any public launch.**

Concretely:

1. **Now (cost: near zero).**
   - Treat "Kazi-Kasi" as a *working* name in the repository and internal docs.
   - Design the product so the name is one configuration value, not a design
     element baked into a hundred screens.
   - Keep a shortlist of defensible coined names in reserve (below).
2. **Before public beta (cost: ~KES 50–80k).**
   - Commission a KIPI compliance search across classes 35 and 42.
   - Only if the search is clean, file the word mark in both classes.
   - Register `kazikasi.co.ke` + `kazikasi.app` before announcing anything.
3. **If the search is contested — rename.** Cheaper at beta than at 5,000 users.

### Reserve names to hold in the shortlist

Each of these keeps either the local meaning or the product promise while moving
away from the exact "Kazi + word" pattern that KaziNow, KaziSasa and KaziConnect
already occupy. All still need the same search before use.

| Candidate | Rationale | Watch out for |
| --- | --- | --- |
| **KaziNane** ("work" + nine/eight, echoing 8-4-4) | Coined compound, unmistakably Kenyan, still says "work" | Still carries the "Kazi" prefix |
| **KaziScope** | Names the product promise directly: scoped, geo-anchored | Same prefix risk; more descriptive, so weaker as a mark |
| **Mradi** ("project", "scheme") | One word, no Kazi crowding, local | Generic on its own; needs a distinctive second element |
| **FanyaKazi** ("do work") | Common phrase, immediately understood | Likely already in use; verify before shortlisting |

Best two on balance: **KaziNane** (escapes the exact crowding) and **KaziScope**
(keeps the promise, accepts the prefix risk).

## 6. Decision record

- **D12 (recommended):** proceed with "Kazi-Kasi" as a working name through the
  Phase-1 build and internal beta; **gate any public launch** on a KIPI compliance
  search in classes 35 and 42 and on registering `kazikasi.co.ke` plus
  `kazikasi.app`. Keep the name in configuration, not in hard-coded strings.
- **Rejected:** paying for logo/identity design before the search is clean.
- **Rejected:** launching as plain "Kazi" — the crowding there is total.

## 7. Checklist

- [ ] Run a KIPI compliance search, classes 35 and 42, and file the report.
- [ ] Check `kazikasi.co.ke`, `kazikasi.ke`, `kazikasi.com`, `kazikasi.app` at a
      KENIC-accredited registrar; buy the first two that are free.
- [ ] Reserve the same handle on X, Instagram, TikTok, LinkedIn.
- [ ] Check the exact app-store display name against KaziNow and KaziSasa.
- [ ] Decide the legal entity name (if any) only after the above.
- [ ] Re-run this check before any paid marketing spend.

**Sources:** public web and app-store listings (October 2026); KIPI fee schedule as
quoted by Kenyan IP practitioners. Costs are indicative and must be re-quoted.
