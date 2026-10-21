# Phase 11 — the scheduled tick: paying the last inch

**Status:** built and tested (874 tests, all offline) · **Network required:** no
**Depends on:** [Phase 5](./phase-5-build.md) digest composition, [Phase 10](./phase-10-signin.md) readiness

Phase 5 could compose a digest and queue it. Phase 6 built the outbox: retries
with backoff, consent re-checked at send time, suppression, receipts. What
neither had was a **clock**. `kazikasi outbox send` was a command a person ran.
A product that promises "constant update" cannot depend on a person remembering.

This phase adds the tick — one endpoint a scheduler calls — and, more
importantly, the three honest refusals that stand in front of it.

---

## 1. The endpoint

```
GET  /api/cron/run        (alias: /api/cron)
POST /api/cron/run
```

`vercel.json`:

```json
"crons": [{ "path": "/api/cron/run", "schedule": "0 15 * * *" }]
```

15:00 UTC is 18:00 EAT — the middle of the default evening window, leaving the
jittered send times (`scheduler.jitter_minutes`) two hours to spread across and
the SMS fallback time to run.

A tick is `scheduler.run_due(conn, transports, now=now, with_brief=True)`:
compose for everyone due, queue the weekly briefs, then deliver. The response is
the scheduler's own report plus `outbox` counts, so one curl answers "did
anything go out?"

## 2. The refusals

Vercel's scheduler sends `Authorization: Bearer $CRON_SECRET` when the variable
exists, and nothing when it does not. Both facts are load-bearing.

| # | condition | status | body |
| --- | --- | --- | --- |
| 1 | `CRON_SECRET` unset | `503` | `{"error": "cron not configured", "hint": "set CRON_SECRET"}` |
| 2 | token missing or wrong | `403` | `{"error": "bad cron token"}` |
| 3 | synthetic corpus, unless `KAZIKASI_ALLOW_SYNTHETIC_SEND=1` | `409` | `{"error": "refusing to send", ...}` |
| 4 | no transport credentials | `503` | `{"error": "no transport configured", "needs": [...], "fallback": [...]}` |

**Refusal 1 is first for a reason.** An endpoint that sends messages and needs no
secret is a spam relay with a URL. There is no "open in demo mode" branch here:
the endpoint is simply not configured until the variable exists.

**Refusal 3 is the one this phase exists for.** The deployed instance currently
serves a synthetic corpus (no `DATABASE_URL`). A cron tick there would compose
real messages about *invented vacancies* and deliver them to a real phone. That
is the single worst failure this product could produce, so it is refused by name
and the error says exactly how to proceed. `demo` (this process is a demo) and
`synthetic_build()` (this deployment is configured like production but has no
store) are both checked; either one means the vacancies are fabricated.

**Refusal 4 is a 503, not a cheerful 200.** "Nothing to send" and "nowhere to
send it" are different answers. A scheduler that gets 200 stops looking.

## 3. The transports

Two, on purpose. `channels.WhatsAppCloudTransport` posts to Meta's Cloud API;
`channels.SmsTransport` posts to Africa's Talking. A different provider is the
fallback because if WhatsApp is down — or the number is not on WhatsApp —
retrying WhatsApp is not a fallback. SMS is priced per segment, so the segment
count is recorded on every delivery.

Both map errors the same way:

| response | classification |
| --- | --- |
| 2xx | delivered |
| 429, 5xx, network error, timeout | `retryable = True` |
| other 4xx | `retryable = False` — this will never work |

That classification is what the outbox's backoff consumes. Tested against a fake
HTTP client: the Cloud API payload shape, the country code without the leading
plus, the `Idempotency-Key` header, Africa's Talking's form fields and sender ID,
segment counting, and constructing either transport without credentials raising
`RuntimeError` rather than failing at send time.

## 4. What `/api/health` now says

```json
{
  "ok": true,
  "schema": 7,
  "synthetic": true,
  "strict": false,
  "outbox": { "queued": 0, "sent_24h": 0, "failed_24h": 0, "suppressed": 0 }
}
```

`synthetic` and `strict` replaced a single `demo` flag that was answering two
different questions:

