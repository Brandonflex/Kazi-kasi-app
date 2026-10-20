# Phase 5 — the WhatsApp digest

**Status:** built and tested (421 tests, all offline) · **Network required:** no
**Depends on:** [Phase 4](./phase-4-build.md) constraints and ranking

D5 was answered in the refinement session as **two surfaces, not one**: a web
feed *and* a WhatsApp digest. Phase 4 built the feed. This phase builds the
half that reaches people who will never open a website on a laptop: five jobs,
one message, once a day, in the evening, on the phone they already have.

It is also the phase where compliance stops being a paragraph in the research
pack and becomes a table with a timestamp in it.

---

## 1. What runs today

```bash
python -m pytest                                                   # 421 tests, no network

kazikasi digest --db ./data/kazi.db --profile demo-fresher --subscribe "0712 000 000"
kazikasi digest --db ./data/kazi.db --profile demo-fresher --preview   # prints, sends nothing
kazikasi digest --db ./data/kazi.db --profile demo-fresher --queue     # queues one message
kazikasi digest --db ./data/kazi.db --all --dry-run                    # every subscriber

kazikasi outbox --db ./data/kazi.db                     # what is waiting
kazikasi outbox --db ./data/kazi.db --send --dry-run    # deliver to a fake transport
kazikasi outbox --db ./data/kazi.db --send              # needs WHATSAPP_* / AT_* credentials

kazikasi serve --db ./data/kazi.db --demo               # /digest is the composed message
```

`--preview` on the synthetic corpus:

```
*Kazi-Kasi* — 5 jobs for you today

1. *Records Management Assistant*
Public Service Commission of Kenya
Nairobi · closes 12 Nov · open to freshers · KES 30,550–39,720/month
matches admin
https://kazikasi.app/job/…

2. *Data Entry Clerk*
Jumuia Data Services
Starehe, Nairobi · closes in 5 days · open to freshers · KES 32,000/month
matches admin
…
Reply STOP to stop these. Reply HELP for the web feed.
```

Nothing in that output is hand-written. It is the exact string the transport is
asked to send — `/digest` renders it with the same function, which is why the
preview can be trusted.

## 2. A digest is not the feed, and that is the whole design

| Rule | Why |
|---|---|
| **Five cards, maximum** | A push is an interruption. The feed can be long; the message cannot. |
| **Closing soonest first** | The feed ranks by fit; a daily reminder is about the door closing. |
| **Never the same job twice** | `already_sent_job_ids()` reads the run history, so yesterday's list cannot repeat. |
| **Skip what was acted on** | Sending a job someone already applied to reads as "we weren't listening". |
| **Skip what was dismissed** | "Not for me" is the strongest signal the product has. Respect it. |
| **Skip scam-flagged and closed** | A push cannot carry a caveat. |
| **One reason per card** | The feed is the argument; the digest is the nudge. |
| **No empty digest** | Silence beats "no jobs today", which reads as failure. |

Selection happens on ranked matches, which means the digest inherits every gate
from Phase 4: impossible eligibility, unreachable distance, and closed deadlines
never reach a phone.

## 3. Consent is a row, not a checkbox

Kenya's Data Protection Act 2019 wants a record of *when* someone agreed, *to
what*, and *how they stop*. The `subscriptions` table holds exactly that:

| Column | Purpose |
|---|---|
| `profile_id` | one subscription per person, not per device |
| `msisdn`, `msisdn_hash` | the number, and a stable non-reversible handle for logs |
| `consented_at`, `consent_source` | when, and through which door (`cli`, `web`, `whatsapp_reply`) |
| `cadence`, `window_start`, `window_end` | daily, 18:00–20:00 **EAT** by default |
| `max_items`, `fallback_channel` | five, and SMS if WhatsApp cannot deliver |
| `unsubscribed_at` | **opt-out is dated, never deleted** — consent needs a history |

Four things follow from that design, and each has a test:

1. **A typo cannot be sent to.** `071234567` is rejected, not guessed at. A digest
   about someone's job search going to a stranger is the worst failure this
   product has.
2. **The number is masked everywhere it is read.** Logs, pages and the API show
   `+2547•••0000`.
