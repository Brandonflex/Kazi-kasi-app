"""Adapters for sources that publish adverts as documents.

PSC and the county governments do not publish job objects. They publish a PDF
or a page of prose: one advert, several posts, one closing date, one inbox.
These adapters wrap ``documents.document_to_candidates`` so that lane plugs into
the same pipeline as the boards — one payload may yield several candidates, and
the identity layer keeps them apart using each post's reference number.

A note on the county adapter: county websites change often and are not
consistent between counties. The selectors here are a starting point, and the
canary is what tells us when they stop being true.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..documents import DocumentError, document_to_candidates
from ..models import JobCandidate
from .base import Adapter, Manifest, Payload


class BulletinAdapter(Adapter):
    """Base for sources whose detail pages are advert documents."""

    #: URL fragments that identify a document link on the listing page.
    document_hints: tuple[str, ...] = (".pdf", "/advert", "/vacanc", "/download")

    #: Public-sector sites mix recruitment PDFs with forms, tenders and budget
    #: documents in one downloads folder. These are never vacancies.
    exclude_hints: tuple[str, ...] = (
        "tender", "form", "pension", "gazette", "policy", "budget", "invoice",
        "strategic-plan", "annual-report", "act-", "bill-", "fee-",
    )

    default_employer: str | None = None
    default_county: str | None = None
    default_email: str | None = None

    def parse_listing(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        for anchor in soup.select("a[href]"):
            href = anchor["href"].strip()
            lowered = href.lower()
            if any(hint in lowered for hint in self.exclude_hints):
                continue
            if any(hint in lowered for hint in self.document_hints):
                links.append(urljoin(base_url, href))
        # Keep the listing order, drop repeats and navigation noise.
        seen: set[str] = set()
        out: list[str] = []
        for link in links:
            if urlparse(link).scheme not in ("http", "https"):
                continue
            if link in seen:
                continue
            seen.add(link)
            out.append(link)
        return out

    def parse_payload(self, payload: Payload, url: str) -> list[JobCandidate]:
        return document_to_candidates(
            payload.raw,
            source_id=self.manifest.id,
            source_url=url,
            content_type=payload.content_type,
            employer=self.default_employer,
            county=self.default_county,
            default_email=self.default_email,
        )

    def parse_detail(self, html: str, url: str) -> JobCandidate:
        """Interface symmetry for the canary: one payload, first post."""
        payload = Payload(url=url, raw=html.encode("utf-8"))
        candidates = self.parse_payload(payload, url)
        if not candidates:
            raise DocumentError("no candidates in document")
        return candidates[0]


class PSCKenya(BulletinAdapter):
    """Public Service Commission of Kenya (psckjobs.go.ke).

    The largest single source of formal entry-level white-collar vacancies in
    the country, and the one with the worst machine-readability. Every advert is
    a PDF, adverts carry a VACANCY NO. unique within the year, and one PDF can
    hold twenty posts.
    """

    manifest = Manifest(
        id="psc",
        label="Public Service Commission of Kenya",
        access="public_html+pdf",
        tier="warm",
        cadence_minutes=240,
        terms_reviewed_at="2026-10-20",
        rate_limit_per_minute=6,
        supports=("pdf", "bulletin", "reference", "deadline", "salary_scale"),
        listing_urls=("https://www.psckjobs.go.ke/",),
        notes="Adverts are PDFs, often several posts per advert with one closing "
        "date. Vacancy numbers restart each year, so references are namespaced by "
        "employer. Overseas missions and HQ posts are both listed.",
    )

    document_hints = (".pdf", "/advert")
    default_employer = "Public Service Commission of Kenya"
    default_county = "Nairobi"


class NairobiCounty(BulletinAdapter):
    """Nairobi City County Government careers page.

    Counties are the second public-sector lane: smaller adverts, shorter
    turnaround, and postings that rarely appear on the boards. Nairobi is the
    beta market, so it is the first county wired up.
    """

    manifest = Manifest(
        id="nairobi_county",
        label="Nairobi City County Government",
        access="public_html+pdf",
        tier="cold",
        cadence_minutes=720,
        terms_reviewed_at="2026-10-20",
        rate_limit_per_minute=4,
        supports=("pdf", "bulletin", "deadline"),
        listing_urls=("https://nairobi.go.ke/careers/",),
        notes="County sites are inconsistent and change often; selectors are a "
        "starting point and the canary is the alarm. Adverts are usually one PDF "
        "per batch. Treat coverage as unverified until the canary has run weekly "
        "for a month.",
    )

    document_hints = (".pdf", "/career", "/vacanc", "/download", "/advert")
    default_employer = "Nairobi City County Government"
    default_county = "Nairobi"
