"""End-to-end ingestion and replay, entirely offline.

There is no network here, and there is no mocking framework either: the pipeline
takes a ``Fetcher`` and a ``RawStore``, so tests supply a fixture fetcher and a
temporary store. If a test touches the network it fails loudly with a KeyError.
"""

from datetime import date

import pytest

from kazikasi.models import JobCandidate
from kazikasi.pipeline import FixtureFetcher, ingest, verify, write_jsonl
from kazikasi.rawstore import FileRawStore, MemoryRawStore
from kazikasi.replay import replay, write_report
from kazikasi.sources import BrighterMonday, MyJobMag, ReliefWeb

BM_LISTING = "https://www.brightermonday.co.ke/jobs"
BM_DETAIL = "https://www.brightermonday.co.ke/listings/software-support-analyst-westlands-1029384"
BM_DETAIL_2 = "https://www.brightermonday.co.ke/listings/graduate-trainee-programme-1029385"
BM_DETAIL_3 = "https://www.brightermonday.co.ke/listings/finance-assistant-1029386"
MJM_LISTING = "https://www.myjobmag.co.ke/jobs"
MJM_DETAIL = "https://www.myjobmag.co.ke/job/marketing-intern-nairobi-88213"


@pytest.fixture
def bm_fetcher(fixtures):
    return FixtureFetcher(
        {
            BM_LISTING: fixtures / "brightermonday-listing.html",
            BM_DETAIL: fixtures / "brightermonday-detail.html",
            BM_DETAIL_2: fixtures / "brightermonday-detail.html",
            BM_DETAIL_3: fixtures / "myjobmag-detail.html",
        }
    )


class TestIngest:
    def test_ingests_listing_then_details(self, bm_fetcher):
        store = MemoryRawStore()
        report = ingest(BrighterMonday(), bm_fetcher, store, pages=1)

        assert report.listing_pages == 1
        assert report.detail_urls == 3
        assert report.parsed == 3
        assert report.errors == []
        assert report.stored == 4  # one listing page + three details

    def test_every_payload_is_stored_before_parsing(self, bm_fetcher):
        store = MemoryRawStore()
        ingest(BrighterMonday(), bm_fetcher, store)
        fetches = list(store.iter_fetches("brightermonday"))
        assert len(fetches) == 4
        kinds = {meta["kind"] for _, meta in fetches}
        assert kinds == {"listing", "detail"}

    def test_store_is_content_addressed(self, bm_fetcher):
        store = MemoryRawStore()
        ingest(BrighterMonday(), bm_fetcher, store)
        # Two detail URLs shared one fixture body, so they share one blob.
        detail_blobs = {
            ref.sha256 for ref, meta in store.iter_refs("brightermonday") if meta["kind"] == "detail"
        }
        assert len(detail_blobs) == 2

    def test_limit_caps_detail_pages(self, bm_fetcher):
        report = ingest(BrighterMonday(), bm_fetcher, MemoryRawStore(), limit=1)
        assert report.detail_urls == 1

    def test_fetch_errors_are_reported_not_swallowed(self, fixtures):
        fetcher = FixtureFetcher({BM_LISTING: fixtures / "brightermonday-listing.html"})
        report = ingest(BrighterMonday(), fetcher, MemoryRawStore())
        assert report.parsed == 0
        assert len(report.errors) == 3
        assert all(error["stage"] == "detail" for error in report.errors)

    def test_listing_failure_does_not_crash_the_run(self):
        report = ingest(BrighterMonday(), FixtureFetcher({}), MemoryRawStore())
        assert report.listing_pages == 0
        assert report.errors and report.errors[0]["stage"] == "listing"

    def test_summary_is_json_safe(self, bm_fetcher):
        report = ingest(BrighterMonday(), bm_fetcher, MemoryRawStore())
        summary = report.summary()
        assert summary["source_id"] == "brightermonday"
        assert isinstance(summary["duration_s"], float)


class TestVerify:
    def test_complete_future_job_is_open(self):
        candidate = JobCandidate(
            source_id="s",
            source_job_id="1",
            source_url="u",
            title="Records Clerk",
            employer_name="Acme",
            county="Nairobi",
            description_md="text",
            deadline=date(2099, 1, 1),
        )
        assert verify(candidate).status == "open"

    def test_expired_job_is_closed_with_a_note(self):
        candidate = JobCandidate(
            source_id="s",
            source_job_id="1",
            source_url="u",
            title="Records Clerk",
            employer_name="Acme",
            county="Nairobi",
            description_md="text",
            deadline=date(2020, 1, 1),
        )
        result = verify(candidate, today=date(2026, 10, 20))
        assert result.status == "closed"
        assert "deadline_passed_at_ingest" in result.parser_notes

    def test_missing_required_goes_to_review_not_live(self):
        candidate = JobCandidate(source_id="s", source_job_id="1", source_url="u", title="Clerk")
        assert verify(candidate).status == "needs_review"

    def test_missing_required_names_the_fields(self):
        candidate = JobCandidate(source_id="s", source_job_id="1", source_url="u", title="Clerk")
        missing = candidate.missing_required()
        assert "employer" in missing and "location" in missing and "description" in missing


