"""Command line entry point.

    kazikasi sources
    kazikasi ingest --source brightermonday --store ./data/raw --out ./data/jobs.jsonl
    kazikasi replay --source brightermonday --store ./data/raw
    kazikasi canary --source all

    kazikasi document --file advert.pdf --source psc     # one advert → its posts

    kazikasi init  --db ./data/kazi.db
    kazikasi load  --db ./data/kazi.db --demo          # synthetic corpus
    kazikasi stats --db ./data/kazi.db
    kazikasi review --db ./data/kazi.db
    kazikasi serve --db ./data/kazi.db --demo
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import db as database
from .canary import run as run_canary
from .corpus import load_corpus
from .documents import DocumentError, document_to_candidates
from .graph import apply_liveness, open_reviews, upsert_candidate
from .metrics import health as metrics_health
from .metrics import stats as metrics_stats
from .models import JobCandidate
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
    conn = database.connect(args.db) if args.db else None
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
            if conn is not None:
                actions: dict[str, int] = {}
                for candidate in report.candidates:
                    action = upsert_candidate(conn, candidate).action
                    actions[action] = actions.get(action, 0) + 1
                summary["graph"] = actions
            summaries.append(summary)
            failed = failed or bool(report.errors)
            for error in report.errors[:5]:
                print(f"  {name} error: {error}", file=sys.stderr)
    finally:
        fetcher.close()
        if conn is not None:
            liveness = apply_liveness(conn)
            summaries.append({"liveness": liveness})
            conn.close()

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


def cmd_document(args: argparse.Namespace) -> int:
    """Parse one advert document from disk. No network, no source needed."""
    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"no such file: {path}")
    content_type = "application/pdf" if path.suffix.lower() == ".pdf" else "text/html"
    try:
        candidates = document_to_candidates(
            path.read_bytes(),
            source_id=args.source,
            source_url=args.url or f"file://{path.resolve()}",
            content_type=content_type,
            employer=args.employer,
            county=args.county,
        )
    except DocumentError as exc:
        print(f"document error: {exc}", file=sys.stderr)
        return 2

    if args.out:
        write_jsonl(candidates, args.out)
    if args.db:
        conn = database.connect(args.db)
        try:
            actions = [upsert_candidate(conn, candidate).action for candidate in candidates]
        finally:
            conn.close()
    else:
        actions = []

    print(
        json.dumps(
            {
                "file": str(path),
                "posts": len(candidates),
                "actions": actions,
                "candidates": [
                    {
                        "title": candidate.title,
                        "reference": candidate.reference,
                        "entry_fit": candidate.entry_fit,
                        "deadline": candidate.deadline.isoformat() if candidate.deadline else None,
                        "pay": [candidate.pay.min_amount, candidate.pay.max_amount, candidate.pay.period],
                    }
                    for candidate in candidates
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if candidates else 1


def cmd_init(args: argparse.Namespace) -> int:
    conn = database.connect(args.db)
    counts = database.table_counts(conn)
    conn.close()
    print(json.dumps({"db": args.db, "tables": counts}, indent=2))
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    conn = database.connect(args.db)
    try:
        if args.demo:
            print(json.dumps(load_corpus(conn), indent=2))
            return 0
        if not args.from_jsonl:
            raise SystemExit("load: pass --demo or --from <jobs.jsonl>")
        actions: dict[str, int] = {}
        with open(args.from_jsonl, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                candidate = JobCandidate.from_dict(json.loads(line))
                action = upsert_candidate(conn, candidate).action
                actions[action] = actions.get(action, 0) + 1
        print(json.dumps({"loaded": actions, "liveness": apply_liveness(conn)}, indent=2))
        return 0
    finally:
        conn.close()


def cmd_stats(args: argparse.Namespace) -> int:
    conn = database.connect(args.db)
    try:
        payload = metrics_stats(conn)
        payload["sources"] = metrics_health(conn)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"live jobs           {payload['live_jobs']}  (of {payload['jobs']} jobs)")
            print(f"observations        {payload['observations']}  → duplication rate {payload['duplication_rate']:.0%}")
            print(f"closing in 7 days   {payload['closing_within_7_days']}")
            print(f"open to freshers    {payload['entry_fit_share_open_to_freshers']:.0%} of live jobs")
            print(f"review queue        {payload['review_queue_open']} open")
            print(f"stale               {payload['stale_jobs']}")
            print("counties            " + ", ".join(f"{c['county']} {c['jobs']}" for c in payload["counties"]))
        return 0
    finally:
        conn.close()


def cmd_review(args: argparse.Namespace) -> int:
    conn = database.connect(args.db)
    try:
        pairs = open_reviews(conn, limit=args.limit)
        if args.json:
            print(json.dumps(pairs, indent=2))
            return 0
        if not pairs:
            print("review queue empty")
            return 0
        for pair in pairs:
            print(
                f"[{pair['id']}] {pair['score']:.2f}  {pair['incoming_title']} "
                f"({pair['incoming_source']})  vs  {pair['job_title']}  ({pair['job_employer']})"
            )
        return 0
    finally:
        conn.close()


def cmd_serve(args: argparse.Namespace) -> int:
    from .serve import serve

    serve(args.db, host=args.host, port=args.port, demo=args.demo)
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
    p_ingest.add_argument("--db", default=None, help="also write the graph into this SQLite file")
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

    p_document = sub.add_parser("document", help="parse one advert document (PDF/HTML) into posts")
    p_document.add_argument("--file", required=True)
    p_document.add_argument("--source", default="document")
    p_document.add_argument("--url", default=None)
    p_document.add_argument("--employer", default=None)
    p_document.add_argument("--county", default=None)
    p_document.add_argument("--out", default=None, help="write candidates as JSONL")
    p_document.add_argument("--db", default=None, help="also write into the graph")
    p_document.set_defaults(func=cmd_document)

    p_init = sub.add_parser("init", help="create or migrate the job graph database")
    p_init.add_argument("--db", default="./data/kazi.db")
    p_init.set_defaults(func=cmd_init)

    p_load = sub.add_parser("load", help="load candidates into the graph")
    p_load.add_argument("--db", default="./data/kazi.db")
    p_load.add_argument("--from", dest="from_jsonl", default=None)
    p_load.add_argument("--demo", action="store_true", help="load the synthetic corpus")
    p_load.set_defaults(func=cmd_load)

    p_stats = sub.add_parser("stats", help="pipeline health and coverage")
    p_stats.add_argument("--db", default="./data/kazi.db")
    p_stats.add_argument("--json", action="store_true")
    p_stats.set_defaults(func=cmd_stats)

    p_review = sub.add_parser("review", help="list ambiguous pairs waiting for a decision")
    p_review.add_argument("--db", default="./data/kazi.db")
    p_review.add_argument("--limit", type=int, default=50)
    p_review.add_argument("--json", action="store_true")
    p_review.set_defaults(func=cmd_review)

    p_serve = sub.add_parser("serve", help="serve the read-only feed (internal)")
    p_serve.add_argument("--db", default="./data/kazi.db")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--demo", action="store_true", help="label the feed as synthetic data")
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
