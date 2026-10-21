"""Content-addressed raw payload store.

Rule 1 of the blueprint: the payload is stored before it is parsed. If a
parser turns out to be wrong, we replay from here. We never re-crawl to
recover from our own bug.

The default implementation is a filesystem store so the spine runs with zero
infrastructure. The interface is the contract; swap in S3 later without
touching the pipeline.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .models import RawRef

PARSER_VERSION = "phase1.0"


class RawStore(Protocol):
    def put(self, payload: bytes, content_type: str, meta: dict) -> RawRef: ...
    def get(self, sha256: str) -> bytes: ...
    def meta(self, sha256: str) -> dict: ...
    def iter_refs(self, source_id: str | None = None): ...

    #: One record per *fetch*, not per blob. Several URLs can share a body
    #: (pagination repeats, syndicated copies), and replay must still cover
    #: every URL that was fetched.
    def iter_fetches(self, source_id: str | None = None): ...


class FileRawStore:
    """``<root>/<aa>/<sha256>.bin`` with a ``.json`` sidecar of fetch metadata."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, sha256: str) -> Path:
        return self.root / sha256[:2] / f"{sha256}.bin"

    def _meta_path(self, sha256: str) -> Path:
        return self.root / sha256[:2] / f"{sha256}.json"

    def put(self, payload: bytes, content_type: str, meta: dict) -> RawRef:
        digest = hashlib.sha256(payload).hexdigest()
        path = self._path(digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(payload)

        sidecar = dict(meta)
        sidecar.update(
            {
                "sha256": digest,
                "content_type": content_type,
                "byte_size": len(payload),
                "stored_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._meta_path(digest).write_text(json.dumps(sidecar, indent=2, ensure_ascii=False))
        self._append_fetch(digest, sidecar)

        return RawRef(
            key=str(path.relative_to(self.root)),
            sha256=digest,
            content_type=content_type,
            byte_size=len(payload),
        )

    def _append_fetch(self, sha256: str, meta: dict) -> None:
        with self._index_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"sha256": sha256, **meta}, ensure_ascii=False) + "\n")

    def _index_path(self) -> Path:
        return self.root / "_index.jsonl"

    def iter_fetches(self, source_id: str | None = None):
        path = self._index_path()
        if not path.exists():
            return
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    meta = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if source_id and meta.get("source_id") != source_id:
                    continue
                yield meta["sha256"], meta

    def get(self, sha256: str) -> bytes:
        return self._path(sha256).read_bytes()

    def meta(self, sha256: str) -> dict:
        path = self._meta_path(sha256)
        return json.loads(path.read_text()) if path.exists() else {}

    def iter_refs(self, source_id: str | None = None):
        """Yield ``RawRef`` objects, optionally filtered by source."""
        for meta_path in sorted(self.root.glob("*/*.json")):
            try:
                meta = json.loads(meta_path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if source_id and meta.get("source_id") != source_id:
                continue
            ref = RawRef(
                key=str(self._path(meta["sha256"]).relative_to(self.root)),
                sha256=meta["sha256"],
                content_type=meta.get("content_type", "binary"),
                byte_size=int(meta.get("byte_size", 0)),
            )
            yield ref, meta


class MemoryRawStore:
    """In-memory store for tests."""

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}
        self._meta: dict[str, dict] = {}
        self._fetches: list[tuple[str, dict]] = []

    def put(self, payload: bytes, content_type: str, meta: dict) -> RawRef:
        digest = hashlib.sha256(payload).hexdigest()
        self._blobs[digest] = payload
        record = {**meta, "content_type": content_type, "sha256": digest}
        self._meta[digest] = record
        self._fetches.append((digest, record))
        return RawRef(key=digest, sha256=digest, content_type=content_type, byte_size=len(payload))

    def iter_fetches(self, source_id: str | None = None):
        for digest, meta in self._fetches:
            if source_id and meta.get("source_id") != source_id:
                continue
            yield digest, meta

    def get(self, sha256: str) -> bytes:
        return self._blobs[sha256]

    def meta(self, sha256: str) -> dict:
        return self._meta.get(sha256, {})

    def iter_refs(self, source_id: str | None = None):
        for digest, meta in self._meta.items():
            if source_id and meta.get("source_id") != source_id:
                continue
            yield (
                RawRef(
                    key=digest,
                    sha256=digest,
                    content_type=meta.get("content_type", "binary"),
                    byte_size=len(self._blobs[digest]),
                ),
                meta,
            )
