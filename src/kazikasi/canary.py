"""Canary: does this source still look the way we think it does?

Job boards redesign without warning. The failure mode that matters is not an
exception — it is a page that parses *successfully* into an empty or mangled
job. So the canary checks the shape of one real page per source and reports the
fields that came back.

Run it on a schedule (daily is enough) and alert when ``ok`` flips to False.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .sources.base import Adapter


@dataclass
class CanaryResult:
    source_id: str
    listing_links: int = 0
    detail_ok: bool = False
    fields_present: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        # A source is healthy if it yields links and a detail page with at least
        # a title and *either* an employer or a location.
        has_identity = len({"title", "employer_name"} & set(self.fields_present)) == 2
        has_place = "county" in self.fields_present or "location_raw" in self.fields_present
        return self.listing_links > 0 and self.detail_ok and has_identity and has_place

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "ok": self.ok,
            "listing_links": self.listing_links,
            "detail_ok": self.detail_ok,
            "fields_present": self.fields_present,
            "missing": self.missing,
            "error": self.error,
        }


FIELD_ORDER = ("title", "employer_name", "county", "sub_county", "location_raw", "description_md", "deadline")


def run(adapter: Adapter, fetcher, *, sample: int = 1) -> CanaryResult:
    result = CanaryResult(source_id=adapter.manifest.id)
    listing_url = adapter.listing_urls(1)[0]
    try:
        page = fetcher.get(listing_url)
        links = adapter.parse_listing(page.body, listing_url)
    except Exception as exc:  # noqa: BLE001 - the canary reports, it does not raise
        result.error = f"listing: {exc!r}"
        return result

    result.listing_links = len(links)
    if not links:
        result.error = "listing produced zero detail links"
        return result

    for url in links[:sample]:
        try:
            detail = fetcher.get(url)
            candidate = adapter.parse_detail(detail.body, url)
        except Exception as exc:  # noqa: BLE001
            result.error = f"detail: {exc!r}"
            return result
        result.detail_ok = True
        result.fields_present = [name for name in FIELD_ORDER if getattr(candidate, name)]

    result.missing = [name for name in FIELD_ORDER if name not in result.fields_present]
    return result
