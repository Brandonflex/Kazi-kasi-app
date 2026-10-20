"""Identity: deciding when two observations are the same job.

Stage 1 only (deterministic). Probabilistic matching lands in Phase 2 and must
be evaluated against a labelled golden set before it can merge anything.

The strongest key in this market is not the title — it is the *apply target*:
the email address, portal URL, or reference number (PSC ``V/No``, county ref)
that every copy of the same advert points at.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .extract import normalize_title
from .models import JobCandidate

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "fbclid", "gclid", "ref", "source", "src", "mc_cid", "mc_eid",
}

ATS_ID_PATTERNS = (
    re.compile(r"boards\.greenhouse\.io/([^/]+)/jobs/(\d+)"),
    re.compile(r"jobs\.lever\.co/([^/]+)/([0-9a-f\-]{8,})"),
    re.compile(r"jobs\.ashbyhq\.com/([^/]+)/([0-9a-f\-]{8,})"),
)

_LEGAL_SUFFIXES = (
    "limited", "ltd", "plc", "inc", "llc", "co", "company", "sacco",
    "group", "holdings", "kenya", "east africa", "africa",
)


def canonicalize_url(url: str) -> str:
    """Lowercase scheme/host, drop tracking params, sort the rest, drop fragment."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return url
    if not parsed.netloc:
        return url.strip()

    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in TRACKING_PARAMS]
    query.sort()

    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    return urlunparse(
        (
            parsed.scheme.lower() or "https",
            parsed.netloc.lower(),
            path,
            "",
            urlencode(query),
            "",
        )
    )


def employer_key(name: str | None, domain: str | None = None) -> str:
    """A stable employer identity key. Domain beats name, always."""
    if domain:
        return "domain:" + domain.lower().removeprefix("www.")
    if not name:
        return "unknown"
    text = name.lower().strip()
    text = re.sub(r"[^\w\s&]", " ", text)
    tokens = [t for t in text.split() if t not in _LEGAL_SUFFIXES]
    return "name:" + " ".join(tokens).strip()


def source_job_id_from_url(url: str) -> str | None:
    """Extract a provider-stable id from a posting URL."""
    path = urlparse(url).path.rstrip("/")
    tail = path.rsplit("/", 1)[-1] if path else ""
    if tail and re.fullmatch(r"[\w\-]{4,}", tail):
        return tail
    return None


def ats_requisition(url: str) -> tuple[str, str] | None:
    for pattern in ATS_ID_PATTERNS:
        match = pattern.search(url or "")
        if match:
            return match.group(1), match.group(2)
    return None


def apply_target(candidate: JobCandidate) -> str:
    """The strongest cross-source identity signal available for this posting.

    Ordered by precision: reference number > apply email > ATS requisition >
    canonical apply URL > canonical source URL.
    """
    if candidate.reference:
        return "ref:" + candidate.reference.lower()
    if candidate.apply_emails:
        return "email:" + candidate.apply_emails[0]
    if candidate.apply_url:
        req = ats_requisition(candidate.apply_url)
        if req:
            return f"ats:{req[0]}:{req[1]}"
        return "url:" + canonicalize_url(candidate.apply_url)
    return "url:" + canonicalize_url(candidate.source_url)


def dedupe_key(candidate: JobCandidate) -> str:
    """Composite cultural key: employer + title + county + deadline.

    Deliberately includes the deadline. Two adverts for the same title at the
    same employer with different closing dates are usually distinct
    requisitions — and in the public sector they are usually distinct *posts*.
    """
    parts = [
        employer_key(candidate.employer_name, candidate.employer_domain),
        normalize_title(candidate.title),
        (candidate.county or "").lower(),
        candidate.deadline.isoformat() if candidate.deadline else "",
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def same_job_stage1(a: JobCandidate, b: JobCandidate) -> bool:
    """Conservative deterministic equality. False is always safe; True must be right."""
    if a.source_id == b.source_id and a.source_job_id == b.source_job_id:
        return True
    if apply_target(a) == apply_target(b) and not apply_target(a).startswith("url:"):
        return True
    return dedupe_key(a) == dedupe_key(b)
