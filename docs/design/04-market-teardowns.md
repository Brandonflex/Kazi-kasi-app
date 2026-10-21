# Market teardowns: ten platforms, thirty borrowings

**What this is:** a competitive study of the products that already work on the
people we are trying to serve, narrowed to ten, with exactly three things
borrowed from each. Not a mood board — every borrowing names the mechanism, the
evidence, what it becomes inside Kazi-Kasi, and what we refuse to take with it.

**What it is for:** deciding the next three months of design and build, and
giving the team a shared vocabulary for "premium" that is specific enough to
argue with.

**What it is not:** a claim that any of these companies is a competitor in
Nairobi. Only BrighterMonday and Fuzu are. The other eight are here because they
have solved one of the five problems we have: being found, being trusted, being
remembered, being enjoyed, or feeling expensive.

---

## 0. The one-line finding

**Job search is not a content problem, it is a certainty problem.**

Every product that wins in this space sells the same thing: *a shorter,
better-ordered list and a reason to believe it*. Volume is table stakes and
commodity; the margin is in **subtraction and proof**. That is good news for
Kazi-Kasi, because subtraction and proof are exactly what a scope product is.

The second finding is about habit. Nobody wants to job-hunt. The products that
get returned to are the ones that make the *return* cheap and the *absence*
costly — and they do it with a ritual, not a notification stream.

---

## 1. What actually works: five mechanisms

Five mechanisms recur across all ten platforms. Everything in §3 is an instance
of one of them.

| # | Mechanism | How it works | Who proves it |
|---|---|---|---|
| M1 | **Finite curation** | A short, bounded set beats an infinite list. "Six new roles this week" is actionable; 4,000 results are a second job. | Otta, Spotify's Discover Weekly, Linear |
| M2 | **Legible arithmetic** | The product shows its working: why this, why now, out of what. Trust comes from the inputs, not the score. | Levels.fyi, Otta's "recommended because", Fuzu |
| M3 | **Ritual with forgiveness** | A repeating moment (weekly, not daily) plus a repair mechanic if it is missed. Loss aversion only works on something intact. | Duolingo (streak + freeze), Spotify Wrapped |
| M4 | **Honest scarcity** | Real deadline and real competition create urgency; invented urgency destroys the product's only asset. | Airbnb ("rare find"), Indeed (freshness) |
| M5 | **Craft as signal** | Speed, restraint and designed micro-states read as "expensive" before any copy does. | Linear, Airbnb, Stripe |

The failure mode is equally consistent: **every platform that added volume to
compensate for weak matching ended up with a search box and a spam problem.**
We are not building a search box.

---

## 2. The shortlist

Chosen for coverage of the five mechanisms, not for fame. Two are Kenyan/East
African (the ones we must beat), one is the distribution system we must plug
into, and seven are the best in the world at one specific thing.

| # | Platform | What it is | The one thing it is best at | Mechanism |
|---|---|---|---|---|
| 1 | **Google Search / Jobs** | Discovery system | Turning structured pages into demand | M2, M4 |
| 2 | **LinkedIn** | Professional network | Making opportunity feel close and legible | M2 |
| 3 | **Indeed** | Volume job board | The alert economy | M1, M4 |
| 4 | **BrighterMonday** | Kenyan incumbent | Local idiom and employer trust | M4 |
| 5 | **Fuzu** | East African career platform | Development attached to jobs | M2 |
| 6 | **Otta / Welcome to the Jungle** | Candidate-first tech jobs | A feed that feels finite and considered | M1, M2 |
| 7 | **Duolingo** | Habit machine | Making a return cheaper than a lapse | M3 |
| 8 | **Spotify** | Personalisation at scale | Turning private data into public identity | M3, M1 |
| 9 | **Airbnb** | Trust marketplace | Desire and honest scarcity | M4 |
| 10 | **Linear** | Craft benchmark | Premium feel through speed and restraint | M5 |

**Honourable mentions, one idea each, not full teardowns:** Levels.fyi (salary
pages as the best SEO in the category — folded into §7), Strava (personal
records; folded into Momentum), Glassdoor (reviews as a moat we should not
build), Naukri/Bayt (regional density, nothing to borrow at our stage).

