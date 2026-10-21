"""Transports. The digest composes; these deliver.

Everything here is behind one small protocol so the product logic can be tested
without credentials or network:

    transport.send(to, body, *, idempotency) -> Delivery

Three implementations:

* ``FakeTransport`` — records what would have been sent. Used by every test and
  by ``--dry-run``.
* ``WhatsAppCloudTransport`` — the Meta Cloud API shape (``graph.facebook.com``,
  ``messaging_product: whatsapp``). Refuses to construct without credentials, so
  a missing token is a startup error and not a silent skip.
* ``SmsTransport`` — the Africa's Talking shape, used only as the fallback when
  WhatsApp fails. Deliberately not free: an operator bills per segment, so
  ``segments`` is part of the delivery record.

Nothing here retries. Retries belong to the outbox, which knows how many times a
message has been tried and when to give up.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Delivery:
    ok: bool
    provider_id: str | None = None
    error: str | None = None
    retryable: bool = False
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "provider_id": self.provider_id,
            "error": self.error,
            "retryable": self.retryable,
            **({"meta": self.meta} if self.meta else {}),
        }


class Transport(Protocol):
    channel: str

    def send(self, to: str, body: str, *, idempotency: str) -> Delivery: ...


class FakeTransport:
    """Records sends. Can be told to fail in specific ways."""

    channel = "fake"

    def __init__(self, *, fail_with: str | None = None, retryable: bool = True) -> None:
        self.sent: list[dict] = []
        self.fail_with = fail_with
        self.retryable = retryable

    def send(self, to: str, body: str, *, idempotency: str) -> Delivery:
        if self.fail_with:
            self.sent.append({"to": to, "body": body, "idempotency": idempotency, "ok": False})
            return Delivery(ok=False, error=self.fail_with, retryable=self.retryable)
        self.sent.append({"to": to, "body": body, "idempotency": idempotency, "ok": True})
        return Delivery(ok=True, provider_id=f"fake-{len(self.sent)}")

    def reset(self) -> None:
        self.sent.clear()


class WhatsAppCloudTransport:
    """Meta WhatsApp Cloud API.

    Kept intentionally thin: one POST per message, an idempotency-aware caller,
    and error mapping that distinguishes "try again" (5xx, timeouts) from "this
    will never work" (4xx, invalid number, template rejected).

    Not exercised in this repository's tests, because it needs a live token.
    """

    channel = "whatsapp"
    api_base = "https://graph.facebook.com/v21.0"

    def __init__(
        self,
        *,
        phone_number_id: str | None = None,
        token: str | None = None,
        timeout: float = 15.0,
        client=None,
    ) -> None:
        self.phone_number_id = phone_number_id or os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
        self.token = token or os.environ.get("WHATSAPP_TOKEN", "")
        if not self.phone_number_id or not self.token:
            raise RuntimeError(
                "WhatsAppCloudTransport needs WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_TOKEN. "
                "Use FakeTransport (or --dry-run) without them."
            )
        self.timeout = timeout
        self._client = client

    def _http(self):
        if self._client is not None:
            return self._client
        import httpx

        self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def send(self, to: str, body: str, *, idempotency: str) -> Delivery:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to.lstrip("+"),
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            # Providers that honour an idempotency key will de-duplicate; those
            # that ignore it are covered by the outbox's unique constraint.
            "Idempotency-Key": idempotency,
        }
        try:
            response = self._http().post(
                f"{self.api_base}/{self.phone_number_id}/messages", json=payload, headers=headers
            )
        except Exception as exc:  # noqa: BLE001 - network failures are retryable by definition
            return Delivery(ok=False, error=f"network: {exc}", retryable=True)

        status = getattr(response, "status_code", 0)
        if status >= 500 or status == 429:
            return Delivery(ok=False, error=f"provider {status}", retryable=True)
        if status >= 400:
            return Delivery(ok=False, error=f"provider {status}: {_short(response)}", retryable=False)

        message_id = None
        try:
            data = response.json()
            message_id = (data.get("messages") or [{}])[0].get("id")
        except Exception:  # noqa: BLE001 - a 200 with an odd body is still a send
            pass
        return Delivery(ok=True, provider_id=message_id)


class SmsTransport:
    """Africa's Talking SMS. The fallback when WhatsApp cannot deliver.

    A different provider on purpose: if WhatsApp is down or the number is not on
    WhatsApp, retrying WhatsApp is not a fallback. Costs money per segment, which
    is why the segment count is recorded.
    """

    channel = "sms"
    api_base = "https://api.africastalking.com/version1/messaging"

    def __init__(self, *, username: str | None = None, api_key: str | None = None, sender: str | None = None, client=None) -> None:
        self.username = username or os.environ.get("AT_USERNAME", "")
        self.api_key = api_key or os.environ.get("AT_API_KEY", "")
        self.sender = sender or os.environ.get("AT_SENDER_ID", "")
        if not self.username or not self.api_key:
            raise RuntimeError("SmsTransport needs AT_USERNAME and AT_API_KEY")
        self._client = client

    def send(self, to: str, body: str, *, idempotency: str) -> Delivery:
        from .digest import SMS_SEGMENT

        data = {"username": self.username, "to": to, "message": body}
        if self.sender:
            data["from"] = self.sender
        headers = {
            "apiKey": self.api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        try:
            response = self._client.post(self.api_base, data=data, headers=headers)
        except Exception as exc:  # noqa: BLE001
            return Delivery(ok=False, error=f"network: {exc}", retryable=True)

        status = getattr(response, "status_code", 0)
        if status >= 500 or status == 429:
            return Delivery(ok=False, error=f"provider {status}", retryable=True)
        if status >= 400:
            return Delivery(ok=False, error=f"provider {status}: {_short(response)}", retryable=False)

        provider_id = None
        try:
            recipients = response.json()["SMSMessageData"]["Recipients"]
            provider_id = recipients[0].get("messageId") if recipients else None
        except Exception:  # noqa: BLE001
            provider_id = None
        return Delivery(
            ok=True,
            provider_id=provider_id,
            meta={"segments": -(-len(body) // SMS_SEGMENT)},
        )


def _short(response) -> str:
    try:
        return str(response.text)[:160]
    except Exception:  # noqa: BLE001
        return "unreadable response"


def transport_for(channel: str, *, dry_run: bool = False, **kwargs) -> Transport:
    """Pick a transport, defaulting to the fake one for dry runs."""
    if dry_run or channel == "fake":
        return FakeTransport()
    if channel == "whatsapp":
        return WhatsAppCloudTransport(**kwargs)
    if channel == "sms":
        return SmsTransport(**kwargs)
    raise ValueError(f"unknown channel {channel!r}")
