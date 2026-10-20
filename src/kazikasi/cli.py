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

    kazikasi profiles --db ./data/kazi.db --seed
    kazikasi match --db ./data/kazi.db --profile demo-fresher
    kazikasi apply --db ./data/kazi.db --profile demo-fresher --job <id> --applied
    kazikasi slo --db ./data/kazi.db

    kazikasi digest --db ./data/kazi.db --profile demo-fresher --subscribe 0712345678
    kazikasi digest --db ./data/kazi.db --profile demo-fresher --preview
    kazikasi digest --db ./data/kazi.db --all --dry-run
    kazikasi outbox --db ./data/kazi.db --send --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import db as database
from .canary import run as run_canary
from .corpus import load_corpus
from .documents import DocumentError, document_to_candidates
from . import graph
from .graph import apply_liveness, open_reviews, upsert_candidate
from .metrics import health as metrics_health
from .metrics import stats as metrics_stats
from .profile import list_profiles, load_profile, seed_profiles
from .ranking import explain, rank
from . import slo as slo_module
from . import tracking
from . import outbox as outbox_module
from . import alerts as alerts_module
from . import bundle as bundle_module
from . import scheduler
from . import searches as searches_module
from .channels import FakeTransport, transport_for


def _now():
    """The clock, in one place, so ``--now`` can exist later without a hunt."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
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
                "status": manifest.status,
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
                _build_adapter(name),
                fetcher,
                store,
                pages=args.pages,
                limit=args.limit,
                allow_unverified=getattr(args, "allow_unverified", False),
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


def cmd_auth(args: argparse.Namespace) -> int:
    """Is sign-in actually ready? Prints configuration, never secrets."""
    from . import accounts

    payload = accounts.readiness(base_url=args.base_url)
    if args.live:
        for key, item in payload["providers"].items():
            if not item["configured"]:
                item["jwks_reachable"] = None
                continue
            try:
                keys = accounts.jwks(
                    accounts.PROVIDERS[key],
                    transport=accounts.urllib_transport,
                )
                item["jwks_reachable"] = True
                item["jwks_keys"] = len(keys)
            except Exception as error:  # noqa: BLE001 - reported, not raised
                item["jwks_reachable"] = False
                item["jwks_error"] = str(error)[:160]
    print(json.dumps(payload, indent=2))
    return 0 if payload["ready"] else 1


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


def cmd_profiles(args: argparse.Namespace) -> int:
    conn = database.connect(args.db)
    try:
        added = seed_profiles(conn) if args.seed else 0
        profiles = list_profiles(conn)
        if args.json:
            print(json.dumps([profile.to_dict() for profile in profiles], indent=2))
        else:
            if added:
                print(f"seeded {added} demo profiles")
            for profile in profiles:
                print(f"{profile.id:22} {profile.name}  ·  {profile.describe()}")
        return 0
    finally:
        conn.close()


def cmd_match(args: argparse.Namespace) -> int:
    conn = database.connect(args.db)
    try:
        seed_profiles(conn)
        profile = load_profile(conn, args.profile)
        if profile is None:
            raise SystemExit(f"unknown profile {args.profile!r}; run `kazikasi profiles`")
        rows = [dict(row) for row in graph.feed(conn, limit=1000, include_stale=True)]
        matches = rank(rows, profile, limit=args.limit, include_blocked=args.include_blocked)
        if args.json:
            print(json.dumps([match.to_dict() for match in matches], indent=2, default=str))
            return 0
        print(profile.name)
        for match in matches:
            print("  " + explain(match))
        return 0
    finally:
        conn.close()


def cmd_apply(args: argparse.Namespace) -> int:
    conn = database.connect(args.db)
    try:
        kind = (
            "saved"
            if getattr(args, "saved", False)
            else "unsaved"
            if getattr(args, "unsaved", False)
            else "applied"
            if args.applied
            else "dismissed"
            if args.dismiss
            else "clicked_through"
        )
        try:
            event_id = tracking.record(conn, args.profile, args.job, kind, detail=args.note)
        except ValueError as error:
            raise SystemExit(str(error)) from error
        print(json.dumps({"event_id": event_id, "kind": kind, "job": args.job}, indent=2))
        return 0
    finally:
        conn.close()


def cmd_slo(args: argparse.Namespace) -> int:
    conn = database.connect(args.db)
    try:
        payload = slo_module.report(conn)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"feed last updated: {payload['feed_last_updated'] or 'never'}")
            print(f"sources within target: {payload['sources_meeting_slo']}/{payload['sources_reporting']}")
            for source in payload["sources"]:
                age = "—" if source["age_minutes"] is None else f"{source['age_minutes']:.0f} min"
                print(f"  {source['source_id']:16} {source['state']:14} {age:>10} (target {source['target_minutes']} min)")
        return 0 if payload["slo_rate"] >= args.min_rate else 1
    finally:
        conn.close()


def cmd_digest(args: argparse.Namespace) -> int:
    conn = database.connect(args.db)
    try:
        seed_profiles(conn)

        if args.subscribe:
            window = ("18:00", "20:00")
            if args.window:
                parts = args.window.split("-")
                if len(parts) != 2:
                    raise SystemExit("--window wants HH:MM-HH:MM, e.g. 18:00-20:00")
                window = (parts[0].strip(), parts[1].strip())
            try:
                subscription = outbox_module.subscribe(
                    conn, args.profile, args.subscribe, source=args.source,
                    channel=args.channel, cadence=args.cadence,
                    fallback_channel=None if args.no_fallback else "sms",
                    max_items=args.max_items, window=window,
                    brief_opt_in=getattr(args, "brief", False), now=_now(),
                )
            except ValueError as error:
                raise SystemExit(str(error)) from error
            print(json.dumps({"subscribed": subscription.to_dict()}, indent=2))
            if not args.preview and not args.queue:
                return 0

        if args.unsubscribe:
            changed = outbox_module.unsubscribe(conn, args.profile, now=_now(), reason=args.source)
            print(json.dumps({"profile_id": args.profile, "unsubscribed": changed}, indent=2))
            return 0

        if args.all:
            # "Every subscriber", not "every profile": a profile without a
            # number has nowhere to send a digest to.
            profiles = [s.profile_id for s in outbox_module.active_subscriptions(conn)]
            if not profiles:
                print("no active subscribers", file=sys.stderr)
                return 1
        else:
            profiles = [args.profile]
        results = []
        for profile_id in profiles:
            try:
                result = outbox_module.queue_digest(
                    conn,
                    profile_id,
                    dry_run=args.dry_run or args.preview,
                    link_base=args.link_base,
                    now=_now(),
                )
            except ValueError as error:
                results.append({"profile_id": profile_id, "error": str(error)})
                continue
            results.append(result)

        if args.json:
            print(json.dumps(results, indent=2, default=str))
            return 0

        for result in results:
            if "error" in result:
                print(f"{result['profile_id']}: {result['error']}")
                continue
            digest = result.get("digest") or {}
            print(f"{result['profile_id']}: {result['state']} ({len(digest.get('items', []))} cards)")
            if result.get("preview"):
                print()
                print(result["preview"])
                print()
        return 0
    finally:
        conn.close()


def cmd_outbox(args: argparse.Namespace) -> int:
    conn = database.connect(args.db)
    try:
        if args.send:
            if args.dry_run:
                transports = {"whatsapp": FakeTransport(), "sms": FakeTransport()}
            else:
                try:
                    transports = {channel: transport_for(channel) for channel in ("whatsapp", "sms")}
                except RuntimeError as error:
                    # A missing token is a configuration mistake, not a crash.
                    raise SystemExit(f"cannot send: {error}") from error
            report = outbox_module.send_due(
                conn,
                transports,
                respect_window=not args.ignore_window,
                dry_run=args.dry_run,
            )
            print(json.dumps(report.to_dict(), indent=2))
            return 0

        summary = outbox_module.outbox_summary(conn)
        if args.json:
            print(json.dumps({"summary": summary, "messages": args.messages and [
                dict(row) for row in conn.execute(
                    "SELECT id, profile_id, channel, state, attempts, last_error, created_at "
                    "FROM messages ORDER BY id DESC LIMIT 20"
                )
            ]}, indent=2, default=str))
        else:
            counts = summary["counts"] or {}
            print("outbox: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "empty"))
        return 0
    finally:
        conn.close()


def cmd_run(args: argparse.Namespace) -> int:
    """One scheduler tick, or a loop of them."""
    conn = database.connect(args.db)
    try:
        seed_profiles(conn)
        if args.explain:
            print(json.dumps(scheduler.explain(conn, now=_now()), indent=2, default=str))
            return 0

        def once() -> dict:
            transports = None
            if args.send or args.dry_run:
                if args.dry_run:
                    transports = {"whatsapp": FakeTransport(), "sms": FakeTransport()}
                else:
                    try:
                        transports = {
                            channel: transport_for(channel) for channel in ("whatsapp", "sms")
                        }
                    except RuntimeError as error:
                        raise SystemExit(f"cannot send: {error}") from error
            return scheduler.run_due(
                conn,
                transports,
                now=_now(),
                link_base=args.link_base,
                dry_run=args.dry_run,
                with_brief=getattr(args, "brief", False),
                with_alerts=not getattr(args, "no_alerts", False),
                with_searches=not getattr(args, "no_searches", False),
            )

        if not args.loop:
            report = once()
            print(json.dumps(report, indent=2, default=str))
            return 0

        import time

        while True:
            report = once()
            if report["due"] or (report.get("sent") or {}).get("sent"):
                print(json.dumps(report, default=str), flush=True)
            time.sleep(max(5, args.interval))
    except KeyboardInterrupt:
        return 0
    finally:
        conn.close()


def cmd_alerts(args: argparse.Namespace) -> int:
    conn = database.connect(args.db)
    try:
        report = alerts_module.queue(conn, hours=args.hours, dry_run=args.dry_run)
        if args.send:
            transports = {
                channel: (FakeTransport() if args.dry_run else transport_for(channel))
                for channel in ("whatsapp", "sms")
            }
            report["sent"] = outbox_module.send_due(conn, transports).to_dict()
        print(json.dumps(report, indent=2, default=str))
        return 0
    finally:
        conn.close()


def cmd_bundle(args: argparse.Namespace) -> int:
    """Build, verify or describe a bundle — the deployment's corpus."""
    if args.action == "build":
        conn = database.connect(args.db)
        try:
            payload = bundle_module.write(conn, args.out, now=_now())
        finally:
            conn.close()
        if args.json:
            print(json.dumps(payload, indent=2, default=str))
        else:
            print(f"built {payload['count']} candidates → {payload['path']} ({payload['bytes']:,} bytes)")
            print(f"sources: {', '.join(payload['sources']) or 'none'}")
        return 0

    source = args.url or args.out
    bundle = (
        bundle_module.from_url(source)
        if str(source).startswith("https://")
        else bundle_module.from_file(source)
    )
    stale = bundle.is_stale(now=_now())
    payload = {**bundle.to_dict(), "stale": stale, "source": source}
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"bundle      {source}")
        print(f"built       {bundle.built_at.isoformat() if bundle.built_at else 'unknown'}"
              f"{'  (STALE)' if stale else ''}")
        print(f"candidates  {bundle.count}  (skipped {bundle.skipped})")
        print(f"sources     {', '.join(bundle.sources) or 'none'}")
        print(f"sha256      {payload['sha256']}")
    return 0


