"""The public market pages: counted, dated, and impossible to inflate.

A number on a public page is a promise, so these tests are mostly about what the
pages refuse to say: flagged adverts do not move a statistic, a band never
appears without its sample size, and a county we have never seen is a 404 rather
than an empty page with a chart on it.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import db, graph, pulse, serve
from kazikasi.corpus import load_corpus
from kazikasi.profile import seed_profiles
from kazikasi.serve import handle

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    connection = serve.demo_connection(now=NOW)
    yield connection
    connection.close()


def text(html: str) -> str:
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    return " ".join(html.split())


class TestNumbers:
    def test_live_is_open_unflagged_only(self, conn):
        expected = conn.execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE status IN ('open','needs_review')"
        ).fetchone()["c"]
        data = pulse.overview(conn, now=NOW)
        flagged = conn.execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE status IN ('open','needs_review') "
            "AND scam_flags != '[]'"
        ).fetchone()["c"]
        assert data["live"] == expected - flagged

    def test_a_flagged_advert_never_moves_a_statistic(self, conn):
        row = conn.execute(
            "SELECT id, scam_flags FROM jobs WHERE status = 'open' AND scam_flags = '[]' LIMIT 1"
        ).fetchone()
        before = pulse.overview(conn, now=NOW)["live"]
        conn.execute("UPDATE jobs SET scam_flags = ? WHERE id = ?", (json.dumps(["fee_requested"]), row["id"]))
        conn.commit()
        assert pulse.overview(conn, now=NOW)["live"] == before - 1

    def test_new_counts_the_window_not_the_corpus(self, conn):
        data = pulse.overview(conn, now=NOW)
        fresh = sum(
            1
            for row in pulse.live_rows(conn)
            if (pulse._as_dt(row["first_seen_at"]) or NOW) >= NOW - timedelta(days=7)
        )
        assert data["new"] == fresh
        assert data["new"] < data["live"], "the demo corpus should look accumulated"

    def test_closing_ignores_deadlines_that_have_passed(self, conn):
        row = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()
        conn.execute("UPDATE jobs SET deadline = ? WHERE id = ?", ("2026-10-01", row["id"]))
        conn.commit()
        closing = conn.execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE status IN ('open','needs_review') "
            "AND deadline BETWEEN '2026-10-20' AND '2026-10-27' AND scam_flags = '[]'"
        ).fetchone()["c"]
        assert pulse.overview(conn, now=NOW)["closing"] == closing

    def test_the_band_ignores_pay_that_is_not_monthly(self, conn):
        rows = [
            {"pay_min": 30_000, "pay_period": "month"},
            {"pay_min": 50_000, "pay_period": "month"},
            {"pay_min": 900_000, "pay_period": "year"},
            {"pay_min": None, "pay_period": "month"},
        ]
        assert pulse.monthly_pay(rows) == [30_000, 50_000]

    def test_one_advert_is_a_band_of_one_and_says_so(self):
        result = pulse.band([42_000])
        assert result == {"n": 1, "p25": 42_000, "median": 42_000, "p75": 42_000}
        assert pulse.band([]) is None


class TestPulsePage:
    def test_it_names_its_window_and_its_update_time(self, conn):
        page = text(handle(conn, "GET", "/pulse", {}, now=NOW).body)
        assert "Counted" in page or "counted" in page
        assert "last 7 days" in page
        assert "EAT" in page

    def test_every_band_carries_its_sample_size(self, conn):
        page = handle(conn, "GET", "/pulse", {}, now=NOW).body
        table = page.split("By county", 1)[1].split("</table>", 1)[0]
        assert "<th>n</th>" in table
        for row in re.findall(r"<tr>(.*?)</tr>", table, re.S)[1:]:
            cells = re.findall(r"<td>(.*?)</td>", row, re.S)
            assert len(cells) == 5
            assert re.fullmatch(r"\d+", cells[4].strip()), "every row needs an n"

    def test_flagged_adverts_are_excluded_and_the_page_says_so(self, conn):
        assert "Flagged adverts are excluded" in text(handle(conn, "GET", "/pulse", {}, now=NOW).body)

    def test_counties_link_to_their_own_page(self, conn):
        body = handle(conn, "GET", "/pulse", {}, now=NOW).body
        assert 'href="/county/nairobi"' in body

    def test_it_works_on_an_empty_corpus(self):
        empty = db.connect(":memory:")
        page = handle(empty, "GET", "/pulse", {}, now=NOW)
        empty.close()
        assert page.status == 200
        assert "0" in text(page.body)


class TestCountyPage:
    def test_a_slug_and_a_name_both_resolve(self, conn):
        for path in ("/county/nairobi", "/county/Nairobi"):
            assert handle(conn, "GET", path, {}, now=NOW).status == 200

    def test_an_unknown_county_is_a_404(self, conn):
        assert handle(conn, "GET", "/county/atlantis", {}, now=NOW).status == 404

    def test_it_lists_only_that_county(self, conn):
        body = handle(conn, "GET", "/county/kiambu", {}, now=NOW).body
        rows = re.findall(r"<tr>(.*?)</tr>", body, re.S)
        assert len(rows) > 1
        titles = [re.findall(r">([^<]+)</a>", row)[0] for row in rows[1:]]
        kiambu = {
            row["title"]
            for row in conn.execute("SELECT title FROM jobs WHERE county = 'Kiambu' AND status = 'open'")
        }
        assert set(titles) <= kiambu

    def test_it_states_where_pay_came_from(self, conn):
        page = text(handle(conn, "GET", "/county/nairobi", {}, now=NOW).body)
        assert "advert" in page


class TestSalariesPage:
    def test_only_counties_with_a_band_are_listed(self, conn):
        body = handle(conn, "GET", "/salaries", {}, now=NOW).body
        listed = set(re.findall(r'href="/county/([a-z-]+)"', body))
        with_band = {
            pulse.slug(item["county"])
            for item in pulse.overview(conn, now=NOW)["counties"]
            if item["band"]
        }
        assert listed <= with_band | {"nairobi", "kiambu", "machakos", "kajiado"}

    def test_it_refuses_to_estimate(self, conn):
        page = text(handle(conn, "GET", "/salaries", {}, now=NOW).body)
        assert "Not an estimate" in page or "not an estimate" in page


class TestCrawlability:
    def test_the_sitemap_lists_live_jobs_and_their_dates(self, conn):
        body = handle(conn, "GET", "/sitemap.xml", {}, now=NOW).body
        assert body.startswith("<?xml")
        assert "<urlset" in body
        for row in conn.execute("SELECT id FROM jobs WHERE status = 'open' AND scam_flags = '[]' LIMIT 3"):
            assert f"/job/{row['id']}" in body
        assert body.count("<lastmod>") == body.count("<url>")

    def test_the_sitemap_leaves_out_flagged_adverts(self, conn):
        row = conn.execute(
            "SELECT id FROM jobs WHERE status IN ('open','needs_review') AND scam_flags != '[]' LIMIT 1"
        ).fetchone()
        assert row, "the corpus should contain a flagged advert"
        body = handle(conn, "GET", "/sitemap.xml", {}, now=NOW).body
        assert row["id"] not in body

    def test_urls_come_from_the_configured_base(self, conn, monkeypatch):
        monkeypatch.setenv("KAZIKASI_BASE_URL", "https://example.co.ke/")
        body = handle(conn, "GET", "/sitemap.xml", {}, now=NOW).body
        assert "https://example.co.ke/job/" in body
        assert "example.co.ke//" not in body

    def test_robots_keeps_the_ops_pages_out_and_points_at_the_sitemap(self, conn):
        body = handle(conn, "GET", "/robots.txt", {}, now=NOW).body
        for blocked in ("/slo", "/review", "/digest", "/webhooks/"):
            assert f"Disallow: {blocked}" in body
        assert "Sitemap: http" in body and body.rstrip().endswith(".xml")


class TestTheNavigation:
    def test_pulse_is_public_and_the_ops_pages_are_not_in_the_nav(self, conn):
        body = handle(conn, "GET", "/", {}, now=NOW).body
        nav = body.split("<nav>", 1)[1].split("</nav>", 1)[0]
        assert "/pulse" in nav
        assert "/slo" not in nav and "/review" not in nav
        assert 'href="/slo"' in body  # still reachable, from the footer
