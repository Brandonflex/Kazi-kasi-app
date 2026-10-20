# Kazi-Kasi — Executive Brief (Kenya)

**Status:** research draft v0.2 · 2026-10-20 · supersedes v0.1 (Romania-first)
**Market:** Kenya, Nairobi metro first
**Scope of this round:** research and framing only. No product code yet.

**Read this first, then:** [`01-source-landscape.md`](./01-source-landscape.md) → [`02-technical-blueprint.md`](./02-technical-blueprint.md) → [`03-refinement-session.md`](./03-refinement-session.md) → [`04-expansion-path.md`](./04-expansion-path.md) → [`05-evidence-log.md`](./05-evidence-log.md)

---

## 1. The correction that changes the thesis

v0.1 assumed Romania. It was wrong, and the error was structural, not cosmetic: it assumed a market with dense employer ATS adoption, GDPR as the governing law, and a large advertised formal job market.

Kenya is the opposite on all three counts — and that is an advantage, not a problem.

| Assumption | Mature market (EU) | Kenya |
|---|---|---|
| Advertised formal vacancies at any moment | Hundreds of thousands | **~1,000–8,000** across every board combined |
| Employer ATS adoption | High (Greenhouse, Lever, Workday) | Low; most hire via boards, email, PDFs, and walk-ins |
| Governing privacy law | GDPR | **Data Protection Act 2019** (ODPC) — GDPR-shaped, lighter enforcement, one hard localisation rule |
| Where the labour market actually is | Mostly formal | **83.8% informal** (18.1M of 21.6M) |
| Distribution channel | Web + email | **WhatsApp**, mobile-first, data-constrained |

**The strategic unlock is in row one.** BrighterMonday — Kenya's largest generalist board — was showing ~1,104 live vacancies for the entire country on the day this was written, 695 of them in Nairobi. That is not a market you need to sample. It is a market you can **enumerate, verify, and become the definitive record of.**

Every global competitor optimises for *coverage at scale*. In Kenya the winning move is the opposite: **completeness at small scale, with proof.** That is a moat a small team can actually build, and it is worth more than an 8-million-row index nobody can trust.

---

## 2. The problem, said plainly

A 24-year-old graduate in Nairobi does not have a "not enough job listings" problem. The listings are findable. They have five other problems:

1. **The market is invisible and small.** ~1 million young people enter the labour market each year; the modern sector added roughly 105,000 jobs in 2025. The formal advertised market is a few thousand roles at a time — and it is scattered across BrighterMonday, Fuzu, MyJobMag, PSC, 47 county public service boards, ReliefWeb, LinkedIn, and hundreds of employer pages.
2. **Everyone applies to the same 40 roles.** Entry-level postings routinely draw 200–500 applications, and roughly 70% of "entry-level" adverts still demand experience. Being *early* beats being *better* — but nobody tells you what just appeared in the last hour.
3. **Scams are endemic.** Fake vacancies that ask for "registration fees", "interview fees", or send applicants to WhatsApp numbers are a known public-safety problem. A listings product that does not screen for this is actively unsafe.
4. **Distance is a real constraint, and nobody models it.** Nairobi's commute is the defining daily cost. A job in Karen and a job in Ruiru are both "Nairobi". Matatu routes, transfer count, fare, and time-of-day matter more than kilometres.
5. **Nothing is verified.** Boards re-date postings. Roles get filled and stay up. There is no "last confirmed open" stamp anywhere in the market.

**Kazi-Kasi's job: become the verified, live, reachable answer — for one city, then one region.**

---

## 3. The one idea

> **Kazi-Kasi is a geo-anchored hiring radar for Kenya.** It continuously watches every place a real job is advertised — boards, public service portals, NGO feeds, employer career pages, PDFs and notice images — resolves them into one live, deduplicated, provenance-tracked job graph, and tells one person which roles are real, reachable, safe to apply for, and worth their time.

Three commitments, unchanged by the market pivot:

| Commitment | What it means concretely | Why it is the moat |
|---|---|---|
| **Complete, not aggregated** | We aim to hold *every* formal vacancy advertised in Nairobi, not a sample. We publish coverage: "we track 94% of the roles BrighterMonday lists, plus 1,200 that never reach it." | Completeness is only credible if you can prove it, and proof requires enumeration + dedupe. Neither global player will do this city-by-city in Africa. |
| **Verified, not listed** | Every job carries `first_seen`, `last_seen`, `closed_at`, `proof[]`, a **scam flag with named evidence**, and a "last verified" stamp. | Boards re-date, roles die, and fraud is common. Verification is operationally expensive and therefore defensible. |
| **Reachable, not nearby** | Commute is modelled as matatu + walking time from your anchors, with fare and transfer count — not a radius. | Digital Matatus published Nairobi's GTFS: 135 routes, ~2,500 stops, open and free. Almost nobody builds on it. This is a real, cheap differentiator. |

