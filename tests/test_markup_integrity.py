"""Markup and stylesheet agree, and every form posts to a route that exists.

Both faults here were invisible to every existing test, and both were visible in one
screenshot:

* the sign-in buttons rendered as unstyled inline text because `.provider-button`
  and `.provider` were named in the markup and defined nowhere — a stylesheet
  rewrite dropped them, and nothing noticed, because HTML with a class nobody styles
  is still valid HTML;
* every "Continue with …" button answered **404**, because the page posts to
  ``/auth/start`` and the router only handled ``GET /auth/<provider>/start``. The
  flow was built and tested through the GET route, which no person ever touches.

These are cheap checks and they cover the whole app, not just sign-in.
"""

from __future__ import annotations

import re

import pytest

from kazikasi import serve

#: Class names that appear in markup as part of a template expression, not a real
#: class. Matching on `class="..."` inside f-strings catches fragment words.
_NOT_CLASSES = {"if", "else", "in", "ops", "for", "and", "or", "not"}


def stylesheet() -> str:
    return serve.STYLE


def styled_classes() -> set[str]:
    return set(re.findall(r"\.([a-zA-Z][\w-]*)", stylesheet()))


def markup_classes() -> set[str]:
    """Literal class names only.

    A ``class`` attribute that contains ``{`` is a template expression — its words
    are Python, not classes (``{'on' if item.saved else ''}`` is not a class called
    ``saved``). Skipping those keeps the check honest instead of noisy.
    """
    source = open(serve.__file__, encoding="utf-8").read()
    found: set[str] = set()
    for block in re.findall(r'class="([^"]+)"', source):
        if "{" in block or "}" in block:
            continue
        for name in re.split(r"\s+", block):
            if re.fullmatch(r"[a-z][a-z0-9-]*", name or "") and name not in _NOT_CLASSES:
                found.add(name)
    return found


class TestNoOrphanedClasses:
    def test_every_class_in_markup_is_styled(self):
        orphans = sorted(markup_classes() - styled_classes())
        assert not orphans, (
            "these classes are used in markup but defined nowhere in STYLE, so they "
            "render unstyled: " + ", ".join(orphans)
        )

    def test_the_sign_in_cards_specifically(self):
        sheet = stylesheet()
        for name in (".provider", ".provider-button", ".provider-state"):
            assert name in sheet, f"{name} must be styled"


class TestEveryFormPostsSomewhereReal:
    """A form whose action 404s is a button that does nothing.

    Collects every ``<form ... action="...">`` and every POST-only route, then
    asserts each action is routable. POST is the interesting verb: GET routes are
    usually exercised by a page render, POST routes are only exercised by the person
    clicking.
    """

    GET_ROUTES = (
        "/", "/feed", "/search", "/shortlist", "/brief", "/pulse", "/salaries",
        "/employers", "/activity", "/account", "/signin", "/setup", "/whatsapp",
    )

    POST_ROUTES = (
        "/auth/start",
        "/auth/guest",
        "/auth/demo",
        "/auth/signout",
        "/action",
        "/digest/subscribe",
        "/digest/unsubscribe",
        "/search/save",
        "/search/stop",
        "/account/cv",
        "/account/forget",
    )

    def forms(self) -> list[tuple[str, str]]:
        """(method, action) for every form, method defaulting to GET per HTML."""
        source = open(serve.__file__, encoding="utf-8").read()
        found = []
        for tag in re.findall(r"<form[^>]*>", source):
            action = re.search(r'action="([^"]+)"', tag)
            if not action or action.group(1).startswith(("{", "$")):
                continue
            method = re.search(r'method="([^"]+)"', tag)
            found.append(((method.group(1) if method else "get").lower(), action.group(1)))
        return found

    def test_every_post_form_targets_a_known_post_route(self):
        unknown = sorted(
            {action for method, action in self.forms() if method == "post"}
            - set(self.POST_ROUTES)
        )
        assert not unknown, "forms post to unrouted paths: " + ", ".join(unknown)

    def test_every_get_form_targets_a_rendered_page(self):
        """A GET form with a typo in its action silently returns 404 on submit."""
        unknown = sorted(
            {
                action
                for method, action in self.forms()
                if method == "get" and action.startswith("/")
            }
            - set(self.GET_ROUTES)
        )
        assert not unknown, "forms GET unrouted paths: " + ", ".join(unknown)

    def test_a_post_to_each_route_is_not_404(self):
        for route in self.POST_ROUTES:
            conn = serve.demo_connection()
            try:
                response = serve.handle(
                    conn, "POST", route, {}, body=b"provider=google&next=/", demo=True
                )
            finally:
                conn.close()
            assert response.status != 404, f"POST {route} answers 404"


class TestTheSignInPageItself:
    def page(self, demo: bool = True, env: dict | None = None, monkeypatch=None) -> str:
        conn = serve.demo_connection()
        try:
            return serve.handle(conn, "GET", "/signin", {}, demo=demo).body
        finally:
            conn.close()

    def test_an_unconfigured_provider_is_not_shown(self):
        body = self.page()
        # When no provider is configured, no forms post to /auth/start
        assert 'action="/auth/start"' not in body
        # A notice points at /setup
        assert "/setup" in body

    def test_a_configured_provider_is_the_primary_form(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        conn = serve.demo_connection()
        try:
            body = serve.handle(conn, "GET", "/signin", {}, demo=True).body
        finally:
            conn.close()
        assert 'action="/auth/start"' in body
        assert 'value="google"' in body
        assert 'class="signin-primary-btn"' in body

    def test_the_label_and_the_description_are_separate_elements(self, monkeypatch):
        """They used to run together as "Continue with GoogleYour name and email address"."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        conn = serve.demo_connection()
        try:
            body = serve.handle(conn, "GET", "/signin", {}, demo=True).body
        finally:
            conn.close()
        # The signin-provider-name and signin-provider-why are separate spans
        assert 'class="signin-provider-name"' in body
        assert 'class="signin-provider-why"' in body


class TestThePostThatWasMissing:
    def test_it_redirects_a_configured_provider_to_the_consent_screen(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        conn = serve.demo_connection()
        try:
            response = serve.handle(
                conn, "POST", "/auth/start", {}, body=b"provider=google", demo=True
            )
        finally:
            conn.close()
        assert response.status == 303
        assert response.headers["Location"] == "/auth/google/start"

    def test_an_unconfigured_provider_says_what_is_missing(self):
        conn = serve.demo_connection()
        try:
            response = serve.handle(
                conn, "POST", "/auth/start", {}, body=b"provider=google", demo=True
            )
        finally:
            conn.close()
        assert response.status == 303
        location = response.headers["Location"]
        assert "GOOGLE_CLIENT_ID" in location
        assert "not configured" in location.replace("%20", " ")

    def test_an_unknown_provider_comes_back_with_a_notice_not_a_crash(self):
        conn = serve.demo_connection()
        try:
            response = serve.handle(
                conn, "POST", "/auth/start", {}, body=b"provider=../etc/passwd", demo=True
            )
        finally:
            conn.close()
        assert response.status == 303
        assert "does%20not%20exist" in response.headers["Location"]

    def test_an_empty_body_does_not_raise(self):
        conn = serve.demo_connection()
        try:
            response = serve.handle(conn, "POST", "/auth/start", {}, body=b"", demo=True)
        finally:
            conn.close()
        assert response.status == 303
