# Kazi-Kasi

A geo-anchored hiring radar for Kenya: complete, verified, reachable job discovery — starting with Nairobi.

> **Current phase: Phase 6 (hardening) + the design system.** The research pack is settled;
> ingestion, the job graph, the document lane, the tailored feed, the WhatsApp digest (with
> inbound STOP, receipts and a scheduler) are built and tested offline, and the brand and
> visual system are implemented. See the phase notes:
> [1](./docs/phase-1-build.md) · [2](./docs/phase-2-build.md) · [3](./docs/phase-3-build.md)
> · [4](./docs/phase-4-build.md) · [5](./docs/phase-5-build.md) · [6](./docs/phase-6-hardening.md)
> · [design system](./docs/design/README.md).

## Start here

- [Research pack index](./docs/research/README.md)
- [Executive brief](./docs/research/00-executive-brief.md) — the idea, the market, the users, the non-goals
- [Source landscape](./docs/research/01-source-landscape.md) — what we can ingest in Kenya, legally and practically
- [Technical blueprint](./docs/research/02-technical-blueprint.md) — schema, pipeline, documents, verification, geography
- [Refinement session](./docs/research/03-refinement-session.md) — decisions taken, decisions open, prompt pack
- [Expansion path](./docs/research/04-expansion-path.md) — Kenya → East Africa → Africa
- [Evidence log](./docs/research/05-evidence-log.md) — every claim and its source
- [Brand and IP check](./docs/research/06-brand-ip-check.md) — the name, the crowding, and the KIPI path
- [Phase 1 build](./docs/phase-1-build.md) — what the ingestion spine does, and how to run it
- [Phase 2 build](./docs/phase-2-build.md) — the job graph: identity rules, liveness, metrics, and the internal feed
- [Phase 3 build](./docs/phase-3-build.md) — the document lane: advert PDFs, "one advert, N posts", PSC and a county source
- [Phase 4 build](./docs/phase-4-build.md) — constraints → relevance → utility, distance bands, the freshness page, apply tracking
- [Phase 5 build](./docs/phase-5-build.md) — the WhatsApp digest: selection rules, consent, idempotency, retries, SMS fallback
- [Phase 6 build](./docs/phase-6-hardening.md) — inbound STOP, delivery receipts, the scheduler, and the defects they exposed
- [Design](./docs/design/README.md) — brand identity, visual system, and the feature cut line
  ([brand](./docs/design/00-brand-identity.md) · [visual system](./docs/design/01-visual-system.md) · [surfaces](./docs/design/02-product-surface-design.md) · [research log](./docs/design/03-research-log.md))

## Run it

```bash
python -m pip install -e ".[dev]"
python -m pytest                                    # 642 tests, no network

kazikasi sources                                    # registered sources + manifests
kazikasi ingest --source brightermonday --store ./data/raw --out ./data/jobs.jsonl
kazikasi replay --source brightermonday --store ./data/raw

kazikasi document --file advert.pdf --source psc     # one advert → its posts
kazikasi load  --db ./data/kazi.db --demo            # synthetic corpus
kazikasi match --db ./data/kazi.db --profile demo-fresher
kazikasi stats --db ./data/kazi.db
kazikasi slo   --db ./data/kazi.db
kazikasi digest --db ./data/kazi.db --profile demo-fresher --subscribe "0712 000 000"
kazikasi digest --db ./data/kazi.db --profile demo-fresher --preview   # the message, unsent
kazikasi outbox --db ./data/kazi.db --send --dry-run                   # deliver, offline
kazikasi run   --db ./data/kazi.db --explain                           # who is due, and why
kazikasi serve --db ./data/kazi.db --demo            # feed, /shortlist, /digest, webhooks on http://localhost:8765
```

## The deployed surface

The project's public face is **<https://kazi-kasi-app.vercel.app/>**, built by
Vercel from `main`. Every pull request also gets its own preview on the same
project, aliased to the branch, so unreviewed changes can be clicked through
before they land:

| what | where |
| --- | --- |
| this branch (pending changes) | <https://kazi-kasi-app-git-arena-882ede8a-kaz-6ecccc-brandonflex108-4814.vercel.app> |
| `main` (merged) | <https://kazi-kasi-app.vercel.app/> |

The preview alias is stable: push to the branch and the same URL rebuilds.
The footer names the deployed commit (`demo build 718f627`) and `/api/health`
returns it, so "is this the new build?" is one glance rather than a guess.

Public surfaces: `/` (the feed), `/shortlist`, `/pulse` (the market, counted),
`/salaries` (advertised pay, with sample sizes), `/county/<slug>`, `/sitemap.xml`
and `/robots.txt`.
`/api/health` is the quickest way to tell which build you are looking at:

```bash
curl -s https://kazi-kasi-app.vercel.app/api/health
# {"ok": true, "schema": 5, "live_jobs": 28, "sources_reporting": 4, ...}
```

How it is wired — there is no build step and no static output:

* `vercel.json` rewrites everything into one function, passing the original path
  as `__path`, because a rewrite is free to discard `PATH_INFO`.
* `api/index.py` is a WSGI adapter. It builds the synthetic corpus **in memory**
  on the first request in a warm instance and reuses it behind a lock; a
  function has no writable disk, so it never opens `data/kazi.db`.
* Routing lives in `kazikasi.serve.handle()` — the same function the local
  `kazikasi serve` uses — so the deployed site and the sandbox cannot drift.
* No `requirements.txt` is needed or wanted: the web surface imports only the
  standard library. `bs4`, `httpx`, and `pypdf` are imported lazily by the
  ingestion CLI, which never runs in a request.
* Remember the demo is seeded: `demo-fresher`, `demo-midcareer`,
  `demo-careerchange`, `demo-remote`. It is a read-only shop window for the
  design, not the live product — every push resets it.

## Scope in one line

Every formal vacancy advertised in Kenya is a few thousand roles at any moment — small enough to enumerate, verify, and become the definitive record of. That is the bet.

## Contributing

Each phase of work lands as its own pull request and is not merged until it is reviewed. See the phase prompts in the refinement session document.
