"""Additional Kenyan job sources.

Expanding coverage beyond the initial 9 sources to 15+ total.
Includes major boards, NGO/development sector, and direct employer feeds.
"""

from __future__ import annotations

import re
from typing import Any

from ..extract import (
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
    html_to_text,
    jsonld_to_candidate_fields,
    parse_date,
    parse_html,
    parse_location,
    parse_pay,
)
from ..models import JobCandidate
from .base import Adapter, Manifest


def _source_job_id(url: str) -> str:
    """Stable per-source key derived from the posting URL path."""
    from urllib.parse import unquote, urlsplit

    return unquote(urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]) or url


def _location_parts(value: str | None) -> tuple[str | None, str | None, str]:
    """Expose the current county/sub-county/raw tuple used by the extractor."""
    return parse_location(value)


def _date_value(value):
    """Normalize JSON-LD date strings while leaving parsed date objects alone."""
    return parse_date(value) if isinstance(value, str) and value else value


def _work_mode(text: str, location: str | None) -> tuple[str, str]:
    """Do not infer on-site work from a country-wide location like “Kenya”."""
    broad_location = (location or "").strip().lower() in {"kenya", "kenya, kenya"}
    return detect_work_mode(text, None if broad_location else location)


class JobWebKenya(Adapter):
    """JobWeb Kenya - major Kenyan job board.
    
    Source: https://jobwebkenya.com
    Focus: Entry to mid-level roles across sectors
    """
    
    source = "jobwebkenya"
    home = "https://jobwebkenya.com"
    listing = "https://jobwebkenya.com/job-listings/"
    detail_pattern = "/job/"
    
    manifest = Manifest(
        id="jobwebkenya", label="JobWeb Kenya", access="public_html", tier="cold",
        cadence_minutes=1440, rate_limit_per_minute=6,
        listing_urls=("https://jobwebkenya.com/job-listings/",), supports=('jsonld_detail', 'full_description'),
        notes="Live selectors and terms have not been verified.", status="unverified",
    )
    
    def parse_listing(self, html: str, base_url: str) -> list[str]:
        soup = parse_html(html)
        links = []
        for anchor in soup.select("a[href*='/job/']"):
            href = anchor.get("href")
            if href and href not in links:
                links.append(self._absolute(href, base_url))
        return links
    
    def parse_detail(self, html: str, url: str) -> JobCandidate:
        soup = parse_html(html)
        notes: list[str] = []
        
        jsonld = extract_jobpostings(html)
        jl: dict[str, Any] = jsonld_to_candidate_fields(jsonld[0]) if jsonld else {}
        if not jsonld:
            notes.append("no_jsonld")
        
        title = jl.get("title") or ""
        employer = jl.get("employer_name") or ""
        location = jl.get("location") or ""
        description = jl.get("description") or ""
        posted = jl.get("date_posted")
        deadline = jl.get("valid_through")
        
        # Fallback to CSS selectors
        if not title:
            title_el = soup.select_one("h1.job-title, h1.entry-title")
            if title_el:
                title = clean_text(title_el.get_text())
        
        if not employer:
            employer_el = soup.select_one(".company-name, .employer")
            if employer_el:
                employer = clean_text(employer_el.get_text())
        
        if not location:
            location_el = soup.select_one(".location, .job-location")
            if location_el:
                location = clean_text(location_el.get_text())
        
        if not description:
            desc_el = soup.select_one(".job-description, .entry-content")
            if desc_el:
                description = html_to_text(str(desc_el))
        
        pay_text = find_pay_text(description)
        deadline = deadline or find_deadline(description)
        emails = find_emails(description)
        reference = find_reference(" ".join((title, employer, url)))
        
        return JobCandidate(
            source_id=self.source,
            source_job_id=_source_job_id(url),
            source_url=url,
            title=title or "",
            employer_name=employer,
            county=_location_parts(location)[0],
            sub_county=_location_parts(location)[1],
            location_raw=_location_parts(location)[2],
            description_md=description,
            pay=parse_pay(pay_text) if pay_text else None,
            deadline=_date_value(deadline),
            date_posted_claimed=_date_value(posted),
            apply_emails=emails,
            reference=reference,
            employment_type=detect_employment_type(description),
            work_mode=_work_mode(description, location)[0],
            work_mode_source=_work_mode(description, location)[1],
            seniority=detect_seniority(title, description),
            entry_fit=entry_fit(f"{title}\n{description}")[0],
            scam_flags=detect_scam_flags(description),
            parser_notes=notes,
        )