3. **Consent is re-checked at send time**, not at compose time. Someone who
   replies STOP between composition and delivery gets nothing; the message is
   marked `suppressed`.
4. **Re-subscribing clears the opt-out and re-dates consent** rather than
   resurrecting the old record's timestamp.

## 4. The outbox, or: why sending has its own table

```
compose → digest_runs + digest_items → messages (queued) → sent | failed | suppressed
```

`messages` carries a **unique idempotency key** — `profile:date:channel:part`.
That single constraint is the safety story:

- a crash mid-loop and a restart converge on one message;
- a manual re-run the same day adds nothing;
- a retry after a 503 reuses the same key, so a provider that honours
  `Idempotency-Key` de-duplicates too.

Failures are visible by construction: `attempts`, `last_error`, and a state that
cannot be "vanished".

**Retries are bounded and spaced.** `MAX_ATTEMPTS = 3`, backoff `(0, 5, 30)`
minutes. A message inside its backoff window is *deferred*, not retried, and not
counted as an error.

**A retry is not a fallback.** After the last failure on WhatsApp the digest is
re-sent as **one SMS segment** through a different provider (Africa's Talking
shape). If WhatsApp is down, or the number simply is not on WhatsApp, retrying
WhatsApp is not a fallback. The fallback is queued through the same outbox, so it
inherits the same idempotency and the same visibility.

## 5. Fitting in 4096 characters

WhatsApp caps a text body at 4096 characters. A digest that truncates
mid-sentence is worse than one that sends fewer cards, so `split_message()` cuts
**only at card boundaries**, and only hard-splits a single block that could never
fit. Each part gets its own idempotency suffix, so part 2 arriving twice is still
one message.

In practice a five-card digest is ~1,000 characters and arrives as one message.
The split exists for the day it is not.

## 6. Timing is Nairobi time

`in_window()` converts to **UTC+3** before comparing, because 18:00 in Nairobi is
15:00 UTC and a service running in `us-east-1` would otherwise start pushing at
9 pm. Kenya has no daylight saving, so the offset is a constant, and the digest's
date — the thing the idempotency key is built on — is Nairobi's date too. A test
covers the 22:00 UTC case where UTC and Nairobi disagree about what day it is.

## 7. Schema v4

Four new tables (`subscriptions`, `digest_runs`, `digest_items`, `messages`).
`migrate()` applies versions in order, so a v3 database upgrades in place; the
`test_db.py` table set is the guard against a half-migration.

Two smaller database changes came out of this phase:

- `_now_iso()` accepts an explicit moment, so tests and backfills are
  deterministic instead of depending on the wall clock.
- A digest run is only demoted to `queued` when it actually queued something, so
  re-running a delivered day does not rewrite its history.

## 8. What this phase deliberately does not do

- **No template messages, no buttons.** Plain text only. Templates are the right
  long-term answer for opt-in broadcasts, but they are a Meta approval process,
  not a code change, and building against an unapproved template is guessing.
- **No inbound webhook.** "Reply STOP" is in the copy and the model supports it,
  but nothing parses replies yet — the CLI and `/digest` are how consent changes
  today. This is the largest known gap in the phase.
- **No delivery receipts.** `sent` means the provider accepted it, not that the
  phone showed it. `delivered` exists in the state machine and nothing sets it.
- **No scheduling loop.** `outbox --send` is a cron-shaped command; there is no
  daemon, no queue worker, no jitter.
- **No per-message costing.** Segments are counted (Africa's Talking bills per
  segment); unit economics are not modelled.
- **No live send.** This sandbox has credentials for nothing and a route to
  nothing, so both transports are proven against stub HTTP clients that speak the
  real payload shapes — 4xx terminal, 429/5xx retryable — not against Meta or
  Africa's Talking.

## 9. Next

1. **The STOP webhook**, because consent you cannot revoke in the channel you
   were contacted in is consent on paper only.
2. **Templates**, once there is a sender identity and something to submit.
3. **Delivery receipts**, to make `sent` mean "arrived" rather than "accepted".
4. **A scheduler with jitter**, so thousands of digests do not leave at 18:00:00.
5. **Measure the only metric that matters here:** how many people who receive a
   digest open a job, and how many of those apply. A digest nobody taps is
   messaging, not a product.