### The compressed thesis

**Own Nairobi end-to-end. Then let the same adapters carry you to Kampala and Dar es Salaam, because the same three boards operate there.**

---

## 4. Who we are building for (from the session)

| Surface | User | Job to be done |
|---|---|---|
| **Feed** (primary) | Early-career **white-collar across the board**: 0–3 years in IT/digital, finance, admin, operations, sales, HR, and NGO programme support — plus internships and industrial attachments | "Show me what just opened, that I can actually get to, that I actually qualify for, and that isn't a scam." |
| **Radar** (secondary, ships after the feed) | Passive watchers: employed, not applying, watching the market | "Tell me when a company I care about hires, when pay moves, and when something better appears — without making me search." |

**Why all white-collar rather than IT only:** graduates do not search by industry vertical, they search by "anything I am eligible for". Narrowing to IT would have sharpened the source set (Fuzu's IT category, BrighterMonday's software/data section, ReliefWeb tech roles) but would have shrunk the addressable user to a fraction of the entry-level market. The cost is a noisier `entry_fit` signal across sectors, which is why eligibility extraction is treated as a first-class field rather than a filter.

These share one engine. The difference is cadence and framing: the Feed pushes *urgency*, Radar pushes *intelligence*. Radar is also the retention product for the 40+ weeks a person is not actively applying — which is most of their life.

**Deliberately not the first user:** blue-collar informal work, senior/executive, and recruiter-side sourcing. All three are real markets; none is the wedge.

---

## 5. What the market already does

| Cluster | Players (Kenya) | Strength | Gap we exploit |
|---|---|---|---|
| **General boards** | BrighterMonday (~1,100 live, 40k employers, 800k seekers, ~1,600 placements/month), Fuzu (~3M talent pool, 7.5M lifetime users) | Brand, employer relationships, application flow | Re-dated listings, no verification, no commute model, weak entry-level fit signal |
| **Aggregators** | MyJobMag (largest traffic: ~756k visits/mo), JobWeb Kenya, Careerjet KE (~94k) | Volume, SEO, government/NGO coverage | Duplication, deadline-only lifecycle, no quality signal, PDF/notice dumps |
| **Public sector** | PSC (`psckjobs.go.ke`, MyGov adverts), TSC, 47 county public service boards, Ajira Digital | Authoritative, free, high volume in bursts | Fragmented across dozens of portals; often published as scanned adverts; no alerts, no dedupe |
| **NGO / development** | ReliefWeb (free API), Devex (paid), UN careers, Impactpool | Structured, deadline-bearing, Nairobi is a global hub | None of them aggregate with private-sector roles; no local commute context |
| **AI-native (emerging)** | SwiftKazi, KaziChat, KaziKit, KaziNest | Already pitching "AI job search Kenya" | Mostly thin wrappers over scraped boards; no verification, no geography, no scam screening |
| **HR tech** | Fuzu (pivoting to AI data operations via Fuzu Atlas), corporate ATS suites | Enterprise relationships | Fuzu's attention is moving away from the job board — a window is open |

**Two conclusions.**

1. **The "AI job search" label is already taken locally, and cheaply.** SwiftKazi and KaziChat already claim it. Competing on "AI matching" is a losing framing in this market — it invites direct comparison to thin wrappers. Competing on **verified completeness and safety** is not.
2. **Fuzu's pivot is a strategic opening.** It raised $3.86M, has 7.5M lifetime users and a 3M talent pool, and is now repositioning around AI data operations for global clients. That is a large incumbent turning its attention elsewhere. The entry-level segment is the one it will service least well.

### Brand note (act on this early)

There are at least four Kenyan products using the "Kazi" prefix: **KaziChat, KaziKit, KaziNest, SwiftKazi**. "Kazi-Kasi" is distinctive in combination and the Swahili meaning (work + speed/rate) is strong — but before printing anything, run a trademark and domain check in Kenya. See D12.

---

## 6. What we can actually ingest (summary)

Full detail in [`01-source-landscape.md`](./01-source-landscape.md). The important structural difference from a mature market: **there is no ATS spine here.** The spine is boards + public portals + documents.

