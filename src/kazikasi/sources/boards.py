"""Kenyan job board adapters.

Parsing strategy for every board, in order:

1. ``schema.org/JobPosting`` JSON-LD on the detail page (best: structural, survives redesigns).
2. Board-specific CSS selectors (documented inline, with fallbacks).
3. Whole-page text heuristics for the fields that are always prose
   (entry fit, scam signals, contacts).

Nothing here raises on unexpected markup: a partial candidate with a
``parser_note`` is worth more than an exception, because the note is what
triggers a schema-drift alarm later.
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


class HtmlBoardAdapter(Adapter):
    """Shared behaviour for the three boards."""

    listing_link_selector: str = ""
    title_selectors: tuple[str, ...] = ("h1",)
    employer_selectors: tuple[str, ...] = ()
    location_selectors: tuple[str, ...] = ()
    description_selectors: tuple[str, ...] = ()

    def parse_listing(self, html: str, base_url: str) -> list[str]:
        soup = parse_html(html)
        links: list[str] = []
        for anchor in soup.select(f"a[href*='{self.detail_pattern}']"):
            href = anchor.get("href")
            if href:
                links.append(self._absolute(href, base_url))
        if self.listing_link_selector:
            for anchor in soup.select(self.listing_link_selector):
                href = anchor.get("href")
                if href:
                    links.append(self._absolute(href, base_url))
        return self._dedupe_links(links)

    def _first_text(self, soup, selectors: tuple[str, ...]) -> str | None:
        for selector in selectors:
            node = soup.select_one(selector)
            if node:
                text = clean_text(node.get_text(" "))
                if text:
                    return text
        return None

    def _description(self, soup) -> tuple[str, str]:
        for selector in self.description_selectors:
            node = soup.select_one(selector)
            if node:
                text = html_to_text(str(node))
                if len(text) > 120:
                    return text, "html"
        # Fallback: the densest block of prose on the page.
        paragraphs = [html_to_text(str(p)) for p in soup.find_all("p")]
        joined = "\n\n".join(p for p in paragraphs if len(p) > 40)
        if len(joined) > 200:
            return joined, "html"
        return "", "html"

    def parse_detail(self, html: str, url: str) -> JobCandidate:
        soup = parse_html(html)
        notes: list[str] = []

        jsonld = extract_jobpostings(html)
        jl: dict[str, Any] = jsonld_to_candidate_fields(jsonld[0]) if jsonld else {}
        if not jsonld:
            notes.append("no_jsonld")

        title = jl.get("title") or self._first_text(soup, self.title_selectors) or ""
        employer = jl.get("employer_name") or self._first_text(soup, self.employer_selectors)
        location_raw = jl.get("location_raw") or self._first_text(soup, self.location_selectors)

        if jl.get("description_text"):
            description, desc_source = jl["description_text"], "html"
        else:
            description, desc_source = self._description(soup)
        if not description:
            notes.append("no_description")

        pay_text = jl.get("pay_text")
        if not pay_text:
            pay_text = self._first_text(
                soup,
                ("[class*='salary']", "[class*='Salary']", "[data-testid*='salary']"),
            )
        if not pay_text:
            pay_text = find_pay_text(description)
            if pay_text:
                notes.append("pay_from_prose")

        body_text = "\n".join(
            part for part in (title, employer, location_raw, description) if part
        )
        county, sub_county, raw_loc = parse_location(location_raw)
        if location_raw and not county:
            notes.append("county_unresolved")

        deadline = parse_date(jl.get("deadline_text"))
        if deadline is None:
            deadline = find_deadline(description)
            if deadline is not None:
                notes.append("deadline_from_prose")
        if deadline is None:
            notes.append("no_deadline")

        fit, fit_evidence, fit_conf = entry_fit(description or body_text)
        work_mode, work_mode_source = detect_work_mode(description, location_raw or "")
        employment_type = detect_employment_type(
            f"{jl.get('employment_type_text', '')} {description[:800]}",
            title=title,
        )

        emails = find_emails(description)
        reference = find_reference(f"{title}\n{description[:2000]}")
        flags, evidence = detect_scam_flags(
            description or body_text,
            emails=emails,
            employer_domain=jl.get("employer_domain"),
            employer_name=employer,
        )

        source_job_id = (
            jl.get("identifier")
            or _id_from_url(url, self.detail_pattern)
            or reference
            or url.rstrip("/").rsplit("/", 1)[-1]
        )

        confidence = 1.0
        if not jsonld:
            confidence -= 0.15
        if not description:
            confidence -= 0.25
        if not employer:
            confidence -= 0.15
            notes.append("no_employer")

        return JobCandidate(
            source_id=self.manifest.id,
            source_job_id=str(source_job_id),
            source_url=url,
            title=title,
            employer_name=employer,
            employer_domain=jl.get("employer_domain"),
            description_md=description or None,
            description_source=desc_source,
            extraction_confidence=max(0.0, round(confidence, 2)),
            seniority=detect_seniority(title, description[:400]),
            entry_fit=fit,
            entry_fit_evidence=fit_evidence,
            employment_type=employment_type,
            work_mode=work_mode,
            work_mode_source=work_mode_source,
            county=county,
            sub_county=sub_county,
            location_raw=raw_loc or None,
            pay=parse_pay(pay_text),
            date_posted_claimed=parse_date(jl.get("date_posted_text")),
            deadline=deadline,
            apply_emails=emails,
            reference=reference,
            apply_url=jl.get("apply_url"),
            scam_flags=flags,
            scam_evidence=evidence,
            status="extracted",
            parser_notes=notes + [f"entry_fit_conf={fit_conf}"],
        )


def _id_from_url(url: str, pattern: str) -> str | None:
    path = url.split("?", 1)[0].rstrip("/")
    tail = path.rsplit("/", 1)[-1]
    if tail and re.fullmatch(r"[\w\-]{4,}", tail):
        return tail
    return None


class BrighterMonday(HtmlBoardAdapter):
    manifest = Manifest(
        id="brightermonday",
        label="BrighterMonday Kenya",
        access="public_html",
        tier="hot",
        cadence_minutes=15,
        terms_reviewed_at="2026-10-20",
        rate_limit_per_minute=20,
        supports=("full_description", "deadline", "jsonld_detail", "stable_id"),
        listing_urls=("https://www.brightermonday.co.ke/jobs",),
        notes="Detail pages are reported to publish schema.org/JobPosting JSON-LD; "
        "salary is often 'Confidential'.",
    )
    detail_pattern = "/listings/"
    listing_link_selector = "a[href*='/listings/']"
    employer_selectors = ("[class*='company']", "[class*='employer']", "h2 a")
    location_selectors = ("[class*='location']", "[class*='Location']")
    description_selectors = (
        "[class*='description']",
        "[class*='job-detail']",
        "article",
        "main",
    )


class Fuzu(HtmlBoardAdapter):
    manifest = Manifest(
        id="fuzu",
        label="Fuzu Kenya",
        access="public_html",
        tier="hot",
        cadence_minutes=20,
        terms_reviewed_at="2026-10-20",
        rate_limit_per_minute=20,
        supports=("full_description", "deadline", "stable_id"),
        listing_urls=("https://www.fuzu.com/kenya/jobs",),
        notes="Country-scoped paths (/kenya). Some postings are 'Only on Fuzu'. "
        "Shows posting date and 'days left to apply'.",
    )
    detail_pattern = "/job/"
    listing_link_selector = "a[href*='/job/']"
    employer_selectors = ("[class*='company']", "[class*='Company']")
    location_selectors = ("[class*='location']",)
    description_selectors = ("[class*='description']", "article", "main")


class MyJobMag(HtmlBoardAdapter):
    manifest = Manifest(
        id="myjobmag",
        label="MyJobMag Kenya",
        access="public_html",
        tier="hot",
        cadence_minutes=20,
        terms_reviewed_at="2026-10-20",
        rate_limit_per_minute=20,
        supports=("full_description", "deadline", "stable_id"),
        listing_urls=("https://www.myjobmag.co.ke/jobs",),
        notes="Highest traffic in Kenya; heavy PSC/county/NGO coverage; "
        "aggregates and republishes other boards, so dedupe matters most here.",
    )
    detail_pattern = "/job/"
    listing_link_selector = "h2 a[href*='/job/'], h3 a[href*='/job/']"
    employer_selectors = ("[class*='company']", "[class*='org']")
    location_selectors = ("[class*='location']",)
    description_selectors = ("[class*='description']", "[class*='job-detail']", "article", "main")


BOARDS = {
    "brightermonday": BrighterMonday,
    "fuzu": Fuzu,
    "myjobmag": MyJobMag,
}