**Explicitly out of scope:** Upwork/Fiverr (gig market, different unit of work),
TikTok/Instagram as products (they are channels — §7), Telegram (wrong channel
in Kenya), Monster/CareerBuilder (declining, nothing to learn).

---

## 3. The thirty borrowings

Format: **what it is → why it works → what it becomes in Kazi-Kasi → the
guardrail.** The guardrail is the part that keeps this from becoming a pastiche.

### 3.1 Google Search / Jobs — the demand engine

Google's job surface is not a competitor, it is the largest free distribution
channel in the category: it indexes pages carrying `JobPosting` structured data
and shows them in a Jobs widget above ordinary results. There is no submission
API; you are crawled or you are invisible.

**G1 — One crawlable page per job, marked up as that job.**
*Why it works:* Google requires exactly one `JobPosting` per URL, on the leaf
page, matching what the visitor sees. Listing pages cannot carry it.
*In Kazi-Kasi:* every `/job/<id>` renders its JSON-LD from the same record object
that renders the page, so markup and content cannot drift. `title`,
`datePosted`, `hiringOrganization`, `jobLocation`, `validThrough` and
`baseSalary` are emitted when we hold them, and omitted when we do not.
`directApply: false` — honest, because the application happens on the employer's
site, and Google rewards honest `directApply` semantics.
*Guardrail:* never mark up a job we have not verified. Never emit a salary we
inferred as if it were advertised.

**G2 — Freshness is a ranking signal; stale pages get demoted.**
*Why it works:* Google's Indexing API exists specifically for job URLs — you
ping on publish and on removal, and expired listings can be dropped rather than
left to rot.
*In Kazi-Kasi:* publish and close events fire the ping (and a 410 for a dead
job); `validThrough` is the deadline we already store; every page carries "last
verified" from the observation log.
*Guardrail:* we do not keep a dead job page alive to hold its ranking. That is
the fastest way to teach a user the product lies.

**G3 — Query-shaped pages that answer a search, not a template.**
*Why it works:* programmatic pages win when each one contains a real answer and
a real sample size. Thin, duplicated pages are penalised.
*In Kazi-Kasi:* `/salaries/<role>/<county>`, `/closing-soon/<week>`,
`/county/<name>` — each computed from our own observations, each showing "n
adverts, dd–dd Mmm, updated daily". If we have fewer than a threshold of
adverts, the page does not exist yet (404, not a thin page).
*Guardrail:* a programmatic page is a by-product of the corpus, never a reason
to loosen the corpus.

### 3.2 LinkedIn — proximity and legibility

**L1 — Network proximity makes an opportunity feel reachable.**
*Why it works:* "3 alumni work here" and "you're in the top 10% of applicants"
convert because they answer *can someone like me get this?* — the real question
behind every application.
*In Kazi-Kasi:* proximity without surveillance. Aggregates only, never names:
"popular with admin graduates in Nairobi", "6 people saved this today" (once we
have the number), and later, with consent, "4 people from your campus applied".
*Guardrail:* no named people, no scraped social graphs, no "your colleague is
looking". Kenya's Data Protection Act treats this as personal data and so do we.

**L2 — A visible completeness meter turns a profile into a task.**
*Why it works:* progress bars exploit the completion bias; the profile improves
because the meter exists.
*In Kazi-Kasi:* the meter is honest about *output*, not vanity: **"Your feed is
tuned to 3 of 6 constraints — add a pay floor and a second role family to see
more of what fits."** It measures the scope, not the person, and disappears
when the scope is complete.
*Guardrail:* we never ask for data we do not use in the ranking. No "add a
photo to reach 100%".

**L3 — Show the other side of the table.**
*Why it works:* recruiters see a candidate summary; candidates see nothing.
Making the asymmetry visible builds trust faster than any claim.
*In Kazi-Kasi:* a **What the employer will see** panel on the job page —
requirements we extracted from the advert, the ones we could not verify, and
what they will ask for. It is the same evidence block, facing outward.
*Guardrail:* never speculate about a specific recruiter's behaviour.

