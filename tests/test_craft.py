"""The premium layer that is not decoration.

Three things are tested here, because they are the three that can be quietly
wrong in production:

* **The ledger** — the diff the product promises ("3 new since Tuesday"). It is
  derived from a signed cookie, so an unreadable or forged value must degrade to
  "first look", never to an invented number.
* **The structured data** — one `JobPosting` per job page, honest about
  `directApply`, and absent rather than thin when we cannot describe the role.
* **The tone** — no manufactured urgency. This is a brand assertion, so it is a
  test: a future sprint cannot slip "hurry" onto a card.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import serve
from kazikasi.serve import handle, read_seen, seen_cookie

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    connection = serve.demo_connection(now=NOW)
    yield connection
    connection.close()


def ledger_line(html: str) -> str:
    match = re.search(r'<p class="ledger">(.*?)</p>', html, re.S)
    assert match, "the feed has no ledger line"
    return re.sub(r"<[^>]+>", "", match.group(1))


class TestTheLedger:
    def test_a_first_visit_says_so_and_plants_the_cookie(self, conn):
        response = handle(conn, "GET", "/", {}, now=NOW)
        assert "First look" in ledger_line(response.body)
        cookie = response.headers["Set-Cookie"]
        assert cookie.startswith("kazi_seen=")
        assert "HttpOnly" in cookie and "SameSite=Lax" in cookie

    def test_the_next_visit_can_say_nothing_changed(self, conn):
        first = handle(conn, "GET", "/", {}, now=NOW)
        cookie = first.headers["Set-Cookie"].split(";")[0]
        second = handle(conn, "GET", "/", {}, headers={"cookie": cookie}, now=NOW)
        line = ledger_line(second.body)
        assert "Nothing new" in line
        assert "earlier today" in line

    def test_a_month_away_counts_what_arrived_meanwhile(self, conn):
        stale = seen_cookie(NOW - timedelta(days=30)).split(";")[0]
        response = handle(conn, "GET", "/", {}, headers={"cookie": stale}, now=NOW)
        line = ledger_line(response.body)
        match = re.search(r"(\d+) new", line)
        assert match, line
        assert int(match.group(1)) > 0
        assert "30 days" not in line  # the copy dates it, it does not editorialise

    def test_a_job_first_seen_in_the_same_second_is_not_new(self):
        """The cookie only stores whole seconds; sub-second arrivals must not spawn "18 new"."""
        seen_at = NOW.replace(microsecond=900_000)
        connection = serve.demo_connection(now=NOW.replace(microsecond=850_000))
        try:
            response = handle(
                connection,
                "GET",
                "/",
                {},
                headers={"cookie": seen_cookie(seen_at).split(";")[0]},
                now=seen_at,
            )
        finally:
            connection.close()
        assert "Nothing new" in ledger_line(response.body)

    def test_a_forged_cookie_is_ignored_not_believed(self, conn):
        forged = "kazi_seen=2020-01-01T00:00:00+00:00.deadbeefdeadbeefdead"
        response = handle(conn, "GET", "/", {}, headers={"cookie": forged}, now=NOW)
        assert "First look" in ledger_line(response.body)

    def test_a_garbage_cookie_is_ignored(self, conn):
        for value in ("kazi_seen=", "kazi_seen", "kazi_seen=.", "other=1"):
            response = handle(conn, "GET", "/", {}, headers={"cookie": value}, now=NOW)
            assert "First look" in ledger_line(response.body)

    def test_the_reader_round_trips_and_verifies(self):
        cookie = seen_cookie(NOW).split(";")[0]
        assert read_seen({"Cookie": cookie}) == NOW
        assert read_seen({"COOKIE": cookie}) == NOW
        assert read_seen({"cookie": cookie.replace("kazi_seen=", "kazi_seen=9")}) is None
        assert read_seen({}) is None

    def test_the_timestamp_is_the_only_thing_stored(self):
        cookie = seen_cookie(NOW)
        assert "profile" not in cookie and "job" not in cookie
        assert cookie.count("=") >= 1


class TestStructuredData:
    def _page(self, conn):
        job_id = conn.execute("SELECT id FROM jobs LIMIT 1").fetchone()["id"]
        response = handle(conn, "GET", f"/job/{job_id}", {}, now=NOW)
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', response.body, re.S
        )
        return response, blocks

    def test_a_job_page_carries_exactly_one_jobposting(self, conn):
        _, blocks = self._page(conn)
        assert len(blocks) == 1
        payload = json.loads(blocks[0])
        assert payload["@type"] == "JobPosting"
        assert payload["@context"].startswith("https://schema.org")

    def test_it_is_honest_about_where_the_application_happens(self, conn):
        _, blocks = self._page(conn)
        assert json.loads(blocks[0])["directApply"] is False

    def test_the_markup_matches_the_page(self, conn):
        response, blocks = self._page(conn)
        payload = json.loads(blocks[0])
        assert payload["title"] in response.body
        assert payload["description"] != payload["title"]
        assert len(payload["description"]) >= 80

    def test_required_fields_are_present(self, conn):
        _, blocks = self._page(conn)
        payload = json.loads(blocks[0])
        for field in ("title", "description", "datePosted", "hiringOrganization"):
            assert payload.get(field), field
        assert payload["jobLocation"]["address"]["addressCountry"] == "KE"

    def test_nothing_is_emitted_when_we_cannot_describe_the_job(self):
        row = {
            "id": "x", "title": "Records Assistant", "employer_name": "PSC",
            "county": "Nairobi", "sub_county": None, "deadline": None, "pay_min": None,
            "pay_max": None, "pay_period": None, "first_seen_at": "2026-10-01",
            "employment_type": "full_time", "work_mode": "onsite",
        }
        assert serve._job_posting(row, "") == ""
        assert serve._job_posting(row, "Too short") == ""

    def test_pay_is_marked_up_only_when_it_is_stated(self):
        base = {
            "id": "x", "title": "Records Assistant", "employer_name": "PSC",
            "county": "Nairobi", "sub_county": "CBD", "deadline": "2026-11-12",
            "pay_min": 30550.0, "pay_max": 39720.0, "pay_period": "month",
            "first_seen_at": "2026-10-01", "employment_type": "full_time",
            "work_mode": "onsite",
        }
        text = "A role doing records work. " * 5
        payload = json.loads(
            serve._job_posting(base, text).split(">", 1)[1].rsplit("<", 1)[0]
        )
        salary = payload["baseSalary"]
        assert salary["currency"] == "KES"
        assert salary["value"]["unitText"] == "MONTH"
        assert salary["value"]["minValue"] == 30550.0

        no_pay = dict(base, pay_min=None, pay_max=None)
        payload = json.loads(
            serve._job_posting(no_pay, text).split(">", 1)[1].rsplit("<", 1)[0]
        )
        assert "baseSalary" not in payload

    def test_a_closing_script_tag_cannot_escape_the_block(self):
        row = {
            "id": "x", "title": "Role", "employer_name": "</script><b>x",
            "county": "Nairobi", "sub_county": None, "deadline": None,
            "pay_min": None, "pay_max": None, "pay_period": None,
            "first_seen_at": "2026-10-01", "employment_type": "full_time",
            "work_mode": "onsite",
        }
        markup = serve._job_posting(row, "A description long enough to qualify. " * 4)
        assert "</script><b>" not in markup
        assert "<\\/script>" in markup


class TestTheTone:
    URGENCY = ("urgent", "hurry", "act now", "last chance", "only 3 left", "don't miss")

    def test_no_manufactured_urgency_anywhere_on_the_feed(self, conn):
        body = handle(conn, "GET", "/", {}, now=NOW).body.lower()
        for phrase in self.URGENCY:
            assert phrase not in body, phrase

    def test_no_manufactured_urgency_on_a_job_page(self, conn):
        job_id = conn.execute("SELECT id FROM jobs LIMIT 1").fetchone()["id"]
        body = handle(conn, "GET", f"/job/{job_id}", {}, now=NOW).body.lower()
        for phrase in self.URGENCY:
            assert phrase not in body, phrase
