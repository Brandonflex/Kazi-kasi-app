"""Unit tests for the deterministic extractors.

These are the rules the product's trust story rests on, so they are tested
against the awkward inputs rather than the tidy ones.
"""

from datetime import date

import pytest

from kazikasi.extract import (
    clean_text,
    detect_employment_type,
    detect_scam_flags,
    detect_seniority,
    detect_work_mode,
    entry_fit,
    extract_jobpostings,
    find_deadline,
    find_emails,
    find_pay_text,
    find_reference,
    jsonld_to_candidate_fields,
    parse_date,
    parse_location,
    parse_pay,
    scam_level,
    to_monthly,
)

TODAY = date(2026, 10, 20)


class TestCleanText:
    def test_collapses_whitespace_and_nbsp(self):
        assert clean_text("  Hello\u00a0\n\n  world  ") == "Hello world"

    def test_handles_none(self):
        assert clean_text(None) == ""


class TestParseDate:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("2026-11-05", date(2026, 11, 5)),
            ("30 November 2026", date(2026, 11, 30)),
            ("5th November 2026", date(2026, 11, 5)),
            ("Oct 14, 2026", date(2026, 10, 14)),
            ("2026-10-31T00:00:00+00:00", date(2026, 10, 31)),
            ("5/11/2026", date(2026, 11, 5)),
        ],
    )
    def test_parses_real_formats(self, value, expected):
        assert parse_date(value) == expected

    def test_reads_a_date_inside_a_sentence(self):
        assert parse_date("30 November 2026. Send your application", TODAY) == date(2026, 11, 30)

    def test_relative_dates(self):
        assert parse_date("Posted 3 days ago", TODAY) == date(2026, 10, 17)

    def test_unparseable_is_none_not_guess(self):
        assert parse_date("Apply soon", TODAY) is None
        assert parse_date("", TODAY) is None


class TestFindDeadline:
    def test_labelled_deadline(self):
        text = "Deadline for applications: 30 November 2026. Send your CV to a@b.co.ke"
        assert find_deadline(text) == date(2026, 11, 30)

    def test_unlabelled_date_is_not_a_deadline(self):
        # A posting date must never be promoted to a closing date: it would
        # silently close a live job.
        assert find_deadline("Posted 14 Oct 2026") is None


class TestParsePay:
    def test_range_per_month(self):
        pay = parse_pay("KSh 55,000 - 75,000 per month")
        assert (pay.min_amount, pay.max_amount) == (55000.0, 75000.0)
        assert pay.currency == "KES" and pay.period == "month"

    def test_ksh_variant(self):
        assert parse_pay("KSh 20,000 per month").min_amount == 20000.0

    def test_daily_wage(self):
        pay = parse_pay("KES 3,000 per day")
        assert pay.period == "day"
        assert to_monthly(pay) == pytest.approx(66000.0)

    def test_confidential_is_empty_with_zero_confidence(self):
        pay = parse_pay("Confidential")
        assert pay.is_empty and pay.confidence == 0.0

    def test_find_pay_text_in_prose(self):
        text = "We are a logistics firm. A stipend of KSh 20,000 per month is provided."
        assert "20,000" in find_pay_text(text)

    def test_find_pay_text_returns_none_when_absent(self):
        assert find_pay_text("We are hiring. Apply by email.") is None


class TestEntryFit:
    def test_explicit_fresher_language_quotes_evidence(self):
        label, evidence, confidence = entry_fit(
            "Fresh graduates are encouraged to apply. No prior work experience required."
        )
        assert label == "open_to_freshers"
        assert evidence and "Fresh graduates" in evidence
        assert confidence > 0.7

    def test_experience_demand(self):
        label, evidence, _ = entry_fit("A minimum of five years of relevant experience is required.")
        assert label == "experienced"
        assert evidence

    def test_unknown_instead_of_guessing(self):
        label, evidence, confidence = entry_fit("We are a company that does things.")
        assert label == "unknown"
        assert evidence is None and confidence == 0.0