### 3.3 Indeed — the alert economy

**I1 — A saved search is an asset; the alert is the interest on it.**
*Why it works:* the search persists after the session, so the product can
return to the user with a reason that predates the visit.
*In Kazi-Kasi:* **Watch** — role family + county + pay floor, saved as an object.
Radar alerts only fire when something *new* lands, never a re-send of the same
thirty jobs.
*Guardrail:* one alert per watch per day, maximum; silent when nothing changed.

**I2 — Pay on the card.**
*Why it works:* advertised pay is the single most decision-changing field on a
job card, and its absence is read as a bad sign.
*In Kazi-Kasi:* the band plus its provenance: `KES 30,550–39,720 · stated in the
advert` or `· estimated from 41 adverts`. Two different claims, two different
labels.
*Guardrail:* an estimate is never styled like a quote, and never below the
advert's own floor.

**I3 — Recency labels drive clicks.**
*Why it works:* "posted 2 minutes ago" is a freshness proxy and works — which
is exactly why it is abused.
*In Kazi-Kasi:* we replace posting recency with **decision recency**: "closes in
9 days" and "checked 12 minutes ago". The first is a deadline, the second is our
own reliability.
*Guardrail:* no "urgent!", no "apply now or lose it", no timers that reset.

### 3.4 BrighterMonday — the incumbent's strengths

**B1 — Local idiom, not localisation.**
*Why it works:* "Kazi Kwako" lands because it is Swahili a Nairobi job seeker
actually uses, not a translated slogan. Trust is dialect.
*In Kazi-Kasi:* Kenyan English with universal Swahili nouns — *kazi*, *maombi*?
No: only where it is clearer. Place names as people say them: Kasarani, Westlands,
CBD, Industrial Area — not "Nairobi Metropolitan Area". Deadlines in EAT, with
the day named.
*Guardrail:* no fake vernacular. A borrowed word that a 23-year-old would not
say out loud is worse than plain English.

**B2 — The employer is a brand, not a row.**
*Why it works:* employer pages give candidates a reason to return to a company
and give the board a B2B product.
*In Kazi-Kasi:* an **employer dossier**, candidate-side and free in v1: what they
have advertised in the last year, how often roles recur, the pay bands they
publish, how quickly their adverts close, and the verification status of the
organisation.
*Guardrail:* until revenue is decided, the dossier is not for sale and ranking is
not for sale. If that changes, it gets a label, in the same type size as the job.

**B3 — A taxonomy that matches how Kenya hires.**
*Why it works:* "internships & attachments" is a first-class category here, not
a filter; "sales & business development" is the biggest white-collar family in
the market.
*In Kazi-Kasi:* role families derived from our own corpus rather than borrowed
from a US board, with **attachment/internship** as a first-class track and
"graduate trainee" as its own shape.
*Guardrail:* families are earned from data; when a family has fewer than ~15
live roles it merges upward rather than fragmenting the filter.

### 3.5 Fuzu — development attached to work

**F1 — A personal score, made legible.**
*Why it works:* a number that changes gives the user something to do between
applications; Fuzu's employability score is the reason people return without a
new job.
*In Kazi-Kasi:* we refuse the global judgement ("you are 62% employable") and
keep the per-job one: **you meet 5 of the 7 stated requirements**, with the two
gaps named. It is arithmetic about the advert, not a verdict about the person.
*Guardrail:* never a score out of 100 for a human. Never a score we cannot
explain in one sentence.

**F2 — The gap you could close.**
*Why it works:* converting rejection into a next step is the difference between
a job board and a career tool.
*In Kazi-Kasi:* one gap, one free resource, no wall: "6 of the 8 shortlisted
candidates will have Excel; the free KNLS course is 4 hours." Shown at most once
per job, never on the card.
*Guardrail:* no paid course marketplace in v1, no "boost your score" upsell.

**F3 — Match percentage with reasons.**
*Why it works:* the percentage is a hook; the reasons are what make it
believable.
*In Kazi-Kasi:* the score is already computed (0.61) and already shown in small
grey type; every card carries exactly three reasons and, where relevant, one
honest gap.
*Guardrail:* no percentage without a reason; no four reasons; no reason that
restates a badge.

