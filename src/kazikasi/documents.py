"""The document lane: advert PDFs and bulletin pages → one candidate per post.

Most of the Kenyan public sector does not publish structured job data. It
publishes a PDF — one advert, several posts, shared closing date — and expects
a human to read it. This module is the part of the product that reads it.

Two rules shape the design:

* **A bulletin is N posts, not one.** "One advert, N posts" is the norm for PSC,
  county governments and many NGOs. Collapsing a bulletin into a single job is
  how a feed silently loses vacancies.
* **A scanned page is not a job.** If there is no extractable text we raise
  ``DocumentError`` instead of inventing one; OCR is a separate, later decision
  with its own confidence model.

Everything here is deterministic: regex, line structure and the extractors in
``extract.py``.
"""

from __future__ import annotations

import io
import re

from .extract import (
    clean_text,
    detect_employment_type,
    detect_scam_flags,
    detect_seniority,
    detect_work_mode,
    entry_fit,
    find_deadline,
    find_emails,
    find_pay_text,
    find_reference,
    html_to_text,
    parse_location,
    parse_pay,
)
from .models import JobCandidate


class DocumentError(Exception):
    """Raised when a document cannot be read honestly (scan-only, encrypted, empty)."""


# --------------------------------------------------------------------------
# Bytes → text
# --------------------------------------------------------------------------

_HTML_HINT = re.compile(r"<(?:html|body|table|div|p)\b", re.I)


def bytes_to_text(data: bytes, content_type: str = "") -> str:
    """Best-effort text from a PDF, HTML fragment or plain advert."""
    if not data:
        raise DocumentError("empty document")

    if data[:5] == b"%PDF-" or "pdf" in content_type.lower():
        return _pdf_to_text(data)

    text = data.decode("utf-8", errors="replace")
    if _HTML_HINT.search(text):
        return html_to_text(text)
    return text


def _pdf_to_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise DocumentError("pypdf is required to read PDF adverts") from exc

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - any parse failure is a document failure
        raise DocumentError(f"unreadable PDF: {exc}") from exc

    if getattr(reader, "is_encrypted", False):
        try:
            reader.decrypt("")
        except Exception as exc:  # noqa: BLE001
            raise DocumentError("encrypted PDF") from exc

    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    if len(text) < 80:
        raise DocumentError("no extractable text (likely a scan; OCR not implemented)")
    return text


# --------------------------------------------------------------------------
# Bulletin structure
# --------------------------------------------------------------------------

#: "VACANCY NO. 1/2026: ASSISTANT OFFICE ADMINISTRATOR - CSG 11"
_VACANCY_LINE = re.compile(
    r"(?im)^[ \t]*(?:VACANCY|POST|POSITION)\s*(?:NO\.?|NUMBER)?\s*[:\-]?\s*"
    r"(?P<ref>[A-Z0-9][A-Z0-9/\-\.]{0,19})\s*[:\-–—]\s*(?P<title>\S.*)$"
)

#: "1. ASSISTANT OFFICE ADMINISTRATOR" — numbered, all-caps, no sentence punctuation.
_NUMBERED_LINE = re.compile(
    r"(?m)^[ \t]*(?P<num>\d{1,2})[.)]\s+(?P<title>[A-Z][A-Z0-9 ,()/'&.\-]{8,90})$"
)

_GRADE_SUFFIX = re.compile(r"\s*[-–—]\s*(?:CSG|JOB GROUP|GRADE)\s*[A-Z0-9\-]+\.?\s*$", re.I)
_POSTS = re.compile(r"number\s+of\s+posts?\s*[:\-]\s*([A-Za-z]+|\d+)\s*(?:\((\d+)\))?", re.I)
_SALARY_LINE = re.compile(r"(?im)^[ \t]*(?:basic\s+)?salary[^:\n]*[:\-]\s*(.+)$")

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _normalise_requirements(text: str) -> str:
    """Make the ways Kenyan adverts write "1 year" readable by ``entry_fit``."""
    # "one (1) year", "three (3) years" → "1 years", "3 years"
    text = re.sub(
        r"\b(" + "|".join(_WORD_NUMBERS) + r")\s*\((\d{1,2})\)\s*(years?|months?)",
        lambda m: f"{m.group(2)} {m.group(3)}",
        text,
        flags=re.I,
    )
    # "(1) year" → "1 year"
    text = re.sub(r"\((\d{1,2})\)\s+(years?|months?)", r"\1 \2", text, flags=re.I)
    return text