class KenyaJobs(Adapter):
    """Kenya Jobs - aggregated job listings.
    
    Source: https://kenyajobs.com
    Focus: Broad coverage, all sectors
    """
    
    source = "kenyajobs"
    home = "https://kenyajobs.com"
    listing = "https://kenyajobs.com/jobs/"
    detail_pattern = "/jobs/"
    
    manifest = Manifest(
        id="kenyajobs", label="KenyaJobs", access="public_html", tier="cold",
        cadence_minutes=1440, rate_limit_per_minute=6,
        listing_urls=("https://kenyajobs.com/jobs/",), supports=('jsonld_detail', 'full_description'),
        notes="Live selectors and terms have not been verified.", status="unverified",
    )
    
    def parse_listing(self, html: str, base_url: str) -> list[str]:
        soup = parse_html(html)
        links = []
        for anchor in soup.select("a[href*='/jobs/']"):
            href = anchor.get("href")
            if href and href not in links:
                links.append(self._absolute(href, base_url))
        return links
    
    def parse_detail(self, html: str, url: str) -> JobCandidate:
        soup = parse_html(html)
        notes: list[str] = []
        
        jsonld = extract_jobpostings(html)
        jl: dict[str, Any] = jsonld_to_candidate_fields(jsonld[0]) if jsonld else {}
        if not jsonld:
            notes.append("no_jsonld")
        
        title = jl.get("title") or ""
        employer = jl.get("employer_name") or ""
        location = jl.get("location") or ""
        description = jl.get("description") or ""
        posted = jl.get("date_posted")
        deadline = jl.get("valid_through")
        
        if not title:
            title_el = soup.select_one("h1, .job-title")
            if title_el:
                title = clean_text(title_el.get_text())
        
        if not employer:
            employer_el = soup.select_one(".company, .employer-name")
            if employer_el:
                employer = clean_text(employer_el.get_text())
        
        if not location:
            location_el = soup.select_one(".location, .job-meta")
            if location_el:
                location = clean_text(location_el.get_text())
        
        if not description:
            desc_el = soup.select_one(".job-description, .content")
            if desc_el:
                description = html_to_text(str(desc_el))
        
        pay_text = find_pay_text(description)
        deadline = deadline or find_deadline(description)
        emails = find_emails(description)
        reference = find_reference(" ".join((title, employer, url)))
        
        return JobCandidate(
            source_id=self.source,
            source_job_id=_source_job_id(url),
            source_url=url,
            title=title or "",
            employer_name=employer,
            county=_location_parts(location)[0],
            sub_county=_location_parts(location)[1],
            location_raw=_location_parts(location)[2],
            description_md=description,
            pay=parse_pay(pay_text) if pay_text else None,
            deadline=_date_value(deadline),
            date_posted_claimed=_date_value(posted),
            apply_emails=emails,
            reference=reference,
            employment_type=detect_employment_type(description),
            work_mode=_work_mode(description, location)[0],
            work_mode_source=_work_mode(description, location)[1],
            seniority=detect_seniority(title, description),
            entry_fit=entry_fit(f"{title}\n{description}")[0],
            scam_flags=detect_scam_flags(description),
            parser_notes=notes,
        )


# Registry for additional sources
ADDITIONAL_SOURCES: dict[str, type[Adapter]] = {
    "jobwebkenya": JobWebKenya,
    "kenyajobs": KenyaJobs,
}


