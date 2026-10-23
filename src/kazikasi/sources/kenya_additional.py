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


class JobWebKenya(Adapter):
    """JobWeb Kenya - major Kenyan job board.
    
    Source: https://jobwebkenya.com
    Focus: Entry to mid-level roles across sectors
    """
    
    source = "jobwebkenya"
    home = "https://jobwebkenya.com"
    listing = "https://jobwebkenya.com/job-listings/"
    detail_pattern = "/job/"
    
    @property
    def manifest(self) -> Manifest:
        return Manifest(
            source=self.source,
            listing_url=self.listing,
            detail_pattern=self.detail_pattern,
            cadence_days=1,
            priority=3,
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
        reference = find_reference(title, employer, url)
        
        return JobCandidate(
            source=self.source,
            url=url,
            title=title or "",
            employer=employer,
            county=parse_location(location).get("county"),
            town=parse_location(location).get("town"),
            description=description,
            pay_text=pay_text,
            pay=parse_pay(pay_text) if pay_text else None,
            deadline=deadline,
            posted=posted or None,
            emails=emails,
            reference=reference,
            employment_type=detect_employment_type(description),
            work_mode=detect_work_mode(description),
            seniority=detect_seniority(title, description),
            entry_fit=entry_fit(title, description),
            scam_flags=detect_scam_flags(description),
            parser_note=", ".join(notes) if notes else None,
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
    
    @property
    def manifest(self) -> Manifest:
        return Manifest(
            source=self.source,
            listing_url=self.listing,
            detail_pattern=self.detail_pattern,
            cadence_days=1,
            priority=3,
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
        reference = find_reference(title, employer, url)
        
        return JobCandidate(
            source=self.source,
            url=url,
            title=title or "",
            employer=employer,
            county=parse_location(location).get("county"),
            town=parse_location(location).get("town"),
            description=description,
            pay_text=pay_text,
            pay=parse_pay(pay_text) if pay_text else None,
            deadline=deadline,
            posted=posted or None,
            emails=emails,
            reference=reference,
            employment_type=detect_employment_type(description),
            work_mode=detect_work_mode(description),
            seniority=detect_seniority(title, description),
            entry_fit=entry_fit(title, description),
            scam_flags=detect_scam_flags(description),
            parser_note=", ".join(notes) if notes else None,
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
    
    @property
    def manifest(self) -> Manifest:
        return Manifest(
            source=self.source,
            listing_url=self.listing,
            detail_pattern=self.detail_pattern,
            cadence_days=3,
            priority=4,
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
        reference = find_reference(title, employer, url)
        
        return JobCandidate(
            source=self.source,
            url=url,
            title=title,
            employer=employer,
            county="Nairobi",
            description=description,
            pay_text=pay_text,
            pay=parse_pay(pay_text) if pay_text else None,
            deadline=deadline,
            emails=emails,
            reference=reference,
            employment_type=detect_employment_type(description),
            work_mode=detect_work_mode(description),
            seniority=detect_seniority(title, description),
            entry_fit=entry_fit(title, description),
            scam_flags=detect_scam_flags(description),
            parser_note=", ".join(notes) if notes else None,
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
    
    @property
    def manifest(self) -> Manifest:
        return Manifest(
            source=self.source,
            listing_url=self.listing,
            detail_pattern=self.detail_pattern,
            cadence_days=2,
            priority=4,
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
        reference = find_reference(title, employer, url)
        
        return JobCandidate(
            source=self.source,
            url=url,
            title=title,
            employer=employer,
            county="Nairobi",
            description=description,
            pay_text=pay_text,
            pay=parse_pay(pay_text) if pay_text else None,
            deadline=deadline,
            emails=emails,
            reference=reference,
            employment_type=detect_employment_type(description),
            work_mode=detect_work_mode(description),
            seniority=detect_seniority(title, description),
            entry_fit=entry_fit(title, description),
            scam_flags=detect_scam_flags(description),
            parser_note=", ".join(notes) if notes else None,
        )


# Update registry
ADDITIONAL_SOURCES.update({
    "unjobs_kenya": UNJobsKenya,
    "devex_kenya": DevexKenya,
})