| Lane | Best sources | Access | Quality | Verdict |
|---|---|---|---|---|
| **Kenyan boards** | BrighterMonday, Fuzu, MyJobMag, JobWeb Kenya | HTML with JSON-LD on detail pages (BrighterMonday publishes `schema.org/JobPosting`); no public API | Medium-high; full descriptions on detail pages | **Build first.** This is the spine. |
| **Public sector** | PSC/`psckjobs.go.ke`, MyGov adverts, 47 county boards, TSC, Ajira | HTML, PDF, scanned images | Authoritative but messy; bursty volume | **Build second.** High differentiation, high extraction cost. |
| **NGO / development** | ReliefWeb API v2 (free, requires a pre-approved `appname`), UN careers, Devex (paid) | JSON API | High: structured, deadline-bearing | **Build second.** Nairobi is a humanitarian hub. |
| **Employer direct** | ~300 target employer career pages and `schema.org/JobPosting` pages | HTML / JSON-LD | Highest where present | **Build third.** Small volume, best quality. |
| **Aggregator APIs** | Adzuna (no KE coverage), Jooble, JSearch | Free tiers / cheap | Low local relevance | **Skip in v1.** Global aggregators barely cover Kenya. |
| **Social / informal** | WhatsApp groups, Telegram, X, Facebook groups, LinkedIn posts | Mostly ToS-hostile or login-gated | High noise, high fraud, personal data | **Out of scope for v1.** Revisit as a *signal* lane with strict corroboration. |
| **Editorial / news** | Business Daily, The Star, Techweez, Kenyan Wall Street, county notices | RSS / HTML | Context, not records | **Enrichment.** Hiring momentum, layoffs, expansions. |

**The engineering reality nobody in this market handles well:** a large share of Kenyan vacancies are published as **PDFs, scanned newspaper adverts, or "apply by email before Friday" text**. So OCR + document parsing is a *day-one* requirement here, not an optimisation. That is also why the local wrappers are weak — it is hard, unglamorous work.

---

## 7. Legal posture (Kenya), in one page

Full treatment in [`01` §6](./01-source-landscape.md).

- **Data Protection Act 2019** governs. It is GDPR-shaped: lawful basis, purpose limitation, data-subject rights, 72-hour breach notification, DPIA for high-risk processing.
- **Registration with the ODPC is mandatory** above thresholds (turnover > KES 5M, > 10 employees, or an 18-sector list). Do it early — it is cheap and it is a credibility asset.
- **Section 50 localisation is the hard constraint:** at least one *serving copy* of personal data must be stored on a server **in Kenya**. This drives hosting choice from day one.
- **Penalties** reach KES 5M or 1% of turnover (whichever is lower) administratively, plus criminal exposure for unlawful disclosure. Smaller than GDPR, but the enforcement record is real — 357 determinations, 134 enforcement notices, 20 penalty notices by 2025.
- **AI-specific law does not exist yet.** The National AI Strategy 2025–2030 is policy, not law. The AI Bill 2026 was rejected at Senate committee stage in October 2026. The DPA is the binding instrument today; the Bill will likely return.
- **Public-sector portals are public documents, not personal data.** Scraping a PSC vacancy list is not the same risk category as scraping people. Keep that boundary absolute: **we index jobs and employers, never people.**

Design consequences: no logged-in scraping, no CV harvesting, no candidate database, no WhatsApp scraping. A published privacy notice in English and Swahili. Export and delete. A DPIA before public launch.

*Not legal advice. Get a Kenyan data-protection lawyer to review the notice and the DPIA before beta.*

---

## 8. What "constant update 24/7" means here

| Class | Sources | Cadence | Why |
|---|---|---|---|
| **Hot** | BrighterMonday, Fuzu, MyJobMag first pages; user's saved employers | 10–20 min | Early application is the product. |
| **Warm** | Full board sweeps, PSC, county boards, ReliefWeb | 1–4 h | Volume without urgency. |
| **Cold** | Employer career pages, long-tail boards | 24 h | Cheap discovery. |
| **Burst** | PSC / county mass recruitment, NGO deadline waves | event-driven | These arrive in hundreds at once; alerting must handle spikes. |

Publish the actual freshness achieved per source. "Last verified 8 minutes ago" on a card is the trust product — and it is falsifiable, which is the point.

---

## 9. Non-goals for v1

- **Indexing the informal economy.** 83.8% of Kenyan work is informal. It is also unverifiable, personal-data-heavy, WhatsApp-based, and not where our first user competes. We say this openly rather than pretending to cover it.
- **Auto-apply.** Volume application is the pathology this market already suffers from; automating it makes the product part of the problem.
- **A CV/resume builder.** Commodity, and it distracts from the data layer.
- **Recruiter CRM or candidate marketplace.** Different buyer, and it turns the user into inventory.
- **Global coverage.** Irrelevant here; global aggregators barely cover Kenya anyway.
- **WhatsApp group scraping.** ToS-hostile, personal data, and a fraud vector.

