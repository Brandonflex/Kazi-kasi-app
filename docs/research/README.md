# Kazi-Kasi — Research Pack (Kenya)

Research-only round. **No product code yet** — by design. The purpose of this folder is to argue the idea into a shape worth building, using evidence rather than enthusiasm.

**Status:** draft v0.2 · 2026-10-20 · Kenya-first
**v0.1 was Romania-first and is superseded.** The architecture survived the pivot; the market, sources, law and geography did not.

---

## Read in this order

| # | Document | What it answers | Length |
|---|---|---|---|
| 0 | [`00-executive-brief.md`](./00-executive-brief.md) | The idea, the market, the user, the non-goals, the 90-day shape | ~10 min |
| 1 | [`01-source-landscape.md`](./01-source-landscape.md) | What exists in Kenya, what we can legally take, what it costs | ~20 min |
| 2 | [`02-technical-blueprint.md`](./02-technical-blueprint.md) | Schema, ingestion, documents, identity, verification, geography, matching | ~25 min |
| 3 | [`03-refinement-session.md`](./03-refinement-session.md) | Decisions taken, decisions open, kill criteria, prompt pack | ~15 min |
| 4 | [`04-expansion-path.md`](./04-expansion-path.md) | Kenya → East Africa → Africa, and what must be rebuilt | ~8 min |
| 5 | [`05-evidence-log.md`](./05-evidence-log.md) | Every claim, its source, and its confidence | reference |

---

## The one-paragraph version

Kazi-Kasi is a **geo-anchored hiring radar for Kenya**. It watches every place a real job is advertised — boards, public-service portals, NGO feeds, employer career pages, PDFs and scanned adverts — resolves them into one live, deduplicated, provenance-tracked job graph, and tells one early-career jobseeker in Nairobi which roles are **real, reachable, safe to apply for, and worth their time**.

Three commitments: **complete, not aggregated** · **verified, not listed** · **reachable, not nearby**.

---

## The finding that changed the design

Every global competitor optimises for coverage at scale. In Kenya, the entire formal advertised market is **a few thousand live roles at any moment** — BrighterMonday showed about 1,100 for the whole country. You do not need to sample that market. You can **enumerate it, verify it, and become the definitive record of it.**

That inverts the strategy:

- Don't compete on "AI matching" — SwiftKazi, KaziChat and others already claim that label locally, cheaply.
- Compete on **completeness with proof**, **liveness**, **eligibility honesty** (`entry_fit`), **scam screening**, and **commute reality**.
- Those are unglamorous, operationally expensive, and impossible to fake in a demo — which is exactly why they are defensible.

---

## Why research before code

The category has commoditised the easy parts; every board and every wrapper now ships "smart matching". What is not commoditised is trust infrastructure: knowing that six adverts are one job, that it closed on Friday, that it does not ask for a fee, and that you can reach it by 8am.

That layer is boring, local, and hard. It is also the only thing in this market that compounds.

---

## What this round produced

- A market map of six competitor clusters in Kenya, and the specific gap we intend to occupy.
- A source inventory covering boards, public-sector portals, NGOs, employer pages, documents, and the social lane we are deliberately excluding.
- A Kenya-specific legal posture grounded in the Data Protection Act 2019, ODPC enforcement, the s.50 localisation rule, and the current status of the AI Bill.
- A canonical schema and eight-stage pipeline built for a document-heavy, mobile-first, WhatsApp-distributed market.
- A verification and scam-screening design with named evidence criteria.
- A Nairobi geography model built on the freely available Digital Matatus GTFS.
- Twelve decisions, with three taken, one delegated, and the rest recommended.
- A kill-criteria register, so stopping is a judgement rather than a mood.

## What this round did not produce

- No code, no scaffolding, no dependencies. Intentionally.
- No visual design.
- No legal opinion — the compliance sections are a design posture and need Kenyan counsel.
- No confirmed partnerships or API approvals. Ten such unknowns are listed in [`05` §7](./05-evidence-log.md).

---

## Immediate next step

Answer D5, D6, D8–D10 and D12 in [`03-refinement-session.md`](./03-refinement-session.md), and the Phase 1 build brief is ready to run.
