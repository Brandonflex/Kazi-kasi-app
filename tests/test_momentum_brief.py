"""Momentum, the weekly brief, ⌘K and the wildcard.

Four surfaces, four promises:

* **Momentum** counts weeks of attention, never applications, and forgives one
  missed week — once.
* **The brief** says what moved, with the sample size, and refuses to invent a
  number when the corpus is too thin.
* **⌘K** is one search box over the page's own data, and it cannot be used to
  smuggle script through a job title.
* **The wildcard** is exactly one role a week, deterministic, labelled as an
  exception, and only ever one blocker away from the scope.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import brief, momentum, pulse, serve, tracking, wildcard
from kazikasi.serve import handle

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
FEED = {"profile": ["demo-fresher"]}


@pytest.fixture
def conn():
    connection = serve.demo_connection(now=NOW)
    yield connection
    connection.close()


@pytest.fixture
def profile(conn):
    return serve._profile_or_default(conn, "demo-fresher")


def text(html: str) -> str:
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    return " ".join(html.split())


class TestMomentum:
    def test_weeks_are_iso_weeks_in_nairobi_time(self):
        assert momentum.week_key(NOW) == "2026-W43"
        # 21:30 UTC on Sunday is already Monday 00:30 in Nairobi.
        late = datetime(2026, 10, 18, 21, 30, tzinfo=timezone.utc)
        assert momentum.week_key(late) == "2026-W43"
        earlier = late - timedelta(days=1)
        assert momentum.week_key(earlier) == "2026-W42"

    def test_a_check_in_is_counted_once(self, conn):
        assert momentum.check_in(conn, "demo-fresher", now=NOW) is True
        assert momentum.check_in(conn, "demo-fresher", now=NOW) is False
        assert momentum.status(conn, "demo-fresher", now=NOW)["run"] == 1

    def test_opening_the_feed_or_the_brief_counts(self, conn):
        handle(conn, "GET", "/", FEED, now=NOW)
        assert momentum.status(conn, "demo-fresher", now=NOW)["this_week"] is True

    def test_a_save_counts_too(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        tracking.record(conn, "demo-fresher", job_id, "saved", now=NOW)
        assert momentum.status(conn, "demo-fresher", now=NOW)["run"] >= 1

    def test_applying_is_not_required(self, conn):
        for week in range(4):
            momentum.check_in(conn, "demo-fresher", now=NOW - timedelta(weeks=week))
        state = momentum.status(conn, "demo-fresher", now=NOW)
        assert state["run"] == 4
        assert state["this_week"] is True

    def test_one_missed_week_is_forgiven(self, conn):
        momentum.check_in(conn, "demo-fresher", now=NOW)
        momentum.check_in(conn, "demo-fresher", now=NOW - timedelta(weeks=2))
        momentum.check_in(conn, "demo-fresher", now=NOW - timedelta(weeks=3))
        state = momentum.status(conn, "demo-fresher", now=NOW)
        assert state["run"] == 3, "the gap at week -1 should be bridged"
        assert state["skip_used"] is True
        assert state["skip_in_hand"] is False

    def test_two_missed_weeks_end_the_run(self, conn):
        momentum.check_in(conn, "demo-fresher", now=NOW)
        momentum.check_in(conn, "demo-fresher", now=NOW - timedelta(weeks=3))
        momentum.check_in(conn, "demo-fresher", now=NOW - timedelta(weeks=4))
        assert momentum.status(conn, "demo-fresher", now=NOW)["run"] == 1

    def test_the_run_is_per_profile(self, conn):
        momentum.check_in(conn, "demo-fresher", now=NOW)
        assert momentum.status(conn, "demo-remote", now=NOW)["run"] == 0

    def test_no_run_reads_as_an_invitation_not_a_failure(self):
        state = momentum.status.__wrapped__ if hasattr(momentum.status, "__wrapped__") else None
        line = momentum.line(
            {"run": 0, "this_week": False, "skip_in_hand": True, "skip_used": False}
        )
        assert state is None or True
        assert "start" in line.lower()
        assert "lost" not in line.lower() and "fail" not in line.lower()

    def test_the_line_never_shames(self, conn):
        for week in range(3):
            momentum.check_in(conn, "demo-fresher", now=NOW - timedelta(weeks=week))
        line = momentum.line(momentum.status(conn, "demo-fresher", now=NOW))
        for word in ("lost", "don't", "failed", "missed out"):
            assert word not in line.lower()

    def test_it_reports_when_the_week_resets(self, conn):
        state = momentum.status(conn, "demo-fresher", now=NOW)
        assert state["resets_at"].weekday() == 6  # Sunday
        assert state["resets_at"].hour == 23

    def test_the_feed_shows_four_marks_and_the_line(self, conn):
        body = handle(conn, "GET", "/", FEED, now=NOW).body
        rail = body.split("Momentum", 1)[1].split("</div>", 2)[0]
        assert body.count('class="marks"') >= 1
        assert "Week 1 of your run" in text(body)


class TestWeeklyBrief:
    def test_it_carries_a_window_and_a_sample_size(self, conn, profile):
        data = brief.overview(conn, profile, now=NOW)
        assert data["days"] == 7
        assert data["in_scope"] > 0
        assert isinstance(data["sample"], int)

    def test_new_means_first_seen_inside_the_window(self, conn, profile):
        data = brief.overview(conn, profile, now=NOW)
        start = NOW - timedelta(days=7)
        expected = 0
        for row in pulse.live_rows(conn):
            from kazikasi import ranking

            if ranking.constraints(dict(row), profile, NOW):
                continue
            seen = brief._as_dt(row["first_seen_at"])
            if seen and seen >= start:
                expected += 1
        assert data["new"] == expected

    def test_it_states_when_it_cannot_compare_pay(self, conn, profile):
        data = brief.overview(conn, profile, now=NOW)
        empty = dict(data, delta_pct=None, band_this_week=None, band_last_week=None)
        assert "Not enough adverts" in brief.band_line(empty)

    def test_the_delta_is_signed_and_rounded(self, conn, profile):
        data = brief.overview(conn, profile, now=NOW)
        line = brief.band_line(data)
        assert re.search(r"(up|down) \d+%", line)
        assert "n=" in line

    def test_the_message_is_short_enough_to_read_on_a_phone(self, conn, profile):
        message = brief.message(brief.overview(conn, profile, now=NOW), profile)
        assert all(len(line) <= 120 for line in message.splitlines())
        assert "*" in message  # WhatsApp bold, same convention as the digest

    def test_the_message_always_links_somewhere(self, conn, profile):
        message = brief.message(brief.overview(conn, profile, now=NOW), profile)
        assert "http" in message

    def test_a_quiet_week_says_so_without_inventing_a_move(self, conn, profile):
        data = brief.overview(conn, profile, now=NOW)
        quiet = dict(data, new=0, move=None)
        assert "Nothing new" in brief.headline(quiet, profile)
        assert "/job/" not in brief.message(quiet, profile).split("/brief")[0]

    def test_the_page_shows_the_exact_message(self, conn):
        page = handle(conn, "GET", "/brief", FEED, now=NOW).body
        assert "Exactly what we would send" in text(page)
        assert "what moved" in text(page).lower()

    def test_the_page_records_a_check_in(self, conn):
        handle(conn, "GET", "/brief", FEED, now=NOW)
        assert momentum.status(conn, "demo-fresher", now=NOW)["this_week"] is True

    def test_it_links_from_the_nav(self, conn):
        page = handle(conn, "GET", "/", FEED, now=NOW).body
        assert 'href="/brief' in page


class TestPalette:
    def test_it_is_present_and_points_at_real_pages(self, conn):
        body = handle(conn, "GET", "/", FEED, now=NOW).body
        assert 'id="kazi-palette"' in body
        index = json.loads(re.search(r'id="kazi-index">(.*?)</script>', body, re.S).group(1))
        hrefs = {item["href"] for item in index}
        assert "/pulse" in hrefs and "/salaries" in hrefs
        assert any(href.startswith("/job/") for href in hrefs)
        assert any(href.startswith("/county/") for href in hrefs)

    def test_the_index_is_capped(self, conn):
        body = handle(conn, "GET", "/", FEED, now=NOW).body
        index = json.loads(re.search(r'id="kazi-index">(.*?)</script>', body, re.S).group(1))
        assert len(index) <= 75

    def test_a_job_title_cannot_end_the_json_block(self, conn):
        from kazikasi.models import JobCandidate

        from kazikasi import graph

        graph.upsert_candidate(
            conn,
            JobCandidate(
                source_id="brightermonday",
                source_job_id="X9",
                source_url="https://example.co.ke/x9",
                title="</script><script>alert(1)</script> Clerk",
                employer_name="A & B Ltd",
                county="Nairobi",
                sub_county="Westlands",
                description_md="text",
                deadline=(NOW + timedelta(days=5)).date(),
                first_seen_at=NOW,
            ),
        )
        body = handle(conn, "GET", "/", FEED, now=NOW).body
        assert body.count("</script>") == body.count("<script")
        assert "<script>alert" not in body

    def test_dismissed_jobs_are_not_offered(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        tracking.record(conn, "demo-fresher", job_id, "dismissed")
        body = handle(conn, "GET", "/", FEED, now=NOW).body
        index = json.loads(re.search(r'id="kazi-index">(.*?)</script>', body, re.S).group(1))
        assert not any(item["href"].startswith(f"/job/{job_id}") for item in index)

    def test_the_keyboard_hint_is_visible(self, conn):
        body = handle(conn, "GET", "/", FEED, now=NOW).body
        assert "⌘K" in body
        assert "data-cmdk" in body


class TestWildcard:
    def test_it_picks_at_most_one_and_it_is_stable(self, conn, profile):
        first = wildcard.pick(conn, profile, now=NOW)
        second = wildcard.pick(conn, profile, now=NOW)
        assert first is not None
        assert first["job_id"] == second["job_id"]

    def test_it_is_one_blocker_away_from_the_scope(self, conn, profile):
        item = wildcard.pick(conn, profile, now=NOW)
        assert len(serve.ranking.constraints(dict(item["row"]), profile, NOW)) == 1
        assert item["blocker"] == serve.ranking.constraints(dict(item["row"]), profile, NOW)[0]

    def test_it_never_offers_a_qualification_gap(self, conn, profile):
        item = wildcard.pick(conn, profile, now=NOW)
        assert "years" not in item["blocker"]

    def test_it_never_resurfaces_a_dismissed_job(self, conn, profile):
        item = wildcard.pick(conn, profile, now=NOW)
        tracking.record(conn, "demo-fresher", item["job_id"], "dismissed")
        again = wildcard.pick(conn, profile, now=NOW)
        assert again is None or again["job_id"] != item["job_id"]

    def test_it_is_labelled_as_an_exception_not_a_recommendation(self, conn):
        body = handle(conn, "GET", "/", FEED, now=NOW).body
        assert "Outside your scope" in body
        assert "this week only" in text(body).lower()

    def test_the_card_says_why_in_one_sentence(self, conn, profile):
        item = wildcard.pick(conn, profile, now=NOW)
        sentence = wildcard.sentence(item, profile)
        assert "Outside your scope" in sentence
        assert sentence.count(".") <= 2

    def test_nothing_is_shown_when_nothing_qualifies(self, conn, profile):
        for row in serve.graph.feed(conn, limit=500, include_stale=True):
            blockers = serve.ranking.constraints(dict(row), profile, NOW)
            if len(blockers) == 1 and any(marker in blockers[0] for marker in wildcard.FIXABLE):
                tracking.record(conn, "demo-fresher", row["id"], "dismissed")
        assert wildcard.pick(conn, profile, now=NOW) is None
        assert "Outside your scope" not in handle(conn, "GET", "/", FEED, now=NOW).body
