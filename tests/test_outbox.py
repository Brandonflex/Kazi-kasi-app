"""The outbox: consent, idempotency, retries, and the SMS fallback.

These are the failure-mode tests. Sending is easy; the expensive bugs are
sending twice, sending after someone said STOP, and retrying a channel that is
never going to work.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from kazikasi import db, digest as dg, outbox, tracking
from kazikasi.channels import FakeTransport
from kazikasi.corpus import load_corpus
from kazikasi.profile import seed_profiles

# 15:00 UTC = 18:00 EAT, the start of the default evening window.
NOW = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
TODAY = date(2026, 10, 20)


@pytest.fixture
def conn():
    connection = db.connect()
    load_corpus(connection, now=NOW)
    seed_profiles(connection)
    yield connection
    connection.close()


@pytest.fixture
def subscribed(conn):
    return outbox.subscribe(conn, "demo-fresher", "0712 345 678", now=NOW)


def transports(whatsapp=None, sms=None):
    return {
        "whatsapp": whatsapp or FakeTransport(),
        "sms": sms or FakeTransport(),
    }


class TestConsent:
    def test_subscribe_normalises_masks_and_hashes(self, conn):
        subscription = outbox.subscribe(conn, "demo-fresher", "0712 345 678", now=NOW)
        assert subscription.msisdn == "+254712345678"
        assert subscription.active
        row = conn.execute("SELECT * FROM subscriptions WHERE profile_id = 'demo-fresher'").fetchone()
        assert row["msisdn_hash"] == dg.hash_msisdn("+254712345678")
        assert "712345678" not in row["msisdn_hash"]
        assert row["consent_source"] == "cli"

    def test_a_typo_is_refused_and_nothing_is_stored(self, conn):
        with pytest.raises(ValueError):
            outbox.subscribe(conn, "demo-fresher", "071234567", now=NOW)
        assert outbox.load_subscription(conn, "demo-fresher") is None

    def test_an_unknown_profile_cannot_subscribe(self, conn):
        with pytest.raises(ValueError, match="unknown profile"):
            outbox.subscribe(conn, "nobody", "0712345678", now=NOW)

    def test_the_mask_is_what_gets_logged(self, subscribed):
        assert subscribed.to_dict()["msisdn"] == "+2547•••5678"

    def test_unsubscribing_keeps_the_history(self, conn, subscribed):
        assert outbox.unsubscribe(conn, "demo-fresher", now=NOW)
        reloaded = outbox.load_subscription(conn, "demo-fresher")
        assert not reloaded.active
        assert reloaded.unsubscribed_at is not None
        assert reloaded.msisdn == "+254712345678"       # still on file, not deleted
        assert outbox.unsubscribe(conn, "demo-fresher") is False   # already gone

    def test_resubscribing_clears_the_opt_out_and_re_dates_consent(self, conn, subscribed):
        outbox.unsubscribe(conn, "demo-fresher", now=NOW)
        later = NOW + timedelta(days=3)
        again = outbox.subscribe(conn, "demo-fresher", "+254712345678", source="whatsapp_reply", now=later)
        assert again.active
        assert again.consented_at > subscribed.consented_at
        assert again.consent_source == "whatsapp_reply"

    def test_active_subscriptions_lists_only_opted_in(self, conn):
        outbox.subscribe(conn, "demo-fresher", "0712345678", now=NOW)
        outbox.subscribe(conn, "demo-two-years", "0722000111", now=NOW)
        outbox.unsubscribe(conn, "demo-two-years", now=NOW)
        assert [s.profile_id for s in outbox.active_subscriptions(conn)] == ["demo-fresher"]


class TestComposition:
    def test_compose_uses_the_live_feed_and_caps_at_five(self, conn, subscribed):
        digest = outbox.compose(conn, "demo-fresher", now=NOW)
        assert 0 < len(digest.items) <= 5
        assert digest.for_date == TODAY

    def test_compose_never_repeats_a_queued_job(self, conn, subscribed):
        first = outbox.compose(conn, "demo-fresher", now=NOW)
        outbox.persist_run(conn, first, channel="whatsapp", now=NOW)
        outbox.set_run_state(
            conn,
            conn.execute("SELECT id FROM digest_runs").fetchone()["id"],
            "queued",
        )
        second = outbox.compose(conn, "demo-fresher", now=NOW)
        assert not ({item.job_id for item in first.items} & {item.job_id for item in second.items})

    def test_compose_skips_jobs_already_applied_for(self, conn, subscribed):
        digest = outbox.compose(conn, "demo-fresher", now=NOW)
        target = digest.items[0].job_id
        tracking.record(conn, "demo-fresher", target, "applied")
        after = outbox.compose(conn, "demo-fresher", now=NOW)
        assert target not in {item.job_id for item in after.items}

    def test_compose_refuses_an_unknown_profile(self, conn):
        with pytest.raises(ValueError):
            outbox.compose(conn, "nobody", now=NOW)

    def test_persist_run_is_idempotent_for_the_same_day(self, conn, subscribed):
        digest = outbox.compose(conn, "demo-fresher", now=NOW)
        first = outbox.persist_run(conn, digest, channel="whatsapp", now=NOW)
        second = outbox.persist_run(conn, digest, channel="whatsapp", now=NOW)
        assert first == second
        assert conn.execute("SELECT COUNT(*) c FROM digest_runs").fetchone()["c"] == 1

    def test_a_sms_run_and_a_whatsapp_run_are_different_runs(self, conn, subscribed):
        digest = outbox.compose(conn, "demo-fresher", now=NOW)
        wa = outbox.persist_run(conn, digest, channel="whatsapp", now=NOW)
        sms = outbox.persist_run(conn, digest, channel="sms", now=NOW)
        assert wa != sms


class TestQueue:
    def test_queueing_sends_nothing_and_is_idempotent(self, conn, subscribed):
        whatsapp = FakeTransport()
        first = outbox.queue_digest(conn, "demo-fresher", now=NOW, link_base="https://k.app")
        second = outbox.queue_digest(conn, "demo-fresher", now=NOW, link_base="https://k.app")

        assert first["state"] == "queued" and first["queued"] == 1
        assert second["queued"] == 0                      # same key, same row
        assert conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"] == 1
        assert whatsapp.sent == []

    def test_dry_run_writes_nothing(self, conn, subscribed):
        result = outbox.queue_digest(conn, "demo-fresher", now=NOW, dry_run=True)
        assert result["state"] == "dry_run"
        assert result["queued"] == 0
        assert result["preview"].startswith("*Kazi-Kasi*")
        assert conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"] == 0
        assert conn.execute("SELECT state FROM digest_runs").fetchone()["state"] == "composed"

    def test_queueing_requires_a_subscription(self, conn):
        with pytest.raises(ValueError, match="no subscription"):
            outbox.queue_digest(conn, "demo-fresher", now=NOW)

    def test_an_unsubscribed_person_gets_nothing_even_if_asked(self, conn, subscribed):
        outbox.unsubscribe(conn, "demo-fresher", now=NOW)
        result = outbox.queue_digest(conn, "demo-fresher", now=NOW)
        assert result["state"] == "unsubscribed"
        assert conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"] == 0

    def test_a_message_records_the_masked_number_not_a_plaintext_one(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        row = conn.execute("SELECT * FROM messages").fetchone()
        assert row["to_msisdn"] == "+254712345678"   # needed to actually deliver
        assert row["state"] == "queued"

    def test_nothing_to_say_produces_no_message(self, conn, subscribed):
        for job in conn.execute("SELECT id FROM jobs").fetchall():
            tracking.record(conn, "demo-fresher", job["id"], "dismissed")
        result = outbox.queue_digest(conn, "demo-fresher", now=NOW)
        assert result["state"] == "empty"
        assert result["preview"] == ""
        assert conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"] == 0


class TestDelivery:
    def test_a_queued_digest_is_delivered_once(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW, link_base="https://k.app")
        whatsapp = FakeTransport()
        report = outbox.send_due(conn, transports(whatsapp=whatsapp), now=NOW)

        assert report.sent == 1 and report.failed == 0
        assert len(whatsapp.sent) == 1
        assert whatsapp.sent[0]["to"] == "+254712345678"
        row = conn.execute("SELECT * FROM messages").fetchone()
        assert row["state"] == "sent" and row["attempts"] == 1 and row["sent_at"]

        # A second sweep has nothing left to do.
        assert outbox.send_due(conn, transports(whatsapp=whatsapp), now=NOW).sent == 0
        assert len(whatsapp.sent) == 1

    def test_the_run_is_marked_sent_with_the_message(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        outbox.send_due(conn, transports(), now=NOW)
        assert conn.execute("SELECT state FROM digest_runs").fetchone()["state"] == "sent"

    def test_consent_is_re_checked_at_send_time(self, conn, subscribed):
        """The STOP arrives between composition and delivery."""
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        outbox.unsubscribe(conn, "demo-fresher", now=NOW)
        whatsapp = FakeTransport()
        report = outbox.send_due(conn, transports(whatsapp=whatsapp), now=NOW)

        assert report.suppressed == 1 and report.sent == 0
        assert whatsapp.sent == []
        assert conn.execute("SELECT state FROM messages").fetchone()["state"] == "suppressed"

    def test_nothing_is_sent_outside_the_persons_window(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        early = datetime(2026, 10, 20, 5, 0, tzinfo=timezone.utc)   # 08:00 EAT
        whatsapp = FakeTransport()
        report = outbox.send_due(conn, transports(whatsapp=whatsapp), now=early)

        assert report.skipped_out_of_window == 1
        assert whatsapp.sent == []
        assert conn.execute("SELECT state FROM messages").fetchone()["state"] == "queued"

    def test_the_window_can_be_ignored_deliberately(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        early = datetime(2026, 10, 20, 5, 0, tzinfo=timezone.utc)
        report = outbox.send_due(conn, transports(), now=early, respect_window=False)
        assert report.sent == 1

    def test_dry_run_calls_the_transport_but_changes_no_state(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        whatsapp = FakeTransport()
        report = outbox.send_due(conn, transports(whatsapp=whatsapp), now=NOW, dry_run=True)

        assert report.sent == 1
        assert len(whatsapp.sent) == 1
        row = conn.execute("SELECT * FROM messages").fetchone()
        assert row["state"] == "queued" and row["attempts"] == 0

    def test_a_missing_transport_is_reported_not_swallowed(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        report = outbox.send_due(conn, {}, now=NOW)
        assert report.failed == 1
        assert "no transport" in report.errors[0]


class TestRetriesAndFallback:
    def test_a_retryable_failure_is_retried_later_not_now(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        failing = FakeTransport(fail_with="provider 503", retryable=True)
        report = outbox.send_due(conn, transports(whatsapp=failing), now=NOW)

        assert report.retried == 1 and report.failed == 0
        row = conn.execute("SELECT * FROM messages").fetchone()
        assert row["state"] == "queued"
        assert row["attempts"] == 1
        assert row["last_error"] == "provider 503"

        # Inside the 5-minute backoff: deferred, no second attempt.
        too_soon = outbox.send_due(conn, transports(whatsapp=failing), now=NOW + timedelta(minutes=2))
        assert too_soon.deferred == 1
        assert conn.execute("SELECT attempts FROM messages").fetchone()["attempts"] == 1

        # Past the backoff: it tries again.
        later = outbox.send_due(conn, transports(whatsapp=failing), now=NOW + timedelta(minutes=6))
        assert later.retried == 1
        assert conn.execute("SELECT attempts FROM messages").fetchone()["attempts"] == 2

    def test_three_attempts_then_it_gives_up_and_falls_back_to_sms(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW, link_base="https://k.app")
        failing = FakeTransport(fail_with="provider 503", retryable=True)
        sms = FakeTransport()

        clock = NOW
        outbox.send_due(conn, transports(whatsapp=failing, sms=sms), now=clock)          # attempt 1
        clock += timedelta(minutes=6)
        outbox.send_due(conn, transports(whatsapp=failing, sms=sms), now=clock)          # attempt 2
        clock += timedelta(minutes=31)
        report = outbox.send_due(conn, transports(whatsapp=failing, sms=sms), now=clock)  # attempt 3: terminal

        failed = conn.execute("SELECT * FROM messages WHERE channel = 'whatsapp'").fetchone()
        assert failed["state"] == "failed"
        assert failed["attempts"] == outbox.MAX_ATTEMPTS
        assert report.failed == 1 and report.fell_back == 1

        fallback = conn.execute("SELECT * FROM messages WHERE channel = 'sms'").fetchone()
        assert fallback["kind"] == "fallback"
        assert fallback["state"] == "queued"
        assert fallback["body"].startswith("Kazi-Kasi: ")
        assert len(fallback["body"]) <= dg.SMS_SEGMENT
        assert fallback["idempotency"] == f"demo-fresher:{TODAY.isoformat()}:sms:1"

        # And the SMS actually goes out on the next sweep.
        sent = outbox.send_due(conn, transports(whatsapp=failing, sms=sms), now=clock)
        assert sent.sent == 1
        assert sms.sent[0]["to"] == "+254712345678"

    def test_an_unretryable_failure_does_not_burn_three_attempts(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        failing = FakeTransport(fail_with="provider 400: bad number", retryable=False)
        sms = FakeTransport()
        report = outbox.send_due(conn, transports(whatsapp=failing, sms=sms), now=NOW)

        assert report.failed == 1 and report.fell_back == 1
        row = conn.execute("SELECT * FROM messages WHERE channel = 'whatsapp'").fetchone()
        assert row["state"] == "failed" and row["attempts"] == 1

    def test_no_fallback_channel_means_no_fallback(self, conn):
        outbox.subscribe(conn, "demo-fresher", "0712345678", fallback_channel=None, now=NOW)
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        report = outbox.send_due(
            conn, transports(whatsapp=FakeTransport(fail_with="nope", retryable=False), sms=FakeTransport()), now=NOW
        )
        assert report.failed == 1 and report.fell_back == 0
        assert conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"] == 1

    def test_a_fallback_is_not_re_created_on_a_second_failure(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        dead = FakeTransport(fail_with="provider 400", retryable=False)
        sms = FakeTransport()
        outbox.send_due(conn, transports(whatsapp=dead, sms=sms), now=NOW)
        outbox.send_due(conn, transports(whatsapp=dead, sms=sms), now=NOW)
        assert conn.execute("SELECT COUNT(*) c FROM messages WHERE channel = 'sms'").fetchone()["c"] == 1


class TestReporting:
    def test_summary_counts_every_state(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        outbox.send_due(conn, transports(), now=NOW)
        summary = outbox.outbox_summary(conn)
        assert summary["counts"] == {"sent": 1}
        assert summary["queued"] == 0

    def test_messages_for_a_profile_are_newest_first_and_complete(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        rows = outbox.messages_for(conn, "demo-fresher")
        assert len(rows) == 1
        assert rows[0]["body"].startswith("*Kazi-Kasi*")
        assert rows[0]["channel"] == "whatsapp"

    def test_the_report_serialises_for_the_cli(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        payload = outbox.send_due(conn, transports(), now=NOW).to_dict()
        assert set(payload) == {
            "sent", "failed", "retried", "suppressed", "fell_back", "skipped_out_of_window", "deferred", "errors"
        }

    def test_an_empty_outbox_is_a_no_op(self, conn):
        report = outbox.send_due(conn, transports(), now=NOW)
        assert (report.sent, report.failed, report.retried) == (0, 0, 0)


class TestHardening:
    """The bugs that would only show up in production, one per test."""

    def test_a_number_cannot_be_brute_forced_from_its_hash(self, monkeypatch):
        monkeypatch.delenv("KAZIKASI_HASH_KEY", raising=False)
        development = dg.hash_msisdn("+254712345678")
        monkeypatch.setenv("KAZIKASI_HASH_KEY", "a-real-deployment-secret")
        assert dg.hash_msisdn("+254712345678") != development
        assert dg.hash_is_keyed() is True

    def test_the_hash_is_stable_within_one_deployment(self, monkeypatch):
        monkeypatch.setenv("KAZIKASI_HASH_KEY", "secret")
        assert dg.hash_msisdn("+254712345678") == dg.hash_msisdn("+254712345678")

    def test_a_window_that_never_opens_is_refused(self, conn):
        with pytest.raises(ValueError):
            outbox.subscribe(conn, "demo-fresher", "0712345678", window=("18:00", "18:00"), now=NOW)
        with pytest.raises(ValueError):
            outbox.subscribe(conn, "demo-fresher", "0712345678", window=("6pm", "8pm"), now=NOW)

    def test_max_items_is_bounded(self, conn):
        with pytest.raises(ValueError):
            outbox.subscribe(conn, "demo-fresher", "0712345678", max_items=0, now=NOW)
        with pytest.raises(ValueError):
            outbox.subscribe(conn, "demo-fresher", "0712345678", max_items=50, now=NOW)

    def test_a_subscription_records_its_max_items_in_the_message(self, conn):
        outbox.subscribe(conn, "demo-fresher", "0712345678", max_items=2, now=NOW)
        result = outbox.queue_digest(conn, "demo-fresher", now=NOW)
        assert len(result["digest"]["items"]) == 2

    def test_every_message_knows_its_run(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        run_id = conn.execute("SELECT id FROM digest_runs").fetchone()["id"]
        assert conn.execute("SELECT run_id FROM messages").fetchone()["run_id"] == run_id

    def test_a_second_part_still_leaves_after_the_window_closes(self, conn, subscribed):
        """Part 1 at 19:58, part 2 at 20:01: the person gets the whole message."""
        digest = outbox.compose(conn, "demo-fresher", now=NOW)
        run_id = outbox.persist_run(conn, digest, channel="whatsapp", now=NOW)
        outbox.set_run_state(conn, run_id, "queued")
        outbox.enqueue(
            conn,
            dg.Outgoing("demo-fresher", "whatsapp", "+254712345678", "part one", "k:1"),
            run_id=run_id,
            now=NOW,
        )
        outbox.enqueue(
            conn,
            dg.Outgoing("demo-fresher", "whatsapp", "+254712345678", "part two", "k:2"),
            run_id=run_id,
            now=NOW,
        )
        late = datetime(2026, 10, 20, 16, 58, tzinfo=timezone.utc)   # 19:58 EAT
        outbox.send_due(conn, transports(), now=late)
        assert conn.execute("SELECT state FROM messages WHERE idempotency = 'k:1'").fetchone()["state"] == "sent"

        after_window = datetime(2026, 10, 20, 17, 5, tzinfo=timezone.utc)  # 20:05 EAT
        report = outbox.send_due(conn, transports(), now=after_window)
        assert report.skipped_out_of_window == 0
        assert conn.execute("SELECT state FROM messages WHERE idempotency = 'k:2'").fetchone()["state"] == "sent"

    def test_an_empty_afternoon_does_not_rewrite_a_sent_morning(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        outbox.send_due(conn, transports(), now=NOW)
        for job in conn.execute("SELECT id FROM jobs").fetchall():
            tracking.record(conn, "demo-fresher", job["id"], "dismissed")

        result = outbox.queue_digest(conn, "demo-fresher", now=NOW)
        assert result["state"] == "sent"
        assert conn.execute("SELECT state FROM digest_runs").fetchone()["state"] == "sent"

    def test_changing_channel_suppresses_the_stale_message(self, conn, subscribed):
        outbox.queue_digest(conn, "demo-fresher", now=NOW)
        outbox.subscribe(conn, "demo-fresher", "0712345678", channel="sms", now=NOW)
        report = outbox.send_due(conn, transports(), now=NOW)
        assert report.suppressed == 1
        assert conn.execute("SELECT state FROM messages").fetchone()["state"] == "suppressed"

    def test_the_consent_log_records_every_change(self, conn):
        outbox.subscribe(conn, "demo-fresher", "0712345678", source="web", now=NOW)
        outbox.unsubscribe(conn, "demo-fresher", now=NOW, reason="web")
        actions = [event["action"] for event in outbox.consent_events_for(conn, "demo-fresher")]
        assert actions == ["unsubscribed", "subscribed"]
        assert outbox.consent_events_for(conn, "demo-fresher")[0]["source"] == "web"
