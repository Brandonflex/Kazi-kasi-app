"""The P2 sources: the long tail that makes the feed cover the market.

`docs/research/01-source-landscape.md` ranks sources by value and cost. The three
here are all P2 — worth having, none of them urgent:

* **CareerPoint Kenya** — a long-running board with a lot of the admin and NGO
  roles the big boards miss.
* **Teachers Service Commission** — national, bursty, and the single largest
  early-career employer in the country by headcount.
* **Ajira Digital** — the government youth digital-work programme; attachments and
  short contracts rather than careers.

### Why these three ship as `unverified`

Their parsers are written against the structure each source is *documented* to
publish — `JobPosting` JSON-LD where it exists, a document lane where adverts are
PDFs — and exercised against fixtures in `tests/fixtures`. But none of them has
been run against a live page from this build: the build sandbox has no route to
those hosts, and inventing CSS selectors from memory is how a scraper silently
returns zero rows for a month.

So the manifests say `status="unverified"`, and `pipeline.ingest` refuses to run
one unless the caller passes `allow_unverified=True`. The gate is the point:
**`kazikasi canary --source tsc --live` is the thing that promotes a source, and a
human reading its output is the thing that signs off.** Until that happens, these
sources cannot quietly ship empty data into the feed.

### What "verified" will require

1. `canary --live` reports ≥1 detail link from the listing and ≥1 candidate from a
   detail page, with title, employer and description present.
2. `terms_reviewed_at` is filled in after reading the site's terms and robots.txt.
3. The listing URL still resolves without a login or a consent interstitial.

None of that is satisfied yet, and the manifests say so in prose rather than
implying otherwise.
"""

from __future__ import annotations

from .base import Manifest
from .bulletins import BulletinAdapter
from .structured import StructuredSource


class CareerPoint(StructuredSource):
    """Career Point Kenya — public HTML board, posts detail pages with JSON-LD."""

    manifest = Manifest(
        id="careerpoint",
        label="Career Point Kenya",
        access="public_html",
        tier="cold",
        cadence_minutes=180,
        rate_limit_per_minute=10,
        supports=("jsonld_detail", "full_description", "deadline"),
        listing_urls=("https://www.careerpointkenya.co.ke/",),
        notes="P2. Listing URL and selectors are unverified in this build — run "
        "`kazikasi canary --source careerpoint --live` before enabling ingestion. "
        "Terms not yet reviewed.",
        status="unverified",
    )
    detail_pattern = "/job/"
    listing_link_selectors = (
        "h2 a[href]",
        "h3 a[href]",
        "[class*='job'] a[href]",
    )
    employer_selectors = ("[class*='company']", "[class*='employer']")
    location_selectors = ("[class*='location']",)


class TSC(BulletinAdapter):
    """Teachers Service Commission — adverts published as PDFs and portal posts.

    TSC does not publish job objects; it publishes an advert document with several
    posts under one closing date. That is exactly what ``BulletinAdapter`` and
    ``documents.document_to_candidates`` were built for, so this adapter inherits
    the whole document lane and only declares where to look.
    """

    manifest = Manifest(
        id="tsc",
        label="Teachers Service Commission",
        access="pdf",
        tier="burst",
        cadence_minutes=360,
        rate_limit_per_minute=6,
        supports=("pdf", "multi_post_advert", "county_spread"),
        listing_urls=("https://www.tsc.go.ke/",),
        notes="P2. National, bursty, and the largest early-career employer by "
        "headcount. Listing URL and document hints are unverified in this build. "
        "Terms not yet reviewed.",
        status="unverified",
    )
    document_hints = (".pdf", "/download", "/vacanc", "/advert", "/career")
    exclude_hints = BulletinAdapter.exclude_hints + ("teacher-code", "registration")
    default_employer = "Teachers Service Commission"
    default_county = None


class Ajira(BulletinAdapter):
    """Ajira Digital — attachments, short contracts and digital-work programmes."""

    manifest = Manifest(
        id="ajira",
        label="Ajira Digital",
        access="public_html",
        tier="cold",
        cadence_minutes=720,
        rate_limit_per_minute=6,
        supports=("attachment", "short_contract", "programme"),
        listing_urls=("https://ajira.go.ke/",),
        notes="P2. Programme listings and attachments rather than careers; the "
        "document hints are unverified in this build. Terms not yet reviewed.",
        status="unverified",
    )
    document_hints = (".pdf", "/opportunit", "/download", "/apply")
    exclude_hints = BulletinAdapter.exclude_hints + ("registration", "login", "faq")
    default_employer = "Ajira Digital"


P2 = {
    "careerpoint": CareerPoint,
    "tsc": TSC,
    "ajira": Ajira,
}