---

## 10. What success looks like

North star: **verified, reachable, relevant roles surfaced per active user per week**, validated by the user's own action (save, apply, or "I got an interview"), not clicks.

| Metric | Target |
|---|---|
| Live-role coverage vs. BrighterMonday + MyJobMag union (Nairobi, entry-level) | ≥ 95% |
| Duplicate rate in feed | < 1% |
| Verified-live rate at 7 days | ≥ 92% |
| Time-to-first-see for a new hot-source posting | p95 < 20 min |
| Scam-flag precision (flagged roles that are genuinely fraudulent) | ≥ 95%, and a low false-positive rate |
| "Why this job" agreement in user interviews | ≥ 80% |
| W4 retention (beta) | ≥ 20% |

Guardrails: false scam accusations are a trust event and a potential defamation exposure — always name the evidence and allow a correction path.

---

## 11. Risks, ranked

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Board access blocked or terms tightened | Medium | High | Adapter abstraction; polite crawling; pursue partnership with at least one board; never depend on a single source |
| 2 | Document extraction (PDF/scan) quality too low | High | High | OCR + LLM extraction with confidence scores; human review queue; publish per-source quality |
| 3 | Legal exposure from a false scam accusation | Medium | High | Evidence-only flags, no public naming of individuals, correction and appeal path, legal review |
| 4 | Distribution: web app doesn't reach users | High | High | WhatsApp digest from week one; PWA; <1MB pages |
| 5 | Data residency (s50) adds cost and complexity | High | Medium | Choose a Kenyan host for the primary store from the start; replicate outward, not inward |
| 6 | Monetisation unclear (undecided) | High | Medium | Keep schema open for B2B; no employer-paid ranking in the feed, ever |
| 7 | Incumbent response (BrighterMonday/Fuzu) | Low | Medium | They are optimising for employer revenue and AI data ops, not verification — move fast on the trust layer |
| 8 | Brand collision with existing "Kazi\*" products | Medium | Medium | Trademark/domain check before launch (D12) |
| 9 | Informal-market expectations ("where are the kazi za mtaa?") | High | Medium | Be explicit about scope; add a clearly-labelled informal signals lane later |

---

## 12. Recommended 90-day shape

| Phase | Weeks | Output |
|---|---|---|
| **0 — Decisions** | 1 | The twelve decisions in [`03`](./03-refinement-session.md) locked; ODPC registration started; host chosen |
| **1 — Spine** | 2–4 | BrighterMonday + Fuzu + MyJobMag adapters, raw store, canonical schema, golden set of 300 postings |
| **2 — Documents** | 4–6 | PDF/scan pipeline for PSC, county boards, and notice images; OCR + confidence scoring; human review queue |
| **3 — Identity & trust** | 6–9 | Dedupe/ER with measured precision; lifecycle state machine; scam screening with named criteria |
| **4 — Feed + WhatsApp** | 9–12 | Explainable matching, "why this job", WhatsApp digest, save/hide feedback, 50–100 user closed beta |
| **5 — Geography** | 12–14 | Matatu GTFS routing, commute bands, fare estimates, "reachable by 8am" scope |

Geography is deliberately late: routing on top of unverified job identity is wasted work. It is also the most visible differentiator once the base is solid.

---

## 13. Confirmed decisions and remaining questions

**Confirmed in session:**

- **Surface (D5):** web feed **and** WhatsApp digest. The feed carries the trust artefacts; WhatsApp carries the alert.
- **Geography (D4b):** Nairobi metro only, including remote-first roles that hire in Kenya.
- **Breadth (D2b):** all white-collar entry-level, not IT only. IT/digital remains the densest source and the easiest place to prove quality.
- **Radar (D3b):** ships after the feed works. It is the retention product, not the acquisition product.

**Still open:**

1. **Board partnership or independent indexing?** A partnership with MyJobMag or BrighterMonday would accelerate coverage and reduce legal risk; it would also constrain the product. Worth one meeting each.
2. **Radar's v1 content, when it lands** — target-company hiring activity and pay movement only, or a second feed? My recommendation: the former.
3. **Monetisation.** Undecided by choice. Keep it free through beta and instrument willingness to pay; do not let employer-paid placement into the feed under any circumstances.
4. **Brand.** "Kazi-Kasi" is strong, but KaziChat, KaziKit, KaziNest and SwiftKazi already exist. Run a Kenyan trademark and domain check before launch.

My working answers, with reasoning, are in [`03-refinement-session.md`](./03-refinement-session.md).