class TestOutput:
    def test_jsonl_round_trip(self, tmp_path, bm_fetcher):
        report = ingest(BrighterMonday(), bm_fetcher, MemoryRawStore())
        out = tmp_path / "jobs.jsonl"
        assert write_jsonl(report.candidates, out) == 3
        lines = out.read_text().strip().splitlines()
        assert len(lines) == 3
        assert '"title": "Software Support Analyst"' in lines[0]


class TestFileStoreAndReplay:
    def test_filesystem_store_is_stable_across_instances(self, tmp_path, bm_fetcher):
        root = tmp_path / "raw"
        store = FileRawStore(root)
        ingest(BrighterMonday(), bm_fetcher, store)

        reopened = FileRawStore(root)
        fetches = list(reopened.iter_fetches("brightermonday"))
        assert len(fetches) == 4
        assert reopened.get(fetches[0][0])

    def test_replay_needs_no_fetcher_at_all(self, tmp_path, bm_fetcher):
        root = tmp_path / "raw"
        ingest(BrighterMonday(), bm_fetcher, FileRawStore(root))

        report = replay(BrighterMonday(), FileRawStore(root))
        assert report.payloads == 3
        assert report.parsed == 3
        assert report.failed == 0

    def test_replay_reports_field_fill(self, tmp_path, bm_fetcher):
        root = tmp_path / "raw"
        ingest(BrighterMonday(), bm_fetcher, FileRawStore(root))
        report = replay(BrighterMonday(), FileRawStore(root))

        assert report.field_fill["title"] == 3
        assert report.field_fill["county"] >= 2
        assert 0 <= report.to_dict()["field_fill"]["title"]["rate"] <= 1

    def test_replay_is_filtered_by_source(self, tmp_path, fixtures):
        root = tmp_path / "raw"
        bm = FixtureFetcher(
            {
                BM_LISTING: fixtures / "brightermonday-listing.html",
                BM_DETAIL: fixtures / "brightermonday-detail.html",
            }
        )
        mjm = FixtureFetcher(
            {
                MJM_LISTING: fixtures / "myjobmag-listing.html",
                MJM_DETAIL: fixtures / "myjobmag-detail.html",
            }
        )
        ingest(BrighterMonday(), bm, FileRawStore(root), limit=1)
        ingest(MyJobMag(), mjm, FileRawStore(root), limit=1)

        bm_report = replay(BrighterMonday(), FileRawStore(root))
        mjm_report = replay(MyJobMag(), FileRawStore(root))
        assert bm_report.payloads == 1
        assert mjm_report.payloads == 1

    def test_replay_writes_a_report(self, tmp_path, bm_fetcher):
        root = tmp_path / "raw"
        ingest(BrighterMonday(), bm_fetcher, FileRawStore(root))
        report = replay(BrighterMonday(), FileRawStore(root))
        path = write_report(report, tmp_path / "replay.json")
        assert path.exists()
        assert '"source_id": "brightermonday"' in path.read_text()


class TestReliefWebOffline:
    def test_items_map_from_a_fixture_without_http(self, fixtures):
        adapter = ReliefWeb(appname="test")
        items = adapter.parse_listing((fixtures / "reliefweb-jobs.json").read_text())
        candidates = [adapter.item_to_candidate(item) for item in items]
        assert [c.title for c in candidates] == ["Programme Assistant", "Senior Finance Manager"]
        assert all(c.source_id == "reliefweb" for c in candidates)


class TestCanary:
    def test_healthy_source(self, bm_fetcher):
        from kazikasi.canary import run as run_canary

        result = run_canary(BrighterMonday(), bm_fetcher)
        assert result.ok
        assert result.listing_links == 3
        assert "title" in result.fields_present

    def test_dead_listing_is_not_ok(self, fixtures):
        from kazikasi.canary import run as run_canary

        fetcher = FixtureFetcher({BM_LISTING: fixtures / "reliefweb-jobs.json"})
        result = run_canary(BrighterMonday(), fetcher)
        assert not result.ok
        assert result.error

    def test_drift_shows_as_missing_fields(self, tmp_path, fixtures):
        from kazikasi.canary import run as run_canary

        # A detail page that parses but loses half its shape is the failure
        # that a try/except would never catch.
        stripped = tmp_path / "stripped.html"
        stripped.write_text("<html><body><h1>Some Job</h1></body></html>")
        fetcher = FixtureFetcher(
            {BM_LISTING: fixtures / "brightermonday-listing.html", BM_DETAIL: stripped}
        )
        result = run_canary(BrighterMonday(), fetcher)
        assert not result.ok
        assert "employer_name" in result.missing
