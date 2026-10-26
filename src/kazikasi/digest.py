"""The WhatsApp digest: what gets sent, in what order, and how it reads.

D5 chose two surfaces: a web feed and a WhatsApp digest. This is the digest.
It is deliberately a *composition* problem first and a transport problem second,
because the hard parts are editorial:

* **A digest is not the feed.** Five cards, closing soonest first, and nothing
  the person has already seen, applied to, or dismissed. A daily push that
  repeats yesterday's list is a notification people mute.
* **Every line must survive WhatsApp.** No markdown tables, no nested bullets,
  no long URLs - WhatsApp renders `*bold*` only, and a URL eats the preview.
* **It has to fit.** WhatsApp caps a text message at 4096 characters. A digest
  that silently truncates mid-sentence is worse than one that sends fewer cards.
* **Consent is part of the model**, not an afterthought: Kenya's DPA 2019 wants
  a record of when someone agreed, to what, and how they stop.

The transport is behind an interface (``channels.py``) so the whole thing runs
and is tested offline. No WhatsApp credentials are required to prove the logic.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

#: Kenya is UTC+3 year round; no daylight saving.
EAT = timezone(timedelta(hours=3))

#: WhatsApp Cloud API limit for a text body.
WHATSAPP_TEXT_LIMIT = 4096
#: One SMS segment in GSM-7 is 160 characters; multipart drops to 153.
SMS_SEGMENT = 160

DEFAULT_MAX_ITEMS = 5


# --------------------------------------------------------------------------
# Phone numbers
# --------------------------------------------------------------------------


def normalise_msisdn(value: str) -> str:
    """Kenyan numbers → E.164. Raises on anything that is not a mobile number.

    Accepts ``0712 345 678``, ``+254712345678``, ``254712345678`` and
    ``0712345678``. Refusing to guess is the point: a digest sent to a typo is
    a message about someone's job search delivered to a stranger.
    """
    digits = re.sub(r"[^\d]", "", (value or "").strip())
    if digits.startswith("254"):
        national = digits[3:]
    elif digits.startswith("0"):
        national = digits[1:]
    elif digits.startswith(("7", "1")):
        national = digits
    else:
        raise ValueError(f"not a Kenyan mobile number: {value!r}")

    if len(national) != 9 or not re.fullmatch(r"[17]\d{8}", national):
        raise ValueError(f"not a Kenyan mobile number: {value!r}")
    return "+254" + national


def mask_msisdn(msisdn: str) -> str:
    """``+254712345678`` → ``+2547•••5678``. For logs and previews."""
    if not msisdn or len(msisdn) < 8:
        return "•••"
    return f"{msisdn[:5]}•••{msisdn[-4:]}"


#: Key for the MSISDN hash. Set ``KAZIKASI_HASH_KEY`` in production.
HASH_KEY_ENV = "KAZIKASI_HASH_KEY"
_DEVELOPMENT_PEPPER = b"kazikasi-development-pepper-v1"

MASKED_SALT_WARNING = (
    "KAZIKASI_HASH_KEY is not set: numbers are hashed with the development "
    "pepper, which is public. Set it before storing real phone numbers."
)


def _hash_key() -> bytes:
    configured = os.environ.get(HASH_KEY_ENV)
    return configured.encode("utf-8") if configured else _DEVELOPMENT_PEPPER


def hash_is_keyed() -> bool:
    """Whether the number hash is keyed with a deployment secret."""
    return bool(os.environ.get(HASH_KEY_ENV))


def hash_msisdn(msisdn: str) -> str:
    """A stable handle for a number that cannot be brute-forced back to it.

    A plain SHA-256 of a Kenyan mobile number is not a privacy measure: the whole
    space is roughly 2×10⁸ candidates, which a laptop walks through in minutes.
    Keying it with a deployment secret (HMAC) is what makes it one - and the
    unkeyed fallback says so out loud rather than pretending.
    """
    return hmac.new(_hash_key(), msisdn.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


# --------------------------------------------------------------------------
# Quoting
# --------------------------------------------------------------------------


def shorten(text: str | None, limit: int) -> str:
    """Trim at a word boundary, with an ellipsis. Never mid-word."""
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if len(clean) <= limit:
        return clean
    cut = clean[: limit - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:.") + "…"


def one_line(text: str | None) -> str:
    """Strip characters that break a WhatsApp line (newlines, tabs, zero-width)."""
    normalised = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", " ", normalised.replace("\u200b", "")).strip()


def pay_line(row: dict) -> str | None:
    low, high, period = row.get("pay_min"), row.get("pay_max"), row.get("pay_period") or "month"
    if not low and not high:
        return None
    if low and high and low != high:
        return f"KES {low:,.0f}–{high:,.0f}/{period}"
    return f"KES {(low or high):,.0f}/{period}"


def deadline_phrase(row: dict, today: date) -> str | None:
    value = row.get("deadline")
    if not value:
        return None
    try:
        deadline = date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
    days = (deadline - today).days
    if days < 0:
        return "closed"
    if days == 0:
        return "closes today"
    if days == 1:
        return "closes tomorrow"
    if days <= 7:
        return f"closes in {days} days"
    return f"closes {deadline.strftime('%d %b')}"


def place_line(row: dict) -> str | None:
    sub, county = row.get("sub_county"), row.get("county")
    if sub and county:
        return f"{sub}, {county}"
    return county or None


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------


@dataclass
class DigestItem:
    job_id: str
    title: str
    employer: str | None
    score: float
    reasons: list[str]
    row: dict
    position: int = 0

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "title": self.title,
            "employer": self.employer,
            "score": round(self.score, 3),
            "position": self.position,
            "reasons": self.reasons,
        }


@dataclass
class Digest:
    profile_id: str
    profile_name: str
    for_date: date
    items: list[DigestItem] = field(default_factory=list)
    skipped: dict[str, int] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.items

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "for_date": self.for_date.isoformat(),
            "items": [item.to_dict() for item in self.items],
            "skipped": self.skipped,
        }


def select(
    ranked_matches,
    *,
    profile_id: str,
    profile_name: str,
    for_date: date,
    already_sent: set[str] | None = None,
    acted_on: set[str] | None = None,
    dismissed: set[str] | None = None,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> Digest:
    """Pick the digest's cards from a ranked list.

    Rules, in order: never re-send, never send something already acted on or
    dismissed, never send a scam-flagged posting, and cap the list. Ordered by
    the ranking it was given - which already puts closing-soonest first among
    equals.
    """
    already_sent = already_sent or set()
    acted_on = acted_on or set()
    dismissed = dismissed or set()

    digest = Digest(profile_id=profile_id, profile_name=profile_name, for_date=for_date)
    skipped = {"already_sent": 0, "acted_on": 0, "dismissed": 0, "flagged": 0, "closed": 0}
    seen: set[str] = set()
    eligible: list = []

    for match in ranked_matches:
        row = match.row or {}
        job_id = match.job_id
        if job_id in seen:
            continue
        seen.add(job_id)

        if job_id in already_sent:
            skipped["already_sent"] += 1
            continue
        if job_id in acted_on:
            skipped["acted_on"] += 1
            continue
        if job_id in dismissed:
            skipped["dismissed"] += 1
            continue
        if (row.get("scam_flags") or "[]") not in ("[]", "", None):
            skipped["flagged"] += 1
            continue
        if row.get("status") == "closed":
            skipped["closed"] += 1
            continue
        if not match.eligible:
            skipped["closed"] += 1
            continue

        eligible.append(match)

    # A daily push is about the closing door, not the prettiest match: sort by
    # deadline first (no deadline last), then by score.
    def sort_key(match):
        deadline = (match.row or {}).get("deadline")
        return (deadline is None, str(deadline or ""), -match.score)

    for match in sorted(eligible, key=sort_key)[:max_items]:
        digest.items.append(
            DigestItem(
                job_id=match.job_id,
                title=match.title,
                employer=match.employer,
                score=match.score,
                reasons=list(match.reasons),
                row=match.row or {},
                position=len(digest.items) + 1,
            )
        )

    digest.skipped = {key: value for key, value in skipped.items() if value}
    return digest


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


REASON_PRIORITY = (
    "confirmed on",
    "internship - entry route",
    "attachment - entry route",
    "pays above",
    "remote - no commute",
    # "closes …" is deliberately absent: the deadline is already a fact on the
    # card, and a digest that says the same thing twice reads like a bug.
)


def _pick_reason(reasons: list[str]) -> str:
    """The single most useful line for a push notification."""
    for marker in REASON_PRIORITY:
        for reason in reasons:
            if reason.startswith(marker):
                return reason
    for reason in reasons:
        # Anything that restates a fact the card already prints is noise.
        if not reason.startswith(("checked", "no closing date", "salary stated", "closes")):
            return reason
    return ""


def render_card(item: DigestItem, today: date, *, number: int | None = None) -> str:
    """One card as WhatsApp renders it: bold title, plain facts, one link."""
    lines = []
    prefix = f"{number}. " if number else ""
    lines.append(f"{prefix}*{one_line(shorten(item.title, 70))}*")
    if item.employer:
        lines.append(one_line(shorten(item.employer, 60)))

    facts = []
    place = place_line(item.row)
    if place:
        facts.append(one_line(place))
    deadline = deadline_phrase(item.row, today)
    if deadline:
        facts.append(deadline)
    eligibility = {
        "open_to_freshers": "open to freshers",
        "some_experience": "1–2 years",
    }.get(item.row.get("entry_fit") or "")
    if eligibility:
        facts.append(eligibility)
    pay = pay_line(item.row)
    if pay:
        facts.append(pay)
    if facts:
        lines.append(" · ".join(facts))

    # One reason, not five, and never one that repeats a fact already on the
    # card. The digest is a nudge; the feed is the argument.
    reason = one_line(shorten(_pick_reason(item.reasons), 80))
    if reason:
        lines.append(reason)

    return "\n".join(lines)


def render_digest(digest: Digest, *, link_base: str | None = None, today: date | None = None) -> str:
    """The message body. Deterministic, so it can be tested and diffed."""
    today = today or digest.for_date
    if digest.is_empty:
        return ""  # callers send nothing rather than a "no jobs" message by default

    count = len(digest.items)
    plural = "job" if count == 1 else "jobs"
    lines = [f"*Kazi-Kasi* - {count} {plural} for you today", ""]

    for item in digest.items:
        lines.append(render_card(item, today, number=item.position))
        if link_base:
            lines.append(f"{link_base.rstrip('/')}/job/{item.job_id}")
        lines.append("")

    lines.append("Reply STOP to stop these. Reply HELP for the web feed.")
    return "\n".join(lines).strip()


def split_message(body: str, limit: int = WHATSAPP_TEXT_LIMIT) -> list[str]:
    """Split at card boundaries, never mid-card, and never above the limit.

    If a single card cannot fit (a pathological title), it is hard-split so that
    *something* is delivered rather than a 400 from the provider.
    """
    if len(body) <= limit:
        return [body] if body else []

    blocks = body.split("\n\n")
    chunks: list[str] = []
    current = ""
    for block in blocks:
        candidate = f"{current}\n\n{block}".strip() if current else block
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(block) > limit:
            chunks.append(block[:limit])
            block = block[limit:]
        current = block
    if current:
        chunks.append(current)
    return chunks


def render_sms(digest: Digest, *, today: date | None = None, max_items: int = 3) -> str:
    """The fallback. One segment if possible: who, how many, and where to look."""
    today = today or digest.for_date
    if digest.is_empty:
        return ""
    count = len(digest.items)
    plural = "job" if count == 1 else "jobs"
    first = digest.items[0]
    deadline = deadline_phrase(first.row, today)
    tail = f" First: {shorten(first.title, 40)}"
    if deadline:
        tail += f" ({deadline})"
    body = f"Kazi-Kasi: {count} new {plural} for you.{tail}. See all at kazikasi.app. Reply STOP to opt out."
    return shorten(body, 320)


# --------------------------------------------------------------------------
# Message assembly
# --------------------------------------------------------------------------


@dataclass
class Outgoing:
    profile_id: str
    channel: str
    msisdn: str
    body: str
    idempotency: str
    kind: str = "digest"

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "channel": self.channel,
            "to": mask_msisdn(self.msisdn),
            "kind": self.kind,
            "idempotency": self.idempotency,
            "characters": len(self.body),
            "segments": len(split_message(self.body)),
        }


def idempotency_key(profile_id: str, for_date: date, channel: str, part: int = 1) -> str:
    """One key per profile per day per channel per part. Retries reuse it."""
    return f"{profile_id}:{for_date.isoformat()}:{channel}:{part}"


def build_messages(
    digest: Digest,
    *,
    channel: str,
    msisdn: str,
    link_base: str | None = None,
) -> list[Outgoing]:
    """Turn a digest into the exact messages a transport will be asked to send."""
    if digest.is_empty:
        return []

    if channel == "sms":
        body = render_sms(digest)
        return [
            Outgoing(
                profile_id=digest.profile_id,
                channel="sms",
                msisdn=msisdn,
                body=body,
                idempotency=idempotency_key(digest.profile_id, digest.for_date, "sms"),
                kind="fallback",
            )
        ]

    body = render_digest(digest, link_base=link_base)
    parts = split_message(body)
    return [
        Outgoing(
            profile_id=digest.profile_id,
            channel=channel,
            msisdn=msisdn,
            body=part,
            idempotency=idempotency_key(digest.profile_id, digest.for_date, channel, index),
            kind="digest",
        )
        for index, part in enumerate(parts, start=1)
    ]


# --------------------------------------------------------------------------
# Timing
# --------------------------------------------------------------------------


def eat_now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(EAT)


def in_window(now: datetime, start: str = "18:00", end: str = "20:00") -> bool:
    """Is it inside the person's quiet-hours-safe window, in Nairobi time?"""
    local = eat_now(now)
    try:
        start_h, start_m = (int(part) for part in start.split(":"))
        end_h, end_m = (int(part) for part in end.split(":"))
    except ValueError:
        return True
    minutes = local.hour * 60 + local.minute
    start_minutes, end_minutes = start_h * 60 + start_m, end_h * 60 + end_m
    if start_minutes <= end_minutes:
        return start_minutes <= minutes < end_minutes
    return minutes >= start_minutes or minutes < end_minutes  # window crosses midnight


def local_date(now: datetime | None = None) -> date:
    """The digest's date is Nairobi's date, not UTC's."""
    return eat_now(now).date()
