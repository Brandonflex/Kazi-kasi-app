# Kenya Source Landscape, Market Map & Legal Posture

**Companion to:** [`00-executive-brief.md`](./00-executive-brief.md) · draft v0.2 · 2026-10-20

Answers three questions: *what exists in Kenya*, *what can we legally and technically take*, and *what does it cost*.

---

## 1. Method and confidence

Desk research across public board snapshots, vendor documentation, regulator guidance, KNBS/CA statistics, and practitioner sources, October 2026.

- **Verified (V)** — documented by a regulator, vendor, or multiple independent sources.
- **Reported (R)** — one credible source; hypothesis to test.
- **Inferred (I)** — our reasoning.

Board inventory numbers are **snapshots**, not stable facts. BrighterMonday showed 1,104 live listings on the day of research; that number moves daily and is used here only to establish order of magnitude.

---

## 2. The market, mapped

### 2.1 The number that reframes the product

| Board | Live vacancies (snapshot) | Monthly visits | Notes |
|---|---|---|---|
| **BrighterMonday** | ~1,104 nationwide; 695 Nairobi; 294 entry-level; 26 internship/graduate | ~437k | Kenya's largest generalist board; Ringier / African Talent Company; ~40,000 employers, ~800,000 seekers, ~1,600 placements/month (company figures) |
| **MyJobMag** | Hundreds, heavily PSC/county/NGO | ~756k — **the largest by traffic** | Aggregates public-sector and county notices; this is where the volume of *government* hiring surfaces |
| **Fuzu** | ~1,300 reported historically; IT category showing ~115 | ~184k | 3M talent pool, 7.5M lifetime users, $3.86M Series A; repositioning toward AI data operations (Fuzu Atlas) |
| **Careerjet KE** | Mirror of other sources | ~94k | Pure aggregator |
| **PSC / psckjobs.go.ke** | Bursts of 100–1,000+ per drive | n/a | Authoritative national government vacancies |
| **47 county public service boards** | Tens to hundreds per county, bursty | n/a | e.g. Mombasa advertised ~3,000 posts in one September 2026 round |
| **ReliefWeb (Kenya filter)** | Dozens at a time | n/a | Free API; Nairobi is a global humanitarian hub |
| **Employer career pages** | Unknown; likely 1,000–3,000 | n/a | Fragmented; some publish `schema.org/JobPosting` |

**Order of magnitude: the entire formal advertised job market in Kenya is a few thousand live roles at any moment — small enough to enumerate exhaustively.**

That is the single most important fact in this document. It inverts the usual product strategy:

- You do **not** need to choose which jobs to show.
- You **do** need to prove that you are complete.
- Verification is affordable at this scale, because a human can review the entire day's new postings.
- A competitor with 8M rows cannot claim completeness in Nairobi. You can.

### 2.2 The labour-market context

| Indicator | Value | Source |
|---|---|---|
| Total recorded employment (2025) | 21.6M | KNBS Economic Survey 2026 |
| Informal employment | **18.1M (83.8%)** | KNBS 2026 |
| Wage (modern-sector) employment | 3.32M | KNBS 2026 |
| New jobs created 2025 | 822,100 — **87.2% informal** | KNBS 2026 |
| Modern-sector jobs added 2025 | ~105,300 | KNBS 2026 |
| New labour-market entrants per year | ~1M youth; >80% land informal | AFIDEP / World Bank |
| Youth NEET | ~1 in 3 | ILO SDG 8.6.1 |
| Youth unemployment, by county | 9% (Nandi, Nyeri) → 35% (Wajir); Mombasa 27% | CDI report, 2026 |
| Graduate unemployment | ~18% mid-2026 (down from 26% in 2022) | Reported, KNBS-derived |
| Applications per entry-level role | 200–500 | Industry reporting |
| Statutory minimum wage (general labourer) | KES 16,113.75/month | KNBS 2026 |

**What this means for the product:** the user's competition is the binding constraint, not the number of listings. A 24-year-old in Nairobi is not short of openings to look at; they are short of *timing, signal, safety, and a credible reason to believe they qualify.* Those are all product problems we can solve, and none of them require indexing the informal economy.

### 2.3 The competing products, honestly

