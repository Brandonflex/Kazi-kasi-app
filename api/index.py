"""Vercel entrypoint — the same app, behind a serverless function.

Vercel runs Python as a WSGI/ASGI callable. The routing, rendering and business
rules all live in `kazikasi.serve.handle()`; this file is only the adapter, so
the deployed site and the sandbox server cannot drift apart.

Two deployment facts shaped it:

* **There is no writable disk.** The database is in-memory, built from the
  synthetic corpus on first request and kept for the life of the instance. That
  is exactly right for a testing link: nothing real is served, nothing has to be
  mounted, and a cold start costs a few milliseconds.
* **There is no `PATH_INFO` guarantee.** A catch-all rewrite can collapse the
  path to `/api/index`, so the original path is passed explicitly as `__path`
  by `vercel.json`, with a fallback chain for anything that loses it.

Diagnostics: `/api/health` returns the schema version, the corpus size and the
path this instance resolved — enough to tell "not deployed" from "deployed and
mis-routed" in one request.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
import threading
import traceback
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:  # local package, not installed in the bundle
    sys.path.insert(0, str(SRC))

from kazikasi import bundle, db, serve  # noqa: E402  (after the path fix)

#: One database per warm instance. Requests are serialised through this lock,
#: which is what makes sharing a single sqlite connection safe.
_LOCK = threading.RLock()
_STATE: dict[str, object] = {"conn": None, "path_source": None}

LIMITER = serve._RateLimiter()
SEARCH_LIMITER = serve._RateLimiter(limit=serve.SEARCH_RATE_LIMIT)
ACTION_LIMITER = serve._RateLimiter(limit=serve.ACTION_RATE_LIMIT)


def _connection():
    """The corpus this instance serves, built once per warm container.

    Priority:

    1. ``DATABASE_URL`` — a real Postgres store (Neon free tier). Everything the
       app writes — accounts, shortlists, the digest outbox, the sweep — lives
       here and survives cold starts. ``/api/setup`` flips ``storage`` to
       ``done`` when this is set and reachable.
    2. ``KAZIKASI_BUNDLE`` — a published sweep file. Real vacancies, but no
       writes; good for a read-only deployment or a staged roll-out.
    3. Synthetic, in-memory — what the test suite and ``vercel dev`` use.

    The connection is opened once per warm instance and reused under the same
    lock the serverless adapter already takes per request.
    """
    with _LOCK:
        if _STATE["conn"] is None:
            connection = None
            database_url = (os.environ.get("DATABASE_URL") or "").strip()
            bundle_url = (os.environ.get("KAZIKASI_BUNDLE") or "").strip()
            if database_url:
                try:
                    connection = db.connect(url=database_url)
                except Exception as exc:  # noqa: BLE001 — surfaced, not swallowed
                    # A bad DATABASE_URL must not take down the whole app: serve
                    # the synthetic corpus and let /api/setup name the variable.
                    sys.stderr.write(f"DATABASE_URL unreachable ({exc}); falling back to synthetic.\n")
                    connection = None
            if connection is None and bundle_url:
                connection = bundle.build_fresh()
            if connection is None:
                connection = serve.demo_connection(thread_safe=True, history=True)
                if bundle_url:
                    serve._seed_demo_history(connection, datetime.now(timezone.utc))
            _STATE["conn"] = connection
        return _STATE["conn"]


def _original_path(environ: dict, query: dict) -> tuple[str, str]:
    """Recover the path the visitor actually asked for.

    Order matters: `__path` is what our rewrite sets, and it is the only one that
    survives every Vercel routing mode.
    """
    explicit = (query.pop("__path", [""]) or [""])[0]
    if explicit:
        return "/" + explicit.lstrip("/"), "rewrite-query"

    path = environ.get("PATH_INFO") or ""
    if path and not path.startswith("/api/index"):
        return path, "path-info"

    for key in ("HTTP_X_FORWARDED_URI", "REQUEST_URI", "RAW_URI"):
        value = environ.get(key) or ""
        if value:
            return value.split("?", 1)[0], key.lower()

    return "/", "default"


def _client(environ: dict) -> str:
    forwarded = (environ.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return forwarded or environ.get("REMOTE_ADDR") or "unknown"


def _headers(environ: dict) -> dict:
    headers = {}
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            headers[key[5:].replace("_", "-").lower()] = value
        elif key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
            headers[key.replace("_", "-").lower()] = value
    return headers


def _body(environ: dict) -> bytes:
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    stream = environ.get("wsgi.input")
    if not length or stream is None:
        return b""
    return stream.read(min(length, 512 * 1024))


def _error_page(exc: Exception) -> bytes:
    """A 500 you can actually debug from a screenshot.

    This deployment serves synthetic data and holds no secrets, so the error is
    shown rather than swallowed. Diagnostics belong in the page, not in a log
    nobody on the other end can read.
    """
    detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    frame = traceback.extract_tb(exc.__traceback__)[-1:] or []
    where = f"{frame[0].filename}:{frame[0].lineno}" if frame else "unknown"
    body = f"""<!doctype html><html lang="en-KE"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Deployment error</title>
