# Evidence Log (Kenya)

Every non-obvious claim in this pack, with its source and confidence. Vendor claims about their own products are treated as *Reported*, not verified.

**V** = verified by primary documentation or multiple independent sources · **R** = reported by one credible source · **I** = inferred by us.

---

## 1. Market size and board landscape

| # | Claim | Source | Conf. |
|---|---|---|---|
| 1.1 | BrighterMonday showed ~1,104 live vacancies nationwide, 695 in Nairobi, 294 entry-level and 26 internship/graduate, on 20 Oct 2026 | Live board snapshot (`brightermonday.co.ke/jobs`) | V (snapshot) |
| 1.2 | BrighterMonday reports ~40,000 employers, ~800,000 seekers and ~1,600 placements/month | BrighterMonday "About" page | R |
| 1.3 | BrighterMonday is owned by Ringier / The African Talent Company and operates across East Africa | Company profiles and board footer | R |
| 1.4 | MyJobMag is the highest-traffic recruitment site in Kenya (~756k monthly visits), ahead of BrighterMonday (~437k), Fuzu (~184k) and Careerjet KE (~94k) | SEMrush trending websites, Kenya, Jan 2026 | R |
| 1.5 | Fuzu reports a 3M talent pool and 7.5M lifetime users; it operates in Kenya, Uganda, Tanzania, Nigeria and Somalia | Fuzu site; funding coverage | R |
| 1.6 | Fuzu raised $3.86M Series A and is repositioning toward managed AI data operations ("Fuzu Atlas") | Funding coverage, 2020 (recirculated 2026); Jobtech Alliance investment note, Jul 2026 | V / R |
| 1.7 | PSC advertises national government vacancies at `publicservice.go.ke` / `psckjobs.go.ke`, often in bursts of 100–1,000+ roles published via MyGov | PSC coverage, multiple outlets, 2026 | V |
| 1.8 | County public service boards advertise separately (e.g. `cpsb.kirinyaga.go.ke`, `recruitment.mcpsb.go.ke`); Mombasa advertised ~3,000 posts in Sept 2026 | County portals; press coverage | V / R |
| 1.9 | ReliefWeb's API v2 is free, publicly accessible, returns JSON, and covers jobs; **v1 is decommissioned and returns HTTP 410**, and since 1 Nov 2025 v2 requires a pre-approved `appname` | `apidoc.reliefweb.int`; independent plugin documentation | V |
| 1.10 | BrighterMonday detail pages publish `schema.org/JobPosting` structured data | Third-party scraper documentation referencing the JSON-LD detail record | R |
| 1.11 | Kenyan "AI job search" products already exist with "Kazi" branding: KaziChat, KaziKit, KaziNest, SwiftKazi | Product sites and startup directories, 2026 | R |

---

## 2. Labour market

| # | Claim | Source | Conf. |
|---|---|---|---|
| 2.1 | Total recorded employment reached 21.6M in 2025; informal employment 18.1M (83.8%); wage employment 3.32M | KNBS Economic Survey 2026 | V |
| 2.2 | 822,100 new jobs in 2025, of which 87.2% (716,800) were informal; modern sector added ~105,300 | KNBS Economic Survey 2026 | V |
| 2.3 | ~1M young people enter the labour market annually; >80% of those employed land in informal work | AFIDEP/CAP-YEI report; World Bank estimate | R |
| 2.4 | Youth NEET is approximately 1 in 3 | ILO SDG 8.6.1 indicator, as reported | R |
| 2.5 | Youth unemployment varies from 9% (Nandi, Nyeri) to 35% (Wajir); Mombasa 27% | CDI report via Business Daily, Oct 2026 | R |
| 2.6 | Graduate unemployment ~18% mid-2026, down from a 26% peak in 2022 | Reported KNBS-derived figure | R |
| 2.7 | Entry-level postings routinely attract 200–500 applications, and ~70% of "entry-level" adverts demand experience | Industry reporting, 2026 | R |
| 2.8 | Statutory minimum wage for general labourers is KES 16,113.75/month; skilled categories ~KES 20,848.40 | KNBS 2026, as reported | R |
| 2.9 | Official unemployment rate ~5.4–5.5%, widely regarded as understating underemployment | KNBS / Trading Economics | R |

