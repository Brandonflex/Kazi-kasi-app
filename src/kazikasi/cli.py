"""Command line entry point.

    kazikasi sources
    kazikasi ingest --source brightermonday --store ./data/raw --out ./data/jobs.jsonl
    kazikasi replay --source brightermonday --store ./data/raw
    kazikasi canary --source all
"""

from __future__ import annotations

import argparse
import json
import sys

from .canary import run as run_canary
from .pipeline import HttpFetcher, ingest, write_jsonl
from .rawstore import FileRawStore
from .replay import replay, write_report
from .sources import REGISTRY


def _select_sources(name: str) -> list[str]:
    if name == "all":
        return sorted(REGISTRY)
    return [name]


def _build_adapter(name: str):
    cls = REGISTRY.get(name)
    if cls is None:
        raise SystemExit(f"unknown source {name!r}; choose from {', '.join(sorted(REGISTRY))}")
    return cls()


def cmd_sources(_: argparse.Namespace) -> int:
    rows = []
    for name, cls in sorted(REGISTRY.items()):
        manifest = cls.manifest
        rows.append(
            {
                "id": manifest.id,
                "label": manifest.label,
                "access": manifest.access,
                "tier": manifest.tier,
                "cadence_minutes": manifest.cadence_minutes,
                "requires_auth": manifest.requires_auth,
                "terms_reviewed_at": manifest.terms_reviewed_at,
                "supports": list(manifest.supports),
            }
        )
    print(json.dumps(rows, indent=2))
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    store = FileRawStore(args.store)
    fetcher = HttpFetcher(min_interval=args.min_interval)
    summaries = []
    failed = False
    try:
        for name in _select_sources(args.source):
            report = ingest(
                _build_adapter(name), fetcher, store, pages=args.pages, limit=args.limit
            )
            summary = report.summary()
            if args.out:
                summary["written"] = write_jsonl(report.candidates, args.out)
            summaries.append(summary)
            failed = failed or bool(report.errors)
            for error in report.errors[:5]:
                print(f"  {name} error: {error}", file=sys.stderr)
    finally:
        fetcher.close()

    print(json.dumps(summaries[0] if len(summaries) == 1 else summaries, indent=2))
    return 1 if failed else 0


def cmd_canary(args: argparse.Namespace) -> int:
    fetcher = HttpFetcher(min_interval=args.min_interval)
    results = []
    try:
        for name in _select_sources(args.source):
            results.append(run_canary(_build_adapter(name), fetcher, sample=args.sample).to_dict())
    finally:
        fetcher.close()
    print(json.dumps(results, indent=2))
    return 0 if all(r["ok"] for r in results) else 1


def cmd_replay(args: argparse.Namespace) -> int:
    adapter = _build_adapter(args.source)
    store = FileRawStore(args.store)
    report = replay(adapter, store, source_id=args.source)
    if args.report:
        write_report(report, args.report)
    print(json.dumps(report.to_dict(), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kazikasi", description="Kazi-Kasi ingestion spine")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sources = sub.add_parser("sources", help="list registered sources")
    p_sources.set_defaults(func=cmd_sources)

    p_ingest = sub.add_parser("ingest", help="fetch, store and parse one source (or 'all')")
    p_ingest.add_argument("--source", required=True)
    p_ingest.add_argument("--store", default="./data/raw")
    p_ingest.add_argument("--out", default=None)
    p_ingest.add_argument("--pages", type=int, default=1)
    p_ingest.add_argument("--limit", type=int, default=None)
    p_ingest.add_argument("--min-interval", type=float, default=1.0)
    p_ingest.set_defaults(func=cmd_ingest)

    p_replay = sub.add_parser("replay", help="re-parse stored payloads offline")
    p_replay.add_argument("--source", required=True)
    p_replay.add_argument("--store", default="./data/raw")
    p_replay.add_argument("--report", default=None)
    p_replay.set_defaults(func=cmd_replay)

    p_canary = sub.add_parser("canary", help="check that a source still parses (network)")
    p_canary.add_argument("--source", default="all")
    p_canary.add_argument("--sample", type=int, default=1)
    p_canary.add_argument("--min-interval", type=float, default=1.0)
    p_canary.set_defaults(func=cmd_canary)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
