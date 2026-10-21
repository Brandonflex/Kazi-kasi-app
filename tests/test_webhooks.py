"""Inbound: STOP has to work, receipts have to land, and neither can be faked.

These are the tests that make the consent story true rather than claimed:

* a signed payload from Meta is accepted, an unsigned one is not;
* STOP from a phone we know opts that person out, dated;
* STOP from a phone we do not know is still logged;
* HELP gets one segment back, once, even if the provider retries;
* a delivered receipt moves the message and its run forward, and a late "sent"
  never moves them back.
"""

from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import db, outbox, webhooks
from kazikasi.corpus import load_corpus
from kazikasi.profile import seed_profiles

NOW = datetime(2026, 10, 20, 15, 30, tzinfo=timezone.utc)  # 18:30 EAT


@pytest.fixture
def conn():
    connection = db.connect()
    load_corpus(connection, now=NOW)
    seed_profiles(connection)
    yield connection
    connection.close()


@pytest.fixture
def subscriber(conn):
    return outbox.subscribe(conn, "demo-fresher", "0712 345 678", source="web", now=NOW)


def meta_message(text, sender="254712345678", message_id="wamid.in.1"):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "1234",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "1"},
                            "messages": [
                                {
                                    "id": message_id,
                                    "from": sender,
                                    "timestamp": "1750000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def meta_status(status, provider_id="wamid.out.1", recipient="254712345678", error=None):
    payload = {
        "id": provider_id,
        "status": status,
        "timestamp": "1750000000",
        "recipient_id": recipient,
        "conversation": {"id": "c1"},
    }
    if error:
        payload["errors"] = [{"title": error}]
    return {
        "entry": [{"id": "1", "changes": [{"field": "messages", "value": {"statuses": [payload]}}]}]
    }


class TestSignatures:
    def test_a_signed_body_verifies(self):
        body = b'{"entry":[]}'
        header = webhooks.sign(body, "secret")
        assert webhooks.verify_signature(body, header, "secret")

    def test_a_tampered_body_does_not(self):
        header = webhooks.sign(b'{"entry":[]}', "secret")
        assert not webhooks.verify_signature(b'{"entry":[1]}', header, "secret")

    def test_the_wrong_secret_does_not(self):
        header = webhooks.sign(b'{"entry":[]}', "secret")
        assert not webhooks.verify_signature(b'{"entry":[]}', header, "other")

    def test_a_missing_header_or_secret_fails_closed(self):
        assert not webhooks.verify_signature(b"{}", None, "secret")
        assert not webhooks.verify_signature(b"{}", "sha256=abc", None)
        assert not webhooks.verify_signature(b"{}", "", "secret")

    def test_the_handshake_echoes_the_challenge_only_for_the_right_token(self):
        params = {"hub.mode": "subscribe", "hub.verify_token": "t", "hub.challenge": "42"}
        assert webhooks.verify_challenge(params, "t") == "42"
        assert webhooks.verify_challenge(params, "wrong") is None
        assert webhooks.verify_challenge(params, None) is None
        assert webhooks.verify_challenge({"hub.mode": "unsubscribe"}, "t") is None


class TestParsing:
    def test_a_text_message_becomes_an_event(self):
        events = webhooks.parse_meta(meta_message("STOP"))
        assert len(events) == 1
        event = events[0]
        assert (event.kind, event.channel, event.text) == ("message", "whatsapp", "STOP")
        assert event.msisdn == "+254712345678"

    def test_a_status_becomes_a_receipt(self):
        events = webhooks.parse_meta(meta_status("delivered"))
        assert events[0].kind == "status"
        assert events[0].status == "delivered"
        assert events[0].msisdn == "+254712345678"

    def test_a_failed_status_carries_the_reason(self):
        events = webhooks.parse_meta(meta_status("failed", error="Recipient not on WhatsApp"))
        assert events[0].error == "Recipient not on WhatsApp"

    def test_an_unexpected_payload_is_empty_not_an_exception(self):
        assert webhooks.parse_meta({}) == []
        assert webhooks.parse_meta({"entry": [{"changes": []}]}) == []
        assert webhooks.parse_json("not json") == {}
        assert webhooks.parse_json("[]") == {}

    def test_an_unknown_sender_is_not_invented(self):
        events = webhooks.parse_meta(meta_message("STOP", sender="not-a-number"))
        assert events[0].msisdn is None

    def test_africas_talking_form_is_parsed(self):
        events = webhooks.parse_africas_talking({"from": "+254712345678", "text": "stop", "id": "AT1"})
        assert events[0].msisdn == "+254712345678"
        assert events[0].text == "stop"

    def test_an_africas_talking_delivery_report_is_a_receipt(self):
        events = webhooks.parse_africas_talking(
            {"from": "+254712345678", "status": "Success", "id": "AT1"}
        )
        assert events[0].kind == "status" and events[0].status == "delivered"


class TestCommands:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("STOP", "stop"),
            ("stop", "stop"),
            ("  Stop please ", "stop"),
            ("STOPALL", "stop"),
            ("unsubscribe", "stop"),
            ("START", "start"),
            ("yes", "start"),
            ("HELP", "help"),
            ("saidia", "help"),
            ("Is this thing on?", "unrecognised"),
            ("", "unrecognised"),
            ("42", "unrecognised"),
        ],
    )
    def test_classification(self, text, expected):
        assert webhooks.classify(text) == expected

    def test_stop_unsubscribes_the_owner_and_is_audited(self, conn, subscriber):
        result = webhooks.handle_meta(conn, meta_message("STOP"), now=NOW)

        assert result["actions"] == {"unsubscribed": 1}
        assert result["results"][0]["matched"] is True
        assert not outbox.load_subscription(conn, "demo-fresher").active

        events = outbox.consent_events_for(conn, "demo-fresher")
        assert events[0]["action"] == "unsubscribed"
        assert events[0]["source"] == "whatsapp"
        assert events[0]["msisdn_hash"] != "+254712345678"

    def test_stop_from_an_unknown_number_is_still_recorded(self, conn):
        result = webhooks.handle_meta(conn, meta_message("STOP", sender="254799999999"), now=NOW)
        assert result["results"][0]["matched"] is False
        row = conn.execute("SELECT * FROM consent_events").fetchone()
        assert row["action"] == "unsubscribed"
        assert row["profile_id"] is None
        assert row["detail"] == "unknown number"

    def test_a_second_stop_does_not_double_unsubscribe(self, conn, subscriber):
        webhooks.handle_meta(conn, meta_message("STOP", message_id="m1"), now=NOW)
        webhooks.handle_meta(conn, meta_message("STOP", message_id="m2"), now=NOW)
        acts = [row["action"] for row in outbox.consent_events_for(conn, "demo-fresher")]
        assert acts.count("unsubscribed") == 1

    def test_start_resumes_and_re_dates_consent(self, conn, subscriber):
        webhooks.handle_meta(conn, meta_message("STOP"), now=NOW)
        later = NOW + timedelta(days=1)
        result = webhooks.handle_meta(conn, meta_message("START"), now=later)

        assert result["results"][0]["matched"] is True
        subscription = outbox.load_subscription(conn, "demo-fresher")
        assert subscription.active
        assert subscription.consented_at > subscriber.consented_at
        assert subscription.consent_source == "whatsapp"

    def test_help_replies_once_even_if_the_provider_retries(self, conn, subscriber):
        first = webhooks.handle_meta(conn, meta_message("HELP", message_id="wamid.h1"), now=NOW)
        second = webhooks.handle_meta(conn, meta_message("HELP", message_id="wamid.h1"), now=NOW)

        assert first["results"][0]["replied"] is True
        assert second["results"][0]["replied"] is False
        notices = conn.execute("SELECT * FROM messages WHERE kind = 'notice'").fetchall()
        assert len(notices) == 1
        assert notices[0]["body"] == outbox.HELP_TEXT
        assert "STOP" in notices[0]["body"]

    def test_an_unknown_sender_gets_help_only_when_we_could_reply(self, conn):
        result = webhooks.handle_meta(conn, meta_message("hello?", sender="254799999999"), now=NOW)
        assert result["results"][0]["action"] == "unrecognised"
        assert result["results"][0]["replied"] is False
        assert conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"] == 0

    def test_an_unparseable_sender_is_logged_not_dropped(self, conn):
        result = webhooks.handle_meta(conn, meta_message("STOP", sender="??"), now=NOW)
        assert result["results"][0]["action"] == "unrecognised"
        assert conn.execute("SELECT COUNT(*) c FROM consent_events").fetchone()["c"] == 1

    def test_sms_stop_works_the_same_way(self, conn, subscriber):
        result = webhooks.handle_africas_talking(
            conn, {"from": "+254712345678", "text": "STOP", "id": "AT9"}, now=NOW
        )
        assert result["actions"] == {"unsubscribed": 1}
        assert not outbox.load_subscription(conn, "demo-fresher").active
        assert outbox.consent_events_for(conn, "demo-fresher")[0]["source"] == "sms"


