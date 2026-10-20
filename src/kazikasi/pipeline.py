"""The ingestion spine.

    listing pages ──► detail URLs ──► detail pages ──► raw store ──► parser ──► candidates

Two properties matter more than throughput at this stage:

1. **Every fetch is stored before it is parsed.** A parser bug is recoverable
   by replay, never by re-crawling.
2. **A failure on one posting does not lose the run.** Errors are captured per
   page and reported, because a silent drop is how a job feed quietly rots.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Protocol

import httpx

from .models import JobCandidate
from .rawstore import PARSER_VERSION, RawStore
from .sources.base import Adapter

USER_AGENT = (
    "KaziKasiBot/0.1 (+https://github.com/Brandonflex/Kazi-kasi-app; "
    "job-indexing research; contact: ops@kazikasi.example)"
)


class Fetcher(Protocol):
    def get(self, url: str, *, json_body: dict | None = None) -> "Fetched": ...


@dataclass
class Fetched:
    url: str
    status: int
    body: str
    content_type: str = "text/html"


class HttpFetcher:
    """Polite HTTP client: one connection pool, explicit UA, no retries by default."""

    def __init__(self, timeout: float = 20.0, min_interval: float = 1.0) -> None:
        self.timeout = timeout
        self.min_interval = min_interval
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"},
            follow_redirects=True,
        )
        self._last: dict[str, float] = {}

    def _throttle(self, url: str) -> None:
        host = httpx.URL(url).host or ""
        elapsed = time.monotonic() - self._last.get(host, 0.0)
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last[host] = time.monotonic()

    def get(self, url: str, *, json_body: dict | None = None) -> Fetched:
        self._throttle(url)
        if json_body is not None:
            response = self._client.post(url, json=json_body)
        else:
            response = self._client.get(url)
        content_type = response.headers.get("content-type", "text/html").split(";")[0]
        return Fetched(url=url, status=response.status_code, body=response.text, content_type=content_type)

    def close(self) -> None:
        self._client.close()


class FixtureFetcher:
    """Reads recorded pages from disk. Used by the entire test suite.

    Raises on any URL it does not have, so a test can never silently hit the
    network.
    """

    def __init__(self, mapping: dict[str, str | Path]) -> None:
        self.mapping = {k: Path(v) for k, v in mapping.items()}
        self.calls: list[str] = []

    def get(self, url: str, *, json_body: dict | None = None) -> Fetched:
        self.calls.append(url)
        if url not in self.mapping:
            raise KeyError(f"No fixture for {url}; tests must never touch the network")
        path = self.mapping[url]
        content_type = "application/json" if path.suffix == ".json" else "text/html"
        return Fetched(url=url, status=200, body=path.read_text(encoding="utf-8"), content_type=content_type)


@dataclass
class IngestReport:
    source_id: str
    listing_pages: int = 0
    detail_urls: int = 0
    parsed: int = 0
    stored: int = 0
    errors: list[dict] = field(default_factory=list)
    candidates: list[JobCandidate] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def summary(self) -> dict:
        return {
            "source_id": self.source_id,
            "listing_pages": self.listing_pages,
            "detail_urls": self.detail_urls,
            "parsed": self.parsed,
            "stored": self.stored,
            "errors": len(self.errors),
            "duration_s": round((datetime.now(timezone.utc) - self.started_at).total_seconds(), 2),
        }


def verify(candidate: JobCandidate, today: date | None = None) -> JobCandidate:
    """Promote to ``open`` only if the record is complete and not expired."""
    today = today or date.today()
    if candidate.deadline and candidate.deadline < today:
        candidate.status = "closed"
        candidate.parser_notes.append("deadline_passed_at_ingest")
        return candidate
    if candidate.missing_required():
        candidate.status = "needs_review"
    elif candidate.extraction_confidence < 0.6:
        candidate.status = "needs_review"
    else:
        candidate.status = "open"
    return candidate


def ingest(
    adapter: Adapter,
    fetcher: Fetcher,
    store: RawStore,
    *,
    pages: int = 1,
    limit: int | None = None,
    verify_records: bool = True,
) -> IngestReport:
    report = IngestReport(source_id=adapter.manifest.id)

    detail_urls: list[str] = []
    for page in range(1, pages + 1):
        for listing_url in adapter.listing_urls(page):
            try:
                fetched = fetcher.get(listing_url)
            except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                report.errors.append({"stage": "listing", "url": listing_url, "error": repr(exc)})
                continue
            report.listing_pages += 1
            store.put(
                fetched.body.encode("utf-8"),
                fetched.content_type,
                {
                    "source_id": adapter.manifest.id,
                    "url": listing_url,
                    "kind": "listing",
                    "status": fetched.status,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "parser_version": PARSER_VERSION,
                },
            )
            report.stored += 1
            try:
                detail_urls.extend(adapter.parse_listing(fetched.body, listing_url))
            except Exception as exc:  # noqa: BLE001
                report.errors.append({"stage": "parse_listing", "url": listing_url, "error": repr(exc)})

    # Preserve order, drop repeats across pages.
    seen: set[str] = set()
    unique: list[str] = []
    for url in detail_urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    if limit is not None:
        unique = unique[:limit]
    report.detail_urls = len(unique)

    for url in unique:
        try:
            fetched = fetcher.get(url)
        except Exception as exc:  # noqa: BLE001
            report.errors.append({"stage": "detail", "url": url, "error": repr(exc)})
            continue

        ref = store.put(
            fetched.body.encode("utf-8"),
            fetched.content_type,
            {
                "source_id": adapter.manifest.id,
                "url": url,
                "kind": "detail",
                "status": fetched.status,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "parser_version": adapter.parser_version(),
            },
        )
        report.stored += 1

        try:
            candidate = adapter.parse_detail(fetched.body, url)
        except Exception as exc:  # noqa: BLE001
            report.errors.append({"stage": "parse_detail", "url": url, "error": repr(exc)})
            continue

        report.parsed += 1
        if verify_records:
            verify(candidate)
        report.candidates.append(candidate)

    return report


def write_jsonl(candidates: Iterable[JobCandidate], path: str | Path) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for candidate in candidates:
            handle.write(json.dumps(candidate.to_dict(), ensure_ascii=False) + "\n")
            count += 1
    return count