class TestLocation:
    @pytest.mark.parametrize(
        "raw,county",
        [
            ("Nairobi", "Nairobi"),
            ("Westlands, Nairobi", "Nairobi"),
            ("Nairobi County", "Nairobi"),
            ("Mombasa", "Mombasa"),
            ("Industrial Area, Nairobi", "Nairobi"),
            ("Kisumu, Kenya", "Kisumu"),
        ],
    )
    def test_county_resolution(self, raw, county):
        assert parse_location(raw)[0] == county

    def test_sub_county(self):
        assert parse_location("Westlands, Nairobi")[1] == "Westlands"

    def test_remote_is_not_a_county(self):
        assert parse_location("Remote")[0] is None


class TestWorkModeAndEmployment:
    def test_hybrid(self):
        assert detect_work_mode("This role is hybrid, three days in office.", "Nairobi")[0] == "hybrid"

    def test_remote(self):
        assert detect_work_mode("Fully remote role.", "Nairobi")[0] == "remote"

    def test_default_onsite_with_reason(self):
        mode, source = detect_work_mode("You will report to the depot daily.", "Nairobi")
        assert mode == "onsite" and source

    def test_internship_beats_full_time(self):
        assert detect_employment_type("Full time internship for six months") == "internship"

    def test_attachment(self):
        assert detect_employment_type("Industrial attachment opportunity") == "attachment"


class TestSeniority:
    def test_management_title(self):
        assert detect_seniority("Senior Finance Manager") == "lead"

    def test_trainee_reads_as_intern(self):
        # Graduate trainee programmes are the main entry funnel in Nairobi; the
        # ladder label matters less than never surfacing them as senior.
        assert detect_seniority("Graduate Trainee Programme") == "intern"

    def test_plain_clerk_is_junior(self):
        assert detect_seniority("Records Clerk") == "junior"

    def test_prefix_senior(self):
        assert detect_seniority("Senior Accountant") == "senior"

    def test_no_signal_is_unknown(self):
        assert detect_seniority("Software Support Analyst") == "unknown"


class TestScamSignals:
    def test_fee_request_is_flagged_with_quote(self):
        flags, evidence = detect_scam_flags(
            "Send a registration fee of KSh 500 via M-Pesa before training.",
            employer_name="Acme",
        )
        assert "fee_requested" in flags
        assert "registration fee" in evidence["fee_requested"].lower()
        assert scam_level(flags) == "likely_scam"

    def test_clean_posting_has_no_flags(self):
        flags, _ = detect_scam_flags(
            "Send your CV to careers@habadata.co.ke.",
            employer_name="Haba Data Systems Ltd",
            employer_domain="habadata.co.ke",
        )
        assert flags == []

    def test_domain_mismatch_is_named(self):
        flags, evidence = detect_scam_flags(
            "Apply to hr@gmail.com",
            employer_domain="habadata.co.ke",
            employer_name="Haba Data Systems Ltd",
        )
        assert "domain_mismatch" in flags
        assert "gmail.com" in evidence["domain_mismatch"]

    def test_no_employer_identity(self):
        flags, _ = detect_scam_flags("Urgent data entry clerks wanted.", employer_name=None)
        assert "no_employer_identity" in flags


class TestContacts:
    def test_emails_lowercased_and_unique(self):
        assert find_emails("Mail A@B.co.ke or a@b.co.ke") == ["a@b.co.ke"]

    def test_psc_vacancy_number(self):
        assert find_reference("V/No. 12/2026") == "12/2026"

    def test_generic_reference(self):
        assert find_reference("Ref No: KFCB/HR/07/2026").startswith("KFCB")


class TestJsonLd:
    def test_extracts_jobposting_from_graph(self, fixtures):
        html = (fixtures / "brightermonday-detail.html").read_text()
        postings = extract_jobpostings(html)
        assert len(postings) == 1
        fields = jsonld_to_candidate_fields(postings[0])
        assert fields["title"] == "Software Support Analyst"
        assert fields["employer_name"] == "Haba Data Systems Ltd"
        assert fields["deadline_text"] == "2026-11-05"
        assert fields["identifier"] == "BM-1029384"
        assert "55000" in fields["pay_text"]

    def test_page_without_jsonld(self, fixtures):
        html = (fixtures / "myjobmag-detail.html").read_text()
        assert extract_jobpostings(html) == []
