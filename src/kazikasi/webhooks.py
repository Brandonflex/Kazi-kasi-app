"""Inbound: the half of the conversation that makes consent real.

Phase 5 could send a digest but could not hear a reply. "Reply STOP" is not
consent if replying STOP does nothing, so this module turns both providers'
inbound callbacks into the same small set of actions:

* **STOP** (and STOPALL, UNSUBSCRIBE, END, CANCEL, QUIT) → opt out, dated.
* **START** (and YES, RESUME, SUBSCRIBE, UNSTOP) → consent again, re-dated.
* **HELP** (and INFO, SAIDIA) → a one-segment explanation, queued through the
  outbox so it is logged and idempotent like everything else.
* **Delivery receipts** → folded into the message state machine.

Two deliberate design choices:

1. **The parser is separate from the transport.** `parse_meta()` and
   `parse_africas_talking()` return plain events; `handle_event()` applies them.
   That means the WhatsApp payload shape can change without touching consent
   logic, and every rule here is testable without a network.
2. **Signature verification is mandatory unless explicitly disabled.** A webhook
   that accepts unsigned POSTs lets anyone unsubscribe anyone.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime

from . import digest as digest_module
from . import outbox

#: Meta signs the raw body with the app secret: `sha256=<hex>`.
SIGNATURE_HEADER = "X-Hub-Signature-256"


@dataclass
class InboundEvent:
    kind: str                      # message | status | ignored
    channel: str
    msisdn: str | None = None
    text: str | None = None
    provider_id: str | None = None
    status: str | None = None
    error: str | None = None
    detail: str | None = None
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "channel": self.channel,
            "msisdn": digest_module.mask_msisdn(self.msisdn) if self.msisdn else None,
            "text": self.text,
            "status": self.status,
            "provider_id": self.provider_id,
        }


# --------------------------------------------------------------------------
# Signatures
# --------------------------------------------------------------------------


def sign(body: bytes, secret: str) -> str:
    """The header value Meta would send for this body."""
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(body: bytes, header: str | None, secret: str | None) -> bool:
    """Constant-time check. No secret configured means "cannot verify", not "ok"."""
    if not secret:
        return False
    if not header:
        return False
    expected = sign(body, secret)
    return hmac.compare_digest(expected, header.strip())


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def _msisdn(value: str | None) -> str | None:
    try:
        return digest_module.normalise_msisdn(value or "")
    except ValueError:
        return None


def parse_meta(payload: dict) -> list[InboundEvent]:
    """WhatsApp Cloud API webhook → events.

    The payload nests everything under `entry[].changes[].value`, with either
    `messages[]` (someone wrote to us) or `statuses[]` (a receipt). Both can be
    missing: a v21 payload also carries metadata we ignore.
    """
    events: list[InboundEvent] = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for message in value.get("messages") or []:
                text = None
                if (message.get("type") == "text"):
                    text = ((message.get("text") or {}).get("body") or "").strip()
                elif message.get("type") == "button":
                    text = ((message.get("button") or {}).get("text") or "").strip()
                events.append(
                    InboundEvent(
                        kind="message",
                        channel="whatsapp",
                        msisdn=_msisdn(message.get("from")),
                        text=text,
                        provider_id=message.get("id"),
                        raw=message,
                    )
                )
            for status in value.get("statuses") or []:
                error = None
                for item in status.get("errors") or []:
                    error = item.get("title") or item.get("message") or str(item)
                    break
                events.append(
                    InboundEvent(
                        kind="status",
                        channel="whatsapp",
                        msisdn=_msisdn(status.get("recipient_id")),
                        provider_id=status.get("id"),
                        status=str(status.get("status") or "").lower(),
                        error=error,
                        raw=status,
                    )
                )
    return events


def parse_africas_talking(form: dict) -> list[InboundEvent]:
    """Africa's Talking inbound SMS callback → events.

    They POST form fields (`from`, `text`, `id`, `date`). Numbers arrive as
    `+2547…`, and shortcodes can send `STOP` in any case.
    """
    text = (form.get("text") or "").strip()
    sender = form.get("from") or form.get("sender") or ""
    if not sender and not text:
        return []
    event = InboundEvent(
        kind="message",
        channel="sms",
        msisdn=_msisdn(sender),
        text=text,
        provider_id=form.get("id") or form.get("messageId"),
        raw=dict(form),
    )
    # Delivery reports for our own outbound SMS arrive on the same endpoint.
    status = (form.get("status") or "").lower()
    if status and not text:
        event.kind = "status"
        event.status = "delivered" if status in ("success", "delivered") else "failed"
        event.error = None if event.status == "delivered" else status
        event.provider_id = form.get("id") or form.get("messageId")
    return [event]


def parse_json(raw: str | bytes) -> dict:
    try:
        loaded = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


# --------------------------------------------------------------------------
# Handling
# --------------------------------------------------------------------------


def classify(text: str | None) -> str:
    """STOP / START / HELP / unrecognised, from whatever they typed."""
    word = (text or "").strip().upper()
    if not word:
        return "unrecognised"
    # Take the first word so "stop please" and "STOP." both work.
    token = "".join(character for character in word.split()[0] if character.isalpha())
    if token in outbox.STOP_WORDS:
        return "stop"
    if token in outbox.START_WORDS:
        return "start"
    if token in outbox.HELP_WORDS:
        return "help"
    return "unrecognised"


def handle_event(conn, event: InboundEvent, *, now: datetime | None = None) -> dict:
    """Apply one inbound event. Pure-ish: returns what happened, writes rows."""
    if event.kind == "status":
        message_id = outbox.record_receipt(
            conn,
            status=event.status or "unknown",
            provider_id=event.provider_id,
            to_msisdn=event.msisdn,
            error=event.error,
            now=now,
        )
        return {"action": "receipt", "status": event.status, "message_id": message_id}

    if event.kind != "message":
        return {"action": "ignored"}

    intent = classify(event.text)
    if event.msisdn is None:
        # An unparseable sender is still worth recording: it is evidence.
        outbox.record_consent_event(
            conn, event.text or "", "unrecognised", source=event.channel, detail="unparseable sender", now=now
        )
        return {"action": "unrecognised", "reason": "unparseable sender"}

    if intent == "stop":
        profile_id = outbox.opt_out_by_msisdn(conn, event.msisdn, source=event.channel, now=now)
        return {"action": "unsubscribed", "profile_id": profile_id, "matched": profile_id is not None}

    if intent == "start":
        profile_id = outbox.resume_by_msisdn(conn, event.msisdn, source=event.channel, now=now)
        return {"action": "resumed", "profile_id": profile_id, "matched": profile_id is not None}

    if intent == "help":
        profile = outbox.find_subscription_by_msisdn(conn, event.msisdn)
        outbox.record_consent_event(
            conn,
            event.msisdn,
            "help",
            source=event.channel,
            profile_id=profile.profile_id if profile else None,
            now=now,
        )
        queued = _queue_help_reply(conn, event, now=now)
        return {"action": "help", "replied": queued}

    outbox.record_consent_event(
        conn,
        event.msisdn,
        "unrecognised",
        source=event.channel,
        detail=(event.text or "")[:80],
        now=now,
    )
    if digest_module.hash_is_keyed():
        # With a keyed hash we can safely answer an unknown number with help.
        queued = _queue_help_reply(conn, event, now=now)
        return {"action": "unrecognised", "replied": queued}
    return {"action": "unrecognised", "replied": False}


def _queue_help_reply(conn, event: InboundEvent, *, now: datetime | None = None) -> bool:
    """One helpful segment, idempotent on the inbound message id.

    Replying to an unknown number is how a person finds out what this is; the
    rate limit lives in the transport, not here.
    """
    if not event.msisdn:
        return False
    key = f"help:{event.channel}:{event.provider_id or event.msisdn}"
    outgoing = digest_module.Outgoing(
        profile_id=_profile_for(conn, event.msisdn) or "unknown",
        channel=event.channel,
        msisdn=event.msisdn,
        body=outbox.HELP_TEXT,
        idempotency=key,
        kind="notice",
    )
    # `messages.profile_id` is a foreign key, so an unknown sender has no row to
    # hang a reply on: record the intent in the consent log instead.
    if outgoing.profile_id == "unknown":
        return False
    return outbox.enqueue(conn, outgoing, now=now)


def _profile_for(conn, msisdn: str) -> str | None:
    subscription = outbox.find_subscription_by_msisdn(conn, msisdn)
    return subscription.profile_id if subscription else None


def handle_meta(conn, payload: dict, *, now: datetime | None = None) -> dict:
    events = parse_meta(payload)
    results = [handle_event(conn, event, now=now) for event in events]
    return summarise(results)


def handle_africas_talking(conn, form: dict, *, now: datetime | None = None) -> dict:
    events = parse_africas_talking(form)
    results = [handle_event(conn, event, now=now) for event in events]
    return summarise(results)


def summarise(results: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for result in results:
        counts[result["action"]] = counts.get(result["action"], 0) + 1
    return {"events": len(results), "actions": counts, "results": results}


# --------------------------------------------------------------------------
# Webhook verification handshake
# --------------------------------------------------------------------------


def verify_challenge(params: dict, expected_token: str | None) -> str | None:
    """The `hub.challenge` echo Meta requires before it will send anything.

    Returns the challenge to echo, or None if the token does not match. An
    unconfigured token means verification fails closed.
    """
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if not expected_token or mode != "subscribe" or token != expected_token:
        return None
    return challenge