| Product | What it is | Strength | Weakness we exploit |
|---|---|---|---|
| **BrighterMonday** | Generalist board, Ringier-owned | Brand, 40k employers, employer-side revenue, publishes JSON-LD on detail pages | No liveness verification, re-dated listings, no commute model, generic matching |
| **Fuzu** | Career platform → AI data-ops company | 7.5M users, 3M talent pool, GIZ partnerships, AI narrative | Attention pivoting away from the board; the entry-level segment is under-served |
| **MyJobMag** | Aggregator, public-sector heavy | Highest traffic; government/county coverage | Duplication, no quality signal, PDF/notice dumps, deadline-only lifecycle |
| **PSC / county boards** | Official portals | Authoritative; free; huge bursts | Fragmented across 48+ portals; scanned adverts; no alerts; no cross-portal search |
| **ReliefWeb / Devex / UN** | Sector-specific | Structured, deadline-bearing | Siloed from private sector; no local context |
| **SwiftKazi / KaziChat / KaziKit / KaziNest** | "AI job search Kenya" | Already marketing the category | Thin scrapers, no verification layer, no geography, no scam screening |

**The gap is not "AI." It is trust infrastructure.** In a market where a fake vacancy can cost a jobseeker their rent money, "verified open, last checked 8 minutes ago, no fee requested, employer confirmed" is a stronger promise than any match score.

---

## 3. Source inventory

Scored on access (1 hard → 5 trivial), quality, freshness, cost, legal risk (5 = low), effort, and whether it belongs in the first 90 days.

### Lane A — Kenyan job boards (the spine)

| Source | Access | What you get | Quirks | Priority |
|---|---|---|---|---|
| **BrighterMonday** | Public HTML; detail pages publish `schema.org/JobPosting` | Title, employer, location, employment type, salary band ("Confidential" often), description, deadline, sometimes AI-summarised requirements | Pagination; "recommended/endorsed" vs. sourced listings; employer pages are a useful identity anchor | **P0** |
| **Fuzu** | Public HTML per country path (`/kenya`) | Title, employer, location, posting date, "days left to apply", descriptions | Mixed content; some listings "Only on Fuzu"; country sites share structure | **P0** |
| **MyJobMag** | Public HTML | Title, employer, location, deadline, full description; heavy PSC/county/NGO coverage | Aggregated duplicates; some posts are summaries of newspaper adverts | **P0** |
| **JobWeb Kenya** | Public HTML | NGO/public-sector depth | Lower volume | P1 |
| **CareerPoint / KenyaOnline / JobsInKenya** | Public HTML | Long-tail coverage | Quality varies; duplication | P2 |

**Why boards first:** they already aggregate the fragmentation for us, they publish full descriptions on detail pages, and BrighterMonday's JSON-LD gives us structured fields for free. The job is to *verify and deduplicate* them, not to replace them.

### Lane B — Public sector (the differentiator)

| Source | Access | Notes | Priority |
|---|---|---|---|
| **PSC / psckjobs.go.ke** | HTML + PDF adverts | National government. Bursts of 100–1,000+ vacancies per drive. Adverts often reference a `V/No` and a closing date. | **P0** |
| **MyGov newspaper adverts** | PDF / scanned images | Where many PSC and parastatal vacancies are formally published. Requires OCR. | **P1** |
| **47 county public service boards** | Individual county websites, many with custom portals | Extremely fragmented. Examples: `cpsb.kirinyaga.go.ke`, `recruitment.mcpsb.go.ke`. Massive spikes (Mombasa ~3,000 posts). | **P1** |
| **TSC** (Teachers Service Commission) | `tsc.go.ke` | Large volume in bursts; national. | P2 |
| **Ajira Digital** | `ajira.go.ke` | Youth digital/freelance work; KEPSA programmes. | P2 |
| **Parastatals / SOEs** | Individual sites | Long tail | P2 |

**Why this matters strategically:** no consumer product does public-sector aggregation well. It is unglamorous, document-heavy, and high-volume — exactly the kind of work a small determined team can own. It is also where a lot of entry-level graduate employment actually is.

### Lane C — NGO / development (the easy win)

