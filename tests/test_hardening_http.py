"""HTTP hardening: a policy that is actually enforced, and limits that hold.

Two things are easy to fake here and both are worthless when faked:

* a **Content-Security-Policy header that exists** but still needs
  `'unsafe-inline'` because the page has inline styles and scripts;
* a **rate limit** that is configured but never reached in a test.

So the tests below recompute the sha256 of the style sheet and the script from
the source and compare them to the hashes in the header, assert the page markup
contains no inline `style=` attributes or event handlers, and drive a limiter
until it returns 429.
"""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path

import pytest

from kazikasi import serve
from kazikasi.serve import PALETTE_JS, STYLE


@pytest.fixture
def conn():
    connection = serve.demo_connection()
    yield connection
    connection.close()


def digest(source: str) -> str:
    return "sha256-" + base64.b64encode(hashlib.sha256(source.encode()).digest()).decode()


def policy(header: str = None) -> dict[str, str]:
    header = header if header is not None else serve.security_headers(https=True)["Content-Security-Policy"]
    out = {}
    for part in header.split(";"):
        part = part.strip()
        if " " in part:
            key, value = part.split(" ", 1)
            out[key] = value
    return out


class TestThePolicyHeader:
    def test_the_style_hash_matches_the_style_that_ships(self):
        csp = policy()
        assert f"'{digest(STYLE)}'" in csp["style-src"]

    def test_the_script_hash_matches_the_script_that_ships(self):
        csp = policy()
        assert f"'{digest(PALETTE_JS)}'" in csp["script-src"]

    def test_nothing_falls_back_to_unsafe_inline(self):
        header = serve.security_headers(https=True)["Content-Security-Policy"]
        assert "unsafe-inline" not in header
        assert "unsafe-eval" not in header

    def test_everything_else_is_denied_by_default(self):
        csp = policy()
        assert csp["default-src"] == "'none'"
        assert csp["object-src"] == "'none'"
        assert csp["base-uri"] == "'none'"
        assert csp["frame-ancestors"] == "'none'"
        assert csp["form-action"] == "'self'"

    def test_the_page_needs_no_inline_style_attributes(self):
        html = serve.render_feed(serve.demo_connection())
        assert not re.search(r'<[^>]+\sstyle="', html), "inline style attributes need unsafe-hashes"

    def test_the_hashes_are_the_hashes_of_the_shipped_blocks(self, conn):
        body = serve.handle(conn, "GET", "/", {}, demo=True).body
        header = serve.security_headers(https=True)["Content-Security-Policy"]
        for block in re.findall(r"<style>(.*?)</style>", body, re.S):
            assert f"'{digest(block)}'" in header
        for block in re.findall(r"<script>(.*?)</script>", body, re.S):
            assert f"'{digest(block)}'" in header

    def test_the_policy_survives_the_pages_that_exist(self, conn):
        pages = ["/", "/shortlist", "/brief", "/pulse", "/salaries", "/employers", "/search", "/activity", "/year"]
        for path in pages:
            body = serve.handle(conn, "GET", path, {}, demo=True).body
            assert not re.search(r'<[^>]+\sstyle="', body), path
            assert "onclick=" not in body and "onload=" not in body, path

    def test_hsts_only_over_https(self):
        assert "Strict-Transport-Security" in serve.security_headers(https=True)
        assert "Strict-Transport-Security" not in serve.security_headers(https=False)

    def test_the_other_headers_say_what_they_mean(self):
        headers = serve.security_headers(https=False)
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "geolocation=()" in headers["Permissions-Policy"]
        assert headers["Cross-Origin-Opener-Policy"] == "same-origin"

    def test_the_error_page_style_is_allowed_too(self):
        assert f"'{serve.ERROR_STYLE_HASH}'" in serve.security_headers(https=True)["Content-Security-Policy"]

    def test_the_serverless_adapter_sends_the_policy(self):
        shim = (Path(serve.__file__).resolve().parents[2] / "api" / "index.py").read_text()
        assert "serve.security_headers()" in shim


class TestTheLimits:
    def test_search_is_limited(self, conn):
        limiter = serve._RateLimiter(limit=2)
        for _ in range(2):
            assert serve.handle(
                conn, "GET", "/search", {}, demo=True, search_limiter=limiter, client="1.2.3.4"
            ).status == 200
        assert serve.handle(
            conn, "GET", "/search", {}, demo=True, search_limiter=limiter, client="1.2.3.4"
        ).status == 429

    def test_the_search_limit_is_per_client(self, conn):
        limiter = serve._RateLimiter(limit=1)
        serve.handle(conn, "GET", "/search", {}, demo=True, search_limiter=limiter, client="a")
        assert serve.handle(
            conn, "GET", "/search", {}, demo=True, search_limiter=limiter, client="b"
        ).status == 200

    def test_actions_are_limited(self, conn):
        limiter = serve._RateLimiter(limit=2)
        body = b"profile=demo-fresher&kind=viewed"
        for _ in range(2):
            assert serve.handle(
                conn, "POST", "/action", {}, body=body, demo=True, action_limiter=limiter, client="x"
            ).status in (200, 303)
        assert serve.handle(
            conn, "POST", "/action", {}, body=body, demo=True, action_limiter=limiter, client="x"
        ).status == 429

    def test_the_limits_are_generous_enough_for_a_person(self):
        assert serve.ACTION_RATE_LIMIT >= 60
        assert serve.SEARCH_RATE_LIMIT >= 30

    def test_no_limiter_means_no_limit(self, conn):
        """The pure router stays a pure function when nothing is injected."""
        for _ in range(5):
            assert serve.handle(conn, "GET", "/search", {}, demo=True).status == 200