def cmd_searches(args: argparse.Namespace) -> int:
    """Saved searches, from a terminal: watch, stop, list or run one tick."""
    conn = database.connect(args.db)
    try:
        seed_profiles(conn)
        if args.watch:
            result = searches_module.watch(
                conn,
                args.profile,
                q=args.q,
                county=args.county,
                family=args.family,
                employment_type=args.employment_type,
                deadline_days=args.days,
                pay_floor=args.pay,
                remote=args.remote,
                cadence=args.cadence,
                now=_now(),
            )
            print(json.dumps(result, indent=2, default=str))
            return 0 if result.get("saved") else 1
        if args.stop is not None:
            stopped = searches_module.stop(conn, args.profile, args.stop, now=_now())
            print(json.dumps({"stopped": stopped, "id": args.stop}, indent=2))
            return 0
        if args.run:
            report = searches_module.queue_due(conn, now=_now(), dry_run=args.dry_run)
            print(json.dumps(report, indent=2, default=str))
            return 0
        rows = searches_module.for_profile(conn, args.profile)
        if args.json:
            print(json.dumps(rows, indent=2, default=str))
        else:
            if not rows:
                print("no saved searches")
            for row in rows:
                print(f"{row['id']:>3}  {row['label']}  ({row['cadence']}, last run {row['last_run_at'] or 'never'})")
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
    p_ingest.add_argument(
        "--allow-unverified",
        action="store_true",
        help="ingest a source whose parser has never been checked against a live page",
    )
    p_ingest.set_defaults(func=cmd_ingest)

    p_replay = sub.add_parser("replay", help="re-parse stored payloads offline")
    p_replay.add_argument("--source", required=True)
    p_replay.add_argument("--store", default="./data/raw")
    p_replay.add_argument("--report", default=None)
    p_replay.set_defaults(func=cmd_replay)

    p_auth = sub.add_parser("auth", help="check sign-in configuration (no secrets shown)")
    p_auth.add_argument(
        "action", nargs="?", default="check", choices=["check"],
        help="what to check (only 'check' for now)",
    )
    p_auth.add_argument("--base-url", default=os.environ.get("KAZIKASI_BASE_URL"))
    p_auth.add_argument("--live", action="store_true", help="also fetch each provider's signing keys")
    p_auth.set_defaults(func=cmd_auth)

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

    p_profiles = sub.add_parser("profiles", help="list jobseeker profiles (constraints)")
    p_profiles.add_argument("--db", default="./data/kazi.db")
    p_profiles.add_argument("--seed", action="store_true", help="insert the demo profiles if missing")
    p_profiles.add_argument("--json", action="store_true")
    p_profiles.set_defaults(func=cmd_profiles)

    p_match = sub.add_parser("match", help="rank live jobs for one profile")
    p_match.add_argument("--db", default="./data/kazi.db")
    p_match.add_argument("--profile", default="demo-fresher")
    p_match.add_argument("--limit", type=int, default=10)
    p_match.add_argument("--include-blocked", action="store_true", help="show excluded jobs and why")
    p_match.add_argument("--json", action="store_true")
    p_match.set_defaults(func=cmd_match)

    p_apply = sub.add_parser("apply", help="record that you clicked through, applied, or passed")
    p_apply.add_argument("--db", default="./data/kazi.db")
    p_apply.add_argument("--profile", required=True)
    p_apply.add_argument("--job", required=True)
    p_apply.add_argument("--saved", action="store_true", help="add to the shortlist")
    p_apply.add_argument("--unsaved", action="store_true", help="remove from the shortlist")
    p_apply.add_argument("--applied", action="store_true")
    p_apply.add_argument("--dismiss", action="store_true")
    p_apply.add_argument("--note", default=None)
    p_apply.set_defaults(func=cmd_apply)

    p_slo = sub.add_parser("slo", help="freshness per source, measured")
    p_slo.add_argument("--db", default="./data/kazi.db")
    p_slo.add_argument("--min-rate", type=float, default=0.999)
    p_slo.add_argument("--json", action="store_true")
    p_slo.set_defaults(func=cmd_slo)

    p_digest = sub.add_parser("digest", help="compose (and optionally queue) a WhatsApp digest")
    p_digest.add_argument("--db", default="./data/kazi.db")
    p_digest.add_argument("--profile", default="demo-fresher")
    p_digest.add_argument("--all", action="store_true", help="every subscribed profile")
    p_digest.add_argument("--subscribe", metavar="MSISDN", default=None, help="record consent for this number")
    p_digest.add_argument("--unsubscribe", action="store_true")
    p_digest.add_argument("--channel", default="whatsapp", choices=["whatsapp", "sms"])
    p_digest.add_argument("--cadence", default="daily", choices=["daily", "weekly"])
    p_digest.add_argument("--window", default=None, metavar="HH:MM-HH:MM")
    p_digest.add_argument("--max-items", type=int, default=5)
    p_digest.add_argument("--source", default="cli", help="how consent was given")
    p_digest.add_argument(
        "--brief",
        action="store_true",
        help="also consent to the weekly brief (a second kind of message)",
    )
    p_digest.add_argument("--no-fallback", action="store_true")
    p_digest.add_argument("--preview", action="store_true", help="print the message, queue nothing")
    p_digest.add_argument("--queue", action="store_true", help="queue it even when subscribing")
    p_digest.add_argument("--dry-run", action="store_true")
    p_digest.add_argument("--link-base", default="https://kazikasi.app")
    p_digest.add_argument("--json", action="store_true")
    p_digest.set_defaults(func=cmd_digest)

    p_outbox = sub.add_parser("outbox", help="inspect or deliver queued messages")
    p_outbox.add_argument("--db", default="./data/kazi.db")
    p_outbox.add_argument("--send", action="store_true")
    p_outbox.add_argument("--dry-run", action="store_true", help="deliver to a fake transport")
    p_outbox.add_argument("--ignore-window", action="store_true")
    p_outbox.add_argument("--messages", action="store_true")
    p_outbox.add_argument("--json", action="store_true")
    p_outbox.set_defaults(func=cmd_outbox)

    p_run = sub.add_parser("run", help="the scheduler: compose and send what is due")
    p_run.add_argument("--brief", action="store_true", help="also queue the weekly brief")
    p_run.add_argument(
        "--no-alerts", action="store_true", help="skip closing-soon alerts for saved jobs"
    )
    p_run.add_argument(
        "--no-searches", action="store_true", help="skip saved-search alerts"
    )
    p_run.add_argument("--db", default="./data/kazi.db")
    p_run.add_argument("--once", action="store_true", help="one tick (default)")
    p_run.add_argument("--loop", action="store_true", help="keep ticking")
    p_run.add_argument("--interval", type=int, default=60, help="seconds between ticks")
    p_run.add_argument("--send", action="store_true", help="really deliver")
    p_run.add_argument("--dry-run", action="store_true", help="fake transports, no writes to state")
    p_run.add_argument("--explain", action="store_true", help="why each subscriber is or is not due")
    p_run.add_argument("--link-base", default="https://kazikasi.app")
    p_run.set_defaults(func=cmd_run)

    p_alerts = sub.add_parser("alerts", help="closing-soon alerts for saved jobs")
    p_alerts.add_argument("--db", default="./data/kazi.db")
    p_alerts.add_argument("--hours", type=int, default=None, help="window before the deadline")
    p_alerts.add_argument("--dry-run", action="store_true", help="show the text, queue nothing")
    p_alerts.add_argument("--send", action="store_true", help="deliver right after queueing")
    p_alerts.add_argument("--json", action="store_true")
    p_alerts.set_defaults(func=cmd_alerts)

    p_bundle = sub.add_parser("bundle", help="a corpus in a file, for deployments without a database")
    p_bundle.add_argument("action", choices=("build", "verify", "show"), nargs="?", default="build")
    p_bundle.add_argument("--db", default="./data/kazi.db")
    p_bundle.add_argument("--out", default="data/bundle.jsonl")
    p_bundle.add_argument("--url", default=None, help="verify or show a published bundle")
    p_bundle.add_argument("--json", action="store_true")
    p_bundle.set_defaults(func=cmd_bundle)

    p_searches = sub.add_parser("searches", help="saved searches: watch, stop, list, run")
    p_searches.add_argument("--db", default="./data/kazi.db")
    p_searches.add_argument("--profile", default="demo-fresher")
    p_searches.add_argument("--q", default="")
    p_searches.add_argument("--county", default="")
    p_searches.add_argument("--family", default="")
    p_searches.add_argument("--type", dest="employment_type", default="")
    p_searches.add_argument("--days", type=int, default=None)
    p_searches.add_argument("--pay", type=float, default=None)
    p_searches.add_argument("--remote", action="store_true")
    p_searches.add_argument("--cadence", choices=("daily", "weekly"), default="daily")
    p_searches.add_argument("--watch", action="store_true", help="save the search described by the flags")
    p_searches.add_argument("--stop", type=int, default=None, help="stop alerts for a saved search id")
    p_searches.add_argument("--run", action="store_true", help="queue what is due now")
    p_searches.add_argument("--dry-run", action="store_true")
    p_searches.add_argument("--json", action="store_true")
    p_searches.set_defaults(func=cmd_searches)

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