| Source | Access | Notes | Priority |
|---|---|---|---|
| **ReliefWeb API v2** | Free JSON API. **Requires a pre-approved `appname`** (applied for at `apidoc.reliefweb.int`). v1 is decommissioned and returns HTTP 410. | Jobs endpoint filters by country; fields include title, organisation, country, city, closing date, URL, sometimes salary. Excellent for Nairobi-based INGO/UN roles. | **P0** |
| **UN careers** | Public HTML/JSON | Structured by duty station; heavy process | P1 |
| **Impactpool / Devex** | Paid / login-walled | Higher-end development roles | P2 |
| **Individual INGO career pages** | Public HTML | IRC, MSF, Oxfam, Save the Children, CARE, UNHCR, IOM, APHRC, AAS | P1 |

Nairobi hosts regional offices for a large number of UN agencies and INGOs. This lane produces high-quality, deadline-bearing, well-paid roles that never appear on BrighterMonday — and ReliefWeb gives it to us through one free API.

### Lane D — Employer direct

Target list: ~300 employers — banks (Equity, KCB, NCBA, Absa, Stanbic), telcos (Safaricom, Airtel), tech (Google/Microsoft/AWS Africa offices, M-Pesa Africa, Cellulant, Twiga, Kyosk, SunCulture), BPOs, manufacturers, universities, hospitals, and the larger NGOs.

- Detect ATS by URL pattern (`myworkdayjobs.com`, `successfactors`, `taleo`, `greenhouse.io`, `lever.co`, `smartrecruiters`, `zoho`, `workable`).
- Most Kenyan employers will not use any of these — they will have a hand-rolled careers page, a PDF, or an email address.
- **This is where `schema.org/JobPosting` appears when it appears.** Parse it when present; fall back to HTML heuristics; fall back to PDF.

**Priority: P1.** Small volume, best quality, and the highest-value roles (a graduate role at Safaricom will never be exclusively on BrighterMonday).

### Lane E — Documents (the hard, defensible work)

A large share of Kenyan vacancies are published as:

- newspaper adverts (MyGov) scanned as images,
- PDFs with tables of posts and reference numbers,
- plain text with "apply by email to `recruitment@…` before 5pm on Friday",
- images shared on social media.

**Pipeline:** PDF text extraction → OCR fallback → layout-aware parsing → LLM structured extraction with confidence → human review below threshold.

This is the single biggest technical differentiator against local competitors, and the single biggest quality risk. Budget for it explicitly.

### Lane F — Social and informal (out of scope for v1)

| Source | Status | Verdict |
|---|---|---|
| **WhatsApp groups** | Where much informal hiring happens | **Do not touch.** Login-gated, personal data, unverifiable, fraud vector, no consent |
| **Facebook groups** | Login-gated, large | Out of scope |
| **Telegram public channels** | Public but unstructured | Revisit as a *signal lane* with corroboration only |
| **LinkedIn** | ToS prohibits scraping; link-out only | Link-out only; never collect profiles |
| **X** | Paid, restrictive | Out of scope |

**The corroboration rule:** a social signal is never a job. It becomes a candidate only when backed by an employer-controlled URL or an official advert, plus one independent confirmation.

### Lane G — Editorial and macro

Business Daily, The Star, Techweez, Kenyan Wall Street, county notices, KNBS releases, CA sector statistics. Use for:
- hiring momentum and expansions,
- layoffs and closures,
- pay benchmarks,
- employer context on the card ("12 open roles, 3 closed this month").

Never for job records.

---

## 4. Field-level reality check

What Kenyan sources actually return, versus what the product needs.