<style>{serve.ERROR_STYLE}</style></head>
<body><h1>The app failed to start a response</h1>
<p class="mut">{serve._e(where)}</p>
<pre>{serve._e(detail)}</pre>
<p class="mut">Synthetic demo data. Check <code>/api/health</code> after the fix.</p>
</body></html>"""
    return body.encode("utf-8")


def _is_connection_alive(conn) -> bool:
    """Cheap health check. Returns False if the connection has been killed by
    the pooler (idle-in-transaction timeout, network blip, etc.)."""
    try:
        conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def app(environ, start_response):
    """WSGI entrypoint."""
    method = (environ.get("REQUEST_METHOD") or "GET").upper()
    query = parse_qs(environ.get("QUERY_STRING") or "", keep_blank_values=True)
    path, source = _original_path(environ, query)
    _STATE["path_source"] = source

    try:
        with _LOCK:
            conn = _connection()
            # If the pooler killed our connection (idle timeout, etc.), drop it
            # and reconnect. One retry; if the reconnect also fails, fall through
            # to the synthetic corpus via _connection()'s own fallback.
            if not _is_connection_alive(conn):
                _STATE["conn"] = None
                conn = _connection()
            response = serve.handle(
                conn,
                method,
                path,
                query,
                body=_body(environ),
                headers=_headers(environ),
                # Synthetic until a real store exists — see serve.synthetic_build().
                demo=serve.synthetic_build(),
                limiter=LIMITER,
                search_limiter=SEARCH_LIMITER,
                action_limiter=ACTION_LIMITER,
                client=_client(environ),
            )
        status = f"{response.status} {'OK' if response.status < 400 else 'Error'}"
        payload = response.body.encode("utf-8")
        policy = serve.security_headers()
        # If the response has its own CSP header, use that instead of the
        # standard one (e.g. the galaxy page needs different permissions).
        if "Content-Security-Policy" in response.headers:
            policy = {k: v for k, v in policy.items() if k != "Content-Security-Policy"}
        # Redirects skip COOP: it's meant for pages with sensitive content, not
        # for 303s that are part of an OAuth flow coming back from Google.
        if response.is_redirect:
            policy = {k: v for k, v in policy.items() if k != "Cross-Origin-Opener-Policy"}
        headers = [
            ("Content-Type", response.content_type),
            ("Content-Length", str(len(payload))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            *policy.items(),
            *[(key, value) for key, value in response.headers.items()],
        ]
    except Exception as exc:  # noqa: BLE001 - surfaced, not swallowed
        payload = _error_page(exc)
        status = "500 Internal Server Error"
        headers = [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(payload))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            *serve.security_headers().items(),
        ]

    start_response(status, headers)
    return [payload]


# Vercel's Python runtime looks for `app`, `application`, or `handler`.
handler = app
application = app


def health() -> dict:
    """A one-liner for `python -c` and for the deploy checklist."""
    with _LOCK:
        conn = _connection()
        summary = db.table_counts(conn)
    return {"path_source": _STATE["path_source"], "tables": summary, "schema": db.SCHEMA_VERSION}
