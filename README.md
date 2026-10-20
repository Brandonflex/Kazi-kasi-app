# Kazi-Kasi

A geo-anchored hiring radar for Kenya: complete, verified, reachable job discovery — starting with Nairobi.

> **Current phase: Phase 1 build.** The research pack is settled; the ingestion spine is
> built and tested offline. See [`docs/phase-1-build.md`](./docs/phase-1-build.md).

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

## Run it

```bash
python -m pip install -e ".[dev]"
python -m pytest                 # 101 tests, no network
kazikasi sources
kazikasi ingest --source brightermonday --store ./data/raw --out ./data/jobs.jsonl
kazikasi replay --source brightermonday --store ./data/raw
```

## Scope in one line

Every formal vacancy advertised in Kenya is a few thousand roles at any moment — small enough to enumerate, verify, and become the definitive record of. That is the bet.

## Contributing

Each phase of work lands as its own pull request and is not merged until it is reviewed. See the phase prompts in the refinement session document.
