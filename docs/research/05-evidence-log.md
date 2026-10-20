# Evidence Log

Every non-obvious claim in this research pack, with its source and confidence level. Where a source is a vendor describing its own product, that is flagged — vendor claims are treated as *Reported*, not verified.

Confidence: **V** = verified by primary documentation or multiple independent sources · **R** = reported by one credible source · **I** = inferred by us.

---

## 1. Sources and access

| # | Claim | Source | Conf. |
|---|---|---|---|
| 1.1 | Greenhouse public job board endpoint takes no auth and returns the whole board, with `content=true` adding full HTML descriptions | [Greenhouse Job Board API docs](https://developers.greenhouse.io/job-board.html); reproduced in multiple independent technical write-ups | V |
| 1.2 | Lever postings endpoint returns a bare array; `mode=json` must be passed explicitly; EU-hosted boards live on `api.eu.lever.co` | [Lever Postings API](https://github.com/lever/postings-api); practitioner write-ups | V |
| 1.3 | Ashby's public posting API supports `includeCompensation=true` and returns structured compensation for the large majority of postings | [Ashby Job Postings API](https://developers.ashbyhq.com/docs/public-job-posting-api); third-party benchmark tables | V (endpoint) / R (coverage %) |
| 1.4 | Workday's career-site endpoint is a POST, paginated at 20, returns thin list data (`locationsText` can be `"2 Locations"`), needs one detail call per job, and has no derivable slug | Independent ATS API reference and practitioner write-ups, 2026 | V |
| 1.5 | Workday's official Staffing REST API requires OAuth per tenant, so it is unavailable to third parties | Vendor/practitioner comparisons | V |
| 1.6 | SmartRecruiters career sites publish microdata rather than JSON-LD, requiring a second extractor | Practitioner PR descriptions and ATS reference tables | R |
| 1.7 | ~7,500 companies use Greenhouse | Vendor-adjacent marketing claims | R |
| 1.8 | `schema.org/JobPosting` is used on 100K–1M domains | schema.org usage statistics | R |
| 1.9 | Google requires `title`, `description`, `datePosted`, `hiringOrganization`, `jobLocation`; recommends `validThrough`, `employmentType`, `baseSalary`, `identifier`, `directApply`, `jobLocationType`; prefers JSON-LD; one JobPosting per URL | Google Search Central / schema.org documentation, via multiple implementation guides | V |
| 1.10 | Adzuna free tier defaults to 2,500 calls/month (250/day) across 16–20 countries; commercial use needs a licence after a trial; it restricts redistribution of derived aggregates | Adzuna developer docs; independent API comparisons | V |
| 1.11 | Jooble offers a free key on request, covers 60–70 countries, returns snippets and a source name, and publishes no public limits or lifecycle fields | Jooble API page; independent comparisons | V / R |
| 1.12 | Careerjet requires a publisher key and the end user's IP and user agent on every call, and caps paging near 1,100 results | Careerjet API documentation; independent analysis | V |
| 1.13 | JSearch is a RapidAPI wrapper over Google for Jobs results, free tier 200 requests/month, no ATS coverage, no dedupe, no webhooks, freshness lag 24–48h | Vendor docs; independent comparisons | V / R (lag) |
| 1.14 | Unified jobs APIs now exist that add cross-source dedupe, `status`, `closed_at`, `ghost_score` and webhooks (e.g. JobsPipe-class vendors) | Vendor documentation and pricing pages | R |
| 1.15 | ANOFM is Romania's public employment service; employers are legally required to declare vacancies; listings carry COR codes, RON salary, county, employer CIF and contacts | [EURES Romania — living and working](https://eures.europa.eu/living-and-working/living-and-working-conditions-europe/living-and-working-conditions-romania_en); practitioner extractors | V |
| 1.16 | eJobs has roughly 15,000 ads live and answers a public JSON API without a key | Third-party extractor documentation | R |
| 1.17 | BestJobs publishes no posting dates on its list pages | Third-party extractor documentation | R |
| 1.18 | Reddit stops accepting new public API requests 31 Oct 2026, ends RSS 13 Nov 2026, and closes public API access by March 2027 | Reddit announcements as reported by TechCrunch and others, Sep–Oct 2026 | V |
| 1.19 | Bluesky's AT Protocol firehose is free and public; Jetstream is the lighter alternative; rate limit ~5,000 points/hour | [Bluesky firehose docs](https://docs.bsky.app/docs/advanced-guides/firehose); independent analyses | V / R (limit) |
| 1.20 | LinkedIn's user agreement prohibits scraping and bots; automated collection is the pattern courts have enforced against | LinkedIn User Agreement; case law below | V |

---

## 2. Legal and regulatory

| # | Claim | Source | Conf. |
|---|---|---|---|
| 2.1 | Scraping publicly accessible pages is generally not a CFAA violation; *Van Buren* narrowed "exceeds authorized access" | *hiQ Labs v. LinkedIn* (9th Cir. 2022); *Van Buren v. United States* (2021) | V |
| 2.2 | hiQ won the CFAA point and lost on breach of contract; the case ended with a $500K judgment, a permanent injunction, and hiQ's shutdown | Consent judgment, N.D. Cal., Dec 2022 | V |
| 2.3 | Logged-out scraping of public pages was held outside Meta's terms; Meta dropped the case | *Meta Platforms v. Bright Data*, N.D. Cal., Jan 2024 | V |
| 2.4 | In the EU, contract terms can restrict extraction even where database rights do not apply | *Ryanair v. PR Aviation*, CJEU C-30/14 (2015) | V |
| 2.5 | An EU *sui generis* database right can separately restrict substantial extraction | EU Database Directive; subsequent national rulings | V |
| 2.6 | The CNIL fined KASPR €240,000 over LinkedIn-derived personal data and closed the injunction only after the database was erased and collection stopped | CNIL decision; case coverage, 2025–2026 | V |
| 2.7 | The EDPB's 2026 guidance on web scraping confirms GDPR applies whenever personal data is involved, and that public posting is not consent | EDPB guidance (adopted Jul 2026) as summarised by multiple legal analyses | R |
| 2.8 | GDPR Art. 22 restricts solely automated decisions with significant effects; Art. 35 requires a DPIA for systematic evaluation of candidates | GDPR text; regulator guidance | V |
| 2.9 | Recruiting and selection AI is Annex III high-risk under the AI Act, explicitly including candidate ranking and *targeted placement of job advertisements* | Regulation (EU) 2024/1689, Annex III 4(a) | V |
| 2.10 | Regulation (EU) 2026/1744 (Digital Omnibus on AI) moved the Annex III high-risk date from 2 Aug 2026 to **2 Dec 2027**, and entered into force 27 Jul 2026 | Official Journal, 24 Jul 2026; multiple law-firm and compliance summaries | V |
| 2.11 | Article 50 transparency obligations applied on schedule from 2 Aug 2026 | Same | V |
| 2.12 | A system that profiles candidates is always high-risk; the Art. 6(3) narrow-task exemption is unavailable for it | AI Act Art. 6(3); Commission draft classification guidelines (May 2026) | R |
| 2.13 | Art. 86 gives affected persons a right to a meaningful explanation of a high-risk system's role in a decision, from Dec 2027 | AI Act Art. 86 | V |
| 2.14 | High-risk penalties reach €15M or 3% of global turnover | AI Act Art. 99 | V |

---

## 3. Data quality and pipeline

| # | Claim | Source | Conf. |
|---|---|---|---|
| 3.1 | Cross-source duplication in job data runs 40–60% overall; 60–70% for Google Jobs/aggregator-sourced records; <2% within a single ATS | Published data-methodology page of a commercial job-data vendor (Canaria) | R |
| 3.2 | Roughly 40% of near-duplicate candidate pairs retrieved by embedding similarity are true duplicates, so semantic validation (LLM) is needed | Peer-reviewed study on job-posting deduplication, *Information* (MDPI), 2026, on 50,000 postings | V |
| 3.3 | GPT-4o reached ~95.1% F1 on duplicate validation; a lightweight model (Phi-4) reached ~92.6% at much lower cost | Same study | V |
| 3.4 | Hybrid company matching (fuzzy + URL + ML) achieves ~90–95% accuracy with <1% false merges; LinkedIn company ID joins are the strongest single signal | Vendor methodology page | R |
| 3.5 | Ghost/filled-but-listed postings are commonly estimated at 15–22% of listings | Industry commentary and a 2026 study of 175k+ listings reported via Forbes | R |
| 3.6 | Posting lifetimes are board-dependent; ATS boards detect closes quickly, while LinkedIn/Indeed closures cluster at the 30-day expiry | Vendor research on posting lifespan | R |
| 3.7 | Boards re-date postings; the reliable freshness signal is first-sighting anywhere, not the claimed posted date | Multiple data-vendor methodology write-ups | R |
| 3.8 | Canonicalising the apply URL (stripping UTM/tracking params, extracting ATS requisition IDs) is the most reliable practical dedupe key | Practitioner write-ups and open-source implementations | R |
| 3.9 | Silent schema drift (a parser returning null instead of failing) is a primary cause of dataset decay; field-fill-rate monitoring is the countermeasure | Practitioner write-ups | R |

---

## 4. Geography and labour markets

| # | Claim | Source | Conf. |
|---|---|---|---|
| 4.1 | Job attractiveness decays roughly exponentially with distance (~0.3 per km in one UK estimate); a job 5 km further can be ~4.5× less attractive | Manning & Petrongolo, "How Local Are Labour Markets?", CEP Discussion Paper 1101 | V |
| 4.2 | Administrative units (MSAs, TTWAs, commuting zones) mis-measure labour markets; travel time or commuting flows perform better | Same; related spatial matching literature | V |
| 4.3 | H3 resolution 7 ≈ 5 km² per cell; resolution 9 ≈ 0.1 km² | H3 documentation | V |
| 4.4 | Travel-time isochrones and H3 travel-time matrices are commercially available and used for catchment analysis | TravelTime API documentation; public-sector labour-shed analyses | V |
| 4.5 | Staffing practitioners rank candidates by commute burden rather than straight-line distance | Industry practitioner write-ups | R |
| 4.6 | Bucharest GTFS availability for STB/Metrorex is patchy and needs verification before transit routing is promised | Our assessment from available open-data sources | I |

---

## 5. Romanian labour market

| # | Claim | Source | Conf. |
|---|---|---|---|
| 5.1 | National average net monthly earnings were RON 5,734 in June 2026 (gross RON 9,564) | INS releases as reported, Aug 2026 | V |
| 5.2 | Average net earnings in IT/programming and consultancy were RON 13,474 in June 2026 | INS release as reported | V |
| 5.3 | Bucharest average net earnings exceed RON 7,000; Cluj and Timiș exceed RON 6,000; Vaslui, Vrancea and Teleorman are below RON 4,100; Olt lowest at ~RON 3,700 | INS county data as reported | R |
| 5.4 | Statutory minimum wage is RON 4,325 gross/month from 1 July 2026 | Reported from Government decision; **verify against the Official Gazette before publishing** | R |
| 5.5 | Employee contributions: CAS 25%, CASS 10%, income tax 10% | Romanian fiscal code, widely reported | V |
| 5.6 | Romania's unemployment rate was ~6.4% in Aug 2026; employment rate ~62.7% in Q2 2026 | INS via Trading Economics | R |
| 5.7 | Romania is administratively divided into 41 județe plus București, with SIRUTA codes for localities | INS / official administrative nomenclature | V |

---

## 6. Competitive landscape

| # | Claim | Source | Conf. |
|---|---|---|---|
| 6.1 | HiringCafe indexes employer career pages directly, claims ~5.7M live jobs, filters ghost jobs, and raised $6.8M | Company statements and press, Sep 2026 | R |
| 6.2 | Jobright indexes ~8M listings and adds ~400K daily; its FAQ states it currently supports US-based jobs only | Vendor site and independent reviews | R |
| 6.3 | Simplify's free tier covers autofill + tracker; premium ~$39.99/mo | Independent reviews, 2026 | R |
| 6.4 | Teal offers unlimited free tracking and resumes; premium from ~$13/week | Independent reviews, 2026 | R |
| 6.5 | Otta was acquired by Welcome to the Jungle in Jan 2024 and rebranded; curated tech roles across UK/US/FR/ES/CZ | Press and vendor site | V |
| 6.6 | "Find the hiring manager's email" features operate in a grey zone relative to LinkedIn's ToS | Independent reviews flagging the risk | R |

---

## 7. Things we explicitly do not know yet

Honesty section. These are open, and each has an owner and a phase.

| Unknown | Why it matters | How we resolve it |
|---|---|---|
| Exact coverage of the Romanian ATS board universe | Determines whether the spine alone can fill a Bucharest feed | Board-discovery run over 1,000 RO employer domains in Phase 1 |
| Whether eJobs/BestJobs will grant API access or tolerate structured collection | Determines whether we scrape, license, or partner | Direct outreach before Phase 2 |
| Bucharest GTFS completeness and licensing | Determines whether transit commute is a launch feature | Verify by end of Phase 3 |
| Real duplication rate in Romanian sources specifically | Global benchmarks may not transfer | Measure on the 500-posting golden set |
| Whether users will accept link-out apply | Determines the retention argument | Beta interviews, W4 |
| Whether a B2B data product is viable for a small team in the EU | Determines the second act | Defer to after beta; keep schema open |
| Total legal cost of a defensible DPIA + source policy | Determines launch timeline | Get a quote before Phase 4 |
