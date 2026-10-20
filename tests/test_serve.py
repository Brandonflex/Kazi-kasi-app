"""The feed surface: ranking, reasons, apply link-out, freshness page, HTTP."""

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import db, graph, tracking
from kazikasi.corpus import load_corpus
from kazikasi.profile import seed_profiles
from kazikasi.serve import make_server, render_feed, render_job, render_review, render_slo

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
        assert "Software Support Analyst" not in readable(render_feed(conn, profile_id="demo-fresher", now=NOW))

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

    def test_unknown_path_is_404(self, server):
        with pytest.raises(urllib.error.HTTPError) as error:
            self._get(f"{server}/nothing")
        assert error.value.code == 404

    def test_unknown_job_is_404(self, server):
        with pytest.raises(urllib.error.HTTPError) as error:
            self._get(f"{server}/job/does-not-exist")
        assert error.value.code == 404
