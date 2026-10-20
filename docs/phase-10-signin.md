# Phase 10 — making sign-in real: verified tokens, honest readiness

Phase 7 shipped the OAuth flow with one documented shortcut: `exchange()` read the
`id_token`'s claims **without verifying its signature**, on the standard argument
that the token arrived over TLS directly from the provider's token endpoint in
response to our own client-authenticated request.

That argument is about a network path, not about a token. It stops being true the
moment anything else consumes those claims — a log line, a second service, a
support tool. And "documented" is not the same as "safe".

This phase removes the shortcut and replaces it with the real check, adds the
deployment hygiene that sign-in needs, and gives you a command that says whether
any of it is actually configured.

---

## 1. What is verified now

`accounts.verify_id_token()` — in order, failing closed at every step:

| check | why it matters |
| --- | --- |
| **shape** (`three parts`) | anything else is not a JWT |
| **`alg` is RS256** | `alg: none` is the oldest JWT attack there is |
| **`kid` resolves to a published key** | otherwise a token could name its own key |
| **RS256 signature** | the actual security boundary |
| **`iss`** | Google / Apple / LinkedIn each have exactly one issuer we accept |
| **`aud`** | a token minted for another client is not ours |
| **`exp`**, **`iat`** | with ±120 s of leeway; a token with no expiry is refused |
| **JWKS fetched` | if the key set cannot be fetched, **verification fails** — it never silently passes |

The RSA check is implemented in `rsa_sha256_verify()` with nothing but integer
arithmetic: PKCS#1 v1.5 verification is `pow(signature, e, n)` plus a fixed padding
comparison, and it keeps the serverless bundle dependency-free (there is still no
`requirements.txt`). JWKS responses are cached for an hour per provider, so a
provider outage cannot take sign-in down, and a key rotation is picked up within
the hour.

`userinfo` is now used **only to fill gaps**, never to override a verified claim.
A response that contradicts the `id_token` loses.

## 2. Deployment hygiene

Two mistakes are common and both are silent:

* shipping without `KAZIKASI_SECRET`, so every session cookie is signed with the
  demo key;
* shipping with the demo key, so anyone who has read this repository can forge a
  session.

`strict_mode()` is on whenever `KAZIKASI_DEMO != 1`. In strict mode,
`session_cookie()` **raises** if the secret is missing or is the literal demo
value. A loud failure on the sign-in path is the correct outcome: it is the one
path where a quiet fallback is a vulnerability.

## 3. Readiness you can look at

```
kazikasi auth check --base-url https://kazi-kasi-app.vercel.app
kazikasi auth check --live          # also fetches each provider's signing keys
```

and, for a deployed instance:

```
GET /auth/ready
```

Both report the same thing and **neither returns a secret**: per provider, whether
it is configured, which environment variables are missing, the exact
`redirect_uri` to register, the issuer list, and whether the session secret is the
demo one. `kazikasi auth check` exits non-zero when no provider is configured, so
it works as a deploy gate.

The sign-in page also stops pretending: with nothing configured it says so once,
at the top, and points at `/auth/ready`.

## 4. The runbook — what actually has to be done, by a human

Nothing below can be done from this repository; it needs accounts at the three
providers. The code is finished; the credentials are the missing input.

### Google
1. Google Cloud Console → **APIs & Services → Credentials → Create credentials →
   OAuth client ID → Web application**.
2. Authorised redirect URI: `https://kazi-kasi-app.vercel.app/auth/google/callback`
   (and the same path on the branch preview domain).
3. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`.
4. Consent screen: scopes `openid`, `email`, `profile` only.

### Apple
1. Apple Developer → **Certificates, Identifiers & Profiles → Services ID**.
2. Enable **Sign in with Apple**, add the domain and the return URL
   `/auth/apple/callback`.
3. Create a **key** (`.p8`) and note the Key ID and Team ID; Apple's client secret
   is a short-lived JWT signed with that key, so it must be regenerated (at most
   every six months) — that rotation is the operational cost of Apple sign-in.
4. Set `APPLE_CLIENT_ID`, `APPLE_CLIENT_SECRET` (the generated JWT).

### LinkedIn
1. LinkedIn Developers → **Create app** → **Sign In with LinkedIn using OpenID
   Connect** product.
2. Authorised redirect URL: `https://kazi-kasi-app.vercel.app/auth/linkedin/callback`.
3. Set `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`.
4. Requested scopes: `openid profile email`. **Connections are not requested**, and
   the connects block on the job page says so.

### Then, on the deployment
```
KAZIKASI_SECRET=<32+ random bytes, base64>
KAZIKASI_DEMO=0
```
`KAZIKASI_DEMO=0` also turns on strict mode, so a missing secret fails at the
first sign-in rather than shipping a forgeable cookie.

## 5. What is still not done, and why it is acceptable

* **Apple's client secret rotation** is manual. Automating it needs the `.p8` in
  the deployment environment and a scheduled job; at this scale, a calendar
  reminder is the honest solution.
* **No email/password login.** Passwords are a liability we do not need to carry;
  three providers plus a guest path cover the audience.
* **No session revocation list.** Sessions are stateless HMAC cookies; "sign out"
  clears the cookie. Deleting an account tombstones the row, so a stale cookie
  reads as no account. A server-side revocation list would need the disk the
  deployment does not have.

---

## Verification

```
838 passed in 25.87s
```

`tests/test_auth_hardening.py` — 35 tests, with a throwaway 2048-bit key that signs
nothing real: a valid signature verifying; a flipped byte failing; a truncated
signature failing rather than crashing; `alg: none` refused; a tampered payload
refused; a token signed by an unpublished key refused; wrong issuer, wrong
audience, expired, no-expiry and future-dated tokens refused; a list audience
accepted when ours is in it; **a JWKS fetch failure failing closed**; keys cached
across calls; Apple and LinkedIn issuer separation; `exchange()` verifying before
trusting; `userinfo` unable to override a verified claim; readiness listing missing
variables without ever returning a secret; strict mode refusing the demo secret
(absent and literal); a cookie signed with one secret failing under another; and
the `/auth/ready` endpoint plus the CLI exit codes.
