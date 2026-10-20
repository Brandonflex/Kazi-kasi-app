"""Delivery: the senders, the cron tick, and the three refusals in front of it.

The digest composing correctly has been tested since Part 4. What was never
tested is the last inch: an actual HTTP POST to Meta's Cloud API or Africa's
Talking, the difference between "retry this" and "this will never work", and the
question a deployed scheduler forces — *what stops this from texting a real person
a fabricated vacancy?*

That last one is the important test in this file. The demo deployment serves a
synthetic corpus; a cron tick there would deliver invented jobs to a real phone.
So the cron endpoint refuses, by name, and the refusal is what the test pins.

Transports are exercised against a fake HTTP client: no credentials, no network.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import channels, outbox, scheduler, serve
from kazikasi.channels import Delivery, FakeTransport, SmsTransport, WhatsAppCloudTransport
from kazikasi.serve import handle

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeClient:
    def __init__(self, response=None, *, raises: Exception | None = None) -> None:
        self.response = response
        self.raises = raises
        self.calls: list[dict] = []

    def post(self, url, *, json=None, data=None, headers=None):  # noqa: A002 - mirroring httpx
        self.calls.append({"url": url, "json": json, "data": data, "headers": headers})
        if self.raises:
            raise self.raises
        return self.response


@pytest.fixture
def conn():
    connection = serve.demo_connection(now=NOW)
    yield connection
    connection.close()


def get(conn, path, *, query=None, headers=None, now=NOW, demo=True):
    return handle(conn, "GET", path, query or {}, headers=headers or {}, demo=demo, now=now)


def post(conn, path, *, query=None, headers=None, body=b"", now=NOW, demo=True):
    return handle(
        conn, "POST", path, query or {}, body=body, headers=headers or {}, demo=demo, now=now
    )


class TestWhatsApp:
    def test_a_send_posts_the_cloud_api_shape(self):
        client = FakeClient(FakeResponse(200, {"messages": [{"id": "wamid.123"}]}))
        transport = WhatsAppCloudTransport(phone_number_id="1234", token="tok", client=client)
        delivery = transport.send("+254712345678", "hello", idempotency="digest:1")
        assert delivery.ok and delivery.provider_id == "wamid.123"
        call = client.calls[0]
        assert call["url"].endswith("/1234/messages")
        assert call["json"]["messaging_product"] == "whatsapp"
        assert call["json"]["to"] == "254712345678"  # no leading plus
        assert call["headers"]["Idempotency-Key"] == "digest:1"

    def test_a_5xx_is_retryable(self):
        transport = WhatsAppCloudTransport(phone_number_id="1", token="t", client=FakeClient(FakeResponse(503)))
        assert transport.send("2547", "x", idempotency="k").retryable is True

    def test_a_429_is_retryable(self):
        transport = WhatsAppCloudTransport(phone_number_id="1", token="t", client=FakeClient(FakeResponse(429)))
        assert transport.send("2547", "x", idempotency="k").retryable is True

    def test_a_4xx_is_not_retryable(self):
        transport = WhatsAppCloudTransport(phone_number_id="1", token="t", client=FakeClient(FakeResponse(400)))
        delivery = transport.send("2547", "x", idempotency="k")
        assert delivery.ok is False and delivery.retryable is False

    def test_a_network_error_is_retryable(self):
        transport = WhatsAppCloudTransport(
            phone_number_id="1", token="t", client=FakeClient(raises=OSError("boom"))
        )
        delivery = transport.send("2547", "x", idempotency="k")
        assert delivery.retryable is True and "network" in delivery.error

    def test_it_refuses_to_construct_without_credentials(self, monkeypatch):
        monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
        monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)
        with pytest.raises(RuntimeError, match="WHATSAPP_TOKEN"):
            WhatsAppCloudTransport()


class TestSms:
    def test_it_posts_the_africas_talking_shape(self):
        client = FakeClient(FakeResponse(201, {"SMSMessageData": {"Recipients": [{"messageId": "ATX1"}]}}))
        transport = SmsTransport(username="u", api_key="k", sender="KAZI", client=client)
        delivery = transport.send("+254712345678", "hello", idempotency="x")
        assert delivery.ok and delivery.provider_id == "ATX1"
        assert client.calls[0]["data"]["from"] == "KAZI"

    def test_it_counts_segments(self):
        client = FakeClient(FakeResponse(201, {"SMSMessageData": {"Recipients": [{"messageId": "A"}]}}))
        transport = SmsTransport(username="u", api_key="k", client=client)
        delivery = transport.send("2547", "x" * 400, idempotency="x")
        assert delivery.meta["segments"] >= 3

    def test_it_refuses_to_construct_without_credentials(self, monkeypatch):
        monkeypatch.delenv("AT_USERNAME", raising=False)
        monkeypatch.delenv("AT_API_KEY", raising=False)
        with pytest.raises(RuntimeError):
            SmsTransport()


class TestTheCronGate:
    def _env(self, monkeypatch, **values):
        for key, value in {"CRON_SECRET": "cron-token"}.items():
            monkeypatch.setenv(key, value)
        for key, value in values.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)

    def test_it_needs_a_shared_secret(self, conn, monkeypatch):
        monkeypatch.delenv("CRON_SECRET", raising=False)
        response = get(conn, "/api/cron/run", query={"token": ["anything"]})
        assert response.status == 503
        assert "CRON_SECRET" in response.body

    def test_it_refuses_a_bad_token(self, conn, monkeypatch):
        self._env(monkeypatch)
        assert get(conn, "/api/cron/run", query={"token": ["nope"]}).status == 403
        assert get(conn, "/api/cron/run").status == 403

    def test_the_bearer_header_is_accepted(self, conn, monkeypatch):
        self._env(monkeypatch)
        response = get(conn, "/api/cron/run", headers={"authorization": "Bearer cron-token"})
        assert response.status in (409, 503)  # past the gate, refused by the next rule

    def test_it_refuses_to_send_synthetic_vacancies(self, conn, monkeypatch):
        """The one outcome this product must never produce."""
        self._env(monkeypatch, DATABASE_URL=None)
        response = get(conn, "/api/cron/run", query={"token": ["cron-token"]})
        assert response.status == 409
        payload = json.loads(response.body)
        assert "synthetic" in payload["detail"]
        assert "KAZIKASI_ALLOW_SYNTHETIC_SEND" in payload["detail"]

    def test_the_synthetic_guard_can_be_opened_for_a_test_number(self, conn, monkeypatch):
        self._env(monkeypatch, DATABASE_URL=None, KAZIKASI_ALLOW_SYNTHETIC_SEND="1")
        fake = FakeTransport()
        monkeypatch.setattr(serve, "_transports_from_env", lambda: {"whatsapp": fake})
        response = get(conn, "/api/cron/run", query={"token": ["cron-token"]})
        assert response.status == 200
        assert json.loads(response.body)["outbox"]["queued"] >= 0

    def test_it_reports_503_when_no_transport_is_configured(self, conn, monkeypatch):
        self._env(monkeypatch, DATABASE_URL="postgres://example")
        monkeypatch.setattr(serve, "_transports_from_env", lambda: {})
        response = get(conn, "/api/cron/run", query={"token": ["cron-token"]}, demo=False)
        assert response.status == 503
        assert "WHATSAPP_TOKEN" in response.body

    def test_a_real_tick_delivers_a_due_digest(self, conn, monkeypatch):
        self._env(monkeypatch, DATABASE_URL="postgres://example")
        # 18:45 EAT: inside the evening window and past this profile's jitter,
        # so the tick has something due rather than something waiting.
        evening = datetime(2026, 10, 20, 15, 45, tzinfo=timezone.utc)
        outbox.subscribe(conn, "demo-fresher", "0712000111", now=evening)
        fake = FakeTransport()
        monkeypatch.setattr(serve, "_transports_from_env", lambda: {"whatsapp": fake})
        response = get(
            conn, "/api/cron/run", query={"token": ["cron-token"]}, now=evening, demo=False
        )
        assert response.status == 200
        payload = json.loads(response.body)
        assert payload["sent"]["sent"] >= 1
        assert fake.sent, "the fake transport should have been called"

    def test_post_is_also_accepted_for_schedulers_that_use_it(self, conn, monkeypatch):
        self._env(monkeypatch, DATABASE_URL=None)
        # POST is the shape most cron daemons prefer; the gate is identical.
        response = post(conn, "/api/cron/run", query={"token": ["cron-token"]})
        assert response.status == 409


class TestTheHealthReport:
    def test_it_reports_the_outbox(self, conn):
        payload = json.loads(get(conn, "/api/health").body)
        assert set(payload["outbox"]) == {"queued", "sent_24h", "failed_24h", "suppressed"}
        assert payload["synthetic"] is True
        assert payload["strict"] is False

    def test_it_counts_what_is_queued(self, conn):
        outbox.subscribe(conn, "demo-fresher", "0712000111", brief_opt_in=True, now=NOW)
        outbox.queue_brief(conn, "demo-fresher", now=NOW)
        payload = json.loads(get(conn, "/api/health").body)
        assert payload["outbox"]["queued"] == 1