### 3.6 Otta / Welcome to the Jungle — the candidate-first feed

**O1 — Matching instead of scrolling.**
*Why it works:* Otta's whole pitch was "job search shouldn't be soul-crushing":
a profile in, a finite, ordered set out. Nearly two million users and six
million applications in 2023 came from refusing the search box.
*In Kazi-Kasi:* the feed ends. "18 roles fit you · 6 are new" and, at the bottom,
**"That's all of them. We'll tell you when that changes."** The end state is the
product.
*Guardrail:* never infinite scroll, never a "load more" that exists to inflate
session time.

**O2 — The decision fields come first.**
*Why it works:* Otta puts salary, level and mode on the card, before the prose.
The card answers "can I take this?" before "do I want this?".
*In Kazi-Kasi:* deadline, pay, entry-fit and distance on the card; the advert is
on the job page. Title → employer → eligibility → place → deadline → reason.
*Guardrail:* no description previews on cards. A card that needs a paragraph is
a card that has not decided what it is.

**O3 — Context that reduces risk.**
*Why it works:* Otta wraps listings in culture content because the fear is not
"is this job good", it is "is this job real".
*In Kazi-Kasi:* our version of rich content is **provenance**: what the advert
said, when we last saw it, which source, what is missing. Evidence is the
luxury good here, not office photography.
*Guardrail:* no employer-supplied marketing copy inside the evidence block.

### 3.7 Duolingo — the habit engine

The strongest evidence in consumer software: learners who reach a 7-day streak
are ~2.4× more likely to return the next day; streak freezes lengthen average
streaks dramatically (reported ~30.6 days vs ~18.9 by day 21); decoupling the
streak from the daily goal raised day-14 retention ~3.3% and the share of daily
learners holding a streak ~10.5%. The lesson is not "add points". It is
**make the ritual small and forgive the lapse**.

**D1 — A repeating moment with a repair mechanic.**
*Why it works:* loss aversion protects an asset; the freeze protects the asset
from a single bad day, which is what keeps the asset alive long enough to matter.
*In Kazi-Kasi:* **Momentum** — counted in *weeks*, not days (nobody job-hunts
daily). Four weeks of "checked the brief and acted once" = a run. One missed
week is forgiven automatically, once per quarter, and the product says so
plainly.
*Guardrail:* no points, no badges, no mascot, no shame copy. A broken run is
silent and restartable.

**D2 — Make keeping it easier than breaking it.**
*Why it works:* Duolingo's biggest win came from lowering the bar for the streak,
not raising engagement: one lesson, any lesson.
*In Kazi-Kasi:* opening the brief counts; saving a job counts; applying does not
have to happen. The unit of progress is *attention paid*, because that is what
precedes outcomes we cannot control.
*Guardrail:* never tie Momentum to applying. We will not optimise for
application volume — that is how boards become spam.

**D3 — The first seven days are the product.**
*Why it works:* retention curves are decided before day 7; after that, loss
aversion does the work.
*In Kazi-Kasi:* design days 0 → 7 explicitly: day 0 the feed with a named
profile; day 1 "your first brief, nothing new yet — here is what to watch"; day 3
the first save; day 7 the first real brief with a change. Signup copy is a
commitment, not a form: **"Set your scope. We'll do the watching."**
*Guardrail:* no day-7 notification if there is nothing to say. The silence has to
be real on day 2, or the day 7 message means nothing.

### 3.8 Spotify — identity, recaps and made-for-you

Wrapped is the most efficient organic acquisition engine in consumer software:
reported 200M users opening it within 24 hours in 2025, 425M shares in 2024 and
630M+ in 2025, with double-digit download spikes in launch week. The mechanism is
not "a recap" — it is **the user's own data, formatted as identity, at zero
effort**.

**S1 — Named, dated, finite editions.**
*Why it works:* "Discover Weekly" is a promise: a new, small, considered set,
every Monday. The name makes the ritual legible.
*In Kazi-Kasi:* every artifact is named and dated — **"This week's shortlist ·
6 Oct"**, **"Closing soon · Nairobi · week 42"**, **"New since Tuesday · 3"**.
Dated editions also make the product's silence auditable.
*Guardrail:* no edition without a date, no date without a change behind it.

