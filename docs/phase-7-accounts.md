# Phase 7 — accounts, the CV, the application kit, and the tracker

Part 15 of the build. Four things landed together because they are one idea:
**a job board that stops at "here is a job" is a search box with better typography.**
The role of this product is to shorten the distance between seeing a role and being
the kind of applicant that role gets. That means the last mile — the form, the
contact, the record of what you already did — is the product, not an upsell.

Nothing here is a gate. Every surface still works signed out; the feed, the
shortlist, the brief and the tracker are all reachable without an account.

---

## 1. Sign-in — optional, three providers, one guest door

`kazikasi/accounts.py`. Providers: **Google**, **Apple**, **LinkedIn**, all
Authorization Code + **PKCE (S256)**. `start()` mints a state token and a
verifier; `claim_state()` consumes it (single use, 10 minutes, tied to one
provider) and hands back the verifier; `authorize_url()` builds the redirect;
`exchange()` swaps the code for an identity.

Sessions are **HMAC-signed cookies**, not server state. That is not a preference:
the deployed function has no writable disk, so a session table would evaporate on
every cold start. `kazi_id` is `HttpOnly`, `SameSite=Lax`, 30 days, signed with
`KAZIKASI_SECRET` (the demo default is `kazi-kasi-demo` and is named as such in
the code, because a secret that pretends to be one is worse than a labelled
placeholder).

### Why three providers and not "Sign in with Google"

| provider | why it earns the button |
| --- | --- |
| Google | the default on Android in Kenya; an email that is already verified |
| Apple | required on iOS if we ever ship an app; hides the email behind a relay |
| LinkedIn | the only one of the three that arrives carrying a professional headline |

Each is asked for **name, email and nothing else**. LinkedIn is explicitly not
asked for connections: we do not scrape a network, and the copy in the connects
block says so rather than implying otherwise.

### What is not configured, and says so

`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`, `APPLE_CLIENT_ID` / `APPLE_TEAM_ID`
/ `APPLE_KEY_ID` / `APPLE_PRIVATE_KEY`, `LINKEDIN_CLIENT_ID` /
`LINKEDIN_CLIENT_SECRET`. With none of them set, `/auth/<provider>/start` does
not 500 and does not pretend: it renders the exact redirect URI to register and
the names of the variables that are missing. In the demo deployment it also
offers a **synthetic account**, so the whole flow — session, account page, CV,
kit, tracker — can be walked end to end without a provider.

### Known limit, stated rather than hidden

`exchange()` reads the `id_token` claims and the userinfo endpoint but **does not
re-verify the id_token signature**. That is acceptable only because the token
arrives over TLS directly from the provider's token endpoint in response to our
own client-authenticated request — the standard code-flow argument. If a second
consumer of those claims ever appears, this is the line to fix first.

### Deleting is one click and it means it

`forget()` deletes the CV row, blanks the name and email, and keeps an anonymous
tombstone. A tombstone rather than a `DELETE` because the alternative is silent
resurrection: the same Google account signing in again would otherwise look like
a brand-new person, and any consent that had been withdrawn would come back with
them.

---

## 2. The CV — read here, never sent anywhere

`kazikasi/autofill.py`. Paste text, upload `.txt` / `.md` / `.pdf` (PDF through
`pypdf`, imported lazily so the web surface keeps importing nothing).

Every field comes back as **`{value, evidence, confidence}`** — the value, the
line it came from, and how sure the reader is. That shape is the whole argument:

* a field with no evidence does not exist;
* a field the reader is unsure about says so (a year-only range reads
  `about 2 yr` at 0.45, not `2 yr`);
* a gap stays a gap — `missing()` names what the CV does not say, and the kit
  prints "type this one" instead of guessing a phone number.

Extracted: name, email, phone, location, links, experience (computed, in months,
from explicit ranges), education, skills, referees, and the job titles that
suggest role families.

**What is stored is the fields, not the document.** `cvs` has no `text` column;
a test asserts it. The parse happens in the request, the evidence strings are
what survive, and no employer ever receives the file from us.

`profile_suggestions()` proposes a home county and role families — *suggestions*,
never silent edits to the scope. The feed's ranking does not change because a CV
was uploaded; the person still owns their filters.

---

## 3. The application kit — the last mile, prepared

`/job/<id>` now carries, in order: what the advert says, who to address, then the
**kit** — a table of every field an employer's form asks for, each labelled
`cv` / `profile` / `advert` / `default`, ready to copy — and a three-sentence
cover note assembled from the advert and the CV.

`autofill.kit()` covers name, email, phone, location, role applied for, employer,
earliest start, expected pay, notice, referee and the yes/no questions that
reject people by accident (right to work, willing to relocate).

Two rules hold the honesty of it:

