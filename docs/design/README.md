# Design — the decisions, in one page

**Status:** direction chosen and implemented (brand + visual system live in `serve.py`)
**Researched:** October 2026 · **Sources:** [research log](./03-research-log.md)

This folder narrows the look, the voice, the features and the brand from
"a job app for Kenya" into something that can be built against. Five documents:

| Doc | Answers |
|---|---|
| [00-brand-identity](./00-brand-identity.md) | What is this called, what does it mean, how does it sound, what does the mark do? |
| [01-visual-system](./01-visual-system.md) | The tokens: colour roles, type, spacing, components, accessibility contract |
| [02-product-surface-design](./02-product-surface-design.md) | The screens, the hierarchy, the features we are **not** building, and the open questions |
| [03-research-log](./03-research-log.md) | What was read, and what it changed |
| [04-market-teardowns](./04-market-teardowns.md) | Ten platforms, thirty borrowings, the premium rules, and the retention model |

---

## The seven decisions

1. **Kazi-Kasi means "work — and fast."** *Kazi* is work/job; *kasi* is speed or
   force. The hyphen is the pause between them. The brand is not "AI hiring";
   it is **speed with proof**.
2. **The product is a scope, not a marketplace.** The mark, the language and the
   layout all come from one idea: *your radius, your fit, verified.* Not a
   catalogue of every job in Kenya.
3. **Colour carries meaning, not decoration.** Forest green = verified/live,
   amber = closing soon, red = **risk only, never urgency**. That last rule is
   deliberate: competitors use warm red for alerts, and red-for-everything is
   how a job board starts to feel like a scam warning.
4. **No webfonts, no photography, no icon set download.** System fonts, inline
   SVG, and evidence instead of imagery. On a 2–4 GB Android phone on metered
   data, a brand that costs 300 KB is a brand that loads slowly.
5. **The digest is the brand's front door.** Most people will meet Kazi-Kasi as
   a WhatsApp message, not a website. So the message is designed first and the
   site follows it: one card, one reason, one link, STOP in the footer.
6. **Voice: a well-informed cousin, not a recruiter.** Short sentences, no
   exclamation marks, no "opportunity of a lifetime". Every claim has a
   timestamp or a source behind it.
7. **Two surfaces only in v1** — the web feed and the WhatsApp digest — and the
   employer-facing product is explicitly out of scope until the seeker side has
   a returning user.

## What is deliberately *not* decided yet

- **The final name.** "Kazi" is crowded (KaziChat, KaziKit, KaziNest, SwiftKazi)
  and BrighterMonday already uses *"Kazi Kwako!"*. The mark is designed to work
  without the word, and the KIPI filing decision is in the brand doc.
- **Bilingualism.** English-first with Swahili where it is already universal
  ("kazi", "safari", "pole pole") — but the policy and its cost are written down,
  not assumed.
- **Revenue.** Nothing in the design forecloses employer placement, but nothing
  in v1 depends on it.

Those are the next conversation, and they are listed with trade-offs in
[02 §7](./02-product-surface-design.md).

## What the market study added

[04-market-teardowns](./04-market-teardowns.md) is a separate axis: not what we
look like, but what we borrow from products that already work, and what we
refuse to take. It produced one build instruction and one css-sized one, both
shipped:

- **The ledger** — the feed now remembers the last visit (a signed, timestamp-only
  cookie) and opens with the diff: *"3 new since Tue 13 Oct · 4 closing this week"*.
  This is the first implementation of the "mentally calculated experience";
  a first visit says so instead of inventing a number.
- **The craft layer** — 160ms hover/lift, a warming hairline, tabular figures and
  a `prefers-reduced-motion` override, which is where most of the "premium" in a
  server-rendered page actually lives.
- **Structured data** — every job page emits one honest `JobPosting` block
  (`directApply: false`), which is the free distribution channel in this category.
- **The shortlist** — save from the card, compare up to four side by side, and
  earn exactly one reminder 48 hours before the deadline (Airbnb A2, `§3.9`).
  A save is never shared with an employer.
- **The public market pages** — `/pulse` (live, new, closing, median band by
  county), `/salaries` (advertised pay with n on every row) and `/county/<slug>`,
  each computed from checked adverts, each carrying its window. This is §7's
  search engine, in its smallest honest form, plus `sitemap.xml` and `robots.txt`.
- **Momentum** — the weekly run (Duolingo D1–D2, `§3.7`): ISO weeks in EAT, one
  forgiven week, no points and no flame. Opening the brief counts; applying never
  has to.
- **The weekly brief** (`/brief`) — the Briefing primitive from §6.1: what is
  new, what closes, whether advertised pay moved, and one move. The page prints
  the exact WhatsApp message it would send.
- **⌘K** — one search box over the page's own index of jobs, counties and pages
  (Linear N2, `§3.10`). Invisible until pressed; every action still has a
  visible path.
- **The wildcard** — one role a week that ignores the scope, labelled *outside
  your scope*, deterministic per person per week, and only ever one fixable
  blocker away (Spotify's Discover Weekly mechanic, `§3.8`).

- **Sign-in, kept optional** (`/signin`, `/account`) — Google, Apple and LinkedIn
  with PKCE, and a guest door that withholds nothing. The reason to sign in is
  continuity and the application kit, never access to jobs. Deleting an account
  deletes the CV and blanks the identity.
- **The CV as evidence** — every field keeps the line it came from and a
  confidence; gaps stay gaps. The kit fills an employer's form from it and says
  which source each value came from.
- **The job page as the last mile** (`/job/<id>`) — the evidence panel, the
  channel the advert actually specifies, a named contact only when one is
  written down, what the advert does not say, and a direct route to apply.
- **The tracker** (`/activity`) — saved, applied and visited, one row per job
  showing the furthest thing done. The same `apply_events` the ledger already
  used, so the product has one history rather than two.

- **Employer dossiers** (`/employers`, `/employer/<slug>`) — BrighterMonday's B2
  idea, candidate-side and free: what they advertise, the pay they publish with
  `n`, the median run to deadline, and what the advert does not say. Merged names
  are listed; nothing about ordering is for sale.
- **Your year in the market** (`/year`) — Spotify's recap without the confetti:
  private, `noindex`, no rejection count, no interview rate, and a shareable card
  that cannot name an employer you applied to.

The document also narrows the earlier "no gamification" rule rather than
reversing it: no points, badges, mascots or leaderboards — but yes to a weekly
ritual with forgiveness, because the evidence that rituals drive returns is
overwhelming and the brief asked for one.
