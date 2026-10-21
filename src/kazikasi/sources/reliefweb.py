"""ReliefWeb (UN OCHA) jobs adapter — API v2.

Why this source matters: Nairobi hosts regional offices for a large number of
UN agencies and INGOs. These roles are well paid, deadline-bearing, and almost
never appear on the general boards — and ReliefWeb gives them to us through a
free API.

Two hard requirements, both documented by ReliefWeb:

* v1 is decommissioned and returns HTTP 410. Use v2.
* Since 1 November 2025 the API only serves **pre-approved appnames**. Without
  one you get 403. Set ``RELIEFWEB_APPNAME`` in the environment.

The adapter is split so the JSON mapping is testable without the network.
"""

from __future__ import annotations

import os
from typing import Any

from ..extract import (
    clean_text,
    detect_employment_type,
    detect_scam_flags,
    detect_seniority,
    detect_work_mode,
    entry_fit,
    find_emails,
    find_pay_text,
    find_reference,
    html_to_text,
    parse_date,
    parse_location,
    parse_pay,
)
from ..models import JobCandidate
from .base import Adapter, Manifest

API_BASE = "https://api.reliefweb.int/v2/jobs"


class ReliefWeb(Adapter):
    manifest = Manifest(
        id="reliefweb",
        label="ReliefWeb — UN OCHA jobs",
        access="public_json_api",
        tier="warm",
        cadence_minutes=120,
        requires_auth=True,  # appname parameter, not a secret credential
        terms_reviewed_at="2026-10-20",
        rate_limit_per_minute=10,
        supports=("structured", "deadline", "org", "country", "stable_id"),
        listing_urls=(API_BASE,),
        notes="Requires a pre-approved appname (RELIEFWEB_APPNAME). v1 returns 410. "
        "Descriptions may contain copyrighted material owned by the original source — "
        "always attribute and link out.",
    )

    def __init__(self, appname: str | None = None, country: str = "Kenya", limit: int = 100) -> None:
        self.appname = appname or os.environ.get("RELIEFWEB_APPNAME", "")
        self.country = country
        self.limit = limit

    # -- API plumbing ------------------------------------------------------

    def request_body(self) -> dict[str, Any]:
        """POST body for the v2 jobs endpoint."""
        return {
            "appname": self.appname,
            "profile": "list",
            "limit": self.limit,
            "filter": {
                "field": "country",
                "value": [self.country],
            },
            "fields": {
                "include": [
                    "title", "body", "url", "date.created", "date.closing",
                    "source.name", "source.homepage", "country.name", "city.name",
                    "career_categories.name", "type.name", "experience.name",
                ]
            },
            "sort": ["date.created:desc"],
        }

    def parse_listing(self, payload: str, base_url: str = API_BASE) -> list[dict]:
        import json

        data = json.loads(payload)
        return list(data.get("data", []))

    def parse_detail(self, html: str, url: str) -> JobCandidate:
        """Not used for this source; kept for interface symmetry."""
        raise NotImplementedError("ReliefWeb yields full records from the list endpoint")

    # -- mapping -----------------------------------------------------------

    def item_to_candidate(self, item: dict) -> JobCandidate:
        fields = item.get("fields", {})
        notes: list[str] = []

        title = clean_text(fields.get("title"))
        body = html_to_text(fields.get("body") or "")
        source = fields.get("source") or {}
        if isinstance(source, list):
            source = source[0] if source else {}
        employer = clean_text(source.get("name"))

        domain = None
        homepage = source.get("homepage")
        if homepage:
            domain = clean_text(homepage).split("//")[-1].split("/")[0].lower().removeprefix("www.")

        cities = fields.get("city") or []
        if isinstance(cities, dict):
            cities = [cities]
        city_names = [clean_text(c.get("name")) for c in cities if isinstance(c, dict)]
        country_names = [
            clean_text(c.get("name"))
            for c in (fields.get("country") or [])
            if isinstance(c, dict)
        ]
        location_raw = ", ".join([n for n in city_names if n]) or ", ".join(country_names)
        county, sub_county, raw_loc = parse_location(location_raw)
        if county is None and "Nairobi" in location_raw:
            county = "Nairobi"

        types = fields.get("type") or []
        type_text = " ".join(t.get("name", "") for t in types if isinstance(t, dict))
        experience = fields.get("experience") or []
        experience_text = " ".join(e.get("name", "") for e in experience if isinstance(e, dict))

        fit, fit_evidence, _ = entry_fit(f"{experience_text}\n{body}")
        work_mode, work_mode_source = detect_work_mode(body, location_raw)

        emails = find_emails(body)
        flags, evidence = detect_scam_flags(
            body, emails=emails, employer_domain=domain, employer_name=employer
        )

        created = (fields.get("date") or {}).get("created")
        closing = (fields.get("date") or {}).get("closing")
        if not closing:
            notes.append("no_closing_date")

        return JobCandidate(
            source_id=self.manifest.id,
            source_job_id=str(item.get("id")),
            source_url=clean_text(fields.get("url")) or str(item.get("url", "")),
            title=title,
            employer_name=employer or None,
            employer_domain=domain,
            description_md=body or None,
            description_source="html",
            extraction_confidence=0.95,
            seniority=detect_seniority(title, experience_text),
            entry_fit=fit,
            entry_fit_evidence=fit_evidence,
            employment_type=detect_employment_type(f"{type_text} {body[:600]}", title=title),
            work_mode=work_mode,
            work_mode_source=work_mode_source,
            county=county,
            sub_county=sub_county,
            location_raw=raw_loc or location_raw or None,
            pay=parse_pay(find_pay_text(body)),  # ReliefWeb rarely states pay
            date_posted_claimed=parse_date(created),
            deadline=parse_date(closing),
            apply_emails=emails,
            reference=find_reference(body[:1500]),
            apply_url=clean_text(fields.get("url")) or None,
            scam_flags=flags,
            scam_evidence=evidence,
            status="extracted",
            parser_notes=notes,
        )