class UNJobsKenya(Adapter):
    """UN Jobs Kenya - United Nations careers in Kenya.
    
    Source: https://careers.un.org
    Focus: International organizations, NGOs, development sector
    """
    
    source = "unjobs_kenya"
    home = "https://careers.un.org"
    listing = "https://careers.un.org/lbw/home.aspx?viewtype=VJ&lc=KE"
    detail_pattern = "/lbp/"
    
    manifest = Manifest(
        id="unjobs_kenya", label="UN Careers - Kenya", access="public_html", tier="cold",
        cadence_minutes=1440, rate_limit_per_minute=4,
        listing_urls=("https://careers.un.org/lbw/home.aspx?viewtype=VJ&lc=KE",), supports=('jsonld_detail', 'full_description', 'deadline'),
        notes="The legacy listing path and page structure need live verification; terms have not been reviewed.", status="unverified",
    )
    
    def parse_listing(self, html: str, base_url: str) -> list[str]:
        soup = parse_html(html)
        links = []
        for anchor in soup.select("a[href*='/lbp/']"):
            href = anchor.get("href")
            if href and href not in links:
                links.append(self._absolute(href, base_url))
        return links
    
    def parse_detail(self, html: str, url: str) -> JobCandidate:
        soup = parse_html(html)
        notes: list[str] = []
        
        title = ""
        employer = "United Nations"
        location = "Kenya"
        description = ""
        
        title_el = soup.select_one("h1, .job-title")
        if title_el:
            title = clean_text(title_el.get_text())
        
        desc_el = soup.select_one(".job-description, .content, #content")
        if desc_el:
            description = html_to_text(str(desc_el))
        
        pay_text = find_pay_text(description)
        deadline = find_deadline(description)
        emails = find_emails(description)
        reference = find_reference(" ".join((title, employer, url)))
        
        return JobCandidate(
            source_id=self.source,
            source_job_id=_source_job_id(url),
            source_url=url,
            title=title,
            employer_name=employer,
            county=_location_parts(location)[0],
            location_raw=_location_parts(location)[2],
            description_md=description,
            pay=parse_pay(pay_text) if pay_text else None,
            deadline=_date_value(deadline),
            apply_emails=emails,
            reference=reference,
            employment_type=detect_employment_type(description),
            work_mode=_work_mode(description, location)[0],
            work_mode_source=_work_mode(description, location)[1],
            seniority=detect_seniority(title, description),
            entry_fit=entry_fit(f"{title}\n{description}")[0],
            scam_flags=detect_scam_flags(description),
            parser_notes=notes,
        )


class DevexKenya(Adapter):
    """Devex - Development sector jobs in Kenya.
    
    Source: https://devex.com
    Focus: International development, NGOs, aid organizations
    """
    
    source = "devex_kenya"
    home = "https://devex.com"
    listing = "https://devex.com/jobs?location=Kenya"
    detail_pattern = "/jobs/"
    
    manifest = Manifest(
        id="devex_kenya", label="Devex — Kenya development jobs", access="public_html", tier="cold",
        cadence_minutes=1440, rate_limit_per_minute=4,
        listing_urls=("https://www.devex.com/jobs?location=Kenya",), supports=('jsonld_detail', 'full_description', 'deadline'),
        notes="May require a Devex account and/or subscription. Access and terms have not been reviewed; do not ingest until verified.", status="unverified",
    )
    
    def parse_listing(self, html: str, base_url: str) -> list[str]:
        soup = parse_html(html)
        links = []
        for anchor in soup.select("a[href*='/jobs/']"):
            href = anchor.get("href")
            if href and href not in links:
                links.append(self._absolute(href, base_url))
        return links
    
    def parse_detail(self, html: str, url: str) -> JobCandidate:
        soup = parse_html(html)
        notes: list[str] = []
        
        title = ""
        employer = ""
        location = "Kenya"
        description = ""
        
        title_el = soup.select_one("h1, .job-title")
        if title_el:
            title = clean_text(title_el.get_text())
        
        employer_el = soup.select_one(".organization, .company-name")
        if employer_el:
            employer = clean_text(employer_el.get_text())
        
        desc_el = soup.select_one(".job-description, .content")
        if desc_el:
            description = html_to_text(str(desc_el))
        
        pay_text = find_pay_text(description)
        deadline = find_deadline(description)
        emails = find_emails(description)
        reference = find_reference(" ".join((title, employer, url)))
        
        return JobCandidate(
            source_id=self.source,
            source_job_id=_source_job_id(url),
            source_url=url,
            title=title,
            employer_name=employer,
            county=_location_parts(location)[0],
            location_raw=_location_parts(location)[2],
            description_md=description,
            pay=parse_pay(pay_text) if pay_text else None,
            deadline=_date_value(deadline),
            apply_emails=emails,
            reference=reference,
            employment_type=detect_employment_type(description),
            work_mode=_work_mode(description, location)[0],
            work_mode_source=_work_mode(description, location)[1],
            seniority=detect_seniority(title, description),
            entry_fit=entry_fit(f"{title}\n{description}")[0],
            scam_flags=detect_scam_flags(description),
            parser_notes=notes,
        )


# Update registry
ADDITIONAL_SOURCES.update({
    "unjobs_kenya": UNJobsKenya,
    "devex_kenya": DevexKenya,
})
