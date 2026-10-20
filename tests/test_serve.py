"""The feed surface: ranking, reasons, apply link-out, freshness page, HTTP."""

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import db, graph, outbox, tracking
from kazikasi.corpus import load_corpus
from kazikasi.profile import seed_profiles
from kazikasi.serve import (
    make_server,
    render_digest,
    render_feed,
    render_job,
    render_review,
    render_slo,
)

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "kazi.db")
    load_corpus(connection, now=NOW)
    seed_profiles(connection)
    yield connection
    connection.close()


def readable(page: str) -> str:
    """Strip tags and CSS so assertions are about words, not markup."""
    import re

    page = re.sub(r"<style.*?</style>", " ", page, flags=re.S)
    page = re.sub(r"<[^>]+>", " ", page)
    return " ".join(page.split())


class TestFeed:
    def test_feed_is_tailored_to_the_default_profile(self, conn):
        page = readable(render_feed(conn, now=NOW, demo=True))
        assert "Synthetic demo data" in page
        assert "match this profile" in page

    def test_feed_explains_every_card(self, conn):
        page = readable(render_feed(conn, profile_id="demo-fresher", now=NOW))
        assert "matches" in page or "adjacent" in page
        assert "km away" in page or "remote" in page

    def test_a_specific_profile_changes_the_ranking(self, conn):
        fresher = readable(render_feed(conn, profile_id="demo-fresher", now=NOW))
        finance = readable(render_feed(conn, profile_id="demo-two-years", now=NOW))
        assert "Finance Assistant" in finance
        assert fresher.split("Software")[0] != finance.split("Software")[0]

    def test_scam_flagged_postings_never_appear(self, conn):
        page = readable(render_feed(conn, now=NOW))
        assert "Urgent Data Entry Clerks" not in page

    def test_stale_jobs_are_shown_and_labelled(self, conn):
        graph.apply_liveness(conn, now=NOW + timedelta(days=5))
        page = readable(render_feed(conn, now=NOW + timedelta(days=5)))
        assert "not re-checked recently" in page

    def test_dismissed_jobs_leave_the_feed(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE title = 'Software Support Analyst'").fetchone()["id"]
        tracking.record(conn, "demo-fresher", job_id, "dismissed")
        page = render_feed(conn, profile_id="demo-fresher", now=NOW)
        # The id, not the title: another job can legitimately share a prefix
        # ("… Analyst II"), and the promise is that *this* advert leaves.
        assert job_id not in page

    def test_applied_jobs_are_marked_not_hidden(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE title = 'Software Support Analyst'").fetchone()["id"]
        tracking.record(conn, "demo-fresher", job_id, "applied")
        page = readable(render_feed(conn, profile_id="demo-fresher", now=NOW))
        assert "Software Support Analyst" in page
        assert "you applied" in page

    def test_html_is_escaped(self, conn):
        from kazikasi.models import JobCandidate

        graph.upsert_candidate(
            conn,
            JobCandidate(
                source_id="brightermonday",
                source_job_id="X1",
                source_url="https://example.co.ke/x",
                title="<script>alert('x')</script> Clerk",
                employer_name="A & B Ltd",
                county="Nairobi",
                sub_county="Westlands",
                description_md="text",
                deadline=(datetime.now(timezone.utc) + timedelta(days=5)).date(),
                first_seen_at=datetime.now(timezone.utc),
            ),
        )
        page = render_feed(conn, profile_id="demo-fresher", now=datetime.now(timezone.utc))
        assert "<script>alert" not in page
        assert "&lt;script&gt;" in page
        assert "A &amp; B Ltd" in page


class TestJobPage:
    def _job_id(self, conn, title):
        return conn.execute("SELECT id FROM jobs WHERE title = ?", (title,)).fetchone()["id"]

    def test_shows_evidence_sources_and_history(self, conn):
        job_id = self._job_id(conn, "Software Support Analyst")
        page = readable(render_job(conn, job_id, profile_id="demo-fresher", now=NOW))
        assert "Fresh graduates are encouraged to apply." in page
        assert "Where this came from" in page
        assert "matched by" in page

    def test_shows_why_it_was_in_the_feed(self, conn):
        job_id = self._job_id(conn, "Software Support Analyst")
        page = readable(render_job(conn, job_id, profile_id="demo-fresher", now=NOW))
        assert "Why this is in your feed" in page

    def test_shows_why_it_was_excluded_for_another_profile(self, conn):
        job_id = self._job_id(conn, "Senior ICT Officer") if conn.execute(
            "SELECT 1 FROM jobs WHERE title = 'Senior ICT Officer'"
        ).fetchone() else self._job_id(conn, "Finance Officer")
        page = readable(render_job(conn, job_id, profile_id="demo-fresher", now=NOW))
        assert "Why this is not in your feed" in page
        assert "3+ years" in page or "unstated role" in page

    def test_unknown_job_returns_none(self, conn):
        assert render_job(conn, "nope", now=NOW) is None


class TestFreshnessPage:
    def test_reports_every_registered_source(self, conn):
        page = readable(render_slo(conn, now=NOW))
        assert "Freshness" in page
        assert "BrighterMonday" in page
        assert "Public Service Commission" in page

    def test_says_plainly_when_a_source_has_never_been_fetched(self, conn):
        page = readable(render_slo(conn, now=NOW))
        assert "never fetched" in page

    def test_says_plainly_when_a_source_is_late(self, conn):
        page = readable(render_slo(conn, now=NOW + timedelta(hours=6)))
        assert "late" in page or "stale" in page


class TestDigestPage:
    def test_the_page_shows_the_message_exactly_as_it_would_arrive(self, conn):
        page = render_digest(conn, now=NOW, demo=True)
        text = readable(page)
        assert "WhatsApp digest" in text
        assert "Kazi-Kasi" in text and "jobs for you today" in text
        assert "Reply STOP" in text

    def test_the_preview_is_the_same_body_the_transport_would_send(self, conn):
        from kazikasi import digest as digest_module

        digest = outbox.compose(conn, "demo-fresher", now=NOW)
        expected = digest_module.render_digest(digest, link_base="https://kazikasi.app")
        page = render_digest(conn, profile_id="demo-fresher", now=NOW)
        first_card = expected.splitlines()[2]
        assert first_card in page          # inside the <pre>, escaped only

    def test_an_unsubscribed_profile_is_offered_an_opt_in_not_a_digest(self, conn):
        text = readable(render_digest(conn, now=NOW))
        assert "No number on file" in text
        assert "Start the daily digest" in text

    def test_a_subscriber_sees_the_consent_record_and_a_way_out(self, conn):
        outbox.subscribe(conn, "demo-fresher", "0712345678", now=NOW)
        text = readable(render_digest(conn, profile_id="demo-fresher", now=NOW))
        assert "+2547•••5678" in text
        assert "Stop these messages" in text
        assert "12345678" not in text

    def test_the_sms_fallback_is_shown_because_it_is_part_of_the_promise(self, conn):
        text = readable(render_digest(conn, now=NOW))
        assert "If WhatsApp fails" in text
        assert "Kazi-Kasi: 5 new jobs" in text

    def test_what_was_left_out_is_stated(self, conn):
        digest = outbox.compose(conn, "demo-fresher", now=NOW)
        target = digest.items[0].job_id
        tracking.record(conn, "demo-fresher", target, "applied")
        text = readable(render_digest(conn, profile_id="demo-fresher", now=NOW))
        assert "you already applied" in text
        assert target not in text

    def test_an_empty_day_is_silence_not_an_apology(self, conn):
        for job in conn.execute("SELECT id FROM jobs").fetchall():
            tracking.record(conn, "demo-fresher", job["id"], "dismissed")
        page = render_digest(conn, profile_id="demo-fresher", now=NOW)
        assert "Nothing to send today" in readable(page)
        # And no message body was rendered: the person gets silence, not a push.
        assert "Kazi-Kasi — 0 jobs" not in page
        assert 'class="msg sms"></pre>' in page.replace(" ", " ").replace('class="msg sms">\n', 'class="msg sms">')

    def test_the_delivery_log_shows_what_happened(self, conn):
        outbox.subscribe(conn, "demo-fresher", "0712345678", now=NOW)
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        text = readable(render_digest(conn, profile_id="demo-fresher", now=NOW))
        assert "Delivery log" in text
        assert "queued" in text

    def test_the_page_opens_on_someone_who_actually_gets_a_digest(self, conn):
        outbox.subscribe(conn, "demo-two-years", "0712345678", now=NOW)
        text = readable(render_digest(conn, now=NOW))
        assert "Otieno" in text
        assert "Stop these messages" in text

    def test_a_bad_number_is_reported_rather_than_silently_dropped(self, conn):
        text = readable(render_digest(conn, now=NOW, error="not a Kenyan mobile number: '0712'"))
        assert "not a Kenyan mobile number" in text


class TestReviewPage:
    def test_lists_the_ambiguous_pairs(self, conn):
        page = readable(render_review(conn, now=NOW))
        assert "Review queue" in page
        assert "Software Support Analyst II" in page
        assert "similarity" in page


class TestHttpServer:
    @pytest.fixture
    def server(self, tmp_path):
        path = tmp_path / "kazi.db"
        connection = db.connect(path)
        load_corpus(connection, now=datetime.now(timezone.utc))
        seed_profiles(connection)
        connection.close()

        httpd = make_server(path, host="127.0.0.1", port=0, demo=True)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}"
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def _get(self, url):
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, response.read().decode()

    def test_healthz(self, server):
        status, body = self._get(f"{server}/healthz")
        assert (status, body.strip()) == (200, "ok")

    def test_feed_page(self, server):
        status, body = self._get(f"{server}/")
        assert status == 200
        assert "Kazi-Kasi" in body
        assert "Synthetic demo data" in body

    def test_feed_for_a_named_profile(self, server):
        status, body = self._get(f"{server}/?profile=demo-two-years")
        assert status == 200
        assert "Finance Assistant" in body

    def test_api_returns_the_ranking_and_the_reasons(self, server):
        status, body = self._get(f"{server}/api/jobs")
        payload = json.loads(body)
        assert status == 200
        assert payload["profile"]["id"]
        assert payload["matches"]
        first = payload["matches"][0]
        assert {"job_id", "score", "reasons", "eligible"} <= set(first)
        assert isinstance(first["reasons"], list) and first["reasons"]

    def test_slo_page(self, server):
        status, body = self._get(f"{server}/slo")
        assert status == 200
        assert "Freshness" in body

    def test_apply_link_records_the_click_and_redirects_out(self, server):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None

        _, feed = self._get(f"{server}/api/jobs")
        job_id = json.loads(feed)["matches"][0]["job_id"]
        opener = urllib.request.build_opener(NoRedirect)
        with pytest.raises(urllib.error.HTTPError) as error:
            opener.open(f"{server}/go?profile=demo-fresher&job={job_id}", timeout=5)
        assert error.value.code == 303
        assert error.value.headers["Location"].startswith("http")

    def test_dismissal_changes_the_next_page(self, server):
        _, feed = self._get(f"{server}/api/jobs?profile=demo-fresher")
        job_id = json.loads(feed)["matches"][0]["job_id"]
        data = urllib.parse.urlencode(
            {"profile": "demo-fresher", "job": job_id, "kind": "dismissed"}
        ).encode()
        request = urllib.request.Request(
            f"{server}/action", data=data, method="POST",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert json.loads(response.read())["ok"] is True

        _, feed_after = self._get(f"{server}/api/jobs?profile=demo-fresher")
        ids = [match["job_id"] for match in json.loads(feed_after)["matches"]]
        assert job_id not in ids

    def test_digest_page(self, server):
        status, body = self._get(f"{server}/digest")
        assert status == 200
        assert "WhatsApp digest" in body
        assert "Reply STOP" in body

    def test_subscribing_over_http_records_consent_and_masks_the_number(self, server):
        data = urllib.parse.urlencode({"profile": "demo-fresher", "msisdn": "0712 345 678"}).encode()
        request = urllib.request.Request(f"{server}/digest/subscribe", data=data, method="POST")
        with urllib.request.urlopen(request, timeout=5) as response:
            page = response.read().decode()
            assert response.status == 200
        assert "+2547•••5678" in page
        assert "Stop these messages" in page

    def test_a_bad_number_comes_back_as_an_error_not_a_subscription(self, server):
        data = urllib.parse.urlencode({"profile": "demo-fresher", "msisdn": "0712"}).encode()
        request = urllib.request.Request(f"{server}/digest/subscribe", data=data, method="POST")
        with urllib.request.urlopen(request, timeout=5) as response:
            page = response.read().decode()
        assert "not a Kenyan mobile number" in page
        assert "No number on file" in page

    def test_opting_out_over_http_stops_the_digest(self, server):
        data = urllib.parse.urlencode({"profile": "demo-fresher", "msisdn": "0712345678"}).encode()
        urllib.request.urlopen(
            urllib.request.Request(f"{server}/digest/subscribe", data=data, method="POST"), timeout=5
        ).close()
        data = urllib.parse.urlencode({"profile": "demo-fresher"}).encode()
        with urllib.request.urlopen(
            urllib.request.Request(f"{server}/digest/unsubscribe", data=data, method="POST"), timeout=5
        ) as response:
            page = response.read().decode()
        assert "Opted out on" in page
        assert "Start the daily digest" in page

    def test_unknown_path_is_404(self, server):
        with pytest.raises(urllib.error.HTTPError) as error:
            self._get(f"{server}/nothing")
        assert error.value.code == 404

    def test_unknown_job_is_404(self, server):
        with pytest.raises(urllib.error.HTTPError) as error:
            self._get(f"{server}/job/does-not-exist")
        assert error.value.code == 404


@pytest.fixture
def live_server(tmp_path):
    path = tmp_path / "kazi.db"
    connection = db.connect(path)
    load_corpus(connection, now=NOW)
    seed_profiles(connection)
    connection.close()

    httpd = make_server(path, host="127.0.0.1", port=0, demo=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


class TestWebhooksOverHttp:
    """The inbound routes, over a real socket, with real signature checks."""

    def _get(self, url):
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, response.read().decode()

    def _post(self, url, payload, headers=None):
        body = json.dumps(payload).encode() if isinstance(payload, dict) else payload
        request = urllib.request.Request(
            url, data=body, method="POST", headers=headers or {"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read() or b"{}")

    def _stop_payload(self, sender="254712345678"):
        return {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.in.9",
                                        "from": sender,
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

    def _subscribe(self, base):
        data = urllib.parse.urlencode({"profile": "demo-fresher", "msisdn": "0712 345 678"}).encode()
        urllib.request.urlopen(
            urllib.request.Request(f"{base}/digest/subscribe", data=data, method="POST"), timeout=5
        ).close()

    def test_the_verification_handshake(self, live_server, monkeypatch):
        monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-me")
        status, _ = self._get(
            f"{live_server}/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=verify-me&hub.challenge=1234"
        )
        assert status == 200

    def test_a_wrong_verify_token_is_403(self, live_server, monkeypatch):
        monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-me")
        with pytest.raises(urllib.error.HTTPError) as error:
            self._get(f"{live_server}/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=nope&hub.challenge=1")
        assert error.value.code == 403

    def test_an_unsigned_webhook_is_refused_when_a_secret_is_set(self, live_server, monkeypatch):
        monkeypatch.setenv("WHATSAPP_APP_SECRET", "app-secret")
        with pytest.raises(urllib.error.HTTPError) as error:
            self._post(f"{live_server}/webhooks/whatsapp", self._stop_payload())
        assert error.value.code == 403

    def test_a_signed_stop_opts_out(self, live_server, monkeypatch):
        from kazikasi import webhooks

        monkeypatch.setenv("WHATSAPP_APP_SECRET", "app-secret")
        self._subscribe(live_server)
        body = json.dumps(self._stop_payload()).encode()
        signature = webhooks.sign(body, "app-secret")
        status, payload = self._post(
            f"{live_server}/webhooks/whatsapp",
            body,
            {"Content-Type": "application/json", webhooks.SIGNATURE_HEADER: signature},
        )
        assert status == 200
        assert payload["actions"] == {"unsubscribed": 1}

        _, page = self._get(f"{live_server}/digest?profile=demo-fresher")
        assert "Opted out on" in page

    def test_a_sms_stop_without_the_configured_token_is_refused(self, live_server, monkeypatch):
        monkeypatch.setenv("AT_WEBHOOK_TOKEN", "sms-token")
        with pytest.raises(urllib.error.HTTPError) as error:
            self._post(f"{live_server}/webhooks/sms?token=wrong", b"from=%2B254712345678&text=STOP")
        assert error.value.code == 403

    def test_a_sms_stop_with_the_token_opts_out(self, live_server, monkeypatch):
        monkeypatch.setenv("AT_WEBHOOK_TOKEN", "sms-token")
        self._subscribe(live_server)
        status, payload = self._post(
            f"{live_server}/webhooks/sms?token=sms-token",
            b"from=%2B254712345678&text=STOP&id=AT1",
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert status == 200
        assert payload["actions"] == {"unsubscribed": 1}

    def test_a_webhook_is_refused_outright_when_unconfigured_and_not_a_demo(self, tmp_path, monkeypatch):
        monkeypatch.delenv("WHATSAPP_APP_SECRET", raising=False)
        path = tmp_path / "kazi.db"
        connection = db.connect(path)
        load_corpus(connection, now=NOW)
        seed_profiles(connection)
        connection.close()

        httpd = make_server(path, host="127.0.0.1", port=0, demo=False)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            body = json.dumps(self._stop_payload()).encode()
            with pytest.raises(urllib.error.HTTPError) as error:
                self._post(f"{base}/webhooks/whatsapp", body)
            assert error.value.code == 503
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_responses_are_not_sniffed(self, live_server):
        with urllib.request.urlopen(f"{live_server}/digest", timeout=5) as response:
            assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_the_consent_form_is_rate_limited(self, live_server):
        data = urllib.parse.urlencode({"profile": "demo-fresher", "msisdn": "0712345678"}).encode()
        codes = []
        for _ in range(same_origin_limit := 40):
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(f"{live_server}/digest/subscribe", data=data, method="POST"),
                    timeout=5,
                ) as response:
                    codes.append(response.status)
            except urllib.error.HTTPError as error:
                codes.append(error.code)
        assert same_origin_limit == 40
        assert 429 in codes
