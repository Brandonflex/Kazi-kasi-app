# Product surface design

**What this narrows:** the screens, the information hierarchy, the interaction
rules, and — more importantly — the feature list we are *not* building.

---

## 1. Five principles

1. **One card, one decision.** A card exists to be acted on: apply, dismiss, or
   read more. Anything that does not help that decision is removed.
2. **Evidence over adjectives.** Every card carries what was checked and when.
   If we cannot show it, we do not claim it.
3. **A gap is not a fault.** "Eligibility unstated", "pay not stated", "distance
   unknown" are shown as gaps, never as disqualifications — because the advert
   is incomplete, not the person.
4. **Silence is a feature.** On a day with nothing new that fits, the phone gets
   nothing. A product that needs attention every day is a product about itself.
5. **The employer's page is the destination.** We are the scope; the application
   happens where the job lives. No forms, no accounts required to look.

## 2. Surfaces

| Surface | Job to be done | Frequency |
|---|---|---|
| **WhatsApp digest** (`digest.py`) | "Tell me what's new that I could actually get, in one message." | Daily, 18:00–20:00 EAT |
| **Feed** (`/`) | "Show me everything that fits, and let me compare." | A few times a week |
| **Weekly brief** (`/brief`) | "Is this market moving toward me, and what should I do this week?" | Weekly |
| **Momentum** (rail, brief) | "Am I still in this?" | Weekly, passive |
| **Shortlist** (`/shortlist`) | "Keep the ones I am actually considering, and tell me before one closes." | Weekly, and on the one reminder |
| **Job page** (`/job/<id>`) | "Convince me this is real and worth my morning." | On click-through |
| **Ops: freshness** (`/slo`) | "Is the promise holding today?" | Internal, daily |
| **Ops: review** (`/review`) | "Which duplicate pair needs a human?" | Internal, on alert |
| **Ops: digest console** (`/digest`) | "What exactly was sent, to whom, and what happened to it?" | Internal, daily |

Rediscovery via **Radar** (saved searches with alerts) is designed but *not*
built; it is the next surface after the digest has a returning user.

## 3. The card is the product

Everything else is chrome around this one object.

```
┌──────────────────────────────────────────────────────────┐
│ Records Management Assistant                 18/650 ink  │
│ Public Service Commission of Kenya           14 ink-2    │
│                                                          │
│ [open to freshers] [Nairobi] [closes 12 Nov] 12px badges │
│                                                          │
│ matches admin · pays above your KES 40,000 floor   13px  │
│ ── 0.61 · checked 12 minutes ago ─────  Apply on psc ↗ ──│
└──────────────────────────────────────────────────────────┘
```

**Hierarchy is fixed:** title → employer → eligibility → place → deadline →
reason → evidence → action. Nothing is allowed above the title, and the action is
always last.

**What is deliberately absent:** employer logos (unverified, usually broken,
always heavy), job descriptions (they belong on the job page), "posted 2 minutes
ago" hype badges, share buttons, star ratings, "similar jobs" carousels.

### Digest card: the same object, smaller

```
*Records Management Assistant*
Public Service Commission of Kenya
Nairobi · closes 12 Nov · open to freshers · KES 30,550–39,720/month
matches admin
https://kazikasi.app/job/…
```

Four lines and a link. One reason, never four. If a line does not change a
decision, it is cut — the phone screen is the constraint, not the design.

## 4. Screen specs

### 4.1 Feed (`/`)

```
[Scope mark] Kazi-Kasi        Nairobi metro · early career
             Feed  WhatsApp  Freshness  Review

Wanjiru — IT graduate, 0 years        ← whose feed this is
[≤ 18 km from Kasarani] [no pay floor] [it] [admin] [customer]

31 live jobs   9 closing in 7 days   18 match this profile   2 applied
──────────────────────────────────────────────────────────────
[card] [card] [card] …
```

- **The constraint bar is not a settings screen.** It is the argument for why
  this feed looks like this, visible on every visit.
- **The ledger sits under the filters** — one line, computed from the last
  visit: "3 new since Tue 13 Oct · 4 closing this week · checked 12:42 EAT".
  A first visit says "First look" instead of inventing a number. See
  [04 §6](./04-market-teardowns.md).
- Profile switching is a row of first names, not an account menu, because
  accounts do not exist yet.
- The stat strip answers "is this thing alive?" before the first card.

### 4.2 Job page (`/job/<id>`)

Order: title and employer → the verdict (why it was shown to *this* profile) →
the evidence (sources, timestamps, quoted eligibility line) → the advert text →
the apply link → the history (viewed, clicked, applied).

The evidence block is the brand: *"Fresh graduates are encouraged to apply" —
quoted from the advert, on BrighterMonday, checked 12 minutes ago.* No other
Kenyan job product shows the sentence it made its decision from.

### 4.3 Digest console (`/digest`)

