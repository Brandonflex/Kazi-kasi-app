# Expansion Path: Kenya → East Africa → Africa

**Companion to:** [`00-executive-brief.md`](./00-executive-brief.md) · draft v0.2 · 2026-10-20

You said "Africa for the beta stages." That is the right ambition and the wrong unit of work. Here is the honest version: what actually travels, what doesn't, and the order in which it makes sense.

---

## 1. The uncomfortable arithmetic

"Africa" is not a market. It is **54 countries, ~40 currencies, 54 data-protection regimes, and at least 200 job boards**. Every one of them needs its own adapters, its own legal review, and its own employer identity resolution.

The good news: **East Africa is unusually leverageable**, because the same handful of platforms already operate across it.

| Platform | Coverage | What that gives us |
|---|---|---|
| **BrighterMonday** | Kenya, Uganda, Tanzania | One adapter family, three countries |
| **Fuzu** | Kenya, Uganda, Tanzania, Nigeria, Somalia | Same |
| **MyJobMag** | Nigeria-origin, `.co.ke` and other country editions | Same |
| **ReliefWeb** | Global, filter by country | One API, every country with a humanitarian presence |
| **UN careers / Impactpool / Devex** | Global | Same |

So the realistic claim is: **one adapter set covers a meaningful slice of East Africa, and a thin slice beyond it.** That is a legitimate path to "Africa" — taken in three steps, not one.

---

## 2. The sequence

| Stage | Markets | Why now | What must be true first |
|---|---|---|---|
| **1. Prove** | Kenya (Nairobi metro) | Small enough to enumerate; one regulator; one dominant board set; Matatu GTFS exists | ≥95% coverage of Nairobi entry-level; ≥92% liveness; W4 retention ≥20% |
| **2. Leverage** | Uganda (Kampala), Tanzania (Dar es Salaam) | Same three boards already operate there; English/Swahili; EAC labour mobility; similar informality | Kenya unit economics hold; adapters parameterised by country, not hardcoded |
| **3. Deepen** | Rwanda (Kigali), Ethiopia (Addis), Zambia, Ghana, Nigeria | Large youth populations, growing digital hiring, strong NGO/development presence | Local partner or local legal review; a second regulator's requirements (Rwanda's DPL is stricter than Kenya's) |
| **4. Optional** | South Africa, Egypt, Morocco | Large formal markets, but completely different board landscapes and much stronger incumbents | Probably never. Do not plan for it |

**Do not skip stage 1.** A product that is 60% complete in six countries is worth less than one that is 98% complete in one city, because the entire promise is completeness and verification.

---

## 3. What travels, and what must be rebuilt

| Component | Travels? | Notes |
|---|---|---|
| Canonical schema | ✅ | Add `currency`, `country`, `admin_level_1/2`, `regulator` |
| Pipeline architecture | ✅ | Unchanged |
| Entity resolution logic | ✅ | Employer name patterns are the main local variance |
| Scam criteria | ⚠️ Mostly | Fee requests and personal-number-only contacts generalise; templates do not |
| Board adapters | ⚠️ Partly | BrighterMonday/Fuzu/MyJobMag country editions share structure; everything else is new |
| Document pipeline (PDF/OCR) | ✅ | Public-sector adverts look similar across the region |
| Transit routing | ❌ | New GTFS per city; only Nairobi has a well-known open feed |
| Pay baselines | ❌ | New statistical office per country |
| Legal posture | ❌ | New regulator, new registration, new localisation rule |
| WhatsApp distribution | ✅ | Dominant across most of the region |

---

## 4. What changes per market (checklist)

Before entering any new country, answer these seven questions:

1. **Regulator & registration.** Who is the DPA authority, is registration mandatory, what are the penalties, and is there a localisation requirement? *(Kenya: ODPC, yes above thresholds, up to KES 5M/1%, yes — s.50.)*
2. **Dominant boards.** Which two or three platforms account for most formal advertised roles? Are they regional or local?
3. **Public sector.** Is there a central portal, or is it fragmented by region/county/state?
4. **Document formats.** Are adverts HTML, PDF, scanned newspaper, or social posts? This drives the OCR budget.
5. **Transit data.** Is there a GTFS feed, a paratransit map, or nothing? If nothing, the "reachable" promise degrades to distance bands — say so honestly.
6. **Pay baseline.** Which statistical office, which series, which frequency?
7. **Language.** Which languages must the UI and the extraction handle? (Kenya: English + Kiswahili; Tanzania: Kiswahili-first; Ethiopia: Amharic; Rwanda: Kinyarwanda/French/English.)

---

## 5. Why this order is defensible

- **Each step reuses 60–80% of the code.** The adapters and the schema are the expensive parts; the regulatory and transit work is per-market but bounded.
- **The trust promise is portable.** "Last verified 9 minutes ago, no fee requested, closes Friday" means the same thing in Kampala as in Nairobi.
- **The competitive gap widens as you go.** BrighterMonday and Fuzu are strongest in Kenya. Uganda and Tanzania are thinner, and the public-sector/document lane is barely served anywhere in the region.
- **Funding narrative improves without lying.** "Kenya's most complete verified job graph, expanding across East Africa" is a real, defensible story. "Africa's job platform" with 5,000 rows is not.

---

## 6. What would make me change this plan

| Signal | Response |
|---|---|
| A Kenyan incumbent offers a partnership or acquisition | Take the meeting. Distribution beats independence at this scale |
| Kenya coverage plateaus below 80% after Phase 3 | The enumeration thesis is wrong; reconsider before expanding |
| A regional board offers a data licence covering 5 countries | Jump to stage 3 selectively; adapters become cheap |
| Donor/NGO funding appears for youth employment | Prioritise the NGO/public-sector lane and impact reporting; it is the best-aligned money in this market |
| Users outside Kenya dominate signups | Follow demand, but only with a local legal review in place |