*Caveat:* Kenyan labour statistics are revised often and definitions differ (recorded employment excludes small-scale agriculture; informal-sector counts vary by survey). All figures are used for order of magnitude, not precision.

---

## 3. Connectivity, devices and payments

| # | Claim | Source | Conf. |
|---|---|---|---|
| 3.1 | 88.0M active mobile SIM subscriptions at 30 Jun 2026 (165% penetration) | Communications Authority of Kenya, Q4 FY2025/26 report | V |
| 3.2 | 52.3M smartphones and 27.4M feature phones connected | CA Kenya, Q4 FY2025/26 | V |
| 3.3 | 64.3M mobile data subscriptions; 4G/5G carried ~85.5% of mobile internet traffic | CA Kenya, Q4 FY2025/26 | V |
| 3.4 | 51.4M mobile money subscriptions (Q2 FY2025/26), ~501k agents | CA Kenya, Q2 FY2025/26 | V |
| 3.5 | Safaricom holds ~69.8% of mobile subscriptions and ~93% of domestic SMS | CA Kenya, 2026 | V |
| 3.6 | WhatsApp is used by roughly 95% of Kenyan internet users; second most popular platform after Facebook | Industry measurement, 2026 | R |
| 3.7 | Domestic SMS volume 57.1bn in FY2025/26, ~53.5 SMS per subscription per month | Industry analysis of CA data | R |

**Design consequence:** a product that assumes desktop, unlimited data, or email will fail here. Pages must be small, the digest must be WhatsApp, and SMS must exist as a fallback for feature phones.

---

## 4. Legal and regulatory

| # | Claim | Source | Conf. |
|---|---|---|---|
| 4.1 | Kenya's Data Protection Act 2019 is GDPR-shaped: lawful basis, purpose limitation, data-subject rights, breach notification, DPIA | DPA 2019 text; ODPC guidance | V |
| 4.2 | Registration with the ODPC is mandatory above thresholds: turnover > KES 5M, > 10 employees, or in one of 18 mandatory sectors | Registration Regulations 2021 (LN 207/2021) | V |
| 4.3 | Breach notification: ODPC within 72 hours; processors notify controllers within 48 hours | DPA s.43 | V |
| 4.4 | Administrative penalties up to KES 5M or 1% of annual turnover, whichever is lower; criminal offences carry fines up to KES 3M and/or up to 10 years' imprisonment | DPA ss.63, 73 | V |
| 4.5 | Section 50 requires at least one serving copy of personal data to be stored on a server or data centre **in Kenya** | DPA s.50; multiple legal summaries | V |
| 4.6 | Cross-border transfer requires adequacy, appropriate safeguards, contractual necessity, or consent | DPA ss.48–49 | V |
| 4.7 | ODPC had received ~9,061 complaints and issued 357 determinations, 134 enforcement notices, 20 penalty notices and 184 compensation orders by 2025 | ODPC enforcement summaries | R |
| 4.8 | First penalty was KES 5M against Oppo Kenya (Dec 2022) for posting a customer's photograph without consent; a later penalty was reduced to KES 2.5M on appeal | ODPC; ALN and press coverage | V / R |
| 4.9 | Kenya's National AI Strategy 2025–2030 was published in March 2025 and is policy, not law | Ministry of ICT / MICDE | V |
| 4.10 | The Draft AI and Emerging Technologies Policy 2026 closed public consultation on 4 August 2026 and is not law | MICDE; press coverage | V |
| 4.11 | The Artificial Intelligence Bill, 2026 (Senate, sponsored by Sen. Karen Nyamu) was gazetted 19 Feb 2026, received its first reading on 2 April 2026, and was **rejected by the Senate ICT Committee in October 2026** as overregulation | Senate committee coverage, The Star / Techweez, Oct 2026; EY summary | V |
| 4.12 | The AI Bill proposed a four-tier risk model modelled on the EU AI Act, an Office of the AI Commissioner, and penalties up to KES 5M / two years | Bill summaries; EY | V |
| 4.13 | "Never pay for a job" is an established public-safety message in Kenya, reflecting endemic fake-vacancy fraud | Public employment-service and media messaging | R |