```
[mark] WhatsApp digest
one message a day, five jobs at most, closing soonest first

Wanjiru  [Amina] [Brian] [Otieno]
Subscribed 20 Oct via web to +2547•••0000. Daily, 18:00–20:00 EAT, up to 5.
[Stop these messages]

┌ the message, exactly as it will arrive ─────────────┐
│ *Kazi-Kasi* — 5 jobs for you today                  │
│ 1. *Records Management Assistant* …                 │
└─────────────────────────────────────────────────────┘

If WhatsApp fails → one SMS segment
Left out: 5 already sent, 1 you applied to
Delivery log: whatsapp queued · attempts 0 · 18:02
```

The console exists because a digest is invisible by nature. If support cannot
see the exact string that was sent and what happened to it, they cannot answer
"why didn't I get anything?".

### 4.4 Mobile behaviour (the default case)

| Width | Behaviour |
|---|---|
| ≤ 520 px | one card per row; badge row wraps; stat strip becomes a 2×2 grid; apply button full-width at the card foot |
| ≤ 380 px | title wraps to two lines, employer truncates at one; no horizontal scroll at 320 px |
| Touch | 44 px minimum on Apply and profile chips; "Not for me" has 44 px of vertical padding even though the text is small |

There is no separate mobile app in v1. The site is a page, the product is a
message.

## 5. Interaction rules

- **Dismissal is instant and reversible by re-showing nothing.** No undo toast;
  if someone dismissed by mistake, the job stays out — that is the cost of a
  one-tap signal, and it is cheaper than a modal.
- **Applying is recorded, never performed.** The click-out opens the employer's
  page; "I applied" is a separate, explicit mark.
- **No infinite scroll.** The list ends with "That's everything that fits today."
  An endless feed is an engagement mechanic, and this is not that product.
- **Loading states are honest.** If the feed is 24 minutes old, it says so above
  the list, not in a status dot.

## 6. Features: narrowed

The user asked to narrow features. This is the cut line, with the reason.

### v1 — in this repository

| Feature | Why it is in |
|---|---|
| Tailored feed with reasons and gates | The core promise |
| Job page with quoted evidence and sources | Trust is the differentiator |
| WhatsApp digest with consent, outbox, retries, SMS fallback | The distribution that reaches the actual market |
| Inbound STOP/START/HELP | Consent that cannot be revoked is not consent |
| Freshness page (`/slo`) | "Constant update" as a measurement, not a slogan |
| Duplicate review queue | 40–60% cross-source duplication is the reality |
| Document lane (PSC PDFs, county adverts) | The public sector is where entry-level jobs actually are |

### v1.1 — next, not now

| Feature | Why it waits |
|---|---|
| **"Nothing new" weekly notice** | An exhausted pool currently means silence forever; a once-a-week "still quiet, here's your feed" is the fix. Needs a cadence rule, not new UI. |
| **Saved searches / Radar** | The digest already covers the passive case; Radar is for people who want to watch a narrower thing |
| **Bilingual copy (Swahili)** | High value, high cost of getting wrong; needs a native writer, not a translation pass |
| **Delivery receipts in the console** | Backend done (Phase 6); the ops UI shows states but not receipt history |
| **Employer verification badges** | Requires an employer-side data source we do not have |

### Explicitly not building

| Not building | Why |
|---|---|
| Accounts, passwords, profiles with CVs | Every account is a reason not to start; a phone number is the account |
| In-app applications, forms, CV upload | We would become the bottleneck and the liable party |
| Auto-apply, "apply to 50 jobs" | It is spam with a nicer interface, and it is exactly what recruiters are fleeing |
| Employer/recruiter product | v2 conversation; the schema does not foreclose it |
| Gamification: streaks, scores for the user, badges | A job search is not a game, and the people using this are anxious |
| Chatbot career advice | Unverifiable, and it competes with the one thing we do well |
| Native app | WhatsApp *is* the mobile app; a store listing adds a install step before value |

## 7. Open questions

These are the next decisions, each with the trade-off written down.

| # | Question | Options | Current lean |
|---|---|---|---|
| D13 | **Final name** | Keep *Kazi-Kasi* and file KIPI 35/42 · pick a distinctive coined name · keep the mark, change the word | Keep it; the mark works without the word, so the risk is contained |
| D14 | **Default sort in the feed** | Best fit (score) vs closing soonest | **Closing soonest** — the deadline is the only thing that expires |
| D15 | **Language policy** | English-only · English with Swahili interface labels · full bilingual | English with universal Swahili nouns; revisit with a native writer |
| D16 | **Digest frequency default** | Daily · weekdays only · 3×/week | Daily at 18:00, but D16 is genuinely open (weekdays-only may reduce unsubscribes) |
| D17 | **Show the match score to users?** | Show · hide · show on the job page only | Show, small and grey: it is an audit trail, and hiding it invites "why this job?" |
| D18 | **Employer logos** | None · only when verified | None in v1 |

## 8. What "done" looks like for this design pass

- [x] A named direction with a stated rationale, not a moodboard
- [x] Tokens implemented in the product, not only documented
- [x] Contrast enforced by a test
- [x] The digest (primary surface) designed before the website
- [x] Feature list cut to v1 / v1.1 / never
- [ ] A native-speaker review of the Swahili in the brand copy
- [ ] The Scope Mark drawn as production SVG + WhatsApp profile export
- [ ] Five-second test with 5–8 early-career Nairobi users on the card hierarchy
