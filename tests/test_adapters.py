"""Adapter tests: listing extraction, JSON-LD path, selector fallback, scam text."""

from datetime import date

from kazikasi.sources import BrighterMonday, Fuzu, MyJobMag, ReliefWeb
from kazikasi.sources.boards import BOARDS


def read(fixtures, name):
    return (fixtures / name).read_text()


class TestRegistrations:
    def test_all_four_sources_registered(self):
        assert set(BOARDS) == {"brightermonday", "fuzu", "myjobmag"}
        assert ReliefWeb.manifest.access == "public_json_api"

    def test_every_manifest_has_a_review_date(self):
        # The legal posture must never drift away from the code.
        for cls in (*BOARDS.values(), ReliefWeb):
            assert cls.manifest.terms_reviewed_at
            assert cls.manifest.cadence_minutes > 0


class TestListingExtraction:
    def test_brightermonday_links_deduped_across_tracking_params(self, fixtures):
        adapter = BrighterMonday()
        urls = adapter.parse_listing(
            read(fixtures, "brightermonday-listing.html"), "https://www.brightermonday.co.ke/jobs"
        )
        assert len(urls) == 3
        assert not any("utm_source" in u for u in urls)
        assert all(u.startswith("https://www.brightermonday.co.ke/listings/") for u in urls)

    def test_myjobmag_ignores_off_pattern_links(self, fixtures):
        adapter = MyJobMag()
        urls = adapter.parse_listing(
            read(fixtures, "myjobmag-listing.html"), "https://www.myjobmag.co.ke/jobs"
        )
        assert len(urls) == 3
        assert all("/job/" in u for u in urls)
        assert not any("utm_campaign" in u for u in urls)

    def test_pagination_builds_next_page_urls(self):
        assert BrighterMonday().listing_urls(2) == ["https://www.brightermonday.co.ke/jobs?page=2"]

    def test_unknown_board_is_not_registered(self):
        assert Fuzu.manifest.id == "fuzu"


class TestJsonLdDetail:
    def test_full_extraction(self, fixtures):
        candidate = BrighterMonday().parse_detail(
            read(fixtures, "brightermonday-detail.html"),
            "https://www.brightermonday.co.ke/listings/software-support-analyst-westlands-1029384",
        )
        assert candidate.title == "Software Support Analyst"
        assert candidate.employer_name == "Haba Data Systems Ltd"
        assert candidate.employer_domain == "habadata.co.ke"
        assert candidate.county == "Nairobi"
        assert candidate.sub_county == "Westlands"
        assert candidate.employment_type == "full_time"
        assert candidate.deadline == date(2026, 11, 5)
        assert candidate.date_posted_claimed == date(2026, 10, 14)
        assert candidate.pay.min_amount == 55000
        assert candidate.apply_emails == ["careers@habadata.co.ke"]
        assert candidate.extraction_confidence == 1.0
        assert candidate.scam_flags == []

    def test_entry_fit_quotes_the_posting(self, fixtures):
        candidate = BrighterMonday().parse_detail(
            read(fixtures, "brightermonday-detail.html"),
            "https://www.brightermonday.co.ke/listings/x",
        )
        assert candidate.entry_fit == "open_to_freshers"
        assert candidate.entry_fit_evidence
        assert "Fresh graduates" in candidate.entry_fit_evidence

    def test_identifier_comes_from_jsonld(self, fixtures):
        candidate = BrighterMonday().parse_detail(
            read(fixtures, "brightermonday-detail.html"),
            "https://www.brightermonday.co.ke/listings/x",
        )
        assert candidate.source_job_id == "BM-1029384"


class TestSelectorFallback:
    def test_no_jsonld_still_yields_a_candidate(self, fixtures):
        candidate = MyJobMag().parse_detail(
            read(fixtures, "myjobmag-detail.html"),
            "https://www.myjobmag.co.ke/job/marketing-intern-nairobi-88213",
        )
        assert "no_jsonld" in candidate.parser_notes
        assert candidate.extraction_confidence < 1.0
        assert candidate.title == "Marketing Intern"
        assert candidate.employer_name == "Mwangaza Logistics"
        assert candidate.county == "Nairobi"
        # "Industrial Area" is not a sub-county; it resolves to Starehe rather
        # than being stored as if it were one.
        assert candidate.sub_county == "Starehe"
        assert "Industrial Area" in candidate.location_raw

    def test_deadline_recovered_from_prose_and_labelled(self, fixtures):
        candidate = MyJobMag().parse_detail(
            read(fixtures, "myjobmag-detail.html"),
            "https://www.myjobmag.co.ke/job/marketing-intern-nairobi-88213",
        )
        assert candidate.deadline == date(2026, 11, 30)
        assert "deadline_from_prose" in candidate.parser_notes

    def test_stipend_recovered_from_prose(self, fixtures):
        candidate = MyJobMag().parse_detail(
            read(fixtures, "myjobmag-detail.html"),
            "https://www.myjobmag.co.ke/job/marketing-intern-nairobi-88213",
        )
        assert candidate.pay.min_amount == 20000
        assert "pay_from_prose" in candidate.parser_notes

    def test_internship_type_detected(self, fixtures):
        candidate = MyJobMag().parse_detail(
            read(fixtures, "myjobmag-detail.html"),
            "https://www.myjobmag.co.ke/job/marketing-intern-nairobi-88213",
        )
        assert candidate.employment_type == "internship"
        assert candidate.entry_fit == "open_to_freshers"


class TestSuspiciousPosting:
    def test_flags_carry_quoted_evidence(self, fixtures):
        candidate = MyJobMag().parse_detail(
            read(fixtures, "suspicious-detail.html"),
            "https://www.myjobmag.co.ke/job/urgent-data-entry-99999",
        )
        assert "fee_requested" in candidate.scam_flags
        assert "whatsapp_only" in candidate.scam_flags
        assert "no_employer_identity" in candidate.scam_flags
        for flag in candidate.scam_flags:
            assert candidate.scam_evidence.get(flag), f"{flag} has no evidence"


class TestReliefWeb:
    def test_request_body_uses_v2_and_appname(self):
        adapter = ReliefWeb(appname="kazikasi")
        body = adapter.request_body()
        assert body["appname"] == "kazikasi"
        assert body["filter"]["value"] == ["Kenya"]
        assert "date.closing" in body["fields"]["include"]

    def test_item_mapping(self, fixtures):
        adapter = ReliefWeb(appname="kazikasi")
        items = adapter.parse_listing(read(fixtures, "reliefweb-jobs.json"))
        assert len(items) == 2

        entry = adapter.item_to_candidate(items[0])
        assert entry.title == "Programme Assistant"
        assert entry.employer_name == "UN Office for the Coordination of Humanitarian Affairs"
        assert entry.employer_domain == "unocha.org"
        assert entry.county == "Nairobi"
        assert entry.deadline == date(2026, 10, 31)
        assert entry.source_job_id == "4100231"
        assert entry.entry_fit == "some_experience"
        assert entry.scam_flags == []

        senior = adapter.item_to_candidate(items[1])
        assert senior.entry_fit == "experienced"
        assert senior.seniority == "lead"
