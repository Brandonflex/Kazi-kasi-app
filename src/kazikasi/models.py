"""Canonical data model for the Kazi-Kasi job graph.

Design rules encoded here:

* A ``SourceRecord`` is an immutable observation. A ``JobCandidate`` is the
  normalised interpretation of one observation. They are never the same object.
* Every field that can be wrong carries the evidence for it: ``entry_fit`` has
  ``entry_fit_evidence``, pay carries ``source`` and ``confidence``.
* Nothing in this module talks to the network, a database, or an LLM.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from typing import Any

# --- enums as plain strings (kept boring on purpose) -----------------------

EMPLOYMENT_TYPES = {
    "full_time",
    "part_time",
    "contract",
    "internship",
    "attachment",  # Kenyan industrial attachment
    "volunteer",
    "temporary",
    "unknown",
}

WORK_MODES = {"onsite", "hybrid", "remote", "unknown"}

ENTRY_FIT = {
    "open_to_freshers",  # explicitly welcomes 0-experience applicants
    "some_experience",  # 1 year or equivalent
    "experienced",  # 2+ years
    "unknown",
}

STATUSES = {
    "discovered",
    "extracted",
    "verified",
    "open",
    "suspect_closed",
    "closed",
    "archived",
    "needs_review",
}

SCAM_CRITERIA = {
    "fee_requested",
    "personal_number_only",
    "no_employer_identity",
    "domain_mismatch",
    "template_match",
    "whatsapp_only",
    "copy_of_known_scam",
    "no_interview_process",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- value objects ---------------------------------------------------------


@dataclass(frozen=True)
class RawRef:
    """Pointer to a stored payload. Content-addressed, so a ref is its hash."""

    key: str
    sha256: str
    content_type: str
    byte_size: int


@dataclass
class JobLocation:
    county: str | None = None
    sub_county: str | None = None
    town: str | None = None
    lat: float | None = None
    lng: float | None = None
    h3_r9: str | None = None  # ~0.1 km²
    h3_r7: str | None = None  # ~5 km²
    geocode_confidence: float | None = None
    is_primary: bool = True


@dataclass
class JobPay:
    min_amount: float | None = None
    max_amount: float | None = None
    currency: str = "KES"
    period: str | None = None  # month | year | day | hour
    gross_net: str = "unknown"  # gross | net | unknown
    source: str = "unknown"  # stated | parsed | estimated_from_grade | unknown
    confidence: float = 0.0

    @property
    def is_empty(self) -> bool:
        return self.min_amount is None and self.max_amount is None


@dataclass
class Provenance:
    source_id: str
    source_url: str
    first_seen_at: datetime
    last_seen_at: datetime
    source_job_id: str
    is_primary: bool = True


# --- observation -----------------------------------------------------------


@dataclass
class SourceRecord:
    """One immutable observation of one posting on one source."""

    source_id: str
    source_job_id: str
    source_url: str
    fetched_at: datetime
    raw: RawRef
    parsed: dict[str, Any]
    parser_version: str
    content_type: str = "html"

    def fingerprint(self) -> str:
        """Stable hash of the *interpretation*, used for replay and change detection."""
        payload = json.dumps(
            {"parsed": self.parsed, "parser_version": self.parser_version},
            sort_keys=True,
            default=str,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --- normalised job --------------------------------------------------------


@dataclass
class JobCandidate:
    """A normalised job, ready for identity resolution and storage."""

    source_id: str
    source_job_id: str
    source_url: str
    title: str
    employer_name: str | None = None
    employer_domain: str | None = None
    description_md: str | None = None
    description_source: str = "html"  # html | pdf_text | ocr | llm
    extraction_confidence: float = 1.0

    seniority: str = "unknown"
    entry_fit: str = "unknown"
    entry_fit_evidence: str | None = None
    employment_type: str = "unknown"
    work_mode: str = "unknown"
    work_mode_source: str = "unknown"

    county: str | None = None
    sub_county: str | None = None
    location_raw: str | None = None

    pay: JobPay = field(default_factory=JobPay)

    date_posted_claimed: date | None = None
    deadline: date | None = None

    apply_emails: list[str] = field(default_factory=list)
    reference: str | None = None  # PSC V/No, county ref
    apply_url: str | None = None

    scam_flags: list[str] = field(default_factory=list)
    scam_evidence: dict[str, str] = field(default_factory=dict)

    first_seen_at: datetime = field(default_factory=_utcnow)
    status: str = "extracted"
    parser_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("first_seen_at",):
            if isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        for key in ("date_posted_claimed", "deadline"):
            if isinstance(data[key], date):
                data[key] = data[key].isoformat()
        return data

    def provenance(self) -> Provenance:
        return Provenance(
            source_id=self.source_id,
            source_url=self.source_url,
            first_seen_at=self.first_seen_at,
            last_seen_at=self.first_seen_at,
            source_job_id=self.source_job_id,
        )

    def missing_required(self) -> list[str]:
        """Required fields for a job to be considered `verified`."""
        missing = []
        if not self.title or not self.title.strip():
            missing.append("title")
        if not (self.employer_name or self.employer_domain):
            missing.append("employer")
        if not (self.county or self.location_raw):
            missing.append("location")
        if not self.description_md:
            missing.append("description")
        return missing
