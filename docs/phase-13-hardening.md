# Phase 13 — hardening the response: one policy, two limits

**Status:** built and tested (918 tests, all offline) · **Network required:** no
**Depends on:** [Phase 9](./phase-9-sources.md) ingestion, [Phase 12](./phase-12-search.md) search

Two things from this phase were already true before it, and that was the problem:

* the site's responses carried **one** security header (`nosniff`) and it was
  copied into three places — the stdlib server, the function's success path and
  the function's error path. Three copies of a header is three chances to lose
  it;
* `/search` scored **every live row on every request**, and `/action` wrote a row
  per POST, with nothing in front of either.

Neither is a feature. Both are the difference between a shop window and a service.

---

## 1. One policy function

`serve.security_headers()` returns the whole policy. The stdlib server, the
serverless adapter and its error page all call it, so a header cannot exist on one
path and be missing on another. A test reads `api/index.py` off disk and asserts
the call appears on **both** the normal and the error path.

| header | value | why |
| --- | --- | --- |
| `Content-Security-Policy` | `default-src 'none'` + exact hashes | see §2 |
| `X-Content-Type-Options` | `nosniff` | a JSON body must never render as HTML |
| `X-Frame-Options` | `DENY` | no framing; `frame-ancestors` says it again for the modern parsers |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | job pages should not leak a search query onward |
| `Permissions-Policy` | geo/mic/camera/payment/usb denied | nothing here asks for them |
| `Cross-Origin-Opener-Policy` | `same-origin` | no `window.opener` handshake from another origin |
| `Cross-Origin-Resource-Policy` | `same-origin` | the HTML is not a public resource |
| `Strict-Transport-Security` | 180 days | **only** on the deployed origin, where TLS terminates |

## 2. A CSP with no `unsafe-inline`

The page has exactly two inline assets: the style sheet and the ⌘K palette
script. Both are hashed at import time, and the policy lists those two hashes:

```
style-src 'sha256-A4OJ…' 'sha256-Z3NA…'; script-src 'sha256-SA0Z…'
```

That is only honest if the markup actually contains no inline styles. It did —
23 `style="margin-top:26px"`-shaped attributes across eight views, all of which a
strict policy would silently drop. They are now utility classes (`.mt26`,
`.inline-ml`, `.codebox`, `.flush`), and three tests keep them gone:

* no `style="` attribute on any of nine rendered pages;
* no `onclick=`/`onload=` anywhere;
* the hashes in the header are **recomputed from the page that ships**, not read
  from a constant, so changing the CSS without changing the policy fails the
  build instead of breaking the design in a user's browser.

The deployment's error page gets the same treatment: its own `<style>` block is
hashed and allowed, rather than an `unsafe-inline` hole punched for an emergency
page that is normally never served.

## 3. Two more limits, and why they are separate

`_RateLimiter` is an in-process token bucket — not a substitute for an edge
limiter, but enough that a loop on one node cannot enumerate or hammer.

| bucket | limit | what it protects |
| --- | --- | --- |
| consent + webhooks (existing) | 30/min | the subscribe form, provider callbacks |
| **search** (new) | 60/min | the only page that ranks the whole graph per request |
| **action** (new) | 120/min | saves, dismissals and applies — one row each |

Separate buckets on purpose: a person who saves fifteen jobs while reading is not
abusing the subscribe form, and a script hammering `/search` should not lock a
reader out of their shortlist. Both are injected per process, so the pure router
(`handle()`) still does no I/O of its own when nothing is passed in — which is
what lets the tests call it a hundred times.

## 4. What this phase does not do

- **No CSRF tokens.** Every state-changing route is a `POST` to this origin and
  the session cookie is `SameSite=Lax`; the actions are idempotent (save, unsave,
  dismiss, apply-once). A token would add a round trip and a failure mode for a
  threat already closed by the cookie's `SameSite` and by the absence of
  cross-site form targets.
- **No nonce-based CSP.** Hashes are static because the assets are static; a
  nonce per response would mean the page could not be cached by anything, ever.
- **No WAF rules.** `vercel.json` is not a firewall, and pretending otherwise is
  how a deployment gets confident without being protected.
- **No rate-limit state in the database.** Two processes do not share a counter;
  the edge does. When it matters, the answer is the platform's limiter, not a
  table every request writes to.

## 5. Verification

```
918 passed in 27.76s
```

`tests/test_hardening_http.py` — 16 tests: the style and script hashes matching
what ships; no `unsafe-inline`/`unsafe-eval`; `default-src 'none'` and the rest
of the deny list; no inline style attributes on nine pages; HSTS only over HTTPS;
the other headers' exact values; the error page's own hash being allowed; the
serverless adapter calling the policy on both paths; and the two limits — search
429s at the limit, is per client, and is not reached when no limiter is injected;
actions 429 at theirs.
