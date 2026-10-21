"""The deployed surface: WSGI in, HTTP out, with no disk and no network.

A Vercel function is a hostile environment compared to a server: no writable
filesystem, no guarantee that `PATH_INFO` survived the rewrite, and a cold start
that must not need a wheel from PyPI. These tests simulate that environment in
process — the same `app` object Vercel imports, called the way its runtime calls
it.

What they protect:

* the demo corpus is built **in memory**, so nothing is written to disk;
* routing survives both a preserved path and a collapsed one (`__path`);
* POSTs (consent, actions, webhooks) work through the same code as the server;
* a missing third-party package cannot break the web surface;
* an exception produces a debuggable 500 rather than an empty response.
"""

from __future__ import annotations

import io
import json
import sys

import pytest


@pytest.fixture(scope="module")
def deployed():
    from api.index import app

    return app


def call(app, path="/", *, query=None, method="GET", body=b"", headers=None, path_info="/api/index"):
    """Invoke the WSGI app the way Vercel does."""
    qs = query if query is not None else f"__path={path}"
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path_info,
        "QUERY_STRING": qs,
        "wsgi.input": io.BytesIO(body),
        "CONTENT_LENGTH": str(len(body)),
        "REMOTE_ADDR": "203.0.113.9",
        "HTTP_HOST": "kazi-kasi-app.vercel.app",
    }
    environ.update(headers or {})
    captured = {}

    def start_response(status, response_headers):
        captured["status"] = status
        captured["headers"] = dict(response_headers)

    payload = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], payload


class TestRouting:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("/", "Kazi-Kasi"),
            ("/digest", "WhatsApp digest"),
            ("/slo", "Freshness"),
            ("/review", "Review queue"),
        ],
    )
    def test_the_pages_render_through_the_rewrite(self, deployed, path, expected):
        status, headers, body = call(deployed, path)
        assert status.startswith("200")
        assert headers["Content-Type"].startswith("text/html")
        assert expected in body.decode()

    def test_healthz_is_perfectly_dumb_so_a_platform_probe_can_use_it(self, deployed):
        status, headers, body = call(deployed, "/healthz")
        assert (status, body) == ("200 OK", b"ok")
        assert headers["Content-Type"] == "text/plain; charset=utf-8"

    def test_api_health_says_what_this_instance_actually_is(self, deployed):
        status, _, body = call(deployed, "/api/health")
        payload = json.loads(body)
        assert status.startswith("200")
        assert payload["ok"] is True
        assert payload["schema"] >= 5
        assert payload["live_jobs"] > 0
        # The corpus is synthetic (no DATABASE_URL); strictness is a separate
        # question and is reported by /auth/ready.
        assert payload["synthetic"] is True
        assert payload["strict"] is False

    def test_the_api_serves_json_not_html(self, deployed):
        status, headers, body = call(deployed, "/api/jobs")
        payload = json.loads(body)
        assert status.startswith("200")
        assert headers["Content-Type"].startswith("application/json")
        assert payload["matches"]

    def test_a_missing_page_is_a_404_not_a_500(self, deployed):
        status, _, body = call(deployed, "/nothing-here")
        assert status.startswith("404")
        assert "Not found" in body.decode()

    def test_a_preserved_path_is_used_when_there_is_no_rewrite_query(self, deployed):
        """If Vercel keeps PATH_INFO, routing must work without `__path` too."""
        status, _, body = call(deployed, "/digest", query="", path_info="/digest")
        assert status.startswith("200")
        assert "WhatsApp digest" in body.decode()

    def test_the_original_uri_is_the_last_resort(self, deployed):
        status, _, body = call(
            deployed, path_info="/api/index", query="", headers={"REQUEST_URI": "/slo?x=1"}
        )
        assert status.startswith("200")
        assert "Freshness" in body.decode()


