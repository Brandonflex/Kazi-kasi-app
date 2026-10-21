"""Transports. The point of these tests is that no test needs credentials.

The WhatsApp and SMS clients are exercised against a stub HTTP client that
speaks the real payload shape, because the interesting bugs are in the error
mapping: retrying a 400 forever, or giving up on a 503.
"""

import json

import pytest

from kazikasi import channels
from kazikasi.channels import Delivery, FakeTransport, SmsTransport, WhatsAppCloudTransport, transport_for


class StubResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or json.dumps(self._payload)

    def json(self):
        return self._payload


class StubClient:
    """Records requests and returns a queued response (or raises)."""

    def __init__(self, responses=None, raises=None):
        self.responses = list(responses or [])
        self.raises = raises
        self.calls = []

    def post(self, url, json=None, data=None, headers=None, **kwargs):  # noqa: A002 - mirrors httpx
        self.calls.append({"url": url, "json": json, "data": data, "headers": headers or {}})
        if self.raises:
            raise self.raises
        return self.responses.pop(0) if self.responses else StubResponse()


class TestFakeTransport:
    def test_records_what_would_have_been_sent(self):
        fake = FakeTransport()
        delivery = fake.send("+254712345678", "hello", idempotency="k1")
        assert delivery.ok
        assert fake.sent == [{"to": "+254712345678", "body": "hello", "idempotency": "k1", "ok": True}]

    def test_can_be_told_to_fail(self):
        fake = FakeTransport(fail_with="provider 500", retryable=True)
        delivery = fake.send("+254712345678", "hello", idempotency="k1")
        assert not delivery.ok
        assert delivery.retryable
        assert fake.sent[0]["ok"] is False

    def test_reset_clears_the_log(self):
        fake = FakeTransport()
        fake.send("+254712345678", "hello", idempotency="k1")
        fake.reset()
        assert fake.sent == []


class TestWhatsAppCloud:
    def test_refuses_to_construct_without_credentials(self, monkeypatch):
        monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)
        monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="WHATSAPP_TOKEN"):
            WhatsAppCloudTransport()

    def test_reads_credentials_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "1234")
        monkeypatch.setenv("WHATSAPP_TOKEN", "token")
        transport = WhatsAppCloudTransport()
        assert transport.phone_number_id == "1234"
        assert transport.token == "token"

    def test_payload_is_the_cloud_api_shape(self):
        client = StubClient([StubResponse(200, {"messages": [{"id": "wamid.1"}]})])
        transport = WhatsAppCloudTransport(phone_number_id="1234", token="t", client=client)
        delivery = transport.send("+254712345678", "hello *there*", idempotency="demo:1")

        assert delivery.ok and delivery.provider_id == "wamid.1"
        call = client.calls[0]
        assert call["url"].endswith("/1234/messages")
        assert call["json"]["messaging_product"] == "whatsapp"
        assert call["json"]["to"] == "254712345678"      # E.164 without the plus
        assert call["json"]["text"]["body"] == "hello *there*"
        assert call["json"]["text"]["preview_url"] is False
        assert call["headers"]["Idempotency-Key"] == "demo:1"
        assert call["headers"]["Authorization"] == "Bearer t"

    @pytest.mark.parametrize("status", [429, 500, 502, 503])
    def test_rate_limits_and_outages_are_retryable(self, status):
        client = StubClient([StubResponse(status, {"error": "busy"})])
        transport = WhatsAppCloudTransport(phone_number_id="1", token="t", client=client)
        delivery = transport.send("+254712345678", "x", idempotency="k")
        assert not delivery.ok and delivery.retryable
        assert str(status) in delivery.error

    @pytest.mark.parametrize("status", [400, 401, 404, 470])
    def test_client_errors_are_terminal(self, status):
        client = StubClient([StubResponse(status, {"error": {"message": "bad number"}})])
        transport = WhatsAppCloudTransport(phone_number_id="1", token="t", client=client)
        delivery = transport.send("+254712345678", "x", idempotency="k")
        assert not delivery.ok and not delivery.retryable
        assert "bad number" in delivery.error

    def test_a_network_exception_is_retryable_not_a_crash(self):
        client = StubClient(raises=TimeoutError("timed out"))
        transport = WhatsAppCloudTransport(phone_number_id="1", token="t", client=client)
        delivery = transport.send("+254712345678", "x", idempotency="k")
        assert not delivery.ok and delivery.retryable
        assert "network" in delivery.error

    def test_a_200_with_an_odd_body_is_still_a_send(self):
        client = StubClient([StubResponse(200, {})])
        transport = WhatsAppCloudTransport(phone_number_id="1", token="t", client=client)
        delivery = transport.send("+254712345678", "x", idempotency="k")
        assert delivery.ok and delivery.provider_id is None


class TestSms:
    def test_refuses_to_construct_without_credentials(self, monkeypatch):
        monkeypatch.delenv("AT_USERNAME", raising=False)
        monkeypatch.delenv("AT_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="AT_API_KEY"):
            SmsTransport()

    def test_sends_the_africas_talking_shape_and_records_segments(self):
        client = StubClient(
            [StubResponse(201, {"SMSMessageData": {"Recipients": [{"messageId": "ATX1", "status": "Success"}]}})]
        )
        transport = SmsTransport(username="sandbox", api_key="k", sender="KAZI", client=client)
        delivery = transport.send("+254712345678", "x" * 200, idempotency="k")

        assert delivery.ok and delivery.provider_id == "ATX1"
        assert delivery.meta["segments"] == 2          # 200 chars = two 160-char segments
        call = client.calls[0]
        assert call["data"]["to"] == "+254712345678"   # Africa's Talking wants E.164
        assert call["data"]["from"] == "KAZI"
        assert call["headers"]["apiKey"] == "k"

    def test_a_server_error_is_retryable(self):
        client = StubClient([StubResponse(503, text="down")])
        transport = SmsTransport(username="u", api_key="k", client=client)
        assert transport.send("+254712345678", "x", idempotency="k").retryable

    def test_a_client_error_is_terminal(self):
        client = StubClient([StubResponse(403, text="no credit")])
        transport = SmsTransport(username="u", api_key="k", client=client)
        delivery = transport.send("+254712345678", "x", idempotency="k")
        assert not delivery.ok and not delivery.retryable
        assert "no credit" in delivery.error


class TestTransportFor:
    def test_dry_run_always_gets_the_fake(self):
        assert isinstance(transport_for("whatsapp", dry_run=True), FakeTransport)
        assert isinstance(transport_for("sms", dry_run=True), FakeTransport)

    def test_channels_map_to_their_transport(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "1")
        monkeypatch.setenv("WHATSAPP_TOKEN", "t")
        monkeypatch.setenv("AT_USERNAME", "u")
        monkeypatch.setenv("AT_API_KEY", "k")
        assert isinstance(transport_for("whatsapp"), WhatsAppCloudTransport)
        assert isinstance(transport_for("sms"), SmsTransport)

    def test_an_unknown_channel_is_a_programming_error_not_a_default(self):
        with pytest.raises(ValueError, match="unknown channel"):
            transport_for("telegram")

    def test_delivery_serialises_for_logs(self):
        assert Delivery(ok=True, provider_id="p1").to_dict() == {
            "ok": True,
            "provider_id": "p1",
            "error": None,
            "retryable": False,
        }
        assert "meta" not in Delivery(ok=True).to_dict()
        assert channels.Delivery(ok=True, meta={"segments": 2}).to_dict()["meta"] == {"segments": 2}
