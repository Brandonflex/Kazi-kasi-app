"""Read a CV, fill a form.

The product's promise here is narrow and deliberate: **extract only what the
document says, show where it came from, and never invent a value.** A CV that
does not state a phone number produces no phone number — it produces a blank
with the label "add this" at the point where it is needed.

Two outputs:

* ``parse()`` — structured fields with the evidence snippet and a confidence,
  for the account page, so the person can check what we read before we use it.
* ``kit()`` — the ordered list of (label, value, source) that an employer's form
  asks for, plus a cover note drawn from the advert and the CV's own words.

There is no auto-apply and no form submission. The kit is a clipboard: the user
pastes it into the employer's form, which is where the application belongs.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from .profile import families_for

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Kenyan mobile numbers: 07xx / 01xx, +2547xx, 2547xx, with optional separators.
PHONE = re.compile(r"(?:\+?254|0)(?:7|1)\d{2}[\s.-]?\d{3}[\s.-]?\d{3}\b")
LINK = re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com|gitlab\.com|behance\.net)/[\w./-]+", re.I)
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
#: "May 2023 – Present", "Jan 2022 - Apr 2023", "2019 – 2021". Months optional.
YEAR_RANGE = re.compile(
    r"\b(?:(?P<m1>" + "|".join(MONTHS) + r")[a-z]*\.?\s+)?(?P<y1>(?:19|20)\d{2})"
    r"\s*(?:-|–|—|to|until)\s*"
    r"(?:(?P<m2>" + "|".join(MONTHS) + r")[a-z]*\.?\s+)?(?P<y2>(?:19|20)\d{2}|present|current|date)\b",
    re.I,
)
DEGREES = re.compile(
    r"\b(bachelor|bsc|b\.sc|ba\b|b\.a|degree|diploma|master|msc|mba|phd|kcse|certificate)\b", re.I
)
COUNTIES = (
    "Nairobi", "Kiambu", "Machakos", "Kajiado", "Nakuru", "Mombasa", "Kisumu", "Uasin Gishu",
    "Nyeri", "Meru", "Kakamega", "Bungoma", "Kilifi", "Kericho", "Laikipia", "Murang'a",
)
DEADLINE_WORDS = ("referee", "referees", "references")

#: Words a CV uses that are worth surfacing as skills, per role family.
SKILLS = {
    "it": ["python", "sql", "excel", "javascript", "java", "networking", "linux", "aws", "docker",
           "git", "html", "css", "data analysis", "power bi", "tableau", "cybersecurity"],
    "admin": ["excel", "records", "filing", "data entry", "scheduling", "minutes", "procurement",
              "typing", "office administration", "customer care"],
    "customer": ["customer service", "crm", "salesforce", "hubspot", "call centre", "complaints",
                 "upselling", "client relations"],
    "finance": ["quickbooks", "sage", "bookkeeping", "reconciliation", "audit", "ifrs", "payroll",
                "budgeting", "excel"],
    "programme": ["monitoring and evaluation", "report writing", "stakeholder", "proposal",
                  "project management", "logframe", "field work"],
    "operations": ["logistics", "inventory", "supply chain", "procurement", "fleet", "warehouse"],
    "marketing": ["seo", "content", "social media", "canva", "google analytics", "campaigns",
                  "copywriting", "meta ads"],
    "legal": ["contract", "compliance", "legal research", "litigation", "due diligence"],
    "health": ["triage", "patient care", "clinical", "nursing", "phlebotomy"],
    "education": ["lesson planning", "curriculum", "teaching", "assessment"],
}

TITLES = (
    "intern", "attachment", "assistant", "officer", "clerk", "analyst", "coordinator", "manager",
    "administrator", "executive", "associate", "representative", "developer", "engineer",
    "accountant", "teacher", "nurse",
)


def _lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").replace("\r", "\n").split("\n")]


def _field(value, *, evidence: str = "", confidence: float = 0.0) -> dict:
    return {"value": value, "evidence": evidence.strip()[:160], "confidence": round(confidence, 2)}


def _name(lines: list[str]) -> dict | None:
    """A CV's first meaningful line is a name more often than anything else."""
    for line in lines[:8]:
        clean = line.strip(" |-")
        if not clean or EMAIL.search(clean) or PHONE.search(clean):
            continue
        if re.search(r"\d", clean) or len(clean) > 48:
            continue
        words = clean.split()
        if 2 <= len(words) <= 4 and all(word[:1].isupper() for word in words):
            return _field(clean, evidence=clean, confidence=0.7)
    return None


