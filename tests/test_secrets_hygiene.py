"""Secrets hygiene, enforced instead of promised.

A client secret pasted into a source file is a client secret in every clone, every
fork and every backup — and the deployment that used it keeps working, so nobody
notices. The console dialog says it once; this file says it on every test run.

Two checks, both cheap enough to run with the rest of the suite:

* **no tracked file contains a credential shape.** Google client secrets
  (`GOCSPX-…`), private keys, bearer-style API tokens, and the AWS/GitHub prefixes
  are matched by shape, not by an exact list we would have to maintain.
* **the go-live page cannot echo one.** `/setup` reports presence; a test proves a
  value set in the environment never reaches the HTML or the JSON.

The pattern table builds its own needles by concatenation so this file does not
match itself. That is not cleverness for its own sake: a scanner that skips its own
path can be defeated by renaming the file it protects.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from kazikasi import serve

ROOT = Path(__file__).resolve().parents[1]

#: (name, regex) — shapes, not values. Assembled so this module is not a match.
_NEEDLES = [
    ("google client secret", r"GOCSPX" + r"-[A-Za-z0-9_-]{20,}"),
    ("private key block", r"-----" + r"BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE " + r"KEY-----"),
    ("aws access key", r"AKIA" + r"[0-9A-Z]{16}"),
    ("github token", r"gh[pousr]" + r"_[A-Za-z0-9]{30,}"),
    ("slack token", r"xox" + r"[abposr]-[A-Za-z0-9-]{10,}"),
    ("stripe secret", r"sk" + r"_live_[A-Za-z0-9]{20,}"),
    ("meta/wa token", r"EAA" + r"[A-Za-z0-9]{60,}"),
    ("africas talking key", r"atsk" + r"_[A-Za-z0-9]{20,}"),
]
PATTERNS = [(name, re.compile(rx)) for name, rx in _NEEDLES]

#: Files that are allowed to contain a *shape* as text: this scanner, and the
#: documentation that teaches you what a leak looks like.
ALLOWED_PATHS = {"tests/test_secrets_hygiene.py", "docs/credentials.md"}

TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".jsonl", ".toml", ".cfg", ".ini", ".yml", ".yaml",
    ".html", ".js", ".css", ".sh", ".example", ".env", "",
}


def _git(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def tracked_files() -> list[str]:
    return _git("ls-files")


def visible_files() -> list[str]:
    """Tracked **and** untracked-but-not-ignored.

    The dangerous window is the one before `git add`: a secret sits in a freshly
    written file that `git ls-files` does not know about yet. Scanning both is what
    makes this a check rather than a post-mortem.
    """
    return tracked_files() + _git("ls-files", "--others", "--exclude-standard")


def test_the_repository_tracks_no_credential_shaped_string():
    offenders: list[str] = []
    for relative in visible_files():
        if relative in ALLOWED_PATHS:
            continue
        path = ROOT / relative
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:  # pragma: no cover - unreadable is not a leak
            continue
        for name, pattern in PATTERNS:
            if pattern.search(text):
                offenders.append(f"{relative}: looks like a {name}")
    assert not offenders, "credentials in the repository:\n  " + "\n  ".join(offenders)


def test_no_env_file_is_tracked_except_the_empty_example():
    tracked = tracked_files()
    offenders = [
        path
        for path in tracked
        if Path(path).name.startswith(".env") and Path(path).name != ".env.example"
    ]
    assert not offenders, "an .env file must never be committed; Vercel holds the values"


def test_the_example_carries_no_values():
    """A template is a list of names. One assigned value makes it a leak."""
    text = (ROOT / ".env.example").read_text()
    assigned = [
        line
        for line in text.splitlines()
        if "=" in line
        and not line.strip().startswith("#")
        and line.split("=", 1)[1].strip()
        # public defaults are allowed: they are in every page already
        and line.split("=", 1)[1].strip() not in ("0", "1", "https://kazi-kasi-app.vercel.app")
    ]
    assert not assigned, "the example must be names, not values: " + ", ".join(assigned)


def test_the_ignore_file_covers_the_shapes_we_scan_for():
    ignore = (ROOT / ".gitignore").read_text()
    for pattern in (".env", "*.pem", "credentials.json"):
        assert pattern in ignore


def test_the_deployment_ships_no_tests_or_docs():
    """`.vercelignore` is the other half: credentials tend to arrive in fixtures."""
    ignored = (ROOT / ".vercelignore").read_text()
    for pattern in ("tests/", "docs/", "data/"):
        assert pattern in ignored


class TestThePageCannotEchoOne:
    SECRET_SHAPE = "GOC" + "SPX-" + "abcdefghijklmnopqrstuvwxyz0123456789"

    @pytest.fixture(autouse=True)
    def wired(self, monkeypatch):
        for name in ("GOOGLE_CLIENT_SECRET", "KAZIKASI_SECRET", "CRON_SECRET", "AT_API_KEY"):
            monkeypatch.setenv(name, self.SECRET_SHAPE)
        yield

    def test_the_html_does_not_contain_it(self):
        conn = serve.demo_connection()
        try:
            body = serve.handle(conn, "GET", "/setup", {}, demo=True).body
        finally:
            conn.close()
        assert self.SECRET_SHAPE not in body
        assert "GOOGLE_CLIENT_SECRET" in body  # the *name* is the point

    def test_the_readiness_json_does_not_contain_it(self):
        conn = serve.demo_connection()
        try:
            body = serve.handle(conn, "GET", "/api/setup", {}, demo=True).body
            auth = serve.handle(conn, "GET", "/auth/ready", {}, demo=True).body
        finally:
            conn.close()
        assert self.SECRET_SHAPE not in body
        assert self.SECRET_SHAPE not in auth

    def test_it_still_reports_the_variable_as_present(self):
        import json

        conn = serve.demo_connection()
        try:
            payload = json.loads(serve.handle(conn, "GET", "/api/setup", {}, demo=True).body)
        finally:
            conn.close()
        google = next(step for step in payload["steps"] if step["id"] == "google")
        # the *name* is the point of the page; the *value* must never appear
        assert self.SECRET_SHAPE not in google["detail"]
        assert "set: GOOGLE_CLIENT_SECRET" in google["detail"]
