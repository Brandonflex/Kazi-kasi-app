"""PSC and county adapters, end to end, plus the graph consequences.

The point of these tests is the thing the research flagged as the public-sector
exception: **one advert, N posts**. A bulletin must become N jobs, and the same
bulletin republished as HTML and as a PDF must not become 2N.
"""

from datetime import datetime, timezone

import pytest

from kazikasi import db, graph
from kazikasi.pipeline import FixtureFetcher, ingest
from kazikasi.rawstore import MemoryRawStore
from kazikasi.sources import NairobiCounty, PSCKenya
from kazikasi.sources.base import Payload

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)

PSC_LISTING = "https://www.psckjobs.go.ke/"
PSC_ADVERT = "https://www.psckjobs.go.ke/downloads/vacancies/psc-advert-october-2026.pdf"
NAIROBI_LISTING = "https://nairobi.go.ke/careers/"
NAIROBI_HTML = "https://nairobi.go.ke/careers/adverts/county-vacancies-november-2026"
NAIROBI_PDF = "https://nairobi.go.ke/downloads/nccg-advert-2026-11.pdf"


@pytest.fixture
def psc_fetcher(fixtures):
    return FixtureFetcher(
        {
            PSC_LISTING: fixtures / "psc-listing.html",
            PSC_ADVERT: fixtures / "psc-advert.pdf",
        }
    )


@pytest.fixture
def nairobi_fetcher(fixtures):
    return FixtureFetcher(
        {
            NAIROBI_LISTING: fixtures / "nairobi-listing.html",
            NAIROBI_HTML: fixtures / "nairobi-advert.html",
            NAIROBI_PDF: fixtures / "nairobi-advert.pdf",
        }
    )


class TestPSCListing:
    def test_only_document_links_are_taken(self, fixtures):
        links = PSCKenya().parse_listing_payload(
            Payload(PSC_LISTING, (fixtures / "psc-listing.html").read_bytes()), PSC_LISTING
        )
        assert links == [PSC_ADVERT]

    def test_forms_and_archive_pages_are_excluded(self, fixtures):
        links = PSCKenya().parse_listing_payload(
            Payload(PSC_LISTING, (fixtures / "psc-listing.html").read_bytes()), PSC_LISTING
        )
        assert not any("pension" in link or "archive" in link for link in links)


class TestPSCPayload:
    def test_one_pdf_yields_every_post(self, fixtures):
        payload = Payload(PSC_ADVERT, (fixtures / "psc-advert.pdf").read_bytes(), "application/pdf")
        candidates = PSCKenya().parse_payload(payload, PSC_ADVERT)
        assert len(candidates) == 3
        assert all(candidate.employer_name == "Public Service Commission of Kenya" for candidate in candidates)
        assert all(candidate.county == "Nairobi" for candidate in candidates)
        assert all(candidate.description_source == "pdf_text" for candidate in candidates)

    def test_parse_detail_keeps_the_interface_honest(self, fixtures):
        adapter = PSCKenya()
        candidate = adapter.parse_detail(
            (fixtures / "psc-advert.pdf").read_bytes().decode("latin-1"), PSC_ADVERT
        )
        assert candidate.title == "Assistant Office Administrator"


class TestCountyListing:
    def test_html_advert_and_its_pdf_are_both_found(self, fixtures):
        links = NairobiCounty().parse_listing_payload(
            Payload(NAIROBI_LISTING, (fixtures / "nairobi-listing.html").read_bytes()), NAIROBI_LISTING
        )
        assert set(links) == {NAIROBI_HTML, NAIROBI_PDF}

    def test_tenders_and_budget_documents_are_not_vacancies(self, fixtures):
        links = NairobiCounty().parse_listing_payload(
            Payload(NAIROBI_LISTING, (fixtures / "nairobi-listing.html").read_bytes()), NAIROBI_LISTING
        )
        assert not any("tender" in link or "budget" in link for link in links)


class TestIngestToGraph:
    def test_psc_ingest_stores_the_pdf_bytes(self, psc_fetcher):
        store = MemoryRawStore()
        report = ingest(PSCKenya(), psc_fetcher, store)
        assert report.listing_pages == 1
        assert report.detail_urls == 1
        assert report.payloads == 1
        assert report.parsed == 3
        assert report.errors == []
        # The stored blob must be the original PDF, not a decoded string.
        sha = next(sha for sha, meta in store.iter_fetches() if meta["kind"] == "detail")
        blob = store.get(sha)
        assert blob[:5] == b"%PDF-"

    def test_one_advert_becomes_three_jobs(self, psc_fetcher):
        conn = db.connect()
        try:
            report = ingest(PSCKenya(), psc_fetcher, MemoryRawStore())
            for candidate in report.candidates:
                graph.upsert_candidate(conn, candidate, now=NOW)
            assert db.table_counts(conn)["jobs"] == 3
            titles = {row["title"] for row in conn.execute("SELECT title FROM jobs")}
            assert titles == {
                "Assistant Office Administrator",
                "Records Management Assistant",
                "Senior ICT Officer",
            }
            assert db.table_counts(conn)["review_queue"] == 0
        finally:
            conn.close()

    def test_same_bulletin_as_html_and_pdf_does_not_double_count(self, nairobi_fetcher):
        conn = db.connect()
        try:
            report = ingest(NairobiCounty(), nairobi_fetcher, MemoryRawStore())
            assert report.payloads == 2
            assert report.parsed == 4  # two posts in the HTML, two in the PDF

            actions = [graph.upsert_candidate(conn, candidate, now=NOW).action for candidate in report.candidates]
            assert actions.count("created") == 2
            assert actions.count("attached") == 2
            assert db.table_counts(conn)["jobs"] == 2
        finally:
            conn.close()

    def test_the_two_county_posts_keep_their_own_eligibility(self, nairobi_fetcher):
        conn = db.connect()
        try:
            report = ingest(NairobiCounty(), nairobi_fetcher, MemoryRawStore())
            for candidate in report.candidates:
                graph.upsert_candidate(conn, candidate, now=NOW)
            rows = {row["title"]: row["entry_fit"] for row in conn.execute("SELECT title, entry_fit FROM jobs")}
            assert rows["Assistant Ward Administrator"] == "experienced"
            assert rows["Driver"] == "open_to_freshers"
        finally:
            conn.close()

    def test_county_posts_survive_a_replay_from_the_raw_store(self, tmp_path, nairobi_fetcher):
        from kazikasi.rawstore import FileRawStore
        from kazikasi.replay import replay

        root = tmp_path / "raw"
        ingest(NairobiCounty(), nairobi_fetcher, FileRawStore(root))
        report = replay(NairobiCounty(), FileRawStore(root))
        assert report.payloads == 2
        assert report.parsed == 4
        assert report.failed == 0
