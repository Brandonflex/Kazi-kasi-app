"""Identity resolution and liveness.

The cases that matter here are the *refusals*: two adverts that look alike and
must not be merged, because a wrong merge hides a real vacancy.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from kazikasi import db, graph
from kazikasi.models import JobCandidate

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


def job(**kwargs) -> JobCandidate:
    base = dict(
        source_id="brightermonday",
        source_job_id="BM-1",
        source_url="https://www.brightermonday.co.ke/listings/1",
        title="Software Support Analyst",
        employer_name="Haba Data Systems Ltd",
        employer_domain="habadata.co.ke",
        county="Nairobi",
        sub_county="Westlands",
        description_md="Triage support tickets. Fresh graduates are encouraged to apply.",
        entry_fit="open_to_freshers",
        entry_fit_evidence="Fresh graduates are encouraged to apply.",
        deadline=date(2026, 11, 5),
        apply_emails=["careers@habadata.co.ke"],
        first_seen_at=NOW,
    )
    base.update(kwargs)
    return JobCandidate(**base)


@pytest.fixture
def conn():
    connection = db.connect()
    yield connection
    connection.close()


class TestCreateAndAttach:
    def test_first_candidate_creates_a_job(self, conn):
        result = graph.upsert_candidate(conn, job(), now=NOW)
        assert result.action == "created"
        assert db.table_counts(conn)["jobs"] == 1

    def test_same_posting_on_two_boards_merges(self, conn):
        first = graph.upsert_candidate(conn, job(), now=NOW)
        second = graph.upsert_candidate(
            conn,
            job(
                source_id="myjobmag",
                source_job_id="MJM-1",
                source_url="https://www.myjobmag.co.ke/job/1",
            ),
            now=NOW,
        )
        assert second.action == "attached"
        assert second.job_id == first.job_id
        assert second.match_reason == "key_dedupe"
        assert graph.job_row(conn, first.job_id)["source_count"] == 2

    def test_reingesting_the_same_candidate_is_a_no_op(self, conn):
        graph.upsert_candidate(conn, job(), now=NOW)
        again = graph.upsert_candidate(conn, job(), now=NOW)
        assert again.action == "duplicate"
        counts = db.table_counts(conn)
        assert counts["jobs"] == 1 and counts["observations"] == 1

    def test_changed_payload_is_a_new_observation(self, conn):
        graph.upsert_candidate(conn, job(), now=NOW)
        changed = graph.upsert_candidate(conn, job(description_md="Completely rewritten advert."), now=NOW)
        assert changed.observation_id != 1
        assert db.table_counts(conn)["observations"] == 2


class TestSharedKeysDoNotOverMerge:
    def test_shared_careers_inbox_does_not_merge_different_titles(self, conn):
        # The bug this rule exists for: one employer, twenty vacancies, one inbox.
        graph.upsert_candidate(conn, job(), now=NOW)
        other = graph.upsert_candidate(
            conn,
            job(
                source_id="fuzu",
                source_job_id="FZ-9",
                source_url="https://www.fuzu.com/kenya/job/9",
                title="Junior Data Analyst",
            ),
            now=NOW,
        )
        assert other.action == "created"
        assert db.table_counts(conn)["jobs"] == 2

    def test_shared_inbox_merges_when_titles_and_dates_agree(self, conn):
        graph.upsert_candidate(conn, job(), now=NOW)
        merged = graph.upsert_candidate(
            conn,
            job(
                source_id="myjobmag",
                source_job_id="MJM-2",
                source_url="https://www.myjobmag.co.ke/job/2",
                description_md="Different text, same advert.",
            ),
            now=NOW,
        )
        assert merged.action == "attached"
        assert merged.match_reason in ("key_dedupe", "shared_email+title")

    def test_shared_inbox_with_a_different_deadline_asks_a_human(self, conn):
        graph.upsert_candidate(conn, job(), now=NOW)
        second = graph.upsert_candidate(
            conn,
            job(
                source_id="myjobmag",
                source_job_id="MJM-2",
                source_url="https://www.myjobmag.co.ke/job/2",
                deadline=date(2026, 12, 1),
            ),
            now=NOW,
        )
        assert second.action == "created"
        assert graph.open_reviews(conn)[0]["reason"] == "shared_key_deadline_conflict"

    def test_reference_number_merges_even_when_titles_differ(self, conn):
        graph.upsert_candidate(conn, job(reference="NCG/HR/12/2026"), now=NOW)
        merged = graph.upsert_candidate(
            conn,
            job(
                source_id="myjobmag",
                source_job_id="MJM-3",
                source_url="https://www.myjobmag.co.ke/job/3",
                title="Clerical Officer",
                reference="NCG/HR/12/2026",
                deadline=date(2026, 12, 3),
            ),
            now=NOW,
        )
        assert merged.action == "attached"
        assert merged.match_reason == "key_ref"


class TestHardSeparators:
    def test_different_deadline_is_a_different_post(self, conn):
        graph.upsert_candidate(conn, job(), now=NOW)
        second = graph.upsert_candidate(conn, job(deadline=date(2026, 12, 1), source_job_id="BM-2"), now=NOW)
        assert second.action == "created"
        assert db.table_counts(conn)["jobs"] == 2

    def test_grade_marker_is_never_merged_away(self, conn):
        graph.upsert_candidate(conn, job(), now=NOW)
        second = graph.upsert_candidate(
            conn,
            job(source_id="fuzu", source_job_id="FZ-2", source_url="https://fuzu/2", title="Software Support Analyst II"),
            now=NOW,
        )
        assert second.action == "created"
        reviews = graph.open_reviews(conn)
        assert len(reviews) == 1
        assert reviews[0]["incoming_title"] == "Software Support Analyst II"

    def test_different_county_is_a_different_job(self, conn):
        graph.upsert_candidate(conn, job(), now=NOW)
        second = graph.upsert_candidate(
            conn, job(county="Mombasa", source_job_id="BM-3", sub_county=None), now=NOW
        )
        assert second.action == "created"

    def test_near_duplicate_goes_to_review_not_into_the_job(self, conn):
        graph.upsert_candidate(conn, job(title="Marketing Intern"), now=NOW)
        second = graph.upsert_candidate(
            conn, job(title="Marketing & Communications Intern", source_job_id="BM-4"), now=NOW
        )
        assert second.action == "created"
        assert db.table_counts(conn)["review_queue"] == 1

    def test_unrelated_jobs_are_not_queued(self, conn):
        graph.upsert_candidate(conn, job(), now=NOW)
        graph.upsert_candidate(conn, job(title="Finance Officer", source_job_id="BM-5"), now=NOW)
        assert db.table_counts(conn)["review_queue"] == 0


class TestLiveness:
    def test_aging_moves_a_job_to_stale_then_suspect(self, conn):
        result = graph.upsert_candidate(conn, job(deadline=None), now=NOW)
        assert graph.apply_liveness(conn, now=NOW + timedelta(days=4))["stale"] == 1
        assert graph.job_row(conn, result.job_id)["status"] == "stale"
        assert graph.apply_liveness(conn, now=NOW + timedelta(days=8))["suspect_closed"] == 1
        assert graph.job_row(conn, result.job_id)["status"] == "suspect_closed"

    def test_a_passed_deadline_closes_after_the_grace_period(self, conn):
        result = graph.upsert_candidate(conn, job(), now=NOW)
        # Deadline is 2026-11-05; two days of grace.
        assert graph.apply_liveness(conn, now=datetime(2026, 11, 7, tzinfo=timezone.utc))["closed"] == 0
        assert graph.apply_liveness(conn, now=datetime(2026, 11, 9, tzinfo=timezone.utc))["closed"] == 1
        assert graph.job_row(conn, result.job_id)["status"] == "closed"

    def test_a_sighting_reopens_a_stale_job(self, conn):
        created = graph.upsert_candidate(conn, job(deadline=None), now=NOW)
        graph.apply_liveness(conn, now=NOW + timedelta(days=4))
        again = graph.upsert_candidate(
            conn,
            job(deadline=None, source_id="myjobmag", source_job_id="MJM-7", description_md="Updated text."),
            now=NOW + timedelta(days=5),
        )
        assert again.action == "attached"
        assert graph.job_row(conn, created.job_id)["status"] == "open"
        events = [event["kind"] for event in graph.job_events(conn, created.job_id)]
        assert "stale" in events and "reopened" in events

    def test_missing_fields_are_not_a_freshness_problem(self, conn):
        created = graph.upsert_candidate(conn, job(employer_name=None, employer_domain=None, deadline=None), now=NOW)
        assert graph.job_row(conn, created.job_id)["status"] == "needs_review"
        graph.apply_liveness(conn, now=NOW + timedelta(days=9))
        assert graph.job_row(conn, created.job_id)["status"] == "needs_review"


class TestReviewResolution:
    def test_merge_moves_members_and_keys_and_resolves_the_pair(self, conn):
        keeper = graph.upsert_candidate(conn, job(), now=NOW)
        dropped = graph.upsert_candidate(
            conn, job(title="Software Support Analyst II", source_id="fuzu", source_job_id="FZ-3"), now=NOW
        )
        graph.merge_jobs(conn, keeper.job_id, dropped.job_id, now=NOW)

        assert graph.job_row(conn, dropped.job_id) is None
        assert graph.job_row(conn, keeper.job_id)["source_count"] == 2
        assert len(graph.job_sources(conn, keeper.job_id)) == 2
        assert db.table_counts(conn)["review_queue"] == 1
        # The merge answers the open question rather than leaving it dangling.
        assert graph.open_reviews(conn) == []
        resolved = conn.execute("SELECT resolved_at, resolution FROM review_queue").fetchone()
        assert resolved["resolved_at"] and resolved["resolution"] == "merged"

    def test_reject_keeps_both_jobs(self, conn):
        graph.upsert_candidate(conn, job(), now=NOW)
        graph.upsert_candidate(conn, job(title="Marketing Intern", source_job_id="BM-8"), now=NOW)
        graph.upsert_candidate(conn, job(title="Marketing & Communications Intern", source_job_id="BM-9"), now=NOW)
        review = graph.open_reviews(conn)[0]
        graph.reject_pair(conn, review["id"], now=NOW)
        assert graph.open_reviews(conn) == []
        assert db.table_counts(conn)["jobs"] == 3


class TestFeed:
    def test_flagged_jobs_are_hidden_by_default(self, conn):
        graph.upsert_candidate(conn, job(), now=NOW)
        graph.upsert_candidate(
            conn,
            job(
                source_job_id="BM-10",
                title="Urgent Data Entry",
                employer_name=None,
                employer_domain=None,
                scam_flags=["fee_requested"],
            ),
            now=NOW,
        )
        titles = [row["title"] for row in graph.feed(conn)]
        assert titles == ["Software Support Analyst"]

    def test_stale_jobs_need_asking_for(self, conn):
        graph.upsert_candidate(conn, job(deadline=None), now=NOW)
        graph.apply_liveness(conn, now=NOW + timedelta(days=4))
        assert graph.feed(conn) == []
        assert len(graph.feed(conn, include_stale=True)) == 1

    def test_feed_orders_by_deadline(self, conn):
        graph.upsert_candidate(conn, job(deadline=date(2026, 12, 1)), now=NOW)
        graph.upsert_candidate(conn, job(source_job_id="BM-11", title="Soon Role", deadline=date(2026, 10, 25)), now=NOW)
        assert [row["title"] for row in graph.feed(conn)] == ["Soon Role", "Software Support Analyst"]

    def test_freshness_and_deadline_bands(self, conn):
        graph.upsert_candidate(conn, job(), now=NOW)
        row = graph.feed(conn)[0]
        assert graph.freshness_band(row, now=NOW) == "checked today"
        assert graph.deadline_band(row, now=NOW) == "closes 05 Nov"
        assert graph.deadline_band(row, now=datetime(2026, 11, 5, tzinfo=timezone.utc)) == "closes today"
