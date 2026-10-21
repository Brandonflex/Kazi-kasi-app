"""The identity keys, and what each one is allowed to prove.

The distinction this module exists to make:

* an **exclusive** key identifies a posting — a reference number, an ATS
  requisition, or the full cultural key (employer + title + county + deadline);
* a **shared** key identifies an employer or a campaign — a careers inbox, a
  "apply here" URL. A large employer posts twenty jobs all telling you to write
  to ``careers@company.co.ke``. Treating that inbox as identity would collapse
  twenty vacancies into one, which is the single worst thing this system can do.

Shared keys therefore only *corroborate*: they can merge two observations when
the titles agree, and otherwise they are ignored.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
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

#: Roman numerals and trailing digits distinguish real, separate requisitions
#: ("Analyst" vs "Analyst II"). They must never be normalised away.
GRADE_MARKER = re.compile(r"\b(i{1,3}|iv|v|vi|[0-9]{1,2})\b\s*$")


@dataclass(frozen=True)
class IdentityKey:
    kind: str
    value: str
    exclusive: bool

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return f"{self.kind}:{self.value}"


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


def ats_requisition(url: str) -> tuple[str, str] | None:
    for pattern in ATS_ID_PATTERNS:
        match = pattern.search(url or "")
        if match:
            return match.group(1), match.group(2)
    return None


def apply_target(candidate: JobCandidate) -> str:
    """The strongest single form of "where this application goes".

    Ordered by precision: reference number > apply email > ATS requisition >
    canonical apply URL > canonical source URL. Used as a display/debug value
    and as the apply link identity — **not** as proof that two postings are the
    same job. See ``identity_keys`` for that.
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


def identity_keys(candidate: JobCandidate) -> list[IdentityKey]:
    """Every key this candidate offers, tagged with what it is allowed to prove."""
    keys: list[IdentityKey] = [IdentityKey("dedupe", dedupe_key(candidate), True)]

    if candidate.reference:
        keys.append(IdentityKey("ref", candidate.reference.lower(), True))

    if candidate.apply_url:
        requisition = ats_requisition(candidate.apply_url)
        if requisition:
            keys.append(IdentityKey("ats", f"{requisition[0]}:{requisition[1]}", True))
        else:
            keys.append(IdentityKey("apply_url", canonicalize_url(candidate.apply_url), False))

    for email in candidate.apply_emails:
        # A careers inbox is an employer signal, not a job id.
        keys.append(IdentityKey("email", email.lower(), False))

    url = canonicalize_url(candidate.source_url)
    if url:
        keys.append(IdentityKey("source_url", url, False))

    return keys


def same_job_stage1(a: JobCandidate, b: JobCandidate) -> bool:
    """Conservative deterministic equality. False is always safe; True must be right."""
    if a.source_id == b.source_id and a.source_job_id == b.source_job_id:
        return True
    if dedupe_key(a) == dedupe_key(b):
        return True
    if a.reference and b.reference and a.reference.lower() == b.reference.lower():
        return True
    # A shared inbox only counts when the titles agree as well.
    if set(a.apply_emails) & set(b.apply_emails) and normalize_title(a.title) == normalize_title(b.title):
        return True
    return False


def grade_marker(title: str | None) -> str | None:
    match = GRADE_MARKER.search(normalize_title(title or ""))
    return match.group(1) if match else None