**S2 — The recap as a shareable artifact.**
*Why it works:* people share things that say something about *them*. Wrapped is
designed 9:16 first, one idea per slide, zero effort from the user.
*In Kazi-Kasi:* **"Your year in the market"** in December — roles seen, saved,
closed; the band you were aiming at versus the band you were offered; the month
you were most active; the job you almost took. Private by default, one tap to
share a single card, no numbers that identify an employer you applied to.
*Guardrail:* never share an application outcome, a rejection, or a salary the
user did not choose to reveal.

**S3 — Personalisation that compounds.**
*Why it works:* the longer you stay, the better the fit — a switching cost made
of accumulated context, not contracts.
*In Kazi-Kasi:* the scope learns (dismissals teach; saves teach more), and it
tells you what it learned in one line. But the history is exportable, because a
premium product does not hold your data hostage.
*Guardrail:* no dark-pattern retention; deleting is one click and the export is
free.

### 3.9 Airbnb — desire and honest scarcity

**A1 — Scarcity that is true.**
*Why it works:* "Rare find" means *usually booked* — a claim about supply, not a
timer. It converts because it is verifiable and because it is rare.
*In Kazi-Kasi:* scarcity comes from real competition and real deadlines: "closes
Friday, 5pm EAT"; later, "42 people opened this, 6 saved it" once the number is
real. Never a countdown that resets on refresh.
*Guardrail:* if we do not have the number, we do not imply it. One invented
scarcity claim would cost more trust than a year of conversion gains.

**A2 — The wishlist is a return ticket.**
*Why it works:* saving is an act of intent; the saved object is the most
legitimate reason to come back, and it is the user's own idea.
*In Kazi-Kasi:* **Shortlist** — save from the card, compare up to four side by
side, and get one reminder 48 hours before the earliest deadline. This is the
single strongest retention mechanic available to us and it costs nothing to run.
*Guardrail:* a save is never shared with an employer, and never used as a lead.

**A3 — Trust is voice and material honesty.**
*Why it works:* Airbnb's design chief describes the interface as deliberately
"softer and more human than most traditional marketplaces" — the copy does the
trust work that badges cannot.
*In Kazi-Kasi:* plain, specific, warm sentences. "Closes Friday at 5pm, Nairobi
time." "The advert does not state a salary — that is the advert's gap, not
yours." No stock photography, no superlatives, no exclamation marks.
*Guardrail:* never a claim we cannot date and source.

### 3.10 Linear — the craft benchmark

**N1 — Speed is the product.**
*Why it works:* Linear's sub-100ms interactions and local-first rendering are
experienced as quality before any feature is understood. Perceived performance
is an emotional response.
*In Kazi-Kasi:* server-rendered HTML, no client framework, no spinner on first
paint, filtering via links (instant), total page weight under ~60KB. The site
should feel like a well-set document that happens to be live.
*Guardrail:* no animation that delays content; no font loading that shifts
layout.

**N2 — One entry point for everything.**
*Why it works:* ⌘K collapses navigation into intent — type what you want, get it.
It is also a progressive-disclosure device: beginners never see it, power users
never leave it.
*In Kazi-Kasi:* **⌘K / Ctrl-K** to jump to a job, a role family, a county, or a
profile; type-ahead over the local page's data. Invisible until pressed, hinted
in the footer.
*Guardrail:* the palette never becomes the only way to do something. Every
action has a visible path.

**N3 — Micro-states and designed motion.**
*Why it works:* premium UI is mostly the six states of a button and the 120–180ms
of an honest transition. Linear designs hover, focus, active, disabled, loading
and empty, and never animates layout.
*In Kazi-Kasi:* card hover lifts 1px and darkens the hairline (no shadow stack);
focus ring is the only 3:1 element; motion is 140–180ms `ease-out` on
opacity/transform only; `prefers-reduced-motion` removes all of it. Empty, error,
and "nothing changed" states get the same care as the happy path.
*Guardrail:* no bounce, no confetti, no skeleton screens that outlive the data.

