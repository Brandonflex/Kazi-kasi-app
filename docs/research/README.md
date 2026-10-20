# Kazi-Kasi — Research Pack

Research-only round. **No product code yet** — by design. The purpose of this folder is to argue the idea into a shape that is worth building, using evidence rather than enthusiasm.

**Status:** draft v0.1 · 2026-10-20

---

## Read in this order

| # | Document | What it answers | Length |
|---|---|---|---|
| 0 | [`00-executive-brief.md`](./00-executive-brief.md) | What are we building, why this, why now, what do we refuse to build | ~10 min |
| 1 | [`01-source-landscape.md`](./01-source-landscape.md) | What data exists, what we can legally take, what it costs, who else is doing this | ~20 min |
| 2 | [`02-technical-blueprint.md`](./02-technical-blueprint.md) | How it is built: schema, ingestion, identity, lifecycle, geography, matching, ops | ~25 min |
| 3 | [`03-refinement-session.md`](./03-refinement-session.md) | The twelve decisions to settle, with recommendations and a prompt pack | ~15 min |
| 5 | [`05-evidence-log.md`](./05-evidence-log.md) | Every claim, its source, and its confidence level | reference |

---

## The one-paragraph version

Kazi-Kasi is a **geo-anchored hiring radar**. It continuously watches the hiring internet — employer ATS boards first, structured job markup second, Romanian public registries and local boards third — and resolves every posting into one live, deduplicated, provenance-tracked job graph. It then answers, for one person, in their own language and travel reality, the only question that matters: *what is actually open, actually reachable, and actually worth my time?*

Three commitments: **live, not listed** · **reachable, not nearby** · **explained, not scored**.

---

## Why research before code

The category has already commoditised the easy parts. "AI job matching" is a feature every competitor ships and every model vendor gives away. What is *not* commoditised is a trustworthy data layer: knowing which of six copies is the real job, whether it is still open, and whether you can actually get there by 9am.

That layer is unglamorous, expensive to build, and impossible to fake in a demo. Which is precisely why it is the right place to start.

---

## What this round produced

- A market map of four competitor clusters and the specific gap we intend to occupy.
- A scored inventory of every ingestible source lane, with access model, quality, freshness, cost, and legal risk.
- A legal posture for EU/Romania collection, grounded in current case law and the deferred AI Act timeline.
- A canonical data schema and an eight-stage pipeline design that can be operated by one or two people.
- A 90-day phased build sequence with acceptance criteria and a kill-criteria register.
- Twelve explicit decisions, each with a recommendation, so the next conversation is about choices rather than vibes.

## What this round did not produce

- No code, no scaffolding, no dependencies. Intentionally.
- No visual design.
- No legal opinion — the compliance sections are a design posture, and they need a Romanian/EU DPO review before any public launch.
- No confirmed partnerships or API keys. Six such unknowns are listed in [`05` §7](./05-evidence-log.md).

---

## Immediate next step

Open [`03-refinement-session.md`](./03-refinement-session.md), answer **D1–D3**, and the Phase 1 build brief is ready to run.
