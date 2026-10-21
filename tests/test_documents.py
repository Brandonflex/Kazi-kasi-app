"""The document lane: PDFs and bulletin pages → one candidate per post."""

from datetime import date

import pytest

from kazikasi.documents import (
    DocumentError,
    bytes_to_text,
    document_to_candidates,
    is_bulletin,
    parse_bulletin,
    parse_single_advert,
    split_bulletin,
)


def read(fixtures, name):
    return (fixtures / name).read_bytes()


class TestBytesToText:
    def test_pdf_text_is_extracted(self, fixtures):
        text = bytes_to_text(read(fixtures, "psc-advert.pdf"), "application/pdf")
        assert "PUBLIC SERVICE COMMISSION" in text
        assert "VACANCY NO. 1/2026" in text

    def test_html_is_flattened_with_line_structure(self, fixtures):
        text = bytes_to_text(read(fixtures, "nairobi-advert.html"), "text/html")
        assert "VACANCY NO. NCCG/HR/45/2026" in text
        # Heading and body must stay on different lines or nothing splits.
        assert "\n" in text
        assert any(line.startswith("Salary:") for line in text.splitlines())

    def test_empty_document_raises(self):
        with pytest.raises(DocumentError):
            bytes_to_text(b"", "application/pdf")

    def test_pdf_without_a_text_layer_raises(self):
        # A PDF header with no readable objects: the honest answer is "scan",
        # not a silent empty job.
        with pytest.raises(DocumentError):
            bytes_to_text(b"%PDF-1.4\nnot really a pdf\n", "application/pdf")


class TestSplitBulletin:
    def test_vacancy_number_headings(self, fixtures):
        text = bytes_to_text(read(fixtures, "psc-advert.pdf"), "application/pdf")
        sections = split_bulletin(text)
        assert [section["ref"] for section in sections] == ["1/2026", "2/2026", "3/2026"]
        assert sections[0]["title"] == "ASSISTANT OFFICE ADMINISTRATOR"
        assert "SENIOR ICT OFFICER" in sections[2]["title"]

    def test_numbered_headings(self, fixtures):
        text = bytes_to_text(read(fixtures, "nairobi-advert.pdf"), "application/pdf")
        sections = split_bulletin(text)
        assert len(sections) == 2
        assert sections[1]["title"].startswith("DRIVER")

    def test_a_single_advert_has_no_sections(self):
        assert split_bulletin("We are hiring a records clerk. Apply by email.") == []

    def test_is_bulletin(self, fixtures):
        text = bytes_to_text(read(fixtures, "psc-advert.pdf"), "application/pdf")
        assert is_bulletin(text)
        assert not is_bulletin("A single paragraph of prose about one job.")


class TestParseBulletin:
    @pytest.fixture
    def candidates(self, fixtures):
        text = bytes_to_text(read(fixtures, "psc-advert.pdf"), "application/pdf")
        return parse_bulletin(
            text,
            source_id="psc",
            source_url="https://www.psckjobs.go.ke/downloads/vacancies/psc-advert-october-2026.pdf",
            employer="Public Service Commission of Kenya",
            county="Nairobi",
        )

    def test_one_advert_becomes_three_posts(self, candidates):
        assert len(candidates) == 3
        assert len({candidate.source_job_id for candidate in candidates}) == 3

    def test_posts_are_distinguishable_by_reference(self, candidates):
        refs = [candidate.reference for candidate in candidates]
        assert refs == [
            "public-service-commission-of-kenya/1/2026",
            "public-service-commission-of-kenya/2/2026",
            "public-service-commission-of-kenya/3/2026",
        ]

    def test_shared_closing_date_is_applied_to_every_post(self, candidates):
        assert all(candidate.deadline == date(2026, 11, 12) for candidate in candidates)

    def test_salary_scale_is_parsed(self, candidates):
        assert candidates[0].pay.min_amount == 38270
        assert candidates[0].pay.max_amount == 49950
        assert candidates[0].pay.period == "month"

    def test_eligibility_differs_per_post(self, candidates):
        assert [candidate.entry_fit for candidate in candidates] == [
            "some_experience",
            "open_to_freshers",
            "experienced",
        ]

    def test_titles_are_not_shouted(self, candidates):
        assert candidates[0].title == "Assistant Office Administrator"
        assert candidates[2].title == "Senior ICT Officer"

    def test_post_counts_are_kept_as_notes(self, candidates):
        assert "posts=3" in candidates[0].parser_notes
        assert "posts=5" in candidates[1].parser_notes

    def test_requirements_are_quoted_as_evidence(self, candidates):
        assert "no prior work experience" in candidates[1].entry_fit_evidence.lower()

    def test_bulletins_produce_no_scam_flags_by_default(self, candidates):
        assert all(candidate.scam_flags == [] for candidate in candidates)


class TestSingleAdvertFallback:
    def test_a_one_job_document_still_parses(self):
        text = (
            "We are hiring a Records Clerk for our Nairobi office.\n"
            "Salary: KSh. 35,000 per month.\n"
            "Fresh graduates are encouraged to apply.\n"
            "Deadline: 30 November 2026."
        )
        candidates = parse_single_advert(
            text, source_id="county", source_url="https://example.go.ke/a.pdf", employer="Example County"
        )
        assert len(candidates) == 1
        assert candidates[0].title.startswith("We are hiring a Records Clerk")
        assert candidates[0].entry_fit == "open_to_freshers"
        assert candidates[0].deadline == date(2026, 11, 30)
        assert candidates[0].county == "Nairobi"

    def test_document_to_candidates_prefers_the_bulletin_path(self, fixtures):
        candidates = document_to_candidates(
            read(fixtures, "psc-advert.pdf"),
            source_id="psc",
            source_url="u",
            content_type="application/pdf",
            employer="Public Service Commission of Kenya",
        )
        assert len(candidates) == 3
        assert all("bulletin" in candidate.parser_notes for candidate in candidates)
