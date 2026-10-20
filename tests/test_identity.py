"""Identity resolution, stage 1 (deterministic)."""

from datetime import date

from kazikasi.identity import (
    apply_target,
    ats_requisition,
    canonicalize_url,
    dedupe_key,
    employer_key,
    same_job_stage1,
)
from kazikasi.models import JobCandidate


def job(**kwargs) -> JobCandidate:
    base = dict(
        source_id="myjobmag",
        source_job_id="1",
        source_url="https://www.myjobmag.co.ke/job/records-clerk-nairobi-1",
        title="Records Clerk",
        employer_name="Haba Data Systems Ltd",
        county="Nairobi",
    )
    base.update(kwargs)
    return JobCandidate(**base)


class TestCanonicalUrl:
    def test_strips_tracking_and_sorts_query(self):
        url = canonicalize_url(
            "https://WWW.BrighterMonday.co.ke/listings/x?utm_source=feed&b=2&a=1#apply"
        )
        assert url == "https://www.brightermonday.co.ke/listings/x?a=1&b=2"

    def test_same_job_different_campaigns_collapses(self):
        a = canonicalize_url("https://example.co.ke/job/1?utm_source=fb&ref=card")
        b = canonicalize_url("https://example.co.ke/job/1")
        assert a == b

    def test_keeps_meaningful_params(self):
        url = canonicalize_url("https://example.co.ke/jobs?page=2&q=data")
        assert "page=2" in url and "q=data" in url


class TestEmployerKey:
    def test_legal_suffixes_ignored(self):
        assert employer_key("Haba Data Systems Ltd") == employer_key("Haba Data Systems Limited")

    def test_domain_wins(self):
        assert employer_key("Haba", "habadata.co.ke") == "domain:habadata.co.ke"

    def test_www_stripped(self):
        assert employer_key(None, "www.rescue.org") == employer_key(None, "rescue.org")


class TestApplyTarget:
    def test_reference_beats_everything(self):
        candidate = job(reference="V/No. 12/2026", apply_url="https://x.co.ke/a")
        assert apply_target(candidate) == "ref:v/no. 12/2026"

    def test_email_next(self):
        candidate = job(apply_emails=["hr@habadata.co.ke"])
        assert apply_target(candidate) == "email:hr@habadata.co.ke"

    def test_ats_requisition_recognised(self):
        candidate = job(apply_url="https://boards.greenhouse.io/haba/jobs/4012345")
        assert ats_requisition(candidate.apply_url) == ("haba", "4012345")
        assert apply_target(candidate) == "ats:haba:4012345"

    def test_falls_back_to_source_url(self):
        assert apply_target(job()).startswith("url:https://www.myjobmag.co.ke/job/")


class TestSameJob:
    def test_same_posting_on_two_boards_with_same_apply_email(self):
        a = job(source_id="brightermonday", source_job_id="A", apply_emails=["hr@haba.co.ke"])
        b = job(source_id="myjobmag", source_job_id="B", apply_emails=["hr@haba.co.ke"])
        assert same_job_stage1(a, b)

    def test_same_title_and_employer_different_deadline_is_not_a_duplicate(self):
        # In the public sector these are usually two different posts.
        a = job(deadline=date(2026, 11, 1))
        b = job(deadline=date(2026, 12, 1), source_id="brightermonday", source_job_id="2")
        assert not same_job_stage1(a, b)

    def test_deadline_is_part_of_the_key(self):
        assert dedupe_key(job(deadline=date(2026, 11, 1))) != dedupe_key(
            job(deadline=date(2026, 12, 1))
        )

    def test_employer_rename_with_same_domain_still_matches(self):
        a = job(employer_name="Haba Data Systems Ltd", employer_domain="habadata.co.ke")
        b = job(
            employer_name="Haba Data",
            employer_domain="habadata.co.ke",
            source_id="brightermonday",
            source_job_id="9",
        )
        assert same_job_stage1(a, b)

    def test_different_jobs_stay_different(self):
        a = job(title="Records Clerk")
        b = job(title="Finance Assistant", source_id="brightermonday", source_job_id="3")
        assert not same_job_stage1(a, b)