class TestReceipts:
    def _queued(self, conn):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        row = conn.execute("SELECT * FROM messages").fetchone()
        conn.execute(
            "UPDATE messages SET state = 'sent', provider_id = 'wamid.out.1' WHERE id = ?",
            (row["id"],),
        )
        conn.commit()
        return row["id"]

    def test_delivered_moves_the_message_and_finishes_the_run(self, conn, subscriber):
        message_id = self._queued(conn)
        result = webhooks.handle_meta(conn, meta_status("delivered"), now=NOW)

        assert result["actions"] == {"receipt": 1}
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        assert row["state"] == "delivered"
        assert row["delivered_at"]
        assert conn.execute("SELECT state FROM digest_runs").fetchone()["state"] == "sent"

    def test_receipts_are_kept_as_events(self, conn, subscriber):
        message_id = self._queued(conn)
        webhooks.handle_meta(conn, meta_status("delivered"), now=NOW)
        webhooks.handle_meta(conn, meta_status("read"), now=NOW)
        receipts = outbox.receipts_for(conn, message_id)
        assert [receipt["status"] for receipt in receipts] == ["delivered", "read"]

    def test_a_late_sent_does_not_undo_a_delivery(self, conn, subscriber):
        message_id = self._queued(conn)
        webhooks.handle_meta(conn, meta_status("delivered"), now=NOW)
        webhooks.handle_meta(conn, meta_status("sent"), now=NOW)
        row = conn.execute("SELECT state FROM messages WHERE id = ?", (message_id,)).fetchone()
        assert row["state"] == "delivered"

    def test_a_failure_after_delivery_is_not_a_state_change(self, conn, subscriber):
        message_id = self._queued(conn)
        webhooks.handle_meta(conn, meta_status("delivered"), now=NOW)
        webhooks.handle_meta(conn, meta_status("failed", error="too late"), now=NOW)
        row = conn.execute("SELECT state, last_error FROM messages WHERE id = ?", (message_id,)).fetchone()
        assert row["state"] == "delivered"

    def test_a_failure_receipt_records_why(self, conn, subscriber):
        message_id = self._queued(conn)
        webhooks.handle_meta(
            conn, meta_status("failed", error="Recipient not on WhatsApp"), now=NOW
        )
        row = conn.execute("SELECT state, last_error FROM messages WHERE id = ?", (message_id,)).fetchone()
        assert row["state"] == "failed"
        assert row["last_error"] == "Recipient not on WhatsApp"

    def test_a_receipt_for_an_unknown_message_is_logged_not_guessed(self, conn):
        result = webhooks.handle_meta(
            conn, meta_status("delivered", provider_id="wamid.unknown"), now=NOW
        )
        assert result["results"][0]["message_id"] is None
        assert conn.execute("SELECT COUNT(*) c FROM message_receipts").fetchone()["c"] == 1

    def test_a_receipt_can_find_the_message_by_recipient_when_ids_differ(self, conn, subscriber):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        message_id = conn.execute("SELECT id FROM messages").fetchone()["id"]
        outbox.record_receipt(conn, status="delivered", to_msisdn="+254712345678", now=NOW)
        row = conn.execute("SELECT state FROM messages WHERE id = ?", (message_id,)).fetchone()
        assert row["state"] == "delivered"


class TestNoSendAfterStop:
    def test_a_message_queued_before_stop_is_suppressed_at_send(self, conn, subscriber):
        from kazikasi.channels import FakeTransport

        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        webhooks.handle_meta(conn, meta_message("STOP"), now=NOW)

        whatsapp = FakeTransport()
        report = outbox.send_due(conn, {"whatsapp": whatsapp, "sms": FakeTransport()}, now=NOW)
        assert report.suppressed == 1
        assert whatsapp.sent == []
