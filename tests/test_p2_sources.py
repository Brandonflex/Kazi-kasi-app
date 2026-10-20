"""The P2 sources, the declarative adapter, and the unverified gate.

The point of these tests is not that three specific Kenyan websites parse. It is
that **adding a source is cheap and shipping an unverified one is hard**:

* a source is configuration — listing URLs, a detail pattern, optional selectors;
* structured data is preferred over CSS, because CSS is what breaks;
* a source that has never parsed a live page cannot ingest by accident, and the
  error message names the canary command that would change that.

The fixtures are synthetic examples of the *structure* each source publishes.
They prove the parser handles that structure; they do not claim the live site
looks like them today. That distinction is the whole reason for the gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kazikasi import cli
from kazikasi.pipeline import FixtureFetcher, UnverifiedSource, ingest
from kazikasi.rawstore import FileRawStore
from kazikasi.sources import REGISTRY
from kazikasi.sources.kenya_p2 import Ajira, CareerPoint, P2, TSC
from kazikasi.sources.structured import StructuredSource

FIXTURES = Path(__file__).parent / "fixtures"
LISTING = "https://www.careerpointkenya.co.ke/"
DETAIL = "https://www.careerpointkenya.co.ke/job/records-assistant-nairobi-county-teaching-hospital"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


class TestRegistry:
    def test_the_three_p2_sources_are_registered(self):
        assert {"careerpoint", "tsc", "ajira"} <= set(REGISTRY)

    def test_every_p2_source_is_unverified(self):
        for key, cls in P2.items():
            assert cls.manifest.status == "unverified", key

    def test_an_unverified_manifest_says_why_in_prose(self):
        for key, cls in P2.items():
            notes = cls.manifest.notes.lower()
            assert "unverified" in notes, key
            assert "terms" in notes, key

    def test_the_existing_sources_stay_active(self):
        for key in ("brightermonday", "fuzu", "myjobmag", "psc", "reliefweb"):
            assert REGISTRY[key].manifest.status == "active", key

    def test_the_listing_reports_status(self, capsys):
        assert cli.main(["sources"]) == 0
        import json

        rows = {row["id"]: row for row in json.loads(capsys.readouterr().out)}
        assert rows["careerpoint"]["status"] == "unverified"
        assert rows["brightermonday"]["status"] == "active"


class TestStructuredListing:
    def test_jsonld_item_list_wins_and_is_canonicalised(self):
        links = CareerPoint().parse_listing(fixture("careerpoint-listing.html"), LISTING)
        assert len(links) == 2
        assert all(link.startswith("https://www.careerpointkenya.co.ke/job/") for link in links)
        assert not any("utm_" in link for link in links)

    def test_anchors_are_the_fallback_when_there_is_no_jsonld(self):
        html = """<html><body>
          <h2><a href="/job/office-assistant-nairobi/">Office Assistant</a></h2>
          <a href="/about">About us</a>
        </body></html>"""
        links = CareerPoint().parse_listing(html, LISTING)
        assert links == ["https://www.careerpointkenya.co.ke/job/office-assistant-nairobi"]

    def test_a_page_with_no_postings_yields_nothing(self):
        assert CareerPoint().parse_listing("<html><body><p>No vacancies.</p></body></html>", LISTING) == []

    def test_a_hostile_listing_is_capped(self):
        html = "<html><body>" + "".join(
            f'<a href="/job/role-{index}">Role {index}</a>' for index in range(200)
        ) + "</body></html>"
        assert len(CareerPoint().parse_listing(html, LISTING)) == 60


class TestStructuredDetail:
    def test_jsonld_is_read_into_the_candidate(self):
        candidate = CareerPoint().parse_detail(fixture("careerpoint-detail.html"), DETAIL)
        assert candidate.title == "Records Assistant"
        assert candidate.employer_name == "Nairobi County Teaching Hospital"
        assert candidate.employer_domain == "ncth.go.ke"
        assert candidate.county == "Nairobi"
        assert str(candidate.deadline) == "2026-11-05"
        assert candidate.source_id == "careerpoint"

    def test_prose_fields_are_marked_as_prose(self):
        candidate = CareerPoint().parse_detail(fixture("careerpoint-detail.html"), DETAIL)
        assert candidate.pay.min_amount == 45000
        assert "pay_from_prose" in candidate.parser_notes
        assert candidate.entry_fit == "open_to_freshers"

    def test_a_page_without_a_title_falls_back_to_the_document_title(self):
        html = "<html><head><title>Finance Assistant at Sanaa Capital</title></head><body><p>Short advert.</p></body></html>"
        candidate = CareerPoint().parse_detail(html, "https://www.careerpointkenya.co.ke/job/x/")
        assert candidate.title == "Finance Assistant at Sanaa Capital"
        assert "title_from_page_title" in candidate.parser_notes

    def test_a_default_employer_is_used_only_when_silent_and_is_disclosed(self):
        class SingleEmployer(StructuredSource):
            from kazikasi.sources.base import Manifest

            manifest = Manifest(
                id="single", label="Single employer", access="public_html",
                tier="cold", cadence_minutes=60,
                listing_urls=("https://single.test/jobs",),
            )
            detail_pattern = "/job/"
            default_employer = "Ajira Digital"

        html = "<html><body><h1>Programme Officer</h1><p>" + ("Duties. " * 40) + "</p></body></html>"
        candidate = SingleEmployer().parse_detail(html, "https://single.test/job/programme-officer")
        assert candidate.employer_name == "Ajira Digital"
        assert "employer_from_manifest" in candidate.parser_notes

    def test_nothing_raises_on_broken_markup(self):
        candidate = CareerPoint().parse_detail("<html><body><h1>", "https://x.test/job/1")
        assert candidate.source_id == "careerpoint"
        assert "no_description" in candidate.parser_notes

    def test_it_is_a_structured_source(self):
        assert isinstance(CareerPoint(), StructuredSource)


class TestDocumentSources:
    def test_tsc_takes_the_advert_and_leaves_the_paperwork(self):
        links = TSC().parse_listing(fixture("tsc-listing.html"), "https://www.tsc.go.ke/")
        assert links == ["https://www.tsc.go.ke/downloads/tsc-advert-teachers-2026-11.pdf"]

    def test_ajira_takes_opportunities_and_programme_documents(self):
        links = Ajira().parse_listing(fixture("ajira-listing.html"), "https://ajira.go.ke/")
        assert any("/opportunities/" in link for link in links)
        assert any(link.endswith(".pdf") for link in links)
        assert not any("/registration" in link or "/faq" in link for link in links)

    def test_tsc_reads_a_real_advert_document(self, tmp_path):
        from kazikasi.sources.base import Payload

        raw = (FIXTURES / "psc-advert.pdf").read_bytes()
        payload = Payload(url="https://www.tsc.go.ke/downloads/tsc-advert-teachers-2026-11.pdf",
                          raw=raw, content_type="application/pdf")
        candidates = TSC().parse_payload(payload, payload.url)
        assert candidates
        assert all(candidate.source_id == "tsc" for candidate in candidates)


class TestTheGate:
    def test_ingest_refuses_an_unverified_source(self, tmp_path):
        fetcher = FixtureFetcher({LISTING: FIXTURES / "careerpoint-listing.html"})
        with pytest.raises(UnverifiedSource) as excinfo:
            ingest(CareerPoint(), fetcher, FileRawStore(tmp_path))
        message = str(excinfo.value)
        assert "canary --source careerpoint --live" in message
        assert "unverified" in message

    def test_the_gate_can_be_opened_deliberately(self, tmp_path):
        fetcher = FixtureFetcher(
            {
                LISTING: FIXTURES / "careerpoint-listing.html",
                DETAIL: FIXTURES / "careerpoint-detail.html",
                "https://www.careerpointkenya.co.ke/job/programme-assistant-internship-kwale": FIXTURES / "careerpoint-detail.html",
            }
        )
        report = ingest(
            CareerPoint(), fetcher, FileRawStore(tmp_path), limit=1, allow_unverified=True
        )
        assert report.parsed == 1
        assert report.candidates[0].title == "Records Assistant"

    def test_the_cli_exposes_the_flag(self):
        assert cli.main(["ingest", "--source", "careerpoint", "--allow-unverified", "--limit", "0"]) in (0, 1)

    def test_active_sources_need_no_flag(self, tmp_path):
        fetcher = FixtureFetcher(
            {
                "https://www.brightermonday.co.ke/jobs": FIXTURES / "brightermonday-listing.html",
            }
        )
        report = ingest(REGISTRY["brightermonday"](), fetcher, FileRawStore(tmp_path), limit=0)
        assert report.listing_pages == 1

    def test_the_gate_does_not_depend_on_an_attribute_being_present(self, tmp_path):
        """An adapter built before `status` existed must still ingest."""

        class Legacy(StructuredSource):
            from kazikasi.sources.base import Manifest

            manifest = Manifest(
                id="legacy",
                label="Legacy",
                access="public_html",
                tier="cold",
                cadence_minutes=60,
                listing_urls=(LISTING,),
            )

        fetcher = FixtureFetcher({LISTING: FIXTURES / "careerpoint-listing.html"})
        report = ingest(Legacy(), fetcher, FileRawStore(tmp_path), limit=0)
        assert report.listing_pages == 1
