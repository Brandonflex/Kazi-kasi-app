# Phase 14 — saved searches: the query, with a clock

**Status:** built and tested (974 tests, all offline) · **Network required:** no
**Depends on:** [Phase 12](./phase-12-search.md) search, [Phase 5](./phase-5-build.md) consent + outbox

Phase 12 built the query and Phase 11 built the clock. A saved search is the two
joined: *this* query, checked on *that* schedule, delivered on the channel the
person already consented to.

It is also the first feature that could quietly become spam, so the rules are the
feature.

---

## 1. Four rules

| rule | mechanism | failure it prevents |
| --- | --- | --- |
| **Consent first** | `watch()` refuses without an active subscription and returns `no_consent` | a "saved search" texting someone who never subscribed |
| **New means new** | `first_seen_at > last_run_at` (first run uses `created_at`) | re-announcing the same three jobs every morning |
| **One message per search per period** | idempotency `saved-search:<id>:<YYYY-MM-DD>` (or ISO week) | a crash, a retry or a second tick sending twice |
| **Quiet when nothing changed** | no message at all for an empty run | a notification that trains people to ignore notifications |

The watermark (`last_run_at`) advances **when the message is queued**, not when it
is delivered. A delivery failure is the outbox's problem and it retries; the
search's job is to not re-query yesterday.

## 2. What a message looks like

```
*6 new roles: “software” in Nairobi*
Software Support Analyst · Haba Data Systems Ltd — closes 29 Oct
Software Engineering Intern · Mkuki Software — closes 19 Nov
Data Entry Clerk · Jumuia Data Services — closes 25 Oct
+3 more
https://kazi-kasi-app.vercel.app/search?profile=…&q=software&county=Nairobi
Stop these alerts: …/search?profile=…&stop=4
```

Three items and a count. Dates are `29 Oct`, never `2026-10-29`: this arrives on
a phone. The stop link is a **GET that asks** — a confirmation page with a POST —
because a link that mutates state is a link a mail scanner can unsubscribe people
with.

## 3. Cadence

`daily` or `weekly`, per search. A daily search runs at most once per calendar day
(EAT); weekly waits seven days. The check is on `last_run_at`, not on the tick
schedule, so a scheduler that fires every ten minutes composes once and is silent
nine times.

## 4. Where it lives

- **`saved_searches`** — schema **v8**. Filters are normalised (`0`/`''` mean "not
  set") so the `UNIQUE` constraint actually deduplicates: re-saving the same
  query resumes it instead of adding a row, and resuming **never rewinds** the
  watermark.
- **`/search`** — a *Keep this search* form for subscribers; for everyone else,
  one sentence explaining that saved searches send messages, so they need a
  subscription first. That is the consent rule, not a paywall, and the page says
  so.
- **`/search/save`, `/search/stop`** — POST, throttled with the action bucket.
- **The tick** — `scheduler.run_due(..., with_searches=True)`, which the cron
  endpoint already passes. `kazikasi run --no-searches` opts out.
- **`kazikasi searches --watch/--stop/--run/--dry-run`** — the same thing from a
  terminal, including a dry run that prints the exact text and queues nothing.

## 5. What this phase does not do

- **No email.** The channel is whatever the subscription already uses. Adding
  email means a new transport, a new consent record, and a whole deliverability
  problem; the WhatsApp path already exists and is consented.
- **No "instant" alerts.** A job board that interrupts within a minute is a job
  board people mute. Daily is the promise; anything faster is a different product.
- **No saved search for a search you have never run.** The form sits under the
  results, so you save what you can see.
- **No cross-device identity.** Searches belong to a profile id, and profiles are
  still the demo ones; real identity arrives with real sign-in.

## 6. Verification

```
974 passed in 30.76s
```

`tests/test_saved_searches.py` — 31 tests: saving refused without a subscription
(and when unsubscribed); filters normalised; the label built from them; the same
search saving once and resuming without rewinding the watermark; an unknown
cadence refused; stopping hides it, twice is false, and one profile cannot stop
another's; due-exclusion for missing consent, opt-out and cadence; daily once a
day and weekly once a week; only arrivals after the watermark; the first run
starting at save time; the message naming the search, capping at three with
`+N more`, using human dates and carrying a stop link; one queued message with the
watermark advanced; a second tick silent; nothing new meaning no message;
unsubscribing stopping it; the dry run; the scheduler handing it to a transport;
and the page: the form for subscribers, the explanation for everyone else, the
list, the confirm-before-stop GET, and the two POSTs end to end.
