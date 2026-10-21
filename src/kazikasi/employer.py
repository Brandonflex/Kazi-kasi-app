"""What the advert itself says about who you would be dealing with.

There is a tempting version of this feature that scrapes LinkedIn for names,
guesses email addresses and presents a "hiring team" it cannot verify. We do not
build that version. Everything below is extracted from the advert we already
hold, quoted, and labelled with where it came from — and when the advert names
nobody, the page says so instead of filling the space.

The shape of the answer:

* **How to apply** — the channel the advert actually specifies (portal, email,
  post, hand delivery), because applying the wrong way is a silent rejection.
* **A named contact**, if one is written down, with the sentence that named them.
* **What is missing** — no named contact, no email, no phone: stated plainly.
* **Connects** — deliberately empty. We do not have somebody's network and will
  not invent one; the page offers the honest alternative (ask a classmate, use
  the shortlist, or come back once referrals exist).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?:\+?254|0)(?:7|1)\d{2}[\s.-]?\d{3}[\s.-]?\d{3}")
NAMED = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof|Eng)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}"
)
ROLE_WORDS = (
    "human resource manager", "hr manager", "human resources officer", "managing director",
    "chief executive", "executive director", "recruitment officer", "administrator",
    "head of", "director", "manager", "officer",
)
PORTALS = {
    "erecruitment": "the government e-recruitment portal",
    "psckjobs": "the PSC portal",
    "brightermonday": "BrighterMonday",
    "fuzu": "Fuzu",
    "myjobmag": "MyJobMag",
    "linkedin": "LinkedIn",
}
INSTRUCTIONS = re.compile(
    r"(applications?\s+(?:should|must|are)\s+(?:be\s+)?(?:sent|submitted|addressed|delivered)"
    r"[^.]{0,200}\.)",
    re.I,
)


@dataclass
class Contact:
    kind: str                 # how to apply | named contact | email | phone | address
    value: str
    evidence: str
    confidence: float = 0.6

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "value": self.value,
            "evidence": self.evidence,
            "confidence": self.confidence,
        }


@dataclass
class Dossier:
    channel: str = "the employer's own site"
    instructions: str | None = None
    contacts: list[Contact] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "channel": self.channel,
            "instructions": self.instructions,
            "contacts": [contact.to_dict() for contact in self.contacts],
            "missing": self.missing,
        }


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if part.strip()]


def read(description: str | None, *, source_id: str | None = None, employer_domain: str | None = None) -> Dossier:
    """Read the advert. Never guess; record the sentence that proves each claim."""
    text = (description or "").strip()
    dossier = Dossier()

    for key, label in PORTALS.items():
        if source_id and key in source_id.lower():
            dossier.channel = label
            break

    match = INSTRUCTIONS.search(text)
    if match:
        dossier.instructions = match.group(1)[:300]

    email = EMAIL.search(text)
    if email:
        address = email.group(0).rstrip(".,;:)")
        sentence = next((s for s in _sentences(text) if address in s), address)
        dossier.contacts.append(Contact("email", address, sentence[:200], 0.9))
        if "email" not in dossier.channel.lower():
            dossier.channel = "email"

    phone = PHONE.search(text)
    if phone:
        sentence = next((s for s in _sentences(text) if phone.group(0) in s), phone.group(0))
        dossier.contacts.append(Contact("phone", phone.group(0), sentence[:200], 0.85))

    named = NAMED.search(text)
    if named:
        sentence = next((s for s in _sentences(text) if named.group(0) in s), named.group(0))
        dossier.contacts.append(Contact("named contact", named.group(0), sentence[:200], 0.7))
    else:
        role = next(
            (
                word
                for word in ROLE_WORDS
                if re.search(rf"\b{re.escape(word)}\b", text, re.I)
            ),
            None,
        )
        if role:
            sentence = next((s for s in _sentences(text) if role in s.lower()), role)
            dossier.contacts.append(Contact("role", role.title(), sentence[:200], 0.5))

    if employer_domain:
        dossier.contacts.append(Contact("employer domain", employer_domain, employer_domain, 0.8))

    if not any(contact.kind in ("email", "phone") for contact in dossier.contacts):
        dossier.missing.append("no email or phone number in the advert")
    if not named:
        dossier.missing.append("no named person to address your application to")
    if not dossier.instructions:
        dossier.missing.append("no closing instructions beyond the deadline")

    return dossier


def opens(conn, job_id: str) -> int:
    """How many times this advert has been opened here — a real number or nothing."""
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM apply_events WHERE job_id = ? AND kind = 'viewed'", (job_id,)
    ).fetchone()
    return int(row["c"]) if row else 0