**Caveat:** this is a design posture, not legal advice. Kenyan counsel should review the privacy notice, DPIA, and scam-flagging policy before public launch.

---

## 5. Geography and transit

| # | Claim | Source | Conf. |
|---|---|---|---|
| 5.1 | Digital Matatus mapped Nairobi's semi-formal matatu network into GTFS: ~135 routes and ~2,500–3,000 stops, released openly and added to Google Maps in 2015 | MIT Civic Data Design Lab; Digital Matatus; peer-reviewed paper (Journal of Transport Geography) | V |
| 5.2 | The project extended GTFS with a "continuous stops" field to represent paratransit boarding behaviour, later adopted by the GTFS community | Same | V |
| 5.3 | The dataset was updated in 2019 using rider/driver focus groups and now includes estimated frequencies | MIT Atlas of Popular Transport | R |
| 5.4 | ~3.5M people depend on matatus daily in Nairobi | MIT News, 2015 | R |
| 5.5 | Job attractiveness decays sharply with commute distance; administrative boundaries mis-measure labour markets | Manning & Petrongolo, CEP DP 1101 (UK); spatial matching literature | V |
| 5.6 | H3 resolution 7 ≈ 5 km² per cell; resolution 9 ≈ 0.1 km² | H3 documentation | V |
| 5.7 | Matatu fares are not reliably encoded in GTFS and vary by route, time, and negotiation | Digital Matatus documentation; practitioner accounts | R |

---

## 6. Data quality and pipeline practice

| # | Claim | Source | Conf. |
|---|---|---|---|
| 6.1 | Cross-source duplication in job data runs 40–60% overall; near-duplicate retrieval alone is insufficient without semantic validation | Commercial data-methodology page; peer-reviewed dedup study on 50,000 postings (*Information*, MDPI, 2026) | R / V |
| 6.2 | LLM validation of candidate duplicate pairs materially improves precision (reported F1 ~95% for a GPT-4o-class model, ~92.6% for a lightweight model) | Same study | V |
| 6.3 | Boards re-date postings; the trustworthy freshness signal is first sighting anywhere | Multiple data-vendor methodology write-ups | R |
| 6.4 | Ghost/filled-but-listed postings are commonly estimated at 15–22% of listings | Industry study of 175k+ listings, reported via Forbes, 2026 | R |
| 6.5 | Silent schema drift (parsers returning null instead of failing) is a primary cause of dataset decay; field-fill-rate monitoring is the countermeasure | Practitioner write-ups | R |
| 6.6 | Canonicalising the apply target (URL, email, or reference number) is the most reliable practical dedupe key | Practitioner implementations | R |

---

## 7. What we do not know yet

| Unknown | Why it matters | How we resolve it |
|---|---|---|
| BrighterMonday's and MyJobMag's terms on automated access | Determines crawl design and partnership strategy | Read ToS; email both in week 1 |
| Whether any Kenyan board offers a partner API | Could replace months of adapter work | One meeting each |
| How many of the 47 county boards publish machine-readable adverts | Determines whether the public-sector lane is 5 sources or 50 | Manual audit in week 2 |
| Real duplication rate across Kenyan sources | Global benchmarks may not transfer at this volume | Measure on the 300-posting golden set |
| OCR quality on MyGov/newspaper scans | Determines whether the document lane is viable | Pilot 50 documents in week 3 |
| Whether employers will confirm postings directly to us | A "verified by employer" badge would be category-defining | Test with 10 friendly employers |
| Kenyan hosting cost and latency | Drives the s.50 solution and unit economics | Quotes from 2–3 providers |
| Trademark availability of "Kazi-Kasi" | Brand risk given KaziChat/KaziKit/KaziNest | Kenya IP search before launch |
| Willingness to pay | Monetisation is undecided | Instrument in beta; no paywall until W8 |
| Whether users will accept link-out apply | Determines the retention argument | Beta interviews at W4 |
