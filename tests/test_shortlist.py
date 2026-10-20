"""The shortlist: saved intent, a comparison, and the one reminder it earns.

A save is the only promise a user makes to this product in advance, so it is
also the only reason the product is allowed to interrupt them. These tests pin
the parts that would otherwise rot: the toggle, the cap on comparison, the
48-hour window, the once-only reminder, and the redirect that must not become an
open redirect.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from kazikasi import serve, shortlist, tracking
from kazikasi.serve import handle

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    connection = serve.demo_connection(now=NOW)
    yield connection
    connection.close()


@pytest.fixture
def jobs(conn):
    """Open jobs, soonest first — the ones a person could actually save."""
    return [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM jobs WHERE status = 'open' AND deadline > ? ORDER BY deadline LIMIT 8",
            (NOW.date().isoformat(),),
        )
    ]


def save(conn, job_id, profile="demo-fresher", kind="saved"):
    body = f"profile={profile}&job={job_id}&kind={kind}&next=/shortlist".encode()
    return handle(conn, "POST", "/action", {}, body=body, now=NOW)


def page(conn, path="/shortlist", profile="demo-fresher", now=NOW):
    return handle(conn, "GET", path, {"profile": [profile]}, now=now).body


def close_in(conn, job_id, hours):
    """Move one deadline into the window, the way the real clock would.

    Deadlines are dates, so the useful question is "which day does it end on";
    a deadline is end-of-day in Nairobi (23:59 EAT).
    """
    when = (NOW + timedelta(hours=hours)).date().isoformat()
    conn.execute("UPDATE jobs SET deadline = ?, status = 'open' WHERE id = ?", (when, job_id))
    conn.commit()


class TestSaving:
    def test_an_empty_shortlist_explains_itself(self, conn):
        body = page(conn)
        assert "Nothing saved yet" in body
        assert "one reminder" in body

    def test_saving_a_job_puts_it_on_the_shortlist(self, conn, jobs):
        save(conn, jobs[0])
        body = page(conn)
        assert jobs[0] in body
        assert "Nothing saved yet" not in body

    def test_the_feed_shows_the_saved_state(self, conn):
        feed = page(conn, "/")
        job_id = re.search(r'href="/job/([a-f0-9]+)\?profile=demo-fresher"', feed).group(1)
        save(conn, job_id)
        body = page(conn, "/")
        assert 'class="badge good">saved' in body

    def test_saving_the_same_job_twice_does_not_duplicate_it(self, conn, jobs):
        save(conn, jobs[0])
        save(conn, jobs[0])
        assert len(shortlist.saved_job_ids(conn, "demo-fresher")) == 1
        assert page(conn).count(f'href="/job/{jobs[0]}') == 1

    def test_removing_it_takes_it_off_again(self, conn, jobs):
        save(conn, jobs[0])
        save(conn, jobs[0], kind="unsaved")
        assert shortlist.saved_job_ids(conn, "demo-fresher") == set()
        assert "Nothing saved yet" in page(conn)

    def test_saves_are_per_profile(self, conn, jobs):
        save(conn, jobs[0], profile="demo-fresher")
        assert "Nothing saved yet" in page(conn, profile="demo-remote")
        assert jobs[0] in page(conn, profile="demo-fresher")

    def test_removing_does_not_delete_the_history(self, conn, jobs):
        save(conn, jobs[0])
        save(conn, jobs[0], kind="unsaved")
        kinds = [row["kind"] for row in tracking.events_for_job(conn, jobs[0])]
        assert kinds == ["saved", "unsaved"]


class TestComparison:
    def test_one_job_needs_no_table(self, conn, jobs):
        save(conn, jobs[0])
        assert "Side by side" not in page(conn)

    def test_two_jobs_compare(self, conn, jobs):
        for job_id in jobs[:2]:
            save(conn, job_id)
        body = page(conn)
        assert "Side by side" in body
        for label in ("Pay", "Deadline", "Place", "Eligibility", "Work mode"):
            assert f"<td>{label}</td>" in body

    def test_four_is_the_cap_and_it_says_so(self, conn, jobs):
        for job_id in jobs[:6]:
            save(conn, job_id)
        body = page(conn)
        table = body.split("Side by side", 1)[1].split("</table>", 1)[0]
        assert table.count("<th>") - 1 == 4  # one empty corner cell
        assert "closing soonest" in body

    def test_closed_jobs_sit_below_open_ones(self, conn, jobs):
        between = conn.execute(
            "SELECT id FROM jobs WHERE deadline < ? LIMIT 1", (NOW.date().isoformat(),)
        ).fetchone()
        assert between, "the corpus should contain an expired job"
        save(conn, between["id"])
        save(conn, jobs[0])
        body = page(conn)
        assert body.index(jobs[0]) < body.index(between["id"])
        assert "closed " in body


class TestTheReminder:
    def test_nothing_is_due_five_days_out(self, conn, jobs):
        save(conn, jobs[0])
        close_in(conn, jobs[0], 24 * 5)
        assert shortlist.reminders_due(conn, "demo-fresher", now=NOW) == []

    def test_one_message_inside_the_window(self, conn, jobs):
        save(conn, jobs[0])
        close_in(conn, jobs[0], 36)
        due = shortlist.reminders_due(conn, "demo-fresher", now=NOW)
        assert len(due) == 1
        text = due[0]["text"]
        assert due[0]["job"]["id"] == jobs[0]
        assert "/job/" in text and "shortlist" in text
        assert "*" in text  # WhatsApp bold, the same convention as the digest

    def test_the_page_says_where_the_reminder_will_go(self, conn, jobs):
        """The page does not pretend to send. It shows the text and the path.

        With no subscription on record the honest answer is "this needs WhatsApp",
        not a button that marks a message as sent when nothing was sent.
        """
        save(conn, jobs[0])
        close_in(conn, jobs[0], 36)
        body = page(conn)
        assert "reminder due now" in body
        assert "Mark as sent" not in body
        assert "closing alerts need a subscription" in body

    def test_a_recorded_reminder_is_not_offered_twice(self, conn, jobs):
        save(conn, jobs[0])
        close_in(conn, jobs[0], 36)
        save(conn, jobs[0], kind="reminded")
        assert shortlist.reminders_due(conn, "demo-fresher", now=NOW) == []
        assert "reminder due now" not in page(conn)

    def test_an_expired_deadline_never_reminds(self, conn, jobs):
        save(conn, jobs[0])
        close_in(conn, jobs[0], -48)
        assert shortlist.reminders_due(conn, "demo-fresher", now=NOW) == []

    def test_removing_a_job_removes_its_reminder(self, conn, jobs):
        save(conn, jobs[0])
        close_in(conn, jobs[0], 36)
        save(conn, jobs[0], kind="unsaved")
        assert shortlist.reminders_due(conn, "demo-fresher", now=NOW) == []

    def test_it_never_fires_twice_in_a_day(self, conn, jobs):
        save(conn, jobs[0])
        close_in(conn, jobs[0], 36)
        assert len(shortlist.reminders_due(conn, "demo-fresher", now=NOW)) == 1
        save(conn, jobs[0], kind="reminded")
        later = NOW + timedelta(hours=6)
        assert shortlist.reminders_due(conn, "demo-fresher", now=later) == []


class TestActions:
    def test_a_visitor_may_report_an_application_they_made(self, conn, jobs):
        """Self-reporting is allowed; claiming we submitted it is not.

        There is no in-app application and no auto-apply. "I applied" records
        what the person says they did, on the employer's site, and the tracker
        counts it. Nothing here talks to an employer.
        """
        body = f"profile=demo-fresher&job={jobs[0]}&kind=applied".encode()
        handle(conn, "POST", "/action", {}, body=body, now=NOW)
        assert [row["kind"] for row in tracking.events_for_job(conn, jobs[0])] == ["applied"]

    def test_a_visitor_cannot_write_a_click_through(self, conn, jobs):
        body = f"profile=demo-fresher&job={jobs[0]}&kind=clicked_through".encode()
        handle(conn, "POST", "/action", {}, body=body, now=NOW)
        assert [row["kind"] for row in tracking.events_for_job(conn, jobs[0])] == []

    def test_next_is_honoured_for_same_site_paths(self, conn, jobs):
        body = f"profile=demo-fresher&job={jobs[0]}&kind=saved&next=/shortlist".encode()
        response = handle(conn, "POST", "/action", {}, body=body, now=NOW)
        assert response.headers["Location"] == "/shortlist"

    def test_next_cannot_be_an_open_redirect(self, conn, jobs):
        for evil in ("https://evil.example/x", "//evil.example", "javascript:alert(1)"):
            body = f"profile=demo-fresher&job={jobs[0]}&kind=saved&next={evil}".encode()
            response = handle(conn, "POST", "/action", {}, body=body, now=NOW)
            assert not response.headers["Location"].startswith(("http", "//", "javascript"))

    def test_without_next_it_falls_back_to_the_feed(self, conn, jobs):
        body = f"profile=demo-fresher&job={jobs[0]}&kind=saved".encode()
        response = handle(conn, "POST", "/action", {}, body=body, now=NOW)
        assert response.headers["Location"] == "/?profile=demo-fresher"


class TestBuildMarker:
    def test_health_reports_the_deployed_commit(self, conn, monkeypatch):
        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "ce94e70a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e")
        import json as _json

        body = handle(conn, "GET", "/api/health", {}, now=NOW).body
        assert _json.loads(body)["build"] == "ce94e70"

    def test_locally_it_says_dev(self, conn, monkeypatch):
        monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
        import json as _json

        body = handle(conn, "GET", "/api/health", {}, now=NOW).body
        assert _json.loads(body)["build"] == "dev"

    def test_the_demo_pages_name_their_build(self, conn, monkeypatch):
        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "abc1234def")
        body = handle(conn, "GET", "/", {}, now=NOW, demo=True).body
        assert "demo build abc1234" in body