class TestPosts:
    def test_an_action_redirects_back_to_the_feed(self, deployed):
        body = b"profile=demo-fresher&job=whatever&kind=dismissed"
        status, headers, _ = call(deployed, "/action", method="POST", body=body)
        assert status.startswith("303")
        assert headers["Location"] == "/?profile=demo-fresher"

    def test_json_clients_get_json(self, deployed):
        body = b"profile=demo-fresher&job=whatever&kind=dismissed"
        status, headers, payload = call(
            deployed, "/action", method="POST", body=body, headers={"HTTP_ACCEPT": "application/json"}
        )
        assert status.startswith("200")
        assert json.loads(payload)["ok"] is True

    def test_subscribing_from_the_deployed_page_works(self, deployed):
        body = b"profile=demo-fresher&msisdn=0712000999"
        status, headers, _ = call(deployed, "/digest/subscribe", method="POST", body=body)
        assert status.startswith("303")
        assert headers["Location"].startswith("/digest?profile=demo-fresher")

        status, _, page = call(deployed, "/digest")
        assert "+2547•••0999" in page.decode()

    def test_a_bad_number_comes_back_as_an_error_in_the_url(self, deployed):
        body = b"profile=demo-fresher&msisdn=0712"
        status, headers, _ = call(deployed, "/digest/subscribe", method="POST", body=body)
        assert "error=" in headers["Location"]

    def test_a_demo_webhook_can_stop_a_subscription(self, deployed):
        call(deployed, "/digest/subscribe", method="POST", body=b"profile=demo-fresher&msisdn=0712000777")
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "w.1",
                                        "from": "254712000777",
                                        "type": "text",
                                        "text": {"body": "STOP"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        status, _, body = call(
            deployed,
            "/webhooks/whatsapp",
            method="POST",
            body=json.dumps(payload).encode(),
            headers={"CONTENT_TYPE": "application/json"},
        )
        assert status.startswith("200")
        assert json.loads(body)["actions"] == {"unsubscribed": 1}

    def test_an_unconfigured_webhook_is_still_open_in_demo_mode_only(self, deployed):
        """`KAZIKASI_DEMO=0` is the production switch; it fails closed."""
        import os

        os.environ["KAZIKASI_DEMO"] = "0"
        try:
            status, _, body = call(
                deployed, "/webhooks/whatsapp", method="POST", body=b"{}",
                headers={"CONTENT_TYPE": "application/json"},
            )
        finally:
            os.environ.pop("KAZIKASI_DEMO", None)
        assert status.startswith("503")


class TestServerlessConstraints:
    def test_it_never_touches_the_filesystem(self, monkeypatch):
        """A function that writes to disk works locally and dies on Vercel."""
        import kazikasi.db as db_module
        import api.index as entry

        def refuse(*args, **kwargs):
            raise AssertionError("the demo surface must not open a file database")

        monkeypatch.setattr(db_module, "connect", refuse)
        entry._STATE["conn"] = None          # force a rebuild
        try:
            with pytest.raises(AssertionError):
                entry._connection()
        finally:
            monkeypatch.undo()
            entry._STATE["conn"] = None      # rebuild for real on the next test

    def test_the_connection_is_shared_and_reused(self, deployed):
        call(deployed, "/")
        import api.index as entry

        first = entry._connection()
        second = entry._connection()
        assert first is second

    def test_the_web_surface_imports_without_any_third_party_packages(self):
        """bs4/httpx/pypdf belong to ingestion, not to serving."""
        import subprocess

        script = """
import sys, builtins
real_import = builtins.__import__
BLOCKED = {"bs4", "httpx", "pypdf"}
def guard(name, *args, **kwargs):
    if name.split(".")[0] in BLOCKED:
        raise AssertionError(f"serving must not import {name}")
    return real_import(name, *args, **kwargs)
builtins.__import__ = guard
sys.path.insert(0, "src")
import kazikasi.serve
print("ok")
"""
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout

    def test_every_response_is_uncached_and_not_sniffed(self, deployed):
        for path in ("/", "/digest", "/api/jobs", "/healthz"):
            _, headers, _ = call(deployed, path)
            assert headers["Cache-Control"] == "no-store"
            assert headers["X-Content-Type-Options"] == "nosniff"


class TestErrors:
    def test_a_crash_becomes_a_readable_500(self, deployed, monkeypatch):
        from kazikasi import serve

        def explode(*args, **kwargs):
            raise RuntimeError("ranking exploded")

        monkeypatch.setattr(serve, "render_feed", explode)
        status, _, body = call(deployed, "/")
        text = body.decode()
        assert status.startswith("500")
        assert "ranking exploded" in text
        assert "<pre>" in text  # the traceback location, not a blank page
