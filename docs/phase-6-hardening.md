# Phase 6 — closing the gaps Phase 5 named

**Status:** built and tested (525 tests, all offline) · **Network required:** no
**Depends on:** [Phase 5](./phase-5-build.md) the digest

Phase 5 ended with an honest list of what it had not built. This phase closes
the three that mattered — **inbound STOP**, **delivery receipts**, **a
scheduler that respects cadence** — and fixes nine defects found while doing it.
Nothing here is a new surface; it is the difference between a feature that demos
and a feature that can be operated.

---

## 1. What runs today

```bash
python -m pytest                                            # 525 tests, no network

kazikasi digest --db ./data/kazi.db --subscribe 0712000000 \
    --cadence weekly --window 07:00-08:00 --max-items 3

kazikasi run --db ./data/kazi.db --explain      # why each subscriber is or is not due
kazikasi run --db ./data/kazi.db --once         # compose what is due, send nothing
kazikasi run --db ./data/kazi.db --once --send  # compose and deliver (needs credentials)
kazikasi run --db ./data/kazi.db --loop --send --interval 60

kazikasi serve --db ./data/kazi.db --demo       # + /webhooks/whatsapp, /webhooks/sms
```

```bash
# the handshake Meta requires before it will send anything
GET /webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=$WHATSAPP_VERIFY_TOKEN&hub.challenge=1

# replies and receipts
POST /webhooks/whatsapp   (X-Hub-Signature-256, signed with $WHATSAPP_APP_SECRET)
POST /webhooks/sms?token=$AT_WEBHOOK_TOKEN     (Africa's Talking form-encoded)
```

## 2. Consent is now revocable in the channel that took it

`webhooks.py` parses both providers into the same events and applies one set of
rules:

| Text | Action | Recorded as |
|---|---|---|
| `STOP`, `STOPALL`, `UNSUBSCRIBE`, `END`, `CANCEL`, `QUIT` | opt out, dated | `unsubscribed` |
| `START`, `YES`, `RESUME`, `SUBSCRIBE`, `UNSTOP` | consent again, re-dated | `subscribed` |
| `HELP`, `INFO`, `SAIDIA` | one segment back, once per inbound id | `help` |
| anything else | logged, no state change | `unrecognised` |

Three details that are the whole point:

- **Unknown numbers are still logged.** A STOP from a phone we never met is
  evidence; it lands in `consent_events` with `profile_id NULL`.
- **Signatures fail closed.** With `WHATSAPP_APP_SECRET` set, an unsigned or
  tampered body is a 403. Without a secret, the endpoint is a 503 *unless* the
  server is running as a demo — because an open webhook lets anyone unsubscribe
  anyone.
- **HELP replies are idempotent** on the inbound message id, so a provider
  retry does not produce two replies.

`consent_events` is append-only and keyed by `msisdn_hash`, which is what a DPA
2019 request for "when did they stop consenting" is actually answered from.

## 3. "Sent" now means "arrived"

`messages.state` was `sent` the moment a provider accepted the message. Receipts
fix that, and they are stored as **events** (`message_receipts`) rather than
overwritten columns:

- `delivered` / `read` → message becomes `delivered`, `delivered_at` is stamped,
  and the run is closed **only when no sibling message is outstanding**;
- `failed` → message becomes `failed` with the provider's reason;
- the state machine is **monotonic**: a late `sent` cannot un-deliver, and a
  late `failed` after delivery is logged but does not reverse it.

## 4. The scheduler, and why jitter is deterministic

`kazikasi run` is the cron-shaped entry point. The rules live in `scheduler.py`
and are tested:

| Rule | Consequence |
|---|---|
| cadence is real | `weekly` means one digest per rolling 7 days; it is not sent daily "because the loop runs daily" |
| the window is Nairobi time | 18:00–20:00 EAT is 15:00–17:00 UTC |
| jitter is keyed on the profile, not the date | a person's digest arrives at the same minute every day, and thousands of them still spread across the window |
| jitter clamps to the window | a 45-minute spread on a 10-minute window sends at 18:09, not never |
| "already served" outranks "jitter not elapsed" | the reason shown to the operator is the true one |

`--explain` exists because an operator needs to answer "why didn't Amina get a
digest?" without reading code.

## 5. The defects this phase found

Every row is a bug with a test that now fails if it returns.

| # | Defect | Why it mattered | Fix |
|---|---|---|---|
| 1 | `lstrip("www.")` on org hosts | strips a *character set*, so `webmail.acme.co.ke` → `ebmail.acme.co.ke`; corrupt identity evidence merges two employers | strip the prefix, not the letters |
| 2 | `sameAs` regex was case-sensitive | `HTTPS://…` produced no domain at all | `re.IGNORECASE` |
| 3 | MSISDN hash was plain SHA-256 | ~2×10⁸ candidates; a laptop reverses it in minutes, so the "anonymised" number was not anonymous | HMAC with `KAZIKASI_HASH_KEY`, plus a loud `hash_is_keyed()` signal |
| 4 | Multi-part digest + window | part 1 sent at 19:58, part 2 at 20:01 → part 2 skipped, and stranded until tomorrow, every day | a run that has started finishes |
| 5 | Empty afternoon rewrote a sent morning | `queue_digest` set the existing run to `empty`, erasing that a digest went out | only a run with nothing sent can become `empty` |
| 6 | Channel change left stale messages | switch to SMS, and the queued WhatsApp digest still went out | suppress when the channel no longer matches (fallbacks exempt) |
| 7 | `--all` meant all *profiles* | profiles with no number produced errors instead of being skipped | `--all` = active subscribers |
| 8 | Consent endpoints unthrottled | a loop could enumerate numbers through the subscribe form | in-process token bucket, 30/min per client, 429 |
| 9 | STOP logged twice | `unsubscribe()` and `opt_out_by_msisdn()` both wrote an event | one writer, one event |
| 10 | `messages` had no `run_id` | receipts could not close a run; the log could not be joined to the digest | column + index, backfilled by migration |
| 11 | `migrate()` had two identical branches | dead code that implied two paths where there was one | one condition |

Also: `X-Content-Type-Options: nosniff` on every response, and the v5 migration
adds columns to an existing `messages` table with a guarded `ALTER TABLE`
(tested by upgrading a real v4 file).

## 6. The week simulation

`tests/test_lifecycle.py` runs three subscribers, one weekly, through seven
tick-days with a transport that fails every third message, plus a STOP on day 3
and a START on day 5. It asserts invariants rather than snapshots:

1. one digest per person per day, never two;
2. no job sent twice to the same person, across the week;
3. nothing delivered on the two opted-out days, and service resumes after START;
4. every message has a `run_id`; every failure has a `last_error`;
5. a fallback exists only where a primary failed;
6. receipts close every accepted message forward.

That is the closest thing to "does this survive a week in production" that can
be run without network access.

## 7. What is still truthfully missing

- **A live send.** No credentials and no route in this sandbox: Meta and
  Africa's Talking are proven against stub clients that speak their payloads,
  not against the providers.
- **Templates and buttons.** Plain text only. STOP-by-button needs an approved
  template.
- **Media, location and interactive replies.** Text in, text out.
- **Exhausted pools.** Once someone has seen every job that fits — about a week
  on a small corpus — the digest goes quiet. That is the designed trade-off
  ("never re-send" beats "stay noisy"), but it needs a weekly "nothing new, here
  is your feed" notice rather than silence. Recorded as a v1.1 feature.
- **Costs.** Segments are counted; unit economics are not modelled.
- **Load.** The rate limiter is per-process and the scheduler is single-node.
