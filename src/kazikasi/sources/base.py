"""Source adapter contract.

An adapter is two things: a manifest (policy, cadence, legal review date) and
a parser (payload → ``JobCandidate``). The manifest exists so that the legal
posture and the code cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import JobCandidate


@dataclass(frozen=True)
class Payload:
    """Raw bytes plus the URL they came from.

    Bytes, not text: advert PDFs are a first-class source here, and decoding
    them as UTF-8 is how a document lane silently stops working.
    """

    url: str
    raw: bytes
    content_type: str = "text/html"

    @property
    def text(self) -> str:
        try:
            return self.raw.decode("utf-8")
        except UnicodeDecodeError:
            return self.raw.decode("latin-1", errors="replace")

    @property
    def is_pdf(self) -> bool:
        return self.raw[:5] == b"%PDF-" or "pdf" in self.content_type.lower()


@dataclass(frozen=True)
class Manifest:
    id: str
    label: str
    access: str  # public_html | public_json_api | pdf | partner_api | signal
    tier: str  # hot | warm | cold | burst
    cadence_minutes: int
    requires_auth: bool = False
    terms_reviewed_at: str | None = None
    rate_limit_per_minute: int = 30
    supports: tuple[str, ...] = ()
    listing_urls: tuple[str, ...] = ()
    notes: str = ""


class Adapter:
    """Base class. Subclasses set ``manifest`` and implement ``parse_listing``/``parse_detail``."""

    manifest: Manifest

    #: Path fragment that identifies an individual posting link.
    detail_pattern: str = ""

    #: Extra attributes merged into parser notes for every candidate.
    defaults: dict[str, Any] = field(default_factory=dict)

    def listing_urls(self, page: int = 1) -> list[str]:
        if page == 1:
            return list(self.manifest.listing_urls)
        return [f"{u}{'&' if '?' in u else '?'}page={page}" for u in self.manifest.listing_urls]

    def parse_listing(self, html: str, base_url: str) -> list[str]:
        """Return absolute detail URLs found on a listing page."""
        raise NotImplementedError

    def parse_detail(self, html: str, url: str) -> JobCandidate:
        """Return exactly one candidate from a detail page."""
        raise NotImplementedError

    # -- payload-level interface (defaults leave the HTML adapters unchanged) --

    def parse_listing_payload(self, payload: Payload, base_url: str) -> list[str]:
        return self.parse_listing(payload.text, base_url)

    def parse_payload(self, payload: Payload, url: str) -> list[JobCandidate]:
        """Return every candidate in one payload.

        A list, not a single object, because a public-sector advert is usually
        several posts under one heading and one closing date.
        """
        return [self.parse_detail(payload.text, url)]

    def parser_version(self) -> str:
        return f"{self.manifest.id}.phase1.0"

    # -- helpers shared by HTML adapters ----------------------------------

    @staticmethod
    def _absolute(href: str, base_url: str) -> str:
        if href.startswith("http"):
            return href
        from urllib.parse import urljoin

        return urljoin(base_url, href)

    def _dedupe_links(self, links: list[str]) -> list[str]:
        from ..identity import canonicalize_url

        seen: set[str] = set()
        out: list[str] = []
        for link in links:
            key = canonicalize_url(link)
            if key and key not in seen and self.detail_pattern in key:
                seen.add(key)
                # Store the canonical form: we want one URL per posting, not
                # one per campaign tag.
                out.append(key)
        return out