---

## 4. What we deliberately do not copy

| Anti-pattern | Who does it | Why we refuse |
|---|---|---|
| Infinite scroll / "load more" | Indeed, LinkedIn | Session time is not the metric; a finite set is the promise |
| Invented urgency ("only 3 left!") | Booking, some boards | One false claim ends the trust the whole product runs on |
| Points, badges, leaderboards | Duolingo (for language) | Ranking applicants against each other is cruel and useless |
| Mascots and streak-shaming | Duolingo | The tone would break the premium promise |
| Application forms on the board | Indeed, LinkedIn | We are the scope, not the destination; forms are how boards become spam |
| Employer-paid ranking, undisclosed | Most boards | If ranking is ever sold, it is labelled in the same size as the job |
| Star ratings of employers | Glassdoor | Unverifiable, litigable, and it makes us the judge |
| Office photography as "culture" | Otta/WTTJ, Airbnb | Kenya's early-career buyer wants proof, not vibes |
| Notification streams | Everyone | A product that speaks daily about itself is not premium |

---

## 5. Premium feel: twelve laws

"Premium" here is not beige minimalism. It is the feeling that **someone
careful is in charge**. Twelve rules, in priority order when they conflict.

1. **Fewer things, better made.** One accent (forest), one action per card, one
   number per claim. If a screen has two primary buttons, it has none.
2. **Silence is the material.** Whitespace is the most expensive thing on the
   page. Sections breathe at 32–48px; cards at 16–20px internal padding.
3. **Type does the talking.** One family (system), three weights (400/600/700),
   tabular numerals for every figure, and a label style (12px, 600,
   +0.04em, uppercase) used sparingly enough to stay a signal.
4. **Warm paper, dark ink.** `#FBF8F2` and `#12161C`, never white-on-black or
   black-on-white. Colour is meaning: forest = action/verified, amber = time,
   risk = danger only.
5. **Edges are drawn, not stacked.** A 1px warm hairline and at most one soft
   shadow. Never a "card floating in space".
6. **Motion under 200ms, and only to explain.** 140–180ms ease-out on opacity
   and transform. Nothing bounces, nothing loops, nothing decorates.
7. **Numbers are typographic events.** Right-aligned, tabular, unit one step
   smaller and one step lighter: `KES 30,550–39,720`. Percentages to one decimal,
   never two.
8. **Every state is designed.** Hover, focus, active, disabled, loading, empty,
   error, offline, stale. The empty state is where premium is proven, because it
   is where most products stop trying.
9. **Copy is specific, second person, unexcited.** No exclamation marks, no
   emoji, no "opportunity of a lifetime". "Closes Friday at 5pm, Nairobi time."
10. **No selling inside the job path.** No upsell, no newsletter modal, no
    cookie wall between a person and a deadline.
11. **Speed is the luxury.** Server-rendered; content in the first 60KB; no
    layout shift; no spinners. A page that appears instantly feels expensive.
12. **Nothing is claimed that cannot be dated.** Every fact carries a source and
    a time, in small grey type. That single habit is the brand.

**The 60-second premium test** (run on every new surface): load it on a mid-range
Android over 3G; if it takes more than a second to first content, or the first
thing you see is a spinner, it is not premium yet.

---

## 6. The calculated experience: how we earn the return visit

The phrase we are designing to: **a mentally calculated experience** — the user
should feel that arithmetic was done on their behalf, and be able to see it.

### 6.1 The four primitives

Every surface answers one of these, in this order.

| Primitive | The question it answers | The artifact | Where it lives |
|---|---|---|---|
| **The Ledger** | *What changed since I last looked?* | "3 new · 1 closing · nothing else moved" | Feed top, digest line 1 |
| **The Fit** | *Why is this here, and does it fit me?* | 0.61 + three reasons + one gap | Every card |
| **The Briefing** | *What does the market look like this week?* | Band movement, new employers, deadlines | Weekly, WhatsApp + `/brief` |
| **The Move** | *What is the one thing to do now?* | "Apply to this before Friday" / "set a pay floor" | One per week, never two |