| question | field | source |
| --- | --- | --- |
| is the corpus invented? | `synthetic` | no `DATABASE_URL` |
| is this production? | `strict` | `KAZIKASI_DEMO=0` / `KAZIKASI_SECRET` posture |

They can disagree, and during the transition they do: production is strict *and*
synthetic. Collapsing them again would mean either refusing webhooks in local dev
or labelling fabricated data as real.

## 5. The other thing the tick carries: closing alerts

A saved job is the strongest signal this product ever gets — someone said "I want
this one". `shortlist.reminders_due()` already knew which saved jobs were inside
the 48-hour window and had the exact text; `/shortlist` rendered it, and a person
could click *Mark as sent*.

That button was the giveaway. **Nothing was sent.** The reminder was a thing you
told the product you had done.

`alerts.py` is the bridge: it takes the same text — the *same composer*, so the
page and the message cannot drift — and puts it in the outbox where consent,
backoff, suppression and receipts already live. The button is gone; the page now
says either *"Queued for your WhatsApp (+2547•••0111) at the next daily tick"* or
*"No message is queued: closing alerts need a subscription."*

Three rules, each with a test:

| rule | why |
| --- | --- |
| no active subscription, no alert | saving a job is an in-app action, not consent to a text |
| one message per job **per deadline** | a re-run, a crash and a restart converge; an extended deadline is a new promise, not silence |
| nothing is marked "reminded" at queue time | the outbox row *is* the record of having spoken; marking early tells the page the person was warned before the message left |

The idempotency key is `closing:<profile>:<job>:<YYYY-MM-DD>`. That date is the
whole design: it makes the alert exactly as durable as the deadline it is about.

`kazikasi run` carries alerts by default (`--no-alerts` opts out), and
`kazikasi alerts --dry-run` prints the text without queueing it.

## 6. Environment

| variable | needed for | if absent |
| --- | --- | --- |
| `CRON_SECRET` | the tick at all | 503, nothing runs |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp delivery | falls through to SMS |
| `AT_USERNAME`, `AT_API_KEY`, optional `AT_SENDER_ID` | SMS delivery / fallback | falls through to no transport → 503 |
| `KAZIKASI_ALLOW_SYNTHETIC_SEND` | testing delivery on the demo corpus | 409, nothing sends |

## 7. What this phase deliberately does not do

- **No in-process scheduler.** Vercel functions do not keep a timer. One endpoint,
  called from outside, is the only shape that survives a cold start.
- **No queue service.** The outbox *is* the queue, and it lives in the database.
  Adding Redis before there are users would add a second source of truth.
- **No retry loop inside the tick.** A tick sends what is due; the next tick
  retries what failed. Backoff lives on the row.
- **No alert for a job you merely viewed.** A view is not a promise. Only a save
  earns a message.
- **No delivery receipts in this phase.** `/webhooks/whatsapp` and
  `/webhooks/sms` already accept provider callbacks and fold them into
  `messages.receipts`; a test asserts the state machine, not a live provider.

## 8. Verification

```
874 passed in 26.75s
```

`tests/test_delivery.py` — 19 tests: the Cloud API request shape and normalised
number; 5xx / 429 / network error marked retryable; 4xx marked terminal;
Africa's Talking's form fields, sender ID and segment maths; both constructors
refusing without credentials; and the four cron refusals — plus the guard opening
under `KAZIKASI_ALLOW_SYNTHETIC_SEND=1`, a real tick delivering a due digest to a
fake transport at 18:45 EAT, `POST` reaching the same gate, and the health
endpoint reporting outbox counts that move when a digest is queued.

`tests/test_alerts.py` — 11 tests: no subscription means no message; a
subscriber with a job closing soon gets exactly one, with the same text the
shortlist page shows; a second tick does not repeat it; a moved deadline does;
an unsubscribed person, a job outside the window and a closed job get nothing; a
dry run queues nothing but shows the text; and one end-to-end tick that delivers
both the digest and the alert through a fake transport.

## 9. Next

1. **`CRON_SECRET` into Vercel**, then the first tick returns `409` — which is the
   correct answer today, and says so.
2. **`DATABASE_URL`**, which flips `synthetic` to `false` and turns refusal 3 into
   a live send.
3. **WhatsApp / Africa's Talking credentials**, which turn refusal 4 into
   delivered messages and populate `sent_24h` for real.