1. **Nothing is submitted from here.** Applications happen on the employer's
   site. The copy says so on the page, not only in this document.
2. **"I applied" is your note to yourself.** It is a self-report the tracker
   counts; no employer is told, and no claim of an in-app application is made
   anywhere. `test_a_visitor_may_report_an_application_they_made` pins this.

`cover_note()` writes three sentences and no adjectives. "Passionate",
"dynamic", "hard-working" and "excellent" are asserted absent — a generated
cover letter that sounds like every other generated cover letter is worse than
a blank field.

---

## 4. Who you would be dealing with

`kazikasi/employer.py`. Everything here is **read from the advert we already
hold**, quoted, with the sentence that proves it:

* the **channel** the advert specifies (email, portal, hand delivery) — applying
  the wrong way is a silent rejection, and it is the most common avoidable one;
* a **named contact**, if one is written down (`Ms. Achieng Otieno, HR Manager`);
* a **role** where only a role is given;
* what is **missing** — "no named person", "no email or phone" — stated plainly.

There is a tempting version of this feature that scrapes LinkedIn for names,
guesses email patterns and presents a hiring team it cannot verify. We do not
build that version, and the page says why: *"Connects: we do not have your
network and will not scrape one."* Inventing a person is worse than an empty
section, because the applicant acts on it.

---

## 5. The tracker — saved, applied, visited, one row per job

`/activity`. Four tabs: **Everything / Saved / Applied / Visited**, with counts.

The record is the same `apply_events` table the ledger already used, so there is
one history in the product, not two. A job you saved, opened and applied to is
**one line**, showing the furthest thing you did with it; "unsaved" is a
transition, not a state, and it removes the save without erasing the visit.
Visits are recorded once per job per day — enough to be useful, not a hit
counter.

Nothing here is shared with an employer. The rail says so, and there is no
mechanism by which it could be.

---

## 6. `kazikasi run --brief`

The weekly brief now has a delivery path with the same discipline as the digest:

* **consent first, and separately** — no active subscription, no message
  (`unsubscribed`); a digest subscriber who never asked for the brief is
  `not_opted_in`. Consent to a daily digest is not consent to a weekly message:
  adding one to the other is how a product teaches people to mute it
  (`kazikasi digest --subscribe … --brief` records the second yes);
* **idempotent by week** — the key is `brief:<profile>:<ISO week in EAT>`, so a
  restart, a retry and a double tick all converge on one message, and next Monday
  gets a new one;
* **cost and cadence unchanged** — it goes through the same outbox, the same
  quiet hours and the same retry/fallback rules;
* **`--dry-run` writes nothing** and prints the body, which is how the message
  was reviewed before it was ever sent.

```
kazikasi run --db ./data/kazi.db --brief --send --dry-run
kazikasi run --db ./data/kazi.db --brief --send
```

The rendered body is 239 characters — five lines plus two links. A weekly message
that needs scrolling has stopped being a brief.

---

## 7. Schema v7

Additive and idempotent, as always:

| table | why |
| --- | --- |
| `accounts` | one row per person: provider, subject, email, name, kind, deleted_at |
| `cvs` | the **fields** and their evidence; no document text |
| `oauth_states` | single-use PKCE state, 10-minute expiry, provider-scoped |

`accounts` is not referenced by `profiles`. A scope is still a scope; an account
is who is holding it. Merging them would have made "sign out" mean "lose your
filters", which is exactly the gate this phase exists to avoid.

---

## 8. What this phase deliberately did not build

* **Auto-apply / in-app applications.** The last mile is the form, prepared. A
  product that submits applications on someone's behalf is selling volume to
  employers and risk to the applicant.
* **Referral graphs.** No scraping, no guessed emails, no "people you may know".
* **A login wall.** Not for the feed, not for the shortlist, not for the brief,
  not for the tracker.
* **CV storage as a document.** Fields and evidence only.

---

## Verification

```
742 passed in 24.83s
```

`tests/test_accounts.py` — 65 tests across cookies (forged, expired, malformed),
PKCE (single use, expiry, provider scope), the unconfigured-provider page, guest
distinctness and deletion, CV parsing and evidence, multipart and pasted
uploads, the kit's source labels, the dossier's quoting and its "we do not have
your network" line, the tracker's one-row-per-job rule, and `run --brief`'s
consent, idempotency and dry run. The final class asserts every public surface
still renders without a session.

The WSGI shim (`api/index.py`) was exercised directly for `/`, `/signin`,
`/account`, `/activity`, `/auth/google/start`, `/brief`, `/pulse`, `/salaries`,
`/county/nairobi` and `/api/health`, plus a guest → CV → account round trip with
a real cookie: all 200/303, `schema 7`.