The arithmetic is already built (`constraints → relevance → utility`, the 0.61
score, the deadline bands). What is missing is **memory**: a stored snapshot of
what this person saw, so the product can compute a difference and say it out
loud. That is the single highest-leverage build in this document.

### 6.2 Why they come back (five triggers, ranked)

| Trigger | Mechanism | Surface | Frequency | Cost |
|---|---|---|---|---|
| **A saved job is closing** | Loss aversion on the user's own intent | WhatsApp utility message | Event, max 1/day | ~KES 0.52 |
| **Something genuinely new fits** | Novelty + relevance | Digest | Weekly (default) | ~KES 3.25 |
| **The market moved in their band** | Curiosity + self-interest | Weekly brief | Weekly | included |
| **Momentum** | Consistency + loss aversion, forgiven | Feed + digest footer | Weekly | free |
| **Their year in the market** | Identity + shareability | December recap | Annual | free |

Note the cost asymmetry, which is a design constraint, not a footnote: since
October 2026 a marketing template in Kenya costs roughly KES 3.20–3.30 and a
utility message inside the 24-hour window roughly KES 0.52. A daily marketing
digest is ~KES 97/month per user; a weekly one is ~KES 13. **The weekly default
is not a product nicety, it is the business model.** Alerts (utility) are cheap;
broadcasts are not.

### 6.3 The five visitor states

Different people need different bait. The product should know which one it is
talking to, and never ask a stranger to sign up before answering their question.

| State | How we know | What they need | The bait |
|---|---|---|---|
| **Cold** (from search) | No cookie, landing on a job/salary page | The answer, now, without a wall | Complete page + "6 more like this" + the deadline |
| **Curious** | 2+ pages, no profile | Proof the scope is real | One-tap demo profile: "see this feed as a 2024 admin graduate" |
| **Active** | Has a profile | A shorter list and a reason to trust it | The Fit, the Ledger, the Shortlist |
| **Committed** | Subscribed | Certainty between visits | Weekly brief, closing alerts, Momentum |
| **Dormant** | No visit 21+ days | A reason that is not a nag | "Your shortlist: 2 closed, 1 still open, 4 new in your band" |

### 6.4 Fun without sugar

The brief asks for fun and immersion with a premium feel. For a job seeker, fun
is not confetti — it is **relief, momentum, surprise, mastery and belonging.** We
get it from five places, all of them cheap and none of them childish:

- **Relief:** silence that is honest, and an end state that says "that's all of
  them".
- **Momentum:** a weekly run with a free skip, shown as four small marks, not a
  flame.
- **Surprise:** **the wildcard** — one role per week, clearly labelled, outside
  the user's filters, chosen because the evidence says they'd be good at it.
  Spotify's Discover Weekly mechanic, applied to work.
- **Mastery:** ⌘K, keyboard filtering, side-by-side compare. The product gets
  faster as the user gets better.
- **Belonging:** aggregates ("popular with admin graduates in Nairobi") and a
  WhatsApp Channel where the weekly three are announced to everyone — a public
  square next to the private digest.

**Immersion** comes from the market being visibly alive: today's counts, "checked
12 minutes ago", a closing-soon strip that is different on Friday than on Monday.
The site should feel like a desk in a newsroom, not a brochure.

---

## 7. Traffic: three engines

### Engine 1 — Search (the compounding one)

- One page per job, `JobPosting` JSON-LD, sitemap + Indexing API pings, 410 on
  close (§3.1).
- Programmatic answer pages, each with n, date range and method:
  `/salaries/<role>/<county>`, `/county/<name>`, `/closing-soon/<iso-week>`,
  `/employer/<slug>`.
- A public **market pulse** page: today's live roles, new this week, closing this
  week, median advertised band for the top families — no login, updated daily.
  This is the page journalists and AI answers cite, and citation is the new
  backlink.
- Every page carries the same evidence discipline, which is what makes it
  quotable: number, date, sample size, source.

### Engine 2 — Shareables (the cheap one)

- **The weekly three**: a 9:16 card, "3 roles closing this week in Nairobi",
  generated from the same data, no tracking pixels.
