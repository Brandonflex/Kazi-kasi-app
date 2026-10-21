# Design research log

**When:** October 2026 · **For:** brand identity, visual system, product surfaces
**Method:** desk research; no primary interviews yet (that is the next step, and
it is listed as an open item rather than pretended away).

Every row says what it changed. Research that changed nothing is not listed.

---

## 1. Language and name

| Source | What it gave us | What it changed |
|---|---|---|
| Wiktionary, *kazi* — Swahili class IX, "work, business, job, occupation" | The word is the ordinary one on every advert | The name is legible to anyone in the market without translation |
| Wiktionary, *kasi* — Swahili, "speed (rapidity)", "force (strength or energy)", from Arabic *qāsin* | Not a made-up suffix; it means speed | The tagline writes itself: **work — and fast** |
| LingQ / Glosbe usage corpus ("kwa kasi", "kuongeza kasi ya kazi") | *kasi* is used for pace of work, not just vehicles | "Kazi-Kasi" reads as a pace, not a pun |

**Consequence:** the hyphen is load-bearing; `KaziKasi` and `Kazi Kasi` are
mis-spellings we correct in brand copy.

## 2. Competitive visual audit

| Brand | Visual territory | Implication |
|---|---|---|
| **BrighterMonday** | Roof Terracotta `#A01C2A` on white; tagline *"Kazi Kwako!"* ([Brandfetch](https://brandfetch.com/brightermonday.co.ke), LinkedIn) | Red is taken — and it is the same red we would want for warnings. We gave red to **risk only** and kept forest/amber for ourselves |
| **Safaricom / M-Pesa** | Green; the trust anchor of Kenyan consumer tech | Green reads as trust here, but Safaricom-green reads as *telco*. We chose a darker forest so it reads as institution |
| **Fuzu** | Career-platform blue/purple, learning modules, "growth" framing | We are not a career platform; no purple, no learning content, no progression metaphors |
| Generic job boards | Briefcase, pin, magnifier iconography | The mark is a **scope**, not a pin: the product measures reach from a person, not a place on a map |

## 3. Channel and device constraints (the strongest design input)

| Source | Finding | What it changed |
|---|---|---|
| WhatsApp Business Platform docs + display-name rules (Meta, via Wati/PayPerWA summaries) | Display name must be the real brand name, no emoji, no promos; green tick needs Business Verification + 30 days + 2FA | `Kazi-Kasi` exactly; the brand must earn trust in **copy**, not from a badge we may not have at launch |
| Template categorisation (Meta; Infobip) | Templates pre-approved, categorised marketing/utility/auth; free-form replies only in the 24-hour window | v1 is plain text inside the window; the identity lives in structure, not in a rich template |
| Channel comparisons for Kenya (Celcom Africa, Soko Sauti, HabariChat) | SMS reaches ~100%, WhatsApp ~85% of smartphones; WhatsApp cost per conversation is 5–10× SMS | The SMS fallback is a **brand surface**, not a technical footnote: it must survive 160 characters |
| USSD comparisons (Mctaba, Helloduty) | USSD works on any phone with no data; 182 characters per screen | Confirms the hierarchy rule: if a fact cannot survive one line, it is not essential |
| Low-end Android design guidance (Wise Hustlers, Nigeria) | 2–4 GB RAM, metered data, sunlight glare, larger targets | **No webfonts, no photography, no icon library**; 16 px body minimum; 44 px primary targets |
| USSD-vs-app-vs-WhatsApp for Kenyan startups (Mctaba) | "Launch with WhatsApp for your MVP… trust and familiarity matter" | Confirms the digest-first ordering of this design pass |

## 4. Trust as the actual product

| Source | Finding | What it changed |
|---|---|---|
| M-Pesa case studies (World Bank, Frontier Fintech, AERC) | Adoption came from **simplicity + predictability**, not features; agents physically painted "Safaricom green" so people could see who to trust | Trust is displayed, not claimed. Hence the evidence block, the timestamps, `/slo` |
| Fintech UX practice (Yuj Designs, DesignX, SaaSFactor) | Ambiguity destroys trust faster than error does; specific confirmation beats "processing" | Every state has a sentence: "checked 12 minutes ago", "address it 3 km away (approximate)" |
| Kenyan app-design guidance (HustleHub) | Local-language, plain words beat corporate terms | "Can't take this one" instead of "eligibility criteria not met" |

## 5. Visual language

| Source | Finding | What it changed |
|---|---|---|
| Kenyan brand-colour writing (Creative Kigen; Pulsar Kenya) | Green = growth/prosperity; green is the dominant financial-sector colour; red/maroon is ~30% of listed brands | Green is safe for trust but crowded; differentiate by **shade and restraint** |
| East African palette guidance (The African Geeks) | Ochres, terracottas, forest greens, deep indigos; forest `#2A5C3F` called out as "grounded" | Amber/ochre as the urgency accent; forest darkened to `#14532D` for AA and differentiation |
| 2026 palette forecasts (Turbologo, Wilogo, Adobe) | Return of warm earth tones; "modernised natural shades"; deep green + high-energy accent | Warm paper `#FBF8F2` instead of grey; a single saturated accent rather than a multi-colour system |
| Kenyan interiors/colour trend writing (Karanu, Real Coat) | Warm neutrals suit Kenya's strong equatorial light; cool greys look dirty beside it | Justifies the paper tone on functional, not aesthetic, grounds |
| Job-board card guidance (Jobboardly, Stan.Vision, Cavuno) | Cards must be scannable: title → company → salary → location; one card, one action; too many filters is a top failure | Fixed card hierarchy, one primary action, no filters in v1 beyond the profile constraint bar |

## 6. Accessibility

| Source | Requirement | What it changed |
|---|---|---|
| WCAG 2.2 SC 1.4.3 (W3C) | 4.5:1 body, 3:1 large text | Every text pair in the palette is ≥5:1; documented in a table and enforced by a test |
| WCAG 2.2 SC 2.5.8 | 24 × 24 CSS px minimum target | 44 px for primary actions, 24 px floor for chips and small buttons |
| WCAG 2.2 SC 1.4.11 | 3:1 for UI edges and focus | Focus ring and borders specified as tokens |
| MDN mobile accessibility checklist | No colour-only meaning; 200% zoom | Badges always carry words; layout tested at 320 px |

## 7. What this research changed, in one list

1. **Red is risk-only.** BrighterMonday owns warm red; using it for urgency would
   both collide and destroy the scam signal.
2. **Forest, not Safaricom green.** Trust without looking like a telco.
3. **Warm paper base.** Cool grey is a default, not a decision.
4. **No webfonts, no photography, no icon downloads.** Device and data reality
   beat brand polish.
5. **The digest is designed first.** It is where most users will meet the brand.
6. **The mark is a scope, not a pin.** The product is a radius from a person.
7. **Every claim carries a timestamp or is cut.** The evidence block became the
   visual centrepiece of the job page.
8. **The SMS fallback is a designed surface** (one segment, STOP included).
9. **Contrast is a build gate**, not an audit item.

## 8. What is still unknown (primary research needed)

| Question | Method | Why it matters |
|---|---|---|
| Does the card hierarchy survive a 5-second glance? | 5–8 unmoderated tests with early-career Nairobi users on a low-end Android | The design bet is "title → eligibility → deadline"; if the deadline is what people actually scan for, the badge order changes |
| Is the score meaningful or noise? | A/B: score visible vs hidden | Decides D17 |
| Does Swahili increase trust or reduce it? | Paired copy test, English vs English + Swahili nouns | Decides D15, and the brand voice |
| What earns trust in a WhatsApp job message? | 10 short interviews, show 3 message variants | The whole distribution channel is one message |
| Daily vs weekdays-only | Holdout on unsubscribe rate | Decides D16 |