| Field | BrighterMonday | Fuzu | MyJobMag | PSC/county | ReliefWeb | Verdict |
|---|---|---|---|---|---|---|
| Title | ✅ | ✅ | ✅ | ✅ | ✅ | Universal |
| Employer | ✅ | ✅ | ✅ | ✅ | ✅ | Needs normalisation (Ltd, PLC, "Kenya", county suffixes) |
| Full description | ✅ detail page | ✅ | ✅ | Partial (advert) | ✅ | Boards good; public sector needs OCR |
| Stable source ID | ✅ in URL | ✅ | ✅ | Reference number (`V/No`) | ✅ | Good |
| Posted date | ⚠️ re-datable | ✅ | ⚠️ | ⚠️ advert date | ✅ | Always pair with `first_seen` |
| Deadline | ✅ | ✅ ("days left") | ✅ | ✅ | ✅ | Strong local asset — better than most EU boards |
| Salary | ⚠️ often "Confidential" | ⚠️ | ⚠️ | ✅ (scale/grade) | ❌ | **Biggest gap.** Needs parsing + KNBS baseline |
| Coordinates | ❌ | ❌ | ❌ | ❌ | Country centroid only | **We geocode ourselves** |
| Employment type | ✅ | ⚠️ | ⚠️ | ✅ | ✅ | Needs normalisation |
| Entry-level signal | ⚠️ "No Experience" filter only | ⚠️ | ⚠️ | ✅ grade-based | ✅ | **Build it ourselves** — this is a wedge |
| Scam indicators | ❌ | ❌ | ❌ | ❌ | ❌ | **Nobody does this. Build it.** |

**Two derived fields are worth more than any raw field:**

1. **`entry_fit`** — a structured judgement of whether a 0–3 year candidate can actually apply, extracted from the requirement text ("3 years experience required" vs. "fresh graduates encouraged"). The market's stated problem is that 70% of "entry-level" ads demand experience; a field that surfaces this honestly is a product.
2. **`scam_flags[]`** — named evidence: asks for a fee, contact is a personal mobile number only, employer domain does not exist, advert reproduces a known scam template, application is via WhatsApp DM. Never a score; always named criteria.

---

## 5. Cost envelope

*Inferred; validate in Phase 1. KES at ~129/USD.*