- **Your year in the market** (December): one card per idea, private by default.
- **The shortlist comparison**: a link that renders a read-only table of up to
  four jobs — useful in a WhatsApp group of classmates, which is exactly where
  Kenyan early-career job hunting happens.
- Rules: the artifact must be useful to someone who never visits the site; the
  brand mark travels, the funnel does not beg.

### Engine 3 — WhatsApp (the local one)

- **Channel** (free, unlimited followers, one-way) for the weekly public three
  and market notes — top of funnel, no template cost.
- **Personal digest** (paid template) is the committed layer; weekly by default.
- **Closing alerts** are utility (≈KES 0.52), capped at one per day.
- **Status** for the Friday "closing soon" card, posted from the same generator.
- Guardrail: no group spam, no unsolicited DMs, opt-in stored with a timestamp
  and a STOP that works (§ Phase 5/6 already built).

---

## 8. Build order

Scored by impact on the two things that matter — *return visits* and *being
found* — against effort. P0 is this design cycle.

| Priority | Item | Borrowed from | Why now | Effort |
|---|---|---|---|---|
| **P0** | The Ledger ("since you last looked") | Spotify S1, our own §6 | The only true retention primitive; makes silence meaningful | M |
| **P0** | `JobPosting` + sitemap + `/job/<id>` polish | Google G1–G2 | Free, compounding distribution; we already have the data | S |
| **P0** | Craft pass: motion, focus, hover, numerals, empty states | Linear N1–N3 | The "premium" the user asked for is mostly 200 lines of CSS | S |
| **P0** | Honest scarcity labels (deadline first, no fake urgency) | Airbnb A1 | Cheap, and it is the brand position | S |
| **P1** | Shortlist + compare + closing reminder | Airbnb A2 | Strongest return ticket we can build without accounts | M |
| **P1** | Weekly brief (market movement in your band) | Spotify S2 + our Briefing | Turns the digest from a list into a reason | M |
| **P1** | `/pulse` + `/salaries/...` pages | Google G3, Levels.fyi | The SEO engine, and it is quotable | M |
| **P1** | Momentum (weekly run + free skip) | Duolingo D1–D2 | Habit with a Kenyan cadence, no mascots | S |
| **P2** | ⌘K palette | Linear N2 | Delight for the power user; cheap | S |
| **P2** | The wildcard | Spotify S1 | Surprise, one per week, clearly labelled | S |
| **P2** | Your year in the market | Spotify S2 | December artifact; build in November | M |
| **P2** | Employer dossier | BrighterMonday B2 | Prepares the B2B option without selling it | M |
| **Never** | Points, badges, leaderboards, mascots, fake urgency | — | Breaks the premium promise | — |

**A note on the earlier decision.** The design pack previously said "no
gamification". This document narrows that rather than reversing it: no points,
badges, leaderboards, mascots or shame — but yes to a weekly ritual with
forgiveness, because the evidence that rituals work is overwhelming and the
brief explicitly asks for a reason to return. The distinction is *manipulation
versus momentum*, and the guardrail is that Momentum never counts applications,
only attention.

---

## 9. Open questions this raises

1. **Accounts.** The Ledger and the Shortlist both need continuity. A cookie
   survives a browser; not a phone. Do we introduce a light identity (phone +
   OTP) in v1, or run the Ledger on a long-lived signed cookie and accept the
   loss? *Leaning: signed cookie in v1, phone identity with the digest
   subscription.*
2. **The wildcard's honesty.** How do we label a role that ignores the user's
   filters without it reading as a bug? *Leaning: "Outside your scope — we
   thought you'd be good at it. Why?"*
3. **Employer dossiers before revenue.** Useful and risky: it is one step from a
   product employers pay to influence. *Leaning: read-only, candidate-side,
   no employer contact in v1.*
4. **How much of Wrapped travels to a job search.** Applications and rejections
   are not taste in music. *Leaning: only counts the user chooses to reveal; no
   outcomes, no employers by name.*
5. **Does the pulse page need a name?** *Leaning: "Market pulse" — plain, and it
   describes the calculation rather than the brand.*
