"""Saved searches: the query with a clock.

The feature is small and the failure modes are not: a search that alerts on jobs
it already mentioned, a search that messages someone who unsubscribed, a "no news"
message, or a watermark that rewinds and re-sends yesterday. Each of those is a
test below.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import outbox, scheduler, searches, serve
from kazikasi.channels import FakeTransport

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    connection = serve.demo_connection(now=NOW)
    yield connection
    connection.close()


def subscribed(conn, profile="demo-fresher", when=NOW):
    outbox.subscribe(conn, profile, "0712000111", now=when)
    return profile


def backdate(conn, search_id=1, days=8):
    """Pretend the search was saved before the corpus was collected."""
    conn.execute(
        "UPDATE saved_searches SET created_at = ? WHERE id = ?",
        ((NOW - timedelta(days=days)).isoformat(), search_id),
    )
    conn.commit()


class TestSaving:
    def test_a_subscription_is_the_price_of_entry(self, conn):
        result = searches.watch(conn, "demo-fresher", q="software", now=NOW)
        assert result["saved"] is False
        assert result["state"] == "no_consent"
        assert searches.for_profile(conn, "demo-fresher") == []

    def test_an_unsubscribed_person_cannot_save(self, conn):
        outbox.subscribe(conn, "demo-fresher", "0712000111", now=NOW)
        outbox.unsubscribe(conn, "demo-fresher", now=NOW)
        assert searches.watch(conn, "demo-fresher", q="x", now=NOW)["saved"] is False

    def test_the_filters_are_stored_normalised(self, conn):
        subscribed(conn)
        result = searches.watch(
            conn, "demo-fresher", q="  software ", county="Nairobi", deadline_days=None, pay_floor=None, now=NOW
        )
        row = conn.execute("SELECT * FROM saved_searches").fetchone()
        assert row["q"] == "software"
        assert row["county"] == "Nairobi"
        assert row["deadline_days"] == 0 and row["pay_floor"] == 0
        assert result["id"] == row["id"]

    def test_the_label_is_built_from_the_filters(self, conn):
        subscribed(conn)
        result = searches.watch(
            conn,
            "demo-fresher",
            q="software",
            county="Nairobi",
            employment_type="internship",
            pay_floor=40000,
            deadline_days=14,
            now=NOW,
        )
        assert "“software”" in result["label"]
        assert "in Nairobi" in result["label"]
        assert "≥ KES 40,000" in result["label"]

    def test_saving_the_same_search_twice_is_one_row(self, conn):
        subscribed(conn)
        first = searches.watch(conn, "demo-fresher", q="software", now=NOW)
        second = searches.watch(conn, "demo-fresher", q="software", now=NOW)
        assert first["id"] == second["id"]
        assert second["state"] == "resumed"
        assert conn.execute("SELECT COUNT(*) AS n FROM saved_searches").fetchone()["n"] == 1

    def test_resuming_does_not_rewind_the_watermark(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", q="software", now=NOW)
        conn.execute("UPDATE saved_searches SET last_run_at = ?, unsubscribed_at = ?", (NOW.isoformat(), NOW.isoformat()))
        conn.commit()
        searches.watch(conn, "demo-fresher", q="software", now=NOW + timedelta(days=3))
        row = conn.execute("SELECT * FROM saved_searches").fetchone()
        assert row["unsubscribed_at"] is None
        assert row["last_run_at"] == NOW.isoformat()

    def test_an_unknown_cadence_is_refused(self, conn):
        subscribed(conn)
        with pytest.raises(ValueError, match="cadence"):
            searches.watch(conn, "demo-fresher", q="x", cadence="hourly", now=NOW)


class TestStopping:
    def test_stop_marks_and_hides(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", q="software", now=NOW)
        assert searches.stop(conn, "demo-fresher", 1, now=NOW) is True
        assert searches.for_profile(conn, "demo-fresher") == []

    def test_stopping_twice_is_not_an_error_but_is_false(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", q="software", now=NOW)
        searches.stop(conn, "demo-fresher", 1, now=NOW)
        assert searches.stop(conn, "demo-fresher", 1, now=NOW) is False

    def test_one_person_cannot_stop_anothers_search(self, conn):
        subscribed(conn, "demo-fresher")
        subscribed(conn, "demo-remote")
        searches.watch(conn, "demo-fresher", q="software", now=NOW)
        assert searches.stop(conn, "demo-remote", 1, now=NOW) is False
        assert len(searches.for_profile(conn, "demo-fresher")) == 1


class TestTheClock:
    def test_a_search_with_no_subscription_is_not_due(self, conn):
        searches.watch(conn, "demo-fresher", q="x", now=NOW)  # refused
        assert searches.due(conn, now=NOW) == []

    def test_daily_runs_once_a_day(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", q="software", now=NOW)
        first = searches.queue_due(conn, now=NOW)
        assert first["considered"] == 1
        conn.execute("UPDATE saved_searches SET last_run_at = ?", (NOW.isoformat(),))
        conn.commit()
        assert searches.due(conn, now=NOW + timedelta(hours=4)) == []

    def test_weekly_waits_seven_days(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", q="software", cadence="weekly", now=NOW)
        conn.execute("UPDATE saved_searches SET last_run_at = ?", (NOW.isoformat(),))
        conn.commit()
        assert searches.due(conn, now=NOW + timedelta(days=3)) == []
        assert len(searches.due(conn, now=NOW + timedelta(days=8))) == 1

    def test_an_opted_out_search_is_not_due(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", q="software", now=NOW)
        searches.stop(conn, "demo-fresher", 1, now=NOW)
        assert searches.due(conn, now=NOW) == []


class TestWhatCountsAsNew:
    def test_only_arrivals_after_the_watermark(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", q="software", now=NOW)
        backdate(conn)
        row = searches.for_profile(conn, "demo-fresher")[0]
        fresh = searches.new_matches(conn, row, now=NOW)
        assert fresh
        for item in fresh:
            assert item.row["first_seen_at"] > (NOW - timedelta(days=8)).isoformat()

    def test_the_first_run_starts_at_the_save_time(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", q="software", now=NOW)
        row = searches.for_profile(conn, "demo-fresher")[0]
        # The corpus was all first seen before or at NOW, so nothing is new yet.
        assert searches.new_matches(conn, row, now=NOW) == []


class TestTheMessage:
    def test_it_names_the_search_and_the_arrivals(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", q="software", now=NOW)
        backdate(conn)
        row = searches.for_profile(conn, "demo-fresher")[0]
        matches = searches.new_matches(conn, row, now=NOW)
        body = searches.message(row, matches)
        assert "new role" in body
        assert row["label"] in body
        assert "/search?" in body
        assert "Stop these alerts" in body

    def test_it_caps_the_list_and_says_how_many_more(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", now=NOW)  # everything
        backdate(conn)
        row = searches.for_profile(conn, "demo-fresher")[0]
        matches = searches.new_matches(conn, row, now=NOW)
        assert len(matches) > searches.MAX_ITEMS
        body = searches.message(row, matches)
        assert f"+{len(matches) - searches.MAX_ITEMS} more" in body

    def test_dates_are_human(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", now=NOW)
        backdate(conn)
        row = searches.for_profile(conn, "demo-fresher")[0]
        body = searches.message(row, searches.new_matches(conn, row, now=NOW))
        assert "closes 2026-" not in body


class TestTheTick:
    def test_it_queues_one_message_and_advances_the_watermark(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", q="", now=NOW)
        backdate(conn)
        report = searches.queue_due(conn, now=NOW)
        assert report["queued"] == 1
        row = conn.execute("SELECT * FROM saved_searches").fetchone()
        assert row["last_run_at"] is not None
        assert conn.execute("SELECT COUNT(*) AS n FROM messages WHERE kind='search'").fetchone()["n"] == 1

    def test_a_second_tick_same_day_sends_nothing(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", now=NOW)
        backdate(conn)
        searches.queue_due(conn, now=NOW)
        again = searches.queue_due(conn, now=NOW + timedelta(hours=2))
        assert again["queued"] == 0
        assert conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"] == 1

    def test_nothing_new_means_no_message(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", q="astrophysics", now=NOW)
        backdate(conn)
        report = searches.queue_due(conn, now=NOW)
        assert report["queued"] == 0 and report["empty"] == 1
        assert conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"] == 0

    def test_unsubscribing_from_the_digest_stops_the_search(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", now=NOW)
        backdate(conn)
        outbox.unsubscribe(conn, "demo-fresher", now=NOW)
        assert searches.queue_due(conn, now=NOW)["considered"] == 0

    def test_a_dry_run_queues_nothing_but_shows_the_text(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", now=NOW)
        backdate(conn)
        report = searches.queue_due(conn, now=NOW, dry_run=True)
        assert report["queued"] == 0 and report["searches"]
        assert report["searches"][0]["body"]
        assert conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"] == 0

    def test_the_scheduler_carries_it_to_a_transport(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", now=NOW)
        backdate(conn)
        evening = datetime(2026, 10, 20, 15, 45, tzinfo=timezone.utc)
        fake = FakeTransport()
        report = scheduler.run_due(conn, {"whatsapp": fake}, now=evening, with_searches=True)
        assert report["searches"]["queued"] == 1
        assert any(key.startswith("saved-search:") for key in (item["idempotency"] for item in fake.sent))


class TestThePage:
    def test_a_subscriber_sees_the_keep_form(self, conn):
        subscribed(conn)
        body = serve.handle(conn, "GET", "/search", {"profile": ["demo-fresher"]}, demo=True, now=NOW).body
        assert "Keep this search" in body
        assert 'action="/search/save"' in body

    def test_a_visitor_is_told_why_they_cannot(self, conn):
        body = serve.handle(
            conn, "GET", "/search", {"profile": ["demo-fresher"], "q": ["software"]}, demo=True, now=NOW
        ).body
        assert "need a subscription" in body
        assert 'action="/search/save"' not in body

    def test_saved_searches_are_listed_and_stoppable(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", q="software", now=NOW)
        body = serve.handle(conn, "GET", "/search", {"profile": ["demo-fresher"]}, demo=True, now=NOW).body
        assert "Saved searches" in body and "“software”" in body
        assert 'action="/search/stop"' in body

    def test_the_stop_link_in_a_message_asks_before_it_stops(self, conn):
        subscribed(conn)
        searches.watch(conn, "demo-fresher", q="software", now=NOW)
        body = serve.handle(
            conn, "GET", "/search", {"profile": ["demo-fresher"], "stop": ["1"]}, demo=True, now=NOW
        ).body
        assert "Stop alerts for" in body
        assert len(searches.for_profile(conn, "demo-fresher")) == 1  # a GET never mutates

    def test_posting_save_and_stop_work_end_to_end(self, conn):
        subscribed(conn)
        response = serve.handle(
            conn, "POST", "/search/save", {}, body=b"profile=demo-fresher&q=software", demo=True, now=NOW
        )
        assert response.status == 303
        assert len(searches.for_profile(conn, "demo-fresher")) == 1
        response = serve.handle(
            conn, "POST", "/search/stop", {}, body=b"profile=demo-fresher&id=1", demo=True, now=NOW
        )
        assert response.status == 303
        assert searches.for_profile(conn, "demo-fresher") == []

    def test_saving_without_consent_sends_them_to_the_digest_page(self, conn):
        response = serve.handle(
            conn, "POST", "/search/save", {}, body=b"profile=demo-fresher&q=x", demo=True, now=NOW
        )
        assert response.status == 303
        assert response.headers["Location"].startswith("/digest")