| Item | Monthly (USD) | Notes |
|---|---|---|
| Compute (1–2 small VPS in Kenya) | 30–80 | Safaricom Cloud, Angani, Truehost, or a Nairobi colo; needed for DPA s50 |
| Managed Postgres + object storage | 25–70 | Can run on the same host early |
| OCR + LLM extraction | 40–200 | PDFs are the cost driver; deterministic parsing first, LLM only on ambiguity |
| Routing (OSRM self-hosted + matatu GTFS) | 0–40 | Self-hosting keeps this near zero |
| WhatsApp Business API | 20–80 | Per-conversation pricing; digest batching keeps it low |
| SMS fallback (Africa's Talking) | 10–50 | Only for users who opt in |
| Board API / partnership (if pursued) | 0–300 | Unknown; a partnership conversation, not a listed price |
| **Total** | **≈ 125–820** | Engineering time remains the real constraint |

---

## 6. Legal and compliance posture (Kenya)

> Not legal advice. Retain Kenyan counsel for the privacy notice, the DPIA, and the scam-flagging policy before public launch.

### 6.1 The governing law

The **Data Protection Act, 2019** (DPA), enforced by the **Office of the Data Protection Commissioner (ODPC)**. It is structurally close to GDPR: lawful basis, purpose limitation, minimisation, storage limitation, data-subject rights, breach notification, DPIAs for high-risk processing.

| Requirement | Detail | Our position |
|---|---|---|
| **Registration** | Mandatory for controllers/processors above thresholds: turnover > KES 5M, or > 10 employees, or in one of 18 mandatory sectors | Register before beta. Cheap, and a credibility signal |
| **Lawful basis** | Consent, contract, legal obligation, vital interest, public interest, legitimate interest | Contract + legitimate interest for the product; explicit consent for alerts |
| **Breach notification** | ODPC within **72 hours**; processors notify controllers within 48 | Incident runbook from day one |
| **DPIA** | Required for high-risk processing | Do one before launch; ranking + profiling is squarely in scope |
| **Cross-border transfer** | Adequacy, appropriate safeguards, contract necessity, or consent | Keep the primary store in Kenya; document any transfer |
| **Localisation (s.50)** | **At least one serving copy of personal data on a server in Kenya** | Primary DB hosted in Kenya. Replicate outward, never inward-only |
| **Penalties** | Up to KES 5M or 1% of turnover (lower of), plus criminal exposure | Treat as a real constraint, not a rounding error |

**Enforcement is real.** By 2025 the ODPC had received ~9,061 complaints and issued 357 determinations, 134 enforcement notices, 20 penalty notices and 184 compensation orders. The first penalty (Oppo Kenya) was KES 5M — the maximum — for posting a customer's photograph without consent. A later case saw a penalty reduced on appeal to KES 2.5M for a first-time offender.

### 6.2 What we collect, and what we refuse to collect

| We collect | We do not collect |
|---|---|
| Job postings (public adverts) | Candidate CVs belonging to other people |
| Employer names, domains, public contact channels | Personal profiles, phone numbers of individuals, social handles |
| The user's own profile, CV, preferences | WhatsApp group content |
| Public statistics (KNBS, CA, ODPC) | Anything behind a login |

**The boundary that matters:** we are a *jobs and employers* database, not a *people* database. That single decision keeps us out of the highest-risk category of both the DPA and any future AI law, and it is also the honest thing to do.

### 6.3 AI regulation

| Instrument | Status | Consequence |
|---|---|---|
| **National AI Strategy 2025–2030** | Published March 2025; policy, not law | Direction only; no obligations |
| **Draft AI & Emerging Technologies Policy 2026** | Consultation closed 4 Aug 2026; not law | Foreshadows a registrar/registry model |
| **Artificial Intelligence Bill, 2026** | Senate Bill; first reading 2 Apr 2026; **rejected by the Senate ICT Committee in October 2026** over proportionality concerns | Not law. Likely to return in amended form. It borrowed the EU's four-tier risk model |
| **Data Protection Act 2019** | In force | **The binding instrument today** |

**Design posture:** build as if a four-tier risk regime will eventually pass. That means: explainability, human decision-making, audit logs, no automated adverse decisions, no protected attributes, and a documented risk assessment. It costs little now and saves a rebuild later.

### 6.4 Online-safety and fraud

- **Fake job adverts are a public-safety issue in Kenya**, and the "never pay for a job" message is well established. Our scam screening is therefore a genuine safety feature, not a differentiator gimmick.
- **Defamation and reputation risk:** flagging a *named employer* as fraudulent is a serious claim. Mitigate by (a) flagging the *posting* not the company where possible, (b) publishing the named evidence, (c) giving a correction/appeal path, (d) requiring high confidence before any public display.
- **Consumer protection:** no fake urgency, no invented "12 people applied", no paid placement disguised as relevance.

---

## 7. What this landscape tells us to build

1. **Boards are the spine, not the enemy.** They already aggregate the market; our value is verification, dedupe, entry-level fit, and reachability.
2. **Public sector is the differentiator nobody else will do.** PSC + 47 counties + newspaper adverts is unglamorous, document-heavy work with real volume.
3. **ReliefWeb is a free, high-quality gift.** One API, one `appname`, dozens of well-paid Nairobi roles with deadlines.
4. **Documents are the moat and the risk.** OCR + structured extraction is what separates us from a scraper.
5. **Social is out of scope, and saying so is a feature.** WhatsApp and Facebook groups are where the informal market lives; they are also unverifiable and full of fraud.
6. **The boring middle wins again:** identity, lifecycle, entry-fit, scam screening, geocoding, KES salary normalisation. None of it demos. All of it compounds.

---

## 8. Loose ends to verify in Phase 1

| Unknown | Why it matters | How to resolve |
|---|---|---|
| BrighterMonday's actual terms on automated access | Determines crawl politeness and partnership strategy | Read ToS; email partnerships |
| Whether any Kenyan board offers a partner API | Could replace months of adapter work | One meeting each with BrighterMonday and MyJobMag |
| County board coverage: how many of the 47 publish machine-readable adverts | Determines whether P1 is 5 sources or 47 | Manual audit in week 2 |
| Real duplication rate across KE sources | Global benchmarks (40–60%) may not hold at this volume | Measure on the 300-posting golden set |
| Whether employers will confirm postings to us | A "verified by employer" badge would be category-defining | Test with 10 friendly employers |
| Cost and latency of Kenyan hosting | Drives the s50 solution and unit economics | Get quotes from 2–3 providers |
| Trademark availability of "Kazi-Kasi" | Brand risk given KaziChat/KaziKit/KaziNest | Kenya IP search before launch |