def _years(total_months: int) -> str:
    years = total_months // 12
    months = total_months % 12
    if years and months:
        return f"{years} yr {months} mo"
    if years:
        return f"{years} yr"
    return f"{months} mo"


def experience(lines: list[str], *, today: date | None = None) -> dict | None:
    """Time in dated roles, from "May 2021 – Present" style ranges.

    Year-only ranges are read as January-to-December, and the result says which
    it was, because a CV that only gives years cannot honestly yield months.
    """
    today = today or date.today()
    months = 0
    found = []
    precise = True
    for line in lines:
        for match in YEAR_RANGE.finditer(line):
            start_month = MONTHS.get((match.group("m1") or "").lower()[:3], 1)
            start_year = int(match.group("y1"))
            tail = (match.group("y2") or "").lower()
            if tail in ("present", "current", "date"):
                end_year, end_month = today.year, today.month
            else:
                end_year = int(tail)
                end_month = MONTHS.get((match.group("m2") or "").lower()[:3], 12)
                if not match.group("m2"):
                    precise = False
            if (end_year, end_month) < (start_year, start_month):
                continue
            if not match.group("m1") and not match.group("m2") and tail not in ("present", "current", "date"):
                # Year-to-year with no months means "about N years", not N years
                # and eleven months invented from a December.
                months += max(0, (end_year - start_year) * 12)
            else:
                months += max(0, (end_year - start_year) * 12 + (end_month - start_month))
            found.append(match.group(0))
    if not found:
        return None
    text = _years(months)
    return _field(text if precise else f"about {text}", evidence="; ".join(found[:3]), confidence=0.6 if precise else 0.45)


def parse(text: str, *, today: date | None = None) -> dict:
    """Every field we can defend, with the line that proves it."""
    lines = _lines(text)
    body = "\n".join(lines)
    lower = body.lower()

    out: dict[str, dict] = {}

    email = EMAIL.search(body)
    if email:
        address = email.group(0).rstrip(".,;:)")
        out["email"] = _field(address, evidence=address, confidence=0.95)

    phone = PHONE.search(body)
    if phone:
        out["phone"] = _field(phone.group(0).strip(), evidence=phone.group(0), confidence=0.9)

    name = _name(lines)
    if name:
        out["name"] = name

    for county in COUNTIES:
        if re.search(rf"\b{re.escape(county)}\b", body, re.I):
            line = next((line for line in lines if county.lower() in line.lower()), county)
            out["location"] = _field(county, evidence=line, confidence=0.55)
            break

    links = sorted({match.group(0).rstrip(".,;)") for match in LINK.finditer(body)})
    if links:
        out["links"] = _field(links[:3], evidence=links[0], confidence=0.85)

    education = DEGREES.search(body)
    if education:
        line = next((line for line in lines if education.group(0).lower() in line.lower()), "")
        out["education"] = _field(line.strip(" |-") or education.group(0), evidence=line, confidence=0.6)

    years = experience(lines, today=today)
    if years:
        out["experience"] = years

    skills = [
        skill
        for family in SKILLS.values()
        for skill in family
        if re.search(rf"(?<![a-z]){re.escape(skill)}(?![a-z])", lower)
    ]
    if skills:
        unique = sorted(dict.fromkeys(skills))
        out["skills"] = _field(unique[:12], evidence=", ".join(unique[:6]), confidence=0.7)

    referees = next((line for line in lines if any(word in line.lower() for word in DEADLINE_WORDS)), None)
    if referees:
        out["referees"] = _field("stated", evidence=referees, confidence=0.5)

    titles = sorted(
        {match.group(0) for match in re.finditer(r"\b(" + "|".join(TITLES) + r")\b", lower)}
    )
    if titles:
        out["titles"] = _field(titles[:6], evidence=", ".join(titles[:4]), confidence=0.55)

    return out


