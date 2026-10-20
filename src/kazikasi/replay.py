"""Replay: re-parse stored payloads without touching the network.

This is the tool that makes parser bugs cheap. When an extractor changes, we
re-run it over the raw store and diff the results, instead of re-crawling and
hoping the pages have not changed.

Usage:
    kazikasi replay --store ./data/raw --source brightermonday --report out.json
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .models import JobCandidate
from .rawstore import RawStore
from .sources.base import Adapter


@dataclass
class ReplayReport:
    source_id: str
    payloads: int = 0
    parsed: int = 0
    failed: int = 0
    errors: list[dict] = field(default_factory=list)
    field_fill: Counter = field(default_factory=Counter)
    candidates: list[JobCandidate] = field(default_factory=list)

    def to_dict(self) -> dict:
        total = self.parsed or 1
        return {
            "source_id": self.source_id,
            "payloads": self.payloads,
            "parsed": self.parsed,
            "failed": self.failed,
            "errors": self.errors[:20],
            "field_fill": {
                name: {"count": count, "rate": round(count / total, 3)}
                for name, count in sorted(self.field_fill.items())
            },
        }


REQUIRED_FIELDS = ("title", "employer_name", "county", "description_md", "deadline")


def replay(adapter: Adapter, store: RawStore, source_id: str | None = None) -> ReplayReport:
    """Re-parse every stored detail payload for a source."""
    source = source_id or adapter.manifest.id
    report = ReplayReport(source_id=source)

    for sha256, meta in store.iter_fetches(source):
        if meta.get("kind") != "detail":
            continue
        report.payloads += 1
        try:
            body = store.get(sha256).decode("utf-8", errors="replace")
            candidate = adapter.parse_detail(body, meta.get("url", ""))
        except Exception as exc:  # noqa: BLE001
            report.failed += 1
            report.errors.append({"url": meta.get("url"), "error": repr(exc)})
            continue
        report.parsed += 1
        report.candidates.append(candidate)
        for name in REQUIRED_FIELDS:
            if getattr(candidate, name):
                report.field_fill[name] += 1
        if candidate.entry_fit != "unknown":
            report.field_fill["entry_fit"] += 1
        if candidate.pay.source != "unknown":
            report.field_fill["pay"] += 1

    return report


def write_report(report: ReplayReport, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return path
