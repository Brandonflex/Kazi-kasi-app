"""Extraction and normalisation.

Everything here is deterministic: regex, rules, and arithmetic. No model calls.
That is deliberate — the ingestion critical path must be replayable and cheap.

Where a judgement is uncertain the function must say so in its return value
(``confidence``, ``evidence``, ``unknown``) rather than guess silently.
"""

from __future__ import annotations

import html as html_lib
import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from bs4 import BeautifulSoup

from .models import JobPay

# --------------------------------------------------------------------------
# Text hygiene
# --------------------------------------------------------------------------

_WS = re.compile(r"\s+")
_MULTI_NL = re.compile(r"\n{3,}")


def clean_text(value: str | None) -> str:
    """Collapse any run of whitespace (including NBSP) to one space.

    Used for single-line fields. ``html_to_text`` is the one that preserves
    paragraph breaks.
    """
    if not value:
        return ""
    value = html_lib.unescape(value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = _WS.sub(" ", value)
    return value.strip()


def html_to_text(markup: str | None) -> str:
    if not markup:
        return ""
    soup = BeautifulSoup(markup, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return clean_text(soup.get_text("\n"))


_STOPWORDS = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "at", "on"}


def normalize_title(title: str) -> str:
    """Lowercased, punctuation-stripped title used for identity, not display."""
    t = clean_text(title).lower()
    t = re.sub(r"\((?:m|f|d|m/f/d|male/female)\)", " ", t)
    t = re.sub(r"[/\-–—_,;:]+", " ", t)
    t = re.sub(r"[^\w\s+#.]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def title_tokens(title: str) -> set[str]:
    return {w for w in normalize_title(title).split() if w not in _STOPWORDS and len(w) > 1}


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Ordered: ISO first, then day-month-year, then month-day-year, then numeric.
_DATE_PATTERNS = (
    re.compile(r"(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})"),
    re.compile(r"(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?P<mon>[A-Za-z]{3,9})\.?,?\s+(?P<y>\d{4})"),
    re.compile(r"(?P<mon>[A-Za-z]{3,9})\.?\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<y>\d{4})"),
    re.compile(r"(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{4})"),
    re.compile(r"(?P<d>\d{1,2})-(?P<m>\d{1,2})-(?P<y>\d{4})"),
)

_RELATIVE = re.compile(r"(\d+)\s*(day|week|month)s?\s*(?:ago|old)", re.I)

_DEADLINE_LABEL = re.compile(
    r"(?:deadline|closing\s*date|closing\s*on|applications?\s*close[sd]?|apply\s*(?:on\s*or\s*)?before)"
    r"[^\n]{0,40}",
    re.I,
)


def _date_from_match(match: re.Match) -> date | None:
    groups = match.groupdict()
    try:
        year = int(groups.get("y"))
        day = int(groups["d"])
        month_raw = groups.get("m") or groups.get("mon")
        if month_raw is None:
            return None
        month = int(month_raw) if month_raw.isdigit() else _MONTHS.get(month_raw.lower().rstrip("."))
        if month is None:
            return None
        return date(year, month, day)
    except (TypeError, ValueError):
        return None


def parse_date(value: str | None, today: date | None = None) -> date | None:
    """Find and parse the first date in a string.

    Works on prose as well as clean values ("Deadline for applications: 30
    November 2026. Send your..." → 2026-11-30), because on Kenyan boards the
    deadline usually lives in a sentence, not a field.
    """
    if not value:
        return None
    text = clean_text(value)
    if not text:
        return None
    today = today or date.today()

    lowered = text.lower()
    if "today" in lowered:
        return today
    if "yesterday" in lowered:
        return today - timedelta(days=1)

    relative = _RELATIVE.search(lowered)
    if relative:
        n = int(relative.group(1))
        unit = relative.group(2).lower()
        return today - timedelta(days=n * {"day": 1, "week": 7, "month": 30}[unit])

    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            parsed = _date_from_match(match)
            if parsed:
                return parsed
    return None


def find_deadline(text: str | None, today: date | None = None) -> date | None:
    """Look for a labelled deadline first, then fall back to no deadline at all.

    Deliberately does *not* return an unlabelled date: on a job page an
    arbitrary date is more likely to be the posting date than the closing date,
    and a wrong deadline closes a live job.
    """
    for match in _DEADLINE_LABEL.finditer(text or ""):
        parsed = parse_date(match.group(0), today=today)
        if parsed:
            return parsed
    return None


# --------------------------------------------------------------------------
# Pay
# --------------------------------------------------------------------------

_CURRENCY_HINTS = (
    ("kes", "KES"),
    ("kshs", "KES"),
    ("ksh", "KES"),
    ("shs", "KES"),
    ("usd", "USD"),
    ("us$", "USD"),
    ("$", "USD"),
    ("eur", "EUR"),
    ("€", "EUR"),
    ("gbp", "GBP"),
    ("£", "GBP"),
)

_AMOUNT = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*([km])?\b", re.I)

_CONFIDENTIAL = re.compile(
    r"\b(confidential|negotiable|competitive|not disclosed|undisclosed|attractive)\b", re.I
)


def _detect_currency(text: str) -> str:
    lowered = text.lower()
    for hint, code in _CURRENCY_HINTS:
        if hint in lowered:
            return code
    return "KES"


def _detect_period(text: str) -> str | None:
    lowered = text.lower()
    if re.search(r"per\s*annum|p\.?a\.?\b|annually|per\s*year|/\s*year|yearly|annual", lowered):
        return "year"
    if re.search(r"per\s*month|/\s*month|monthly|p\.?m\.?\b|a\s*month|\bpm\b", lowered):
        return "month"
    if re.search(r"per\s*day|/\s*day|daily|\bday\b", lowered):
        return "day"
    if re.search(r"per\s*hour|/\s*hour|hourly|hr\b", lowered):
        return "hour"
    return None


def _detect_gross_net(text: str) -> str:
    lowered = text.lower()
    if re.search(r"\bnet\b|take[\s-]?home", lowered):
        return "net"
    if re.search(r"\bgross\b|\bctc\b", lowered):
        return "gross"
    return "unknown"


def parse_pay(value: str | None, *, infer_from_magnitude: bool = True) -> JobPay:
    """Parse a free-text salary string into structured pay.

    Kenyan boards frequently write "Confidential", so an empty result is a
    legitimate and common outcome — not an error.
    """
    if not value:
        return JobPay()
    text = clean_text(value)
    if not text:
        return JobPay()

    amounts: list[float] = []
    for match in _AMOUNT.finditer(text):
        raw = match.group(1).replace(",", "")
        try:
            number = float(raw)
        except ValueError:
            continue
        multiplier = (match.group(2) or "").lower()
        if multiplier == "k":
            number *= 1_000
        elif multiplier == "m":
            number *= 1_000_000
        # Reject incidental numbers: years of experience, "3 posts", dates.
        if not multiplier and number < 1_000:
            continue
        amounts.append(number)
        if len(amounts) == 2:
            break

    if not amounts:
        return JobPay()

    currency = _detect_currency(text)
    period = _detect_period(text)
    gross_net = _detect_gross_net(text)
    confidence = 0.9 if period else 0.75
    source = "parsed"

    if period is None and infer_from_magnitude:
        # Kenyan convention: monthly salaries sit in the tens of thousands;
        # annual packages are quoted in the millions when no period is given.
        period = "year" if max(amounts) >= 1_000_000 else "month"
        confidence = 0.5
        source = "inferred"

    return JobPay(
        min_amount=min(amounts),
        max_amount=max(amounts),
        currency=currency,
        period=period,
        gross_net=gross_net,
        source=source,
        confidence=confidence,
    )


_PAY_CURRENCY = re.compile(r"(?:kshs?|kes|usd|us\$|\$|eur|€|gbp|£|/=)", re.I)
_PAY_KEYWORD = re.compile(r"\b(salary|stipend|allowance|remuneration|pay|wage|compensation)\b", re.I)
_PAY_AMOUNT = re.compile(r"\d[\d,]{2,}")


def find_pay_text(text: str | None, max_chars: int = 180) -> str | None:
    """Find the sentence that states pay, if any.

    Needed because most Kenyan adverts bury the figure in prose ("a stipend of
    KSh 20,000 per month") with no salary field or class to hook onto.
    """
    if not text:
        return None
    segments = re.split(r"(?<=[.!?;])\s+|\n+", clean_text(text))
    for segment in segments:
        if not _PAY_AMOUNT.search(segment):
            continue
        if _PAY_CURRENCY.search(segment) or _PAY_KEYWORD.search(segment):
            return segment[:max_chars]
    return None


def to_monthly(pay: JobPay) -> float | None:
    """Convert a pay object to a monthly figure for comparison. None if unsafe."""
    if pay.is_empty or not pay.period:
        return None
    base = pay.min_amount if pay.min_amount is not None else pay.max_amount
    if base is None:
        return None
    factor = {"month": 1, "year": 1 / 12, "day": 22, "hour": 176}.get(pay.period)
    if factor is None:
        return None
    return round(base * factor, 2)


# --------------------------------------------------------------------------
# Entry fit — the field the market is missing
# --------------------------------------------------------------------------

_FRESH_PHRASES = (
    "fresh graduate",
    "fresh graduates",
    "recent graduate",
    "recent graduates",
    "no experience required",
    "no prior experience",
    "no experience necessary",
    "entry level",
    "entry-level",
    "graduate trainee",
    "graduate programme",
    "graduate program",
    "school leaver",
    "internship",
    "attachment",
    "trainee",
)

_WORD_TO_DIGIT = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

_NUMBER_WORDS = re.compile(
    r"\b(" + "|".join(_WORD_TO_DIGIT) + r")\s*(?:\+)?\s*years?\b", re.I
)

_YEARS_PATTERNS = (
    re.compile(r"(\d+)\s*(?:\+|plus)?\s*(?:to|-|–)\s*(\d+)\s*years?", re.I),
    re.compile(
        r"(?:at least|minimum(?: of)?|over|more than|not less than)\s*(\d+)\s*years?", re.I
    ),
    re.compile(r"(\d+)\s*(?:\+|plus)\s*years?", re.I),
    re.compile(r"(\d+)\s*years?(?:'|\u2019)?\s*(?:of\s+)?(?:relevant\s+)?experience", re.I),
)


def entry_fit(text: str | None) -> tuple[str, str | None, float]:
    """Classify eligibility for a 0–3 year candidate, with quoted evidence.

    Returns ``(label, evidence, confidence)`` where label is one of
    ``open_to_freshers`` / ``some_experience`` / ``experienced`` / ``unknown``.

    When a posting contradicts itself ("fresh graduates encouraged" plus
    "minimum 3 years"), the stricter requirement wins and both phrases are
    quoted in the evidence. The user is better served by a cautious label.
    """
    if not text:
        return "unknown", None, 0.0
    body = clean_text(text)
    body = _NUMBER_WORDS.sub(lambda m: f"{_WORD_TO_DIGIT[m.group(1).lower()]} years", body)
    lowered = body.lower()

    fresh_hit = next((p for p in _FRESH_PHRASES if p in lowered), None)

    required_years: list[int] = []
    ranges = [m for m in _YEARS_PATTERNS[0].finditer(lowered)]
    if ranges:
        # "1-2 years" asks for one year; taking the upper bound would push a
        # fresher-eligible role into "experienced".
        required_years.extend(int(m.group(1)) for m in ranges)
    for pattern in _YEARS_PATTERNS[1:]:
        for match in pattern.finditer(lowered):
            for group in match.groups():
                if group and group.isdigit():
                    required_years.append(int(group))
    max_years = max(required_years) if required_years else None

    def _quote(phrase: str) -> str:
        idx = lowered.find(phrase)
        if idx < 0:
            return phrase
        start = max(0, idx - 60)
        end = min(len(body), idx + len(phrase) + 60)
        return clean_text(body[start:end])

    if max_years is not None:
        if max_years >= 2:
            label = "experienced"
        elif max_years == 1:
            label = "some_experience"
        else:
            label = "open_to_freshers"
        evidence = _quote(f"{max_years} year")
        if fresh_hit and label != "open_to_freshers":
            evidence = f"{evidence} | also says: “{_quote(fresh_hit)}”"
        return label, evidence, 0.9

    if fresh_hit:
        return "open_to_freshers", _quote(fresh_hit), 0.8

    return "unknown", None, 0.0


# --------------------------------------------------------------------------
# Employment type, work mode, seniority
# --------------------------------------------------------------------------

def detect_employment_type(text: str | None, *, title: str | None = None) -> str:
    """Read the type from the title first, then the body.

    Titles are the applicant-facing truth: an advert titled "Marketing Intern"
    that also offers "attachment friendly" placement is an internship, and
    matching the body first would misfile it.
    """
    from_title = _employment_type_from(str(title or ""))
    if from_title != "unknown":
        return from_title
    return _employment_type_from(str(text or ""))


def _employment_type_from(text: str) -> str:
    # schema.org uses FULL_TIME / CONTRACTOR / INTERN; the boards use prose.
    lowered = text.lower().replace("_", " ").replace("-", " ")
    if re.search(r"\battachment\b|industrial attach", lowered):
        return "attachment"
    if re.search(r"\bintern(?:ship|s)?\b", lowered):
        return "internship"
    if re.search(r"\bvolunteer", lowered):
        return "volunteer"
    if re.search(r"\bpart[\s-]?time\b", lowered):
        return "part_time"
    if re.search(r"\bcontract\b|fixed[\s-]?term|\bconsultanc", lowered):
        return "contract"
    if re.search(r"\b(?:temporary|casual)\b", lowered):
        return "temporary"
    if re.search(r"\bfull[\s-]?time\b|permanent", lowered):
        return "full_time"
    return "unknown"


def detect_work_mode(text: str | None, location: str | None = None) -> tuple[str, str]:
    lowered = f"{text or ''}".lower()
    loc = (location or "").lower()
    if re.search(r"\bfully remote\b|100%\s*remote|remote position|work from home|wfh\b", lowered):
        return "remote", "posting"
    if re.search(r"\bhybrid\b", lowered):
        return "hybrid", "posting"
    if re.search(r"\bon[\s-]?site\b|in[\s-]office\b", lowered):
        return "onsite", "posting"
    if "remote" in loc or "work from home" in loc:
        return "remote", "posting"
    if loc and not re.search(r"\bremote\b", loc):
        # A concrete place was named and the posting never said otherwise.
        # Recorded as an inference, not as the posting's own words.
        return "onsite", "inferred_from_location"
    return "unknown", "unknown"


def detect_seniority(title: str | None, text: str | None = None) -> str:
    lowered = f"{title or ''} {text or ''}".lower()
    if re.search(r"\b(intern|attachment|trainee)\b", lowered):
        return "intern"
    if re.search(r"\bgraduate\b", lowered):
        return "graduate"
    if re.search(r"\b(director|head of|chief|vp|vice president|managing director)\b", lowered):
        return "executive"
    if re.search(r"\b(manager|supervisor|lead|principal)\b", lowered):
        return "lead"
    if re.search(r"\b(senior|snr)\b", lowered):
        return "senior"
    if re.search(r"\b(junior|assistant|officer|clerk|associate)\b", lowered):
        return "junior"
    return "unknown"


# --------------------------------------------------------------------------
# Locations
# --------------------------------------------------------------------------

KENYA_COUNTIES = (
    "Baringo", "Bomet", "Bungoma", "Busia", "Elgeyo-Marakwet", "Embu", "Garissa",
    "Homa Bay", "Isiolo", "Kajiado", "Kakamega", "Kericho", "Kiambu", "Kilifi",
    "Kirinyaga", "Kisii", "Kisumu", "Kitui", "Kwale", "Laikipia", "Lamu",
    "Machakos", "Makueni", "Mandera", "Marsabit", "Meru", "Migori", "Mombasa",
    "Murang'a", "Nairobi", "Nakuru", "Nandi", "Narok", "Nyamira", "Nyandarua",
    "Nyeri", "Samburu", "Siaya", "Taita-Taveta", "Tana River", "Tharaka-Nithi",
    "Trans Nzoia", "Turkana", "Uasin Gishu", "Vihiga", "Wajir", "West Pokot",
)

_COUNTY_ALIASES = {
    "nairobi": "Nairobi",
    "nairobi city": "Nairobi",
    "nairobi county": "Nairobi",
    "mombasa": "Mombasa",
    "kisumu": "Kisumu",
    "nakuru": "Nakuru",
    "eldoret": "Uasin Gishu",
    "thika": "Kiambu",
    "kitengela": "Kajiado",
    "ruiru": "Kiambu",
    "karen": "Nairobi",
    "westlands": "Nairobi",
    "kiambu": "Kiambu",
    "machakos": "Machakos",
    "nyeri": "Nyeri",
    "meru": "Meru",
}

SUB_COUNTIES_NAIROBI = (
    "Westlands", "Dagoretti", "Langata", "Kibra", "Roysambu", "Kasarani",
    "Ruaraka", "Embakasi", "Makadara", "Kamukunji", "Starehe", "Mathare",
)

#: Well-known employment districts → sub-county. Approximate by design: they are
#: used for distance bands, never for a precise pin. Anything not here keeps
#: ``sub_county=None`` rather than guessing.
KNOWN_AREAS = {
    "industrial area": ("Nairobi", "Starehe"),
    "upper hill": ("Nairobi", "Starehe"),
    "cbd": ("Nairobi", "Starehe"),
    "city centre": ("Nairobi", "Starehe"),
    "city center": ("Nairobi", "Starehe"),
    "south b": ("Nairobi", "Starehe"),
    "south c": ("Nairobi", "Langata"),
    "kilimani": ("Nairobi", "Dagoretti"),
    "kileleshwa": ("Nairobi", "Dagoretti"),
    "lavington": ("Nairobi", "Dagoretti"),
    "ngong road": ("Nairobi", "Dagoretti"),
    "karen": ("Nairobi", "Langata"),
    "madaraka": ("Nairobi", "Langata"),
    "gigiri": ("Nairobi", "Westlands"),
    "parklands": ("Nairobi", "Westlands"),
    "mombasa road": ("Nairobi", "Embakasi"),
    "thika road": ("Nairobi", "Kasarani"),
    "ruaraka": ("Nairobi", "Ruaraka"),
}


def parse_location(value: str | None) -> tuple[str | None, str | None, str]:
    """Return ``(county, sub_county, raw)`` from a free-text Kenyan location."""
    raw = clean_text(value)
    if not raw:
        return None, None, ""
    lowered = raw.lower().replace("county", "").strip()

    for area, (county, sub) in KNOWN_AREAS.items():
        if re.search(rf"\b{re.escape(area)}\b", lowered):
            return county, sub, raw

    for alias, county in _COUNTY_ALIASES.items():
        if alias in lowered:
            sub = next((s for s in SUB_COUNTIES_NAIROBI if s.lower() in lowered), None)
            return county, sub, raw

    for county in KENYA_COUNTIES:
        if county.lower() in lowered:
            return county, None, raw

    return None, None, raw


# --------------------------------------------------------------------------
# schema.org JobPosting
# --------------------------------------------------------------------------

def _iter_jsonld_blocks(soup: BeautifulSoup) -> list[Any]:
    blocks: list[Any] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        text = script.string or script.get_text()
        if not text or not text.strip():
            continue
        try:
            blocks.append(json.loads(text))
        except json.JSONDecodeError:
            # Some sites emit trailing commas or multiple concatenated objects.
            for chunk in re.split(r"}\s*{", text):
                chunk = chunk.strip()
                if not chunk:
                    continue
                if not chunk.startswith("{"):
                    chunk = "{" + chunk
                if not chunk.endswith("}"):
                    chunk = chunk + "}"
                try:
                    blocks.append(json.loads(chunk))
                except json.JSONDecodeError:
                    continue
    return blocks


def _flatten(nodes: Any) -> list[dict]:
    out: list[dict] = []
    if isinstance(nodes, list):
        for node in nodes:
            out.extend(_flatten(node))
    elif isinstance(nodes, dict):
        if "@graph" in nodes:
            out.extend(_flatten(nodes["@graph"]))
            return out
        types = nodes.get("@type")
        types = types if isinstance(types, list) else [types]
        if any(t and str(t).lower() == "jobposting" for t in types):
            out.append(nodes)
        # A JobPosting nested under an itemListElement is still a JobPosting.
        for key in ("itemListElement", "item", "mainEntity"):
            if key in nodes:
                out.extend(_flatten(nodes[key]))
    return out


def extract_jobpostings(html: str) -> list[dict]:
    """Extract every ``schema.org/JobPosting`` from a page's JSON-LD.

    Handles a single object, a top-level array, ``@graph``, and JobPostings
    nested inside ``itemListElement``. Never raises on malformed markup.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    found: list[dict] = []
    for block in _iter_jsonld_blocks(soup):
        found.extend(_flatten(block))
    return found


def _org_name(posting: dict) -> str | None:
    org = posting.get("hiringOrganization")
    if isinstance(org, dict):
        return clean_text(org.get("name")) or None
    if isinstance(org, str):
        return clean_text(org) or None
    return None


def _org_domain(posting: dict) -> str | None:
    org = posting.get("hiringOrganization")
    candidates: list[str] = []
    if isinstance(org, dict):
        same_as = org.get("sameAs")
        if isinstance(same_as, str):
            candidates.append(same_as)
        elif isinstance(same_as, list):
            candidates.extend(str(s) for s in same_as)
    for url in candidates:
        m = re.match(r"https?://([^/]+)", url)
        if m:
            return m.group(1).lower().lstrip("www.")
    return None


def _posting_location(posting: dict) -> str | None:
    locations = posting.get("jobLocation")
    items = locations if isinstance(locations, list) else [locations]
    for item in items:
        if isinstance(item, dict):
            address = item.get("address")
            if isinstance(address, dict):
                parts = [
                    address.get("addressLocality"),
                    address.get("addressRegion"),
                    address.get("addressCountry"),
                ]
                joined = ", ".join(str(p) for p in parts if p)
                if joined:
                    return clean_text(joined)
            if isinstance(address, str):
                return clean_text(address)
            name = item.get("name")
            if name:
                return clean_text(str(name))
    if posting.get("jobLocationType") == "TELECOMMUTE":
        return "Remote"
    return None


def _posting_salary(posting: dict) -> str | None:
    salary = posting.get("baseSalary")
    if not isinstance(salary, dict):
        return None
    value = salary.get("value")
    if isinstance(value, dict):
        low, high = value.get("minValue"), value.get("maxValue")
        unit = value.get("unitText") or ""
        currency = salary.get("currency") or ""
        if low and high:
            return f"{currency} {low} - {high} {unit}".strip()
        if low or high or value.get("value"):
            return f"{currency} {low or high or value.get('value')} {unit}".strip()
    if isinstance(value, (int, float, str)):
        return f"{salary.get('currency', '')} {value}".strip()
    return None


def jsonld_to_candidate_fields(posting: dict) -> dict[str, Any]:
    """Map a JobPosting dict onto our field names. Missing values stay absent."""
    fields: dict[str, Any] = {}
    if posting.get("title"):
        fields["title"] = clean_text(posting["title"])
    if posting.get("description"):
        fields["description_text"] = html_to_text(posting["description"])
        fields["description_source"] = "html"
    if _org_name(posting):
        fields["employer_name"] = _org_name(posting)
    if _org_domain(posting):
        fields["employer_domain"] = _org_domain(posting)
    if _posting_location(posting):
        fields["location_raw"] = _posting_location(posting)
    if _posting_salary(posting):
        fields["pay_text"] = _posting_salary(posting)
    if posting.get("datePosted"):
        fields["date_posted_text"] = str(posting["datePosted"])
    if posting.get("validThrough"):
        fields["deadline_text"] = str(posting["validThrough"])
    if posting.get("employmentType"):
        fields["employment_type_text"] = str(posting["employmentType"])

    identifier = posting.get("identifier")
    if isinstance(identifier, dict) and identifier.get("value"):
        fields["identifier"] = str(identifier["value"])
    elif isinstance(identifier, str):
        fields["identifier"] = identifier

    url = posting.get("url")
    if isinstance(url, str):
        fields["apply_url"] = url
    return fields


# --------------------------------------------------------------------------
# Contacts, references, and scam signals
# --------------------------------------------------------------------------

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_KE = re.compile(r"(?:\+?254|0)\s?7\d{2}[\s\-]?\d{3}[\s\-]?\d{3}")
_REF = re.compile(
    r"\b(?:V/No|VACANCY\s*NO|REF(?:ERENCE)?(?:\s*NO)?|ADVERT\s*NO)[.:\s#-]*([A-Z0-9][A-Z0-9/._-]{2,})",
    re.I,
)

_FEE = re.compile(
    r"(?:registration|processing|application|interview|training|placement|medical)\s*fee"
    r"|pay(?:able)?\s*(?:a\s*)?(?:fee|ksh|kes)"
    r"|send\s*(?:ksh|kes|money)"
    r"|\bdeposit\b.{0,40}(?:ksh|kes)",
    re.I,
)


def find_emails(text: str | None) -> list[str]:
    return sorted({e.lower() for e in _EMAIL.findall(text or "")})


def find_reference(text: str | None) -> str | None:
    match = _REF.search(text or "")
    return match.group(1).rstrip(".,;") if match else None


def detect_scam_flags(
    text: str | None,
    *,
    emails: list[str] | None = None,
    employer_domain: str | None = None,
    employer_name: str | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Return named criteria plus the quoted evidence for each.

    We flag the *posting*, never a person, and never on a score alone.
    """
    body = text or ""
    lowered = body.lower()
    emails = emails if emails is not None else find_emails(body)
    flags: list[str] = []
    evidence: dict[str, str] = {}

    fee = _FEE.search(body)
    if fee:
        flags.append("fee_requested")
        evidence["fee_requested"] = clean_text(fee.group(0))[:160]

    if re.search(r"wa\.me/|chat\.whatsapp\.com|whatsapp\s*(?:us|only|number)", lowered):
        if not emails:
            flags.append("whatsapp_only")
            evidence["whatsapp_only"] = "Application is via WhatsApp only"

    if _PHONE_KE.search(body) and not emails and not employer_domain:
        flags.append("personal_number_only")
        evidence["personal_number_only"] = _PHONE_KE.search(body).group(0)  # type: ignore[union-attr]

    if not employer_name and not employer_domain:
        flags.append("no_employer_identity")
        evidence["no_employer_identity"] = "No registered employer name or domain in the posting"

    if re.search(r"no\s+interview\s+(?:required|needed)|immediate\s+start.{0,40}no\s+interview", lowered):
        flags.append("no_interview_process")
        evidence["no_interview_process"] = "Advertises no interview process"

    if employer_domain and emails:
        domains = {e.split("@", 1)[1] for e in emails}
        if not any(d == employer_domain or d.endswith("." + employer_domain) for d in domains):
            flags.append("domain_mismatch")
            evidence["domain_mismatch"] = (
                f"Apply email(s) {', '.join(sorted(domains))} do not match {employer_domain}"
            )

    return sorted(set(flags)), evidence


def scam_level(flags: list[str]) -> str | None:
    """Two independent criteria, or any direct request for money."""
    if "fee_requested" in flags or "copy_of_known_scam" in flags:
        return "likely_scam"
    if len(flags) >= 2:
        return "suspicious"
    return None