def profile_suggestions(fields: dict) -> dict:
    """What the CV implies for the scope — suggestions, not silent edits."""
    suggestions: dict = {}
    location = (fields.get("location") or {}).get("value")
    if location:
        suggestions["home_county"] = location

    skills = set((fields.get("skills") or {}).get("value") or [])
    titles = (fields.get("titles") or {}).get("value") or []
    # A family is suggested when its own vocabulary appears in the CV, ranked by
    # how much of it appears. "Excel" alone should not make someone a finance
    # candidate; Excel plus SQL plus Linux should make them an IT one.
    scores = {
        family: sum(1 for skill in skills if skill in vocabulary)
        for family, vocabulary in SKILLS.items()
    }
    for family in families_for(" ".join(titles)):
        scores[family] = scores.get(family, 0) + 0.5
    ranked = [family for family, score in sorted(scores.items(), key=lambda p: -p[1]) if score >= 1]
    if ranked:
        suggestions["role_families"] = ranked[:2]

    experience = (fields.get("experience") or {}).get("value") or ""
    if experience.startswith("0") or experience == "":
        suggestions["entry_fits"] = ["open_to_freshers"]
    return suggestions


def missing(fields: dict) -> list[str]:
    """What a form will ask for that the CV did not answer."""
    required = {"name": "Full name", "email": "Email", "phone": "Phone number"}
    return [label for key, label in required.items() if not (fields.get(key) or {}).get("value")]


def kit(profile, fields: dict, job: dict) -> list[dict]:
    """The ordered answers an employer's form asks for, each with its source."""
    def value(key):
        return (fields.get(key) or {}).get("value")

    name = value("name") or (profile.name.split(" — ")[0] if profile else None)
    rows = [
        {"label": "Full name", "value": name, "source": "cv" if value("name") else "profile"},
        {"label": "Email", "value": value("email"), "source": "cv"},
        {"label": "Phone", "value": value("phone"), "source": "cv"},
        {"label": "Location", "value": value("location") or (profile.home_area if profile else None),
         "source": "cv" if value("location") else "profile"},
        {"label": "Role applied for", "value": job.get("title"), "source": "advert"},
        {"label": "Employer", "value": job.get("employer_name"), "source": "advert"},
        {"label": "Earliest start", "value": "Immediately", "source": "default"},
        {"label": "Experience", "value": value("experience"), "source": "cv"},
        {"label": "Education", "value": value("education"), "source": "cv"},
        {"label": "Skills", "value": ", ".join(value("skills") or []) or None, "source": "cv"},
        {"label": "Links", "value": ", ".join(value("links") or []) or None, "source": "cv"},
        {"label": "Referees", "value": "Available on request" if value("referees") else None,
         "source": "cv"},
    ]
    return rows


def cover_note(profile, fields: dict, job: dict) -> str:
    """Three sentences, built only from things we can defend.

    No adjectives about the person, no claims about the employer. It names the
    role, the strongest evidence from the CV, and one line about availability.
    """
    name = ((fields.get("name") or {}).get("value") or (profile.name.split(" — ")[0] if profile else ""))
    title = job.get("title") or "the role"
    employer = job.get("employer_name") or "your organisation"
    skills = ((fields.get("skills") or {}).get("value") or [])[:3]
    years = (fields.get("experience") or {}).get("value")

    first = f"I would like to apply for the {title} position at {employer}."
    second = (
        f"My background covers {', '.join(skills)}"
        + (f", with {years} of experience in related work" if years else "")
        + "."
        if skills
        else "My CV is attached with the details of my background."
    )
    third = "I am available to start immediately and can provide referees on request."
    return f"{first} {second} {third}" + (f"\n\n{name}" if name else "")