def _posts_count(body: str) -> int | None:
    match = _POSTS.search(body)
    if not match:
        return None
    word, digits = match.group(1), match.group(2)
    if digits:
        return int(digits)
    if word.isdigit():
        return int(word)
    return _WORD_NUMBERS.get(word.lower())


def split_bulletin(text: str) -> list[dict]:
    """Split an advert into ``{ref, title, body}`` sections, in document order.

    Returns an empty list when the text has no recognisable post headings, which
    the caller must treat as "single advert", not as "no jobs".
    """
    matches = list(_VACANCY_LINE.finditer(text))
    if not matches:
        matches = [
            m
            for m in _NUMBERED_LINE.finditer(text)
            if (m.group("title").strip().upper() == m.group("title").strip())
        ]
    if not matches:
        return []

    sections = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        title = clean_text(match.group("title"))
        title = _GRADE_SUFFIX.sub("", title).strip(" :—-")
        sections.append(
            {
                "ref": match.groupdict().get("ref") or match.groupdict().get("num"),
                "title": title,
                "body": text[start:end].strip(),
            }
        )
    return sections


ACRONYMS = {"ict": "ICT", "hr": "HR", "csg": "CSG", "ngo": "NGO", "icts": "ICTs", "pr": "PR"}


def _display_title(title: str) -> str:
    """PSC prints titles in caps; a feed should not shout."""
    if not title or not title.isupper():
        return title
    words = []
    for word in title.title().replace("'S", "'s").split():
        lowered = word.lower().strip("(),")
        words.append(ACRONYMS.get(lowered, word))
    return " ".join(words)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:60]


def parse_bulletin(
    text: str,
    *,
    source_id: str,
    source_url: str,
    employer: str | None = None,
    county: str | None = None,
    sub_county: str | None = None,
    default_email: str | None = None,
    now=None,
) -> list[JobCandidate]:
    """Turn a bulletin into one candidate per post.

    Fields that are shared by the whole document — closing date, application
    email, employer — are read once from the full text and applied to every
    post, which is how these adverts are actually written.
    """
    sections = split_bulletin(text)
    if not sections:
        return []

    document_deadline = find_deadline(text)
    document_emails = find_emails(text)
    if default_email and default_email not in document_emails:
        document_emails = [default_email, *document_emails]
    document_reference = find_reference(text)

    candidates: list[JobCandidate] = []
    for index, section in enumerate(sections, start=1):
        # Line structure matters for "Salary:" and "Number of Posts:", so keep
        # the raw section and use a flattened copy only for prose fields.
        raw_body = _normalise_requirements(section["body"])
        body = clean_text(raw_body)
        title = _display_title(section["title"])

        # Requirements only: duties inflate the match on "experience" phrases
        # that describe the role rather than the candidate.
        requirements = _requirements_slice(body)

        label, evidence, confidence = entry_fit(f"{title}. {requirements}")
        pay_text = _SALARY_LINE.search(raw_body)
        pay = parse_pay(pay_text.group(1) if pay_text else find_pay_text(requirements))

        resolved_county, resolved_sub, raw_location = parse_location(
            f"{requirements} {body[:400]}"
        )
        county_name = resolved_county or county
        if county_name and not raw_location:
            raw_location = county_name

        reference = section["ref"] or document_reference
        reference = f"{_slug(employer or source_id)[:40]}/{reference}" if reference else None

        flags, flag_evidence = detect_scam_flags(
            body, emails=document_emails, employer_name=employer
        )
        work_mode, work_mode_source = detect_work_mode(body, raw_location or "")

        candidates.append(
            JobCandidate(
                source_id=source_id,
                source_job_id=_slug(reference)[:80] if reference else f"{_slug(title)}-{index}"[:80],
                source_url=source_url,
                title=title,
                employer_name=employer,
                description_md=body or None,
                description_source="pdf_text",
                extraction_confidence=0.85 if section["ref"] else 0.7,
                seniority=detect_seniority(title, requirements[:400]),
                entry_fit=label,
                entry_fit_evidence=evidence,
                employment_type=detect_employment_type(body, title=title),
                work_mode=work_mode,
                work_mode_source=work_mode_source,
                county=county_name,
                sub_county=resolved_sub or sub_county,
                location_raw=raw_location or None,
                pay=pay,
                deadline=document_deadline,
                apply_emails=document_emails,
                reference=reference,
                scam_flags=flags,
                scam_evidence=flag_evidence,
                status="extracted",
                parser_notes=[
                    "bulletin",
                    *( [f"posts={_posts_count(body)}"] if _posts_count(body) else [] ),
                    *([f"entry_fit_conf={confidence}"] if confidence else []),
                ],
            )
        )
    return candidates


