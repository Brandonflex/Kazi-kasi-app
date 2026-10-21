# Phase 15 — go-live: what is left, and what to paste

**Status:** built and tested (1017 tests, all offline) · **Network required:** no
**Depends on:** [Phase 10](./phase-10-signin.md) readiness, [Phase 11](./phase-11-cron.md) the tick, [Phase 14](./phase-14-saved-searches.md) bundles

Phase 10 added `/auth/ready`, which answered one question honestly: *is sign-in
configured?* Useful, and too narrow. The real question arrives in a console at
11pm — *which variable goes in which field, and what changes if I paste it?* —
and the answer lived in six consoles and a README.

`/setup` is that answer, **derived from the running process**. Not a document that
ages: a snapshot of which variables exist, which provider is wired, whether the
corpus is real, and what the cron tick would do if it fired right now.

---

## 1. What it computes

| block | source | changes when |
| --- | --- | --- |
| session secret / strict mode | `accounts.readiness()` | `KAZIKASI_SECRET`, `KAZIKASI_DEMO` |
| each provider | `accounts.readiness()` | that provider's two variables |
| storage | `DATABASE_URL`, `KAZIKASI_BUNDLE`, `bundle.STATE` | either is set |
| delivery | `WHATSAPP_*`, `AT_*` | one transport has both halves |
| the tick | all of the above | any of the above |

Seven steps, each with a state — `set`, `missing`, `optional`, `not yet` — and the
page counts **required** steps separately from optional ones, so "0 of 3" never
looks like "0 of 7".

## 1a. A finished step stops instructing you

The first version rendered every card the same way, including the how-to note on
steps that were already done. On a deployment with the session secret set, the
**first card on the page** therefore told you to paste three variables you had
already pasted — and, being first, read like "step 1 of a to-do list". That is a
comprehension bug, not a cosmetic one: it made a finished task look like the
blocker.

Now the page is grouped by what to do about it:

| section | contents | treatment |
| --- | --- | --- |
| **Do these, in this order** | `missing` | numbered from 1, with variables, paste fields and console links |
| **Optional, when you want a second channel** | `optional` | same detail, no number |
| **Deliberately not yet** | `deferred` | why, and when to revisit |
| **Already done — nothing to do here** | `done` | one quiet line, **no instructions at all** |

The headline answers "what now?" in one line — `Next: Google sign-in, then 1
more.` — and switches to *"Nothing required is missing"* when the required list is
empty. Four tests pin it, including one that asserts the specific sentence
("There is no bulk-paste box") disappears once the secret exists.

## 2. Every step names its next click

A checklist that says *configure OAuth* is a riddle. Each missing step carries:

* the **variable names**, as `<code>` chips, exactly as Vercel wants them;
* the **exact value to paste**, in a copyable field with a Copy button —
  the redirect URI (`https://kazi-kasi-app.vercel.app/auth/google/callback`),
  the cron path (`/api/cron/run`), the schedule (`0 15 * * *`);
* the **console URL** to open;
* where it goes, in words: *Settings → Environment Variables → Add another*.

The three failure modes that cost the most time are written down on the page, in
the words of the error message you actually see:

| what you see | what it means |
| --- | --- |
| Google's `403. That's an error. Your client does not have permission to get URL /` | Google's own page, not this app — two accounts signed in at once. Private window, one account, straight to `projectcreate`. |
| LinkedIn's `Please input a valid LinkedIn Page URL` | that field wants a Company Page you administer, **not** the callback. Create a page, then pick it by name. |
| "I set the variable and nothing changed" | variables apply to a build. Deployments → ⋯ → Redeploy. |

## 3. Presence, never values

The page answers *is `KAZIKASI_SECRET` set?* and never *what is it*. A secret that
renders is a secret that leaks through a proxy log, a screenshot or a shared link.

Tests set five variables to one distinctive string and assert that string appears
in **neither the HTML nor the JSON**, while the page still reports each variable
as present.

## 4. The tick, explained before it fires

The cron endpoint refuses in a fixed order (503 → 403 → 409 → 503). Rather than
documenting that chain, the page runs it:

> **The scheduled tick, right now:** 409 refusing to send — needs real storage
> (DATABASE_URL or KAZIKASI_BUNDLE)

So the answer to "why did nothing send?" is on a page, in the same order the
endpoint would have answered, and it names what to change.

## 5. What this phase does not do

- **No write access.** Nothing here sets a variable; the page tells you where the
  box is. A web form that accepts a client secret is a secret in a request log.
- **No probing of external services.** It does not call Google to check your client
  id. That would be a network dependency in a health page, and a way to leak a
  secret into someone else's logs.
- **No login.** It reveals which variables exist — the same fact `/auth/ready`
  already exposes — and nothing more. It is `noindex` and disallowed in
  `robots.txt`.

## 6. Also in this phase: the clock bug the date found

The test suite had been passing for days and failed the morning after a date
change:

```
FAILED tests/test_accounts.py::TestActivity::test_opening_a_job_records_a_visit_once_a_day
assert 3 == 1
```

`_record_view` stores a **Nairobi** day and then de-duplicated by comparing
`substr(at, 1, 10)` — a **UTC** timestamp stamped by a *different* clock
(`tracking.record` used the wall clock, not the request's `now`). Two clocks and
two timezones were deciding "once per day":

- in production, between 21:00 and 23:59 UTC one Nairobi day spans two UTC dates,
  so the same job was recorded twice;
- in tests, whenever the wall clock's date differed from the fixture's.

Fixed at the root: `tracking.record()` takes `now`, `_record_view` compares the
Nairobi day it already stores in `detail` (with the old prefix check kept as a
fallback for existing rows), and three tests pin it — including one that visits
across the UTC/EAT boundary and one that visits on the next day and must record
again.

## 7. Verification

```
1017 passed in 28.85s
```

`tests/test_setup.py` — 40 tests: every step derived from the environment
(bare, secret set, the demo secret refused, Google, a database, each transport
alone, half a credential); no secret value in the HTML or the JSON while presence
is still reported; the exact redirect URI, cron path and schedule with a
copy button; every missing step naming its variables; the console links; the tick
chain through all four answers; `noindex`, `Disallow`, absent from the sitemap;
both console traps documented; all inline scripts allowed by the policy; no inline
handlers; and the JSON route agreeing with the page.
