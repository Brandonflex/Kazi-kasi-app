"""The go-live page: derived from the process, and incapable of leaking a secret.

The value of a page like this is entirely in whether it tells the truth. So the
tests are about derivation, not layout: flip a variable, watch a step change; and
about the one thing it must never do — render a value it was only told to check
for existence.
"""

from __future__ import annotations

import json

import pytest

from kazikasi import bundle, serve, setup

NOW = __import__("datetime").datetime(2026, 10, 20, 9, tzinfo=__import__("datetime").timezone.utc)
SECRET = "Zx9-donotprint-this-4f2a"


@pytest.fixture
def conn():
    connection = serve.demo_connection(now=NOW)
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in (
        "DATABASE_URL",
        "KAZIKASI_BUNDLE",
        "KAZIKASI_SECRET",
        "KAZIKASI_DEMO",
        "KAZIKASI_BASE_URL",
        "CRON_SECRET",
        "WHATSAPP_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
        "AT_USERNAME",
        "AT_API_KEY",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "KAZIKASI_ALLOW_SYNTHETIC_SEND",
    ):
        monkeypatch.delenv(name, raising=False)
    yield


def build(conn):
    return setup.plan(
        conn, now=NOW, synthetic=serve.synthetic_build(), strict=True, base_url="https://kazi-kasi-app.vercel.app"
    )


def step(plan, key):
    return next(item for item in plan.steps if item.id == key)


def page(conn):
    return serve.handle(conn, "GET", "/setup", {}, demo=True, now=NOW).body


def api(conn):
    return json.loads(serve.handle(conn, "GET", "/api/setup", {}, demo=True, now=NOW).body)