def _requirements_slice(body: str) -> str:
    """The requirements paragraph if it can be found, else the whole body."""
    match = re.search(
        r"(?:requirements?\s+for\s+appointment|minimum\s+qualifications?|qualifications?\s+(?:and|&)\s+requirements?)"
        r"(?P<text>.{0,2000})",
        body,
        re.I | re.S,
    )
    if not match:
        return body
    text = match.group("text")
    stop = re.search(r"\b(?:duties|responsibilities|how to apply|applications? should)\b", text, re.I)
    return text[: stop.start()] if stop else text


def parse_single_advert(
    text: str,
    *,
    source_id: str,
    source_url: str,
    employer: str | None = None,
    county: str | None = None,
) -> list[JobCandidate]:
    """Fallback for a one-job document with no recognisable heading."""
    whole = _normalise_requirements(text)
    title = next((clean_text(line) for line in text.splitlines() if clean_text(line)), "Untitled advert")
    label, evidence, confidence = entry_fit(whole)
    resolved_county, sub_county, raw = parse_location(whole)
    flags, flag_evidence = detect_scam_flags(whole, employer_name=employer)
    pay_text = _SALARY_LINE.search(whole)
    return [
        JobCandidate(
            source_id=source_id,
            source_job_id=_slug(title)[:80] or "document",
            source_url=source_url,
            title=title[:200],
            employer_name=employer,
            description_md=clean_text(whole)[:20000] or None,
            description_source="pdf_text",
            extraction_confidence=0.6,
            entry_fit=label,
            entry_fit_evidence=evidence,
            employment_type=detect_employment_type(whole, title=title),
            county=resolved_county or county,
            sub_county=sub_county,
            location_raw=raw or None,
            pay=parse_pay(pay_text.group(1) if pay_text else find_pay_text(whole)),
            deadline=find_deadline(whole),
            apply_emails=find_emails(whole),
            scam_flags=flags,
            scam_evidence=flag_evidence,
            status="extracted",
            parser_notes=["single_advert", f"entry_fit_conf={confidence}"],
        )
    ]


def document_to_candidates(
    data: bytes,
    *,
    source_id: str,
    source_url: str,
    content_type: str = "",
    employer: str | None = None,
    county: str | None = None,
    sub_county: str | None = None,
    default_email: str | None = None,
    now=None,
) -> list[JobCandidate]:
    """The one entry point callers need: bytes in, candidates out."""
    text = bytes_to_text(data, content_type)
    sections = parse_bulletin(
        text,
        source_id=source_id,
        source_url=source_url,
        employer=employer,
        county=county,
        sub_county=sub_county,
        default_email=default_email,
        now=now,
    )
    if sections:
        return sections
    return parse_single_advert(
        text, source_id=source_id, source_url=source_url, employer=employer, county=county
    )


def is_bulletin(text: str) -> bool:
    return bool(split_bulletin(text))


def looks_scanned(data: bytes) -> bool:
    """Cheap heuristic for the canary: a PDF with images and no text layer."""
    if data[:5] != b"%PDF-":
        return False
    try:
        _pdf_to_text(data)
    except DocumentError:
        return True
    return False


def document_title(data: bytes, content_type: str = "") -> str:
    """First meaningful line — used for logging and as a fallback title."""
    text = bytes_to_text(data, content_type)
    for line in text.splitlines():
        if clean_text(line):
            return clean_text(line)[:120]
    return "Untitled"
