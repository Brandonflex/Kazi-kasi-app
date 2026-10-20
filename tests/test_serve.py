"""The read-only feed: rendering, escaping, and the HTTP surface."""

import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone

import pytest

from kazikasi import db, graph
from kazikasi.corpus import load_corpus
from kazikasi.serve import make_server, render_feed, render_job, render_review

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "kazi.db")
    load_corpus(connection, now=NOW)
    yield connection
    connection.close()


class TestRenderFeed:
    def test_feed_shows_live_jobs_and_their_provenance(self, conn):
        page = render_feed(conn, now=NOW, demo=True)
        assert "Software Support Analyst" in page
        assert "checked today" in page
        assert "on 2 sources" in page
        assert "Synthetic demo data" in page

    def test_feed_labels_eligibility_in_plain_words(self, conn):
        page = render_feed(conn, now=NOW)
        assert "Open to freshers" in page
        assert "1–2 years" in page or "3+ years" in page

    def test_feed_hides_scam_flagged_postings(self, conn):
        page = render_feed(conn, now=NOW, include_stale=True)
        assert "Urgent Data Entry Clerks" not in page

    def test_feed_shows_stale_marker_when_asked(self, conn):
        graph.apply_liveness(conn, now=NOW.replace(day=25))
        page = render_feed(conn, now=NOW.replace(day=25), include_stale=True)
        assert "not re-checked recently" in page

    def test_county_filter(self, conn):
        page = render_feed(conn, county="Kiambu", now=NOW)
        assert "Records Clerk" in page
        assert "Marketing Intern" not in page

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
                description_md="text",
                first_seen_at=datetime.now(timezone.utc),
            ),
        )
        page = render_feed(conn, now=datetime.now(timezone.utc))
        assert "<script>alert" not in page
        assert "&lt;script&gt;" in page
        assert "A &amp; B Ltd" in page


class TestRenderJob:
    def _job_id(self, conn, title):
        return conn.execute("SELECT id FROM jobs WHERE title = ?", (title,)).fetchone()["id"]

    def test_job_page_shows_evidence_and_sources(self, conn):
        job_id = self._job_id(conn, "Software Support Analyst")
        page = render_job(conn, job_id, now=NOW)
        assert "Fresh graduates are encouraged to apply." in page
        assert "Where this came from" in page
        assert "matched by" in page
        assert "checked" in page

    def test_job_page_shows_history(self, conn):
        job_id = self._job_id(conn, "Clerical Officer")
        page = render_job(conn, job_id, now=NOW)
        assert "source added" in page
        assert "opened" in page

    def test_unknown_job_returns_none(self, conn):
        assert render_job(conn, "nope", now=NOW) is None

    def test_review_page_lists_pairs(self, conn):
        page = render_review(conn, now=NOW)
        assert "Software Support Analyst II" in page
        assert "similarity" in page


class TestHttpServer:
    @pytest.fixture
    def server(self, tmp_path):
        path = tmp_path / "kazi.db"
        connection = db.connect(path)
        load_corpus(connection, now=datetime.now(timezone.utc))
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

    def test_api_returns_json(self, server):
        status, body = self._get(f"{server}/api/jobs")
        payload = json.loads(body)
        assert status == 200
        assert isinstance(payload, list) and payload
        assert {"id", "title", "deadline", "source_count"} <= set(payload[0])

    def test_unknown_path_is_404(self, server):
        with pytest.raises(urllib.error.HTTPError) as error:
            self._get(f"{server}/nothing")
        assert error.value.code == 404

    def test_unknown_job_is_404(self, server):
        with pytest.raises(urllib.error.HTTPError) as error:
            self._get(f"{server}/job/does-not-exist")
        assert error.value.code == 404