class TestDerivation:
    def test_everything_is_missing_on_a_bare_environment(self, conn):
        plan = build(conn)
        assert step(plan, "session").state == "missing"
        assert step(plan, "google").state == "missing"
        assert step(plan, "storage").state == "missing"
        assert plan.live is False

    def test_a_secret_flips_the_session_step(self, conn, monkeypatch):
        monkeypatch.setenv("KAZIKASI_SECRET", SECRET)
        monkeypatch.setenv("KAZIKASI_DEMO", "0")
        assert step(build(conn), "session").state == "done"

    def test_the_demo_secret_does_not_count(self, conn, monkeypatch):
        monkeypatch.setenv("KAZIKASI_SECRET", "kazi-kasi-demo")
        monkeypatch.setenv("KAZIKASI_DEMO", "0")
        assert step(build(conn), "session").state == "missing"

    def test_google_credentials_flip_that_step(self, conn, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        assert step(build(conn), "google").state == "done"

    def test_a_database_flips_storage_and_the_corpus_flag(self, conn, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgres://example")
        plan = build(conn)
        assert step(plan, "storage").state == "done"
        assert plan.instance["synthetic"] is False

    def test_each_transport_alone_is_enough(self, conn, monkeypatch):
        assert step(build(conn), "delivery").state == "optional"
        monkeypatch.setenv("AT_USERNAME", "kazi")
        monkeypatch.setenv("AT_API_KEY", "key")
        assert step(build(conn), "delivery").state == "done"

    def test_half_a_credential_is_not_a_transport(self, conn, monkeypatch):
        monkeypatch.setenv("WHATSAPP_TOKEN", "tok")
        assert step(build(conn), "delivery").state == "optional"


class TestNoSecrets:
    def test_the_html_never_renders_a_value(self, conn, monkeypatch):
        for name in ("KAZIKASI_SECRET", "CRON_SECRET", "GOOGLE_CLIENT_SECRET", "AT_API_KEY", "WHATSAPP_TOKEN"):
            monkeypatch.setenv(name, SECRET)
        body = page(conn)
        assert SECRET not in body

    def test_neither_does_the_json(self, conn, monkeypatch):
        for name in ("KAZIKASI_SECRET", "CRON_SECRET", "GOOGLE_CLIENT_SECRET"):
            monkeypatch.setenv(name, SECRET)
        assert SECRET not in json.dumps(api(conn))

    def test_it_still_says_the_variable_exists(self, conn, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", SECRET)
        assert step(build(conn), "cron").state == "done"
        assert "CRON_SECRET" in page(conn)


class TestWhatToPaste:
    def test_the_redirect_uri_is_exact_and_copyable(self, conn):
        plan = build(conn)
        google = step(plan, "google")
        value = google.paste[0].value
        assert value == "https://kazi-kasi-app.vercel.app/auth/google/callback"
        assert not value.endswith("/")
        assert value in page(conn)
        assert f'data-copy="{value}"' in page(conn)

    def test_the_cron_step_carries_the_path_and_schedule(self, conn):
        values = {item.label: item.value for item in step(build(conn), "cron").paste}
        assert values["Vercel cron path"] == "/api/cron/run"
        assert values["Schedule (UTC)"] == "0 15 * * *"

    def test_every_missing_step_names_its_variables(self, conn):
        for item in build(conn).steps:
            if item.state == "missing":
                assert item.env, item.id

    def test_the_console_links_point_at_the_right_consoles(self, conn):
        plan = build(conn)
        assert "console.cloud.google.com" in step(plan, "google").link[1]
        assert "linkedin.com/developers" in step(plan, "linkedin").link[1]


class TestTheTick:
    def test_no_cron_secret_means_503(self, conn):
        assert build(conn).instance["tick"]["answer"].startswith("503")
        assert build(conn).instance["tick"]["needs"] == "CRON_SECRET"

    def test_a_synthetic_corpus_refuses_to_send(self, conn, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "tok")
        tick = build(conn).instance["tick"]
        assert tick["runs"] is False
        assert tick["answer"] == "409 refusing to send"
        assert "storage" in tick["needs"]

    def test_no_transport_is_503_not_a_cheerful_200(self, conn, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "tok")
        monkeypatch.setenv("DATABASE_URL", "postgres://example")
        tick = build(conn).instance["tick"]
        assert tick["answer"] == "503 no transport configured"

    def test_all_three_and_it_runs(self, conn, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "tok")
        monkeypatch.setenv("DATABASE_URL", "postgres://example")
        monkeypatch.setenv("WHATSAPP_TOKEN", "tok")
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "1")
        assert build(conn).instance["tick"]["runs"] is True


class TestThePage:
    def test_it_renders_and_is_noindex(self, conn):
        body = page(conn)
        assert "What is left, and what to paste" in body
        assert 'name="robots" content="noindex"' in body

    def test_it_is_disallowed_to_crawlers(self, conn):
        assert "Disallow: /setup" in serve.handle(conn, "GET", "/robots.txt", {}, now=NOW).body

    def test_it_is_not_in_the_sitemap(self, conn):
        assert "/setup" not in serve.handle(conn, "GET", "/sitemap.xml", {}, now=NOW).body

    def test_the_two_console_traps_are_documented(self, conn):
        body = page(conn)
        assert "403" in body
        assert "LinkedIn Page" in body
        assert "Company Page" in body

    def test_its_scripts_are_allowed_by_the_policy(self, conn):
        import base64
        import hashlib
        import re

        header = serve.security_headers(https=True)["Content-Security-Policy"]
        for block in re.findall(r"<script>(.*?)</script>", page(conn), re.S):
            digest = "sha256-" + base64.b64encode(hashlib.sha256(block.encode()).digest()).decode()
            assert f"'{digest}'" in header

    def test_it_contains_no_inline_handlers(self, conn):
        body = page(conn)
        assert "onclick=" not in body and "onload=" not in body

    def test_the_json_route_agrees_with_the_page(self, conn, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "tok")
        payload = api(conn)
        assert payload["total"] == len(setup.plan(
            conn, now=NOW, synthetic=serve.synthetic_build(), strict=True,
            base_url="https://kazi-kasi-app.vercel.app",
        ).steps)
        cron = next(item for item in payload["steps"] if item["id"] == "cron")
        assert cron["state"] == "done"

    def test_a_loaded_bundle_shows_in_the_corpus_block(self, conn):
        bundle.STATE.update({"source": "bundle", "built_at": NOW.isoformat(), "count": 26, "error": None})
        try:
            plan = build(conn)
            assert plan.instance["corpus"]["source"] == "bundle"
            assert plan.instance["corpus"]["count"] == 26
        finally:
            bundle.STATE.clear()
            bundle.STATE.update({"source": "synthetic", "built_at": None, "count": 0, "error": None})


class TestRotationGuidance:
    """A leaked secret is a procedure, not a paragraph of shame."""

    def test_the_page_explains_rotation_without_downtime(self, conn):
        body = page(conn)
        assert "Add secret" in body
        assert "delete the old" in body.lower() or "delete the old one" in body.lower()

    def test_it_says_the_console_can_still_show_the_secret(self, conn):
        body = page(conn)
        assert "masked" in body
        assert "creation dialog" in body


class TestThePageDoesNotInstructYouAboutFinishedWork:
    """The regression that caused a real "step one? what step one?".

    The first version rendered the how-to note on completed steps too, so the top
    card on the page told you to paste variables you had already set — and, being
    first, read like "step 1 of a to-do list". A checklist that keeps instructing
    after you are finished is a checklist people stop trusting.
    """

    @pytest.fixture(autouse=True)
    def configured(self, monkeypatch):
        monkeypatch.setenv("KAZIKASI_SECRET", "not-the-demo-secret-000000000")
        monkeypatch.setenv("KAZIKASI_DEMO", "0")
        monkeypatch.setenv("KAZIKASI_BASE_URL", "https://kazi-kasi-app.vercel.app")

    def test_a_done_step_shows_no_instructions(self):
        conn = serve.demo_connection(now=NOW)
        try:
            body = page(conn)
        finally:
            conn.close()
        assert "Already done" in body
        # the session step is complete: its "here is how" note must be gone
        assert "There is no bulk-paste box" not in body
        # ...but it is still reported, with evidence
        assert "Session secret and production mode" in body
        assert "secret set: True" in body

    def test_the_next_action_is_named_in_one_line(self):
        conn = serve.demo_connection(now=NOW)
        try:
            body = page(conn)
        finally:
            conn.close()
        assert "Next: Google sign-in" in body

    def test_missing_steps_are_numbered_from_one(self):
        conn = serve.demo_connection(now=NOW)
        try:
            body = page(conn)
        finally:
            conn.close()
        assert 'class="kicker stepnum">1.' in body
        # the completed step is not numbered at all
        assert 'class="kicker stepnum">1. Session' not in body

    def test_with_nothing_missing_the_headline_says_so(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgres://example")
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        conn = serve.demo_connection(now=NOW)
        try:
            body = page(conn)
        finally:
            conn.close()
        assert "Nothing required is missing" in body
        assert "Do these, in this order" not in body


class TestWhyAVariableIsUnusable:
    """"missing" is four different mistakes with four different fixes.

    On Vercel the same word covers: never saved, saved blank, saved with a pasted
    newline (which OAuth rejects as invalid_client), and saved under a
    nearly-identical name. Each has its own remedy, so the page names the state.
    """

    @pytest.fixture(autouse=True)
    def clean(self, monkeypatch):
        for name in (
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
            "GOOGLE_CLIENT_SECRET_KEY",
            "LINKEDIN_CLIENT_ID",
            "WHATSAPP_TOKEN",
            "AT_USERNAME",
            "AT_API_KEY",
        ):
            monkeypatch.delenv(name, raising=False)

    def test_a_plain_value_is_set(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id.apps.googleusercontent.com")
        assert setup._probe("GOOGLE_CLIENT_ID")["state"] == "set"

    def test_empty_is_not_missing(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "   ")
        assert setup._probe("GOOGLE_CLIENT_ID")["state"] == "blank"

    def test_a_pasted_newline_is_reported_as_padding(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-abc\n")
        probe = setup._probe("GOOGLE_CLIENT_SECRET")
        assert probe["state"] == "padded"

    def test_a_near_identical_name_is_named(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET_KEY", "value")
        probe = setup._probe("GOOGLE_CLIENT_SECRET")
        assert probe["state"] == "near"
        assert probe["seen"] == "GOOGLE_CLIENT_SECRET_KEY"

    def test_lowercase_and_hyphens_count_as_the_same_name(self, monkeypatch):
        monkeypatch.setenv("google-client-secret", "value")
        assert setup._probe("GOOGLE_CLIENT_SECRET")["state"] == "near"

    def test_absent_says_redeploy(self):
        assert setup._probe("GOOGLE_CLIENT_ID")["state"] == "absent"
        assert "redeploy" in setup._explain(["GOOGLE_CLIENT_ID"])

    def test_the_sentence_never_contains_a_value(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-do-not-print-me\n")
        text = setup._explain(["GOOGLE_CLIENT_SECRET"])
        assert "GOCSPX-do-not-print-me" not in text
        assert "whitespace" in text

    def test_the_page_surfaces_the_redeploy_hint(self):
        conn = serve.demo_connection(now=NOW)
        try:
            body = page(conn)
        finally:
            conn.close()
        assert "redeploy" in body


class TestTheHostItIsActuallyServedOn:
    """A redirect_uri built for a domain the visitor is not on fails at the callback.

    The failure shows up as a state-mismatch on Google's end, which points at
    cookies and CSRF, not at KAZIKASI_BASE_URL. Catching it on /setup is the whole
    point of deriving the page from the request.
    """

    def test_a_matching_host_is_quiet(self):
        conn = serve.demo_connection(now=NOW)
        try:
            page_html = serve.render_setup(
                conn, now=NOW, headers={"host": "kazi-kasi-app.vercel.app"}
            )
        finally:
            conn.close()
        assert "but this build thinks it lives at" not in page_html

    def test_a_mismatched_host_is_named(self):
        conn = serve.demo_connection(now=NOW)
        try:
            page_html = serve.render_setup(conn, now=NOW, headers={"host": "example.org"})
        finally:
            conn.close()
        assert "You are on example.org" in page_html
        assert "KAZIKASI_BASE_URL" in page_html

    def test_the_json_reports_it_too(self):
        conn = serve.demo_connection(now=NOW)
        try:
            plan = setup.plan(
                conn, synthetic=True, strict=True, host="example.org:443"
            )
        finally:
            conn.close()
        assert plan.instance["host_matches"] is False
        assert plan.instance["served_host"] == "example.org"


class TestTheTestingRecipe:
    """The page has to say how to *verify*, not only what to paste."""

    def test_it_lists_the_sign_in_test_in_order(self):
        conn = serve.demo_connection(now=NOW)
        try:
            body = page(conn)
        finally:
            conn.close()
        assert "How to test sign-in" in body
        assert "redirect_uri_mismatch" in body
        assert "invalid_client" in body
        assert "/signin" in body

    def test_the_redeploy_entry_names_the_environment_scope(self):
        conn = serve.demo_connection(now=NOW)
        try:
            body = page(conn)
        finally:
            conn.close()
        assert "Preview environment only" in body or "Production" in body
