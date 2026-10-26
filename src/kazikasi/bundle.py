"""A corpus in a file: the deployed site without a database.

The function on Vercel has no writable disk and no database behind it, so it has
been serving the synthetic corpus - a shop window, not a product. The honest fix
is Postgres; the cheap, honest, *working* fix is this: run the sweep somewhere
with a network, write the result to one JSONL file, and let the deployment load
it at cold start.

Nothing here is new storage. `observations.payload` already holds the exact
`JobCandidate` dict the parser produced, and `JobCandidate.from_dict` already
reads it back, so a bundle is a list of those plus a header. The round trip is the
test.

Three rules, because a stale corpus is worse than an empty one:

* **the header says when it was built**, and the page says so too;
* **a line that does not parse is skipped and counted** - one bad advert must not
  take the site down;
* **a bundle older than ``STALE_HOURS`` is labelled stale** on every page, not
  quietly served as current.

The deployment never writes to a bundle. It is produced by ``kazikasi bundle
build`` (after ``ingest``) and published wherever ``KAZIKASI_BUNDLE`` points.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from . import db as database
from .graph import apply_liveness, upsert_candidate
from .models import JobCandidate

KIND = "kazikasi-bundle"
SCHEMA = 1
#: A corpus older than this is labelled, not hidden. Two sweeps of slack.
STALE_HOURS = 36

#: What the running process is serving. Read by ``serve`` for the banner and by
#: ``/api/health``; set by :func:`load_into`.
STATE: dict = {"source": "synthetic", "built_at": None, "count": 0, "error": None}


class BundleError(ValueError):
    """The file is not a bundle, or is a bundle of a schema we do not read."""


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(timezone.utc)


def export(conn, *, now: datetime | None = None) -> list[dict]:
    """Every live job's primary observation, as a candidate dict.

    The primary observation is the advert we trust most; re-exporting it means a
    bundle carries the same evidence a local database does, and importing it is
    not a lossy summary.
    """
    rows = conn.execute(
        """SELECT o.payload
             FROM jobs j
             JOIN observations o ON o.id = j.primary_observation_id
            WHERE j.status IN ('open', 'stale')
            ORDER BY j.first_seen_at, j.id"""
    ).fetchall()
    candidates = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict) and payload.get("title"):
            candidates.append(payload)
    return candidates


def header(candidates: list[dict], *, now: datetime | None = None) -> dict:
    moment = _now(now)
    sources = sorted({str(item.get("source_id")) for item in candidates if item.get("source_id")})
    return {
        "kind": KIND,
        "schema": SCHEMA,
        "built_at": moment.isoformat(),
        "count": len(candidates),
        "sources": sources,
        "generator": "kazikasi bundle build",
    }


def write(conn, path: str | os.PathLike, *, now: datetime | None = None) -> dict:
    """Write a bundle. Returns its header plus the file's byte size."""
    candidates = export(conn, now=now)
    head = header(candidates, now=now)
    lines = [json.dumps(head, ensure_ascii=False, sort_keys=True)]
    lines += [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in candidates]
    text = "\n".join(lines) + "\n"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return {**head, "path": str(path), "bytes": len(text.encode("utf-8")), "sha256": _sha(text)}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Bundle:
    candidates: list[dict] = field(default_factory=list)
    built_at: datetime | None = None
    sources: list[str] = field(default_factory=list)
    skipped: int = 0
    sha256: str = ""

    @property
    def count(self) -> int:
        return len(self.candidates)

    def age_hours(self, *, now: datetime | None = None) -> float | None:
        if self.built_at is None:
            return None
        return (_now(now) - self.built_at).total_seconds() / 3600

    def is_stale(self, *, now: datetime | None = None, hours: int = STALE_HOURS) -> bool:
        age = self.age_hours(now=now)
        # No date at all is treated as stale: an undated corpus is not current.
        return True if age is None else age > hours

    def to_dict(self) -> dict:
        return {
            "kind": KIND,
            "schema": SCHEMA,
            "count": self.count,
            "skipped": self.skipped,
            "sources": self.sources,
            "built_at": self.built_at.isoformat() if self.built_at else None,
            "sha256": self.sha256,
        }


