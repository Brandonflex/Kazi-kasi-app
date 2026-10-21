# Credentials: where they live, how to rotate, what to do when one leaks

This file contains **no secrets** and never will. It describes the shapes and the
runbook, because the failure this page exists to prevent is a client secret
pasted into a source file, a chat, or a screenshot — and then forgotten while the
deployment keeps working.

Two things enforce the rule instead of promising it:

- `tests/test_secrets_hygiene.py` scans every tracked file **and every untracked,
  non-ignored file** for credential shapes and fails the suite (so the window
  before `git add` is covered too);
- `.gitignore` covers `.env*`, `*.pem`, `*.p8`, `credentials.json`,
  `client_secret*.json`.

---

## 1. Where each credential belongs

| credential | where it lives | who can read it back |
| --- | --- | --- |
| `KAZIKASI_SECRET` | Vercel env vars | nobody (Vercel stores it write-only) |
| `GOOGLE_CLIENT_ID` | Vercel env vars | public — it is in the auth URL |
| `GOOGLE_CLIENT_SECRET` | Vercel env vars | Google Cloud console → Clients → your client |
| `LINKEDIN_CLIENT_*` | Vercel env vars | LinkedIn developer console → Auth |
| `DATABASE_URL` | Vercel env vars | Neon / Supabase dashboard |
| `WHATSAPP_TOKEN`, `AT_API_KEY` | Vercel env vars | the provider's dashboard; usually reissuable |
| `CRON_SECRET` | Vercel env vars | nobody — you generated it |

**"Otherwise it's gone forever" is half true.** Google's creation dialog says you
will not see the secret again *once that dialog closes* — but the client's detail
page in the console (`APIs & Services → Credentials → OAuth 2.0 Client IDs →
your client`) shows it again, masked, with a copy button. LinkedIn and Meta are
similar; Africa's Talking lets you regenerate.

What genuinely cannot be recovered is anything you generate yourself —
`KAZIKASI_SECRET` and `CRON_SECRET`. Those are only ever needed *inside* Vercel, so
"lost" only matters if you want to reproduce the deployment elsewhere. Generate
them there, once, and let them be write-only.

**The one habit worth having:** a password manager entry per project, holding the
values you actually need to reproduce the environment. Not a note file, not a
screenshot, not a chat.

## 2. The Vercel click path (there is no bulk paste)

1. **vercel.com/dashboard** → click the project behind `kazi-kasi-app.vercel.app`
2. **Settings** → **Environment Variables**
3. **Add another** once per variable. Each needs its own **Key** and **Value**.
4. Tick **Production**, **Preview** (and **Development** if you use the CLI).
5. **Save**, then **Deployments** → top entry → **⋯** → **Redeploy**.

A variable applies to the *next build*, never the running one. If nothing changed,
you have not redeployed.

## 3. If a secret has been shared

Treat it as public. The order matters:

1. **Rotate first, investigate second.** In Google Cloud: the client's detail page
   → **Add secret** → a second secret appears → copy it into Vercel → redeploy →
   verify sign-in → **delete the old secret**. Two secrets can be live at once
   precisely so this has no downtime.
   (For LinkedIn: **Auth** tab → *Client Secret* → **Regenerate**.)
2. **Check whether it was ever committed** — in file *contents*, not commit
   messages (where the pattern is talked about, legitimately):

   ```bash
   # the *shape* (20+ characters of value), not the bare prefix that prose mentions
   git grep -I -E 'GOCSPX-[A-Za-z0-9_-]{20,}' $(git rev-list --all) -- . | head
   ```

   No output means it never entered a tree. If it did, **rotation is what fixes the
   exposure**; rewriting history only cleans the tree, not the clones already out
   there.
3. **Check what it could do.** A *web application* OAuth client secret can only be
   used with a redirect URI registered on that client. It cannot read mail, call
   APIs on your behalf, or spend money. This is why the redirect URI list being
   exact matters more than the secret being long.
4. **Write the date down** in the deployment notes — not for compliance theatre,
   but because "when did we last rotate" is the question you ask at 2am.

## 4. What the deployment tells you

| page | answers |
| --- | --- |
| `/setup` | which variables exist, which step is missing, the exact string to paste where |
| `/api/setup` | the same as JSON |
| `/auth/ready` | sign-in configuration only: providers, redirect URIs, whether the demo secret is in use |
| `/api/health` | build, schema, corpus size, whether the corpus is synthetic, outbox counts |

All four report **presence, never values**. A test sets five variables to one
distinctive string and asserts it appears in neither the HTML nor the JSON.

## 5. Rotation cadence

Not on a calendar. Rotate when:

- a value has been shared anywhere (chat, screenshot, ticket, a colleague's
  laptop);
- someone with console access leaves;
- a provider emails about a leak you have never heard of.

A quarterly rotation for its own sake trains people to click through the one
rotation that matters.
