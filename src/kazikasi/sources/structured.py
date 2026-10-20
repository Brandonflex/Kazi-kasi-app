"""A source defined by declaration, not by a new parser.

Every Kenyan board that survived long enough to matter publishes one of two
things: **schema.org/JobPosting JSON-LD**, or a list of links to pages that do.
That makes a new source mostly configuration — a listing URL, a URL fragment that
identifies a posting, and a handful of selector fallbacks for the sites that never
got round to structured data.

Why this exists as a class rather than as copy-pasted adapters: three quarters of
the maintenance cost of a job aggregator is the *fourth* source. Making the fourth
source 20 lines of configuration is the difference between a feed that covers the
market and a feed that covers three boards.

Two rules inherited from the board adapters, because they were right:

* **JSON-LD first, selectors second, prose third.** Structure survives redesigns;
  CSS classes do not.
* **Never raise on unexpected markup.** A candidate with a `parser_note` is worth
  more than an exception, because the note is what the canary reports later.
"""

from __future__ import annotations

from ..extract import (
    clean_text,
    extract_jobpostings,
    html_to_text,
    parse_html,
)
from ..models import JobCandidate
from .boards import HtmlBoardAdapter

#: How deep we are willing to walk a listing page for links. A listing page with
#: 400 anchors is a navigation menu, not a jobs page.
MAX_LINKS = 60


class StructuredSource(HtmlBoardAdapter):
    """JSON-LD-first adapter configured by class attributes.

    Subclasses need only a manifest and a detail pattern; selectors are optional
    and only used when structured data is absent.
    """

    #: Anchors to try, in order, when the page carries no JSON-LD item list.
    listing_link_selectors: tuple[str, ...] = ()

    #: Fallbacks for sources that publish one employer or one region only (a
    #: commission, a programme, a single campus). Used only when the advert is
    #: silent, and recorded in ``parser_notes`` so the provenance stays visible.
    default_employer: str | None = None
    default_county: str | None = None

    def parse_listing(self, html: str, base_url: str) -> list[str]:
        """Detail URLs, from JSON-LD first, then anchors.

        A listing page that publishes an ``ItemList`` of ``JobPosting`` objects is
        the best case: the URLs are canonical, deduplicated by the publisher, and
        independent of whatever the page's markup looks like this month.
        """
        links: list[str] = []

        for posting in extract_jobpostings(html):
            url = posting.get("url") or posting.get("@id")
            if isinstance(url, str) and url.startswith("http"):
                links.append(url)

        soup = parse_html(html)
        if self.detail_pattern:
            for anchor in soup.select(f"a[href*='{self.detail_pattern}']"):
                href = anchor.get("href")
                if href:
                    links.append(self._absolute(href, base_url))
        for selector in self.listing_link_selectors:
            for anchor in soup.select(selector):
                href = anchor.get("href")
                if href:
                    links.append(self._absolute(href, base_url))

        deduped = self._dedupe_links(links) if self.detail_pattern else _unique(links)
        return deduped[:MAX_LINKS]

    def parse_detail(self, html: str, url: str) -> JobCandidate:
        candidate = super().parse_detail(html, url)
        if not candidate.title:
            # A posting with no title is a navigation link that looked like a job.
            # Give it the page's own <title> and say so, rather than emitting "".
            soup = parse_html(html)
            if soup.title and clean_text(soup.title.get_text(" ")):
                candidate.title = clean_text(soup.title.get_text(" "))
                candidate.parser_notes.append("title_from_page_title")
        if self.default_employer and not candidate.employer_name:
            candidate.employer_name = self.default_employer
            candidate.parser_notes.append("employer_from_manifest")
        if self.default_county and not candidate.county:
            candidate.county = self.default_county
            candidate.parser_notes.append("county_from_manifest")
        return candidate

    def _description_fallback(self, html: str) -> str:
        soup = parse_html(html)
        return html_to_text(str(soup))


def _unique(links: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for link in links:
        key = link.split("#", 1)[0]
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out