def parse(text: str) -> Bundle:
    """Read a bundle, skipping lines that do not parse and counting them."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise BundleError("the bundle is empty")
    try:
        head = json.loads(lines[0])
    except ValueError as error:
        raise BundleError(f"the first line is not JSON: {error}") from error
    if not isinstance(head, dict) or head.get("kind") != KIND:
        raise BundleError("that file is not a Kazi-Kasi bundle")
    if int(head.get("schema") or 0) != SCHEMA:
        raise BundleError(
            f"bundle schema {head.get('schema')!r} is not supported (this build reads {SCHEMA})"
        )
    built_at = None
    if head.get("built_at"):
        try:
            built_at = datetime.fromisoformat(str(head["built_at"]))
            if built_at.tzinfo is None:
                built_at = built_at.replace(tzinfo=timezone.utc)
        except ValueError:
            built_at = None

    candidates, skipped = [], 0
    for line in lines[1:]:
        try:
            payload = json.loads(line)
        except ValueError:
            skipped += 1
            continue
        if not isinstance(payload, dict) or not payload.get("title") or not payload.get("source_id"):
            skipped += 1
            continue
        candidates.append(payload)
    return Bundle(
        candidates=candidates,
        built_at=built_at,
        sources=list(head.get("sources") or []),
        skipped=skipped,
        sha256=_sha(text),
    )


def from_file(path: str | os.PathLike) -> Bundle:
    with open(path, encoding="utf-8") as handle:
        return parse(handle.read())


def fetch_text(url: str, *, timeout: float = 20.0) -> str:
    """One GET, as text. The only network call in this module."""
    import urllib.request

    if not str(url).lower().startswith("https://"):
        raise BundleError("refusing to fetch a bundle over anything but HTTPS")
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json, text/plain", "User-Agent": "kazikasi-bundle/1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - https checked above
        return response.read().decode("utf-8", errors="replace")


def from_url(url: str, *, fetch=None) -> Bundle:
    """Fetch a bundle over HTTPS. The fetch is injectable so tests stay offline."""
    return parse((fetch or fetch_text)(url))


def load(conn, bundle: Bundle, *, now: datetime | None = None) -> dict:
    """Upsert a bundle into a connection. Idempotent: loading twice is a no-op."""
    moment = _now(now)
    actions: dict[str, int] = {}
    for payload in bundle.candidates:
        try:
            candidate = JobCandidate.from_dict(payload)
        except Exception:  # noqa: BLE001 - one bad advert is not an outage
            continue
        try:
            action = upsert_candidate(conn, candidate, now=moment).action
        except Exception:  # noqa: BLE001
            continue
        actions[action] = actions.get(action, 0) + 1
    conn.commit()
    return {"loaded": actions, "liveness": apply_liveness(conn, now=moment)}


def load_into(conn, source: str, *, now: datetime | None = None, fetch=None) -> dict:
    """Load from a path or URL, and record what the process is now serving.

    Failures are recorded, not raised: a deployment that cannot reach its bundle
    should serve the synthetic corpus **and say so**, rather than return 500 to
    every visitor.
    """
    try:
        bundle = from_url(source, fetch=fetch) if "://" in source else from_file(source)
        counts = load(conn, bundle, now=now)
        STATE.update(
            {
                "source": "bundle",
                "built_at": bundle.built_at.isoformat() if bundle.built_at else None,
                "count": bundle.count,
                "skipped": bundle.skipped,
                "error": None,
            }
        )
        return {"ok": True, **bundle.to_dict(), **counts}
    except Exception as error:  # noqa: BLE001 - the site must still render
        STATE.update({"source": "synthetic", "built_at": None, "count": 0, "error": repr(error)})
        return {"ok": False, "error": repr(error)}


def notice(*, now: datetime | None = None) -> str:
    """A one-line truth about the corpus, for the page banner. Empty when synthetic."""
    if STATE.get("source") != "bundle":
        return ""
    built = STATE.get("built_at")
    if not built:
        return "Live data - build time unknown."
    try:
        moment = datetime.fromisoformat(str(built))
    except ValueError:
        return "Live data."
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    eat = moment.astimezone(timezone(timedelta(hours=3)))
    if _now(now) - moment > timedelta(hours=STALE_HOURS):
        return f"Data last refreshed {eat:%-d %b %H:%M} EAT - the sweep has not run since."
    return f"Live data, refreshed {eat:%-d %b %H:%M} EAT."


def build_fresh(conn=None, *, now: datetime | None = None):
    """A connection with the corpus loaded from ``KAZIKASI_BUNDLE``, if set.

    Used by the deployment. Falls back to the synthetic corpus on any problem,
    and records why in :data:`STATE` so ``/api/health`` can be honest about it.
    """
    source = (os.environ.get("KAZIKASI_BUNDLE") or "").strip()
    if not source:
        return None
    connection = database.connect(":memory:", check_same_thread=False)
    result = load_into(connection, source, now=now)
    if not result.get("ok"):
        connection.close()
        return None
    return connection
