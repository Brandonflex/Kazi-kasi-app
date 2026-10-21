"""Closing-soon alerts: the message a saved job is worth.

`shortlist.reminders_due()` already knew which saved jobs were inside the
window and had the text; the /shortlist page rendered it. What these tests pin is
the step that was missing — the send — and the three rules that make it safe:

* no consent, no message (a saved job is not a subscription);
* one message per job per deadline, forever, even across restarts;
* an extended deadline is a *new* promise, so it produces a new message.

The last one is the interesting failure: a naive "already reminded" flag would
go quiet exactly when the person most needs reminding, because the deadline
moved.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import alerts, outbox, scheduler, serve, shortlist
from kazikasi.channels import FakeTransport

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    connection = serve.demo_connection(now=NOW)
    yield connection
    connection.close()


def _saved_closing_soon(conn, profile_id="demo-fresher", *, hours=30):
    """Save one live job and give it a deadline inside the reminder window."""
    job = conn.execute(
        "SELECT id FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1"
    ).fetchone()
    shortlist.save(conn, profile_id, job["id"])
    deadline = (NOW + timedelta(hours=hours)).astimezone(shortlist.EAT).date().isoformat()
    conn.execute("UPDATE jobs SET deadline = ? WHERE id = ?", (deadline, job["id"]))
    conn.commit()
    return job["id"]


def test_a_saved_job_with_no_subscription_is_not_an_alert(conn):
    """The whole consent model in one assertion."""
    _saved_closing_soon(conn)
    assert outbox.load_subscription(conn, "demo-fresher") is None
    report = alerts.queue(conn, now=NOW)
    assert report["queued"] == 0
    assert report["considered"] == 0


def test_a_subscriber_with_a_saved_job_closing_soon_gets_one_message(conn):
    job_id = _saved_closing_soon(conn)
    outbox.subscribe(conn, "demo-fresher", "0712000111", now=NOW)

    report = alerts.queue(conn, now=NOW)

    assert report["queued"] == 1
    assert report["alerts"][0]["job_id"] == job_id
    rows = conn.execute("SELECT * FROM messages WHERE kind = 'closing'").fetchall()
    assert len(rows) == 1
    body = rows[0]["body"]
    assert "closes" in body and "/job/" in body
    assert rows[0]["channel"] == "whatsapp"


def test_it_says_the_same_thing_as_the_shortlist_page(conn):
    """One composer, not two. The page and the message cannot drift."""
    job_id = _saved_closing_soon(conn)
    outbox.subscribe(conn, "demo-fresher", "0712000111", now=NOW)
    page_text = shortlist.reminders_due(conn, "demo-fresher", now=NOW)[0]["text"]
    alerts.queue(conn, now=NOW)
    body = conn.execute("SELECT body FROM messages WHERE kind = 'closing'").fetchone()["body"]
    assert body == page_text
    assert f"/job/{job_id}" in body


def test_a_second_tick_does_not_send_it_twice(conn):
    _saved_closing_soon(conn)
    outbox.subscribe(conn, "demo-fresher", "0712000111", now=NOW)

    first = alerts.queue(conn, now=NOW)
    second = alerts.queue(conn, now=NOW + timedelta(minutes=5))

    assert first["queued"] == 1
    assert second["queued"] == 0
    assert second["already"] == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"] == 1


def test_a_moved_deadline_is_a_new_message(conn):
    job_id = _saved_closing_soon(conn, hours=30)
    outbox.subscribe(conn, "demo-fresher", "0712000111", now=NOW)
    alerts.queue(conn, now=NOW)

    later = (NOW + timedelta(days=2)).astimezone(shortlist.EAT).date().isoformat()
    conn.execute("UPDATE jobs SET deadline = ? WHERE id = ?", (later, job_id))
    conn.commit()

    # Still inside the window from the original moment? No: use a moment inside
    # the new deadline's window.
    near_the_new_deadline = datetime.combine(
        datetime.fromisoformat(later).date(), datetime.min.time(), tzinfo=shortlist.EAT
    ) - timedelta(hours=20)
    report = alerts.queue(conn, now=near_the_new_deadline)
    assert report["queued"] == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"] == 2


def test_an_unsubscribed_person_gets_nothing(conn):
    _saved_closing_soon(conn)
    outbox.subscribe(conn, "demo-fresher", "0712000111", now=NOW)
    outbox.unsubscribe(conn, "demo-fresher", now=NOW)
    assert alerts.queue(conn, now=NOW)["queued"] == 0


def test_the_window_is_respected(conn):
    _saved_closing_soon(conn, hours=200)  # over a week away
    outbox.subscribe(conn, "demo-fresher", "0712000111", now=NOW)
    assert alerts.queue(conn, now=NOW)["queued"] == 0
    wide = alerts.queue(conn, now=NOW, hours=24 * 12)
    assert wide["queued"] == 1


def test_a_dry_run_queues_nothing_and_shows_the_text(conn):
    _saved_closing_soon(conn)
    outbox.subscribe(conn, "demo-fresher", "0712000111", now=NOW)
    report = alerts.queue(conn, now=NOW, dry_run=True)
    assert report["queued"] == 0
    assert len(report["alerts"]) == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"] == 0


def test_a_closed_job_is_not_alerted(conn):
    job_id = _saved_closing_soon(conn)
    outbox.subscribe(conn, "demo-fresher", "0712000111", now=NOW)
    conn.execute("UPDATE jobs SET status = 'closed' WHERE id = ?", (job_id,))
    conn.commit()
    assert alerts.queue(conn, now=NOW)["queued"] == 0


def test_the_tick_sends_the_alert_through_the_outbox(conn):
    """End to end: a tick delivers it, and a second tick sends nothing.

    18:45 EAT — inside the evening send window, which `send_due` respects.
    """
    _saved_closing_soon(conn)
    evening = datetime(2026, 10, 20, 15, 45, tzinfo=timezone.utc)
    outbox.subscribe(conn, "demo-fresher", "0712000111", now=evening)
    fake = FakeTransport()

    first = scheduler.run_due(conn, {"whatsapp": fake}, now=evening, with_alerts=True)
    assert first["alerts"]["queued"] == 1
    # The daily digest is due at this hour too, so the tick carries both: the
    # alert is queued by `alerts`, the digest by `scheduler`.
    assert first["sent"]["sent"] == 2
    keys = [item["idempotency"] for item in fake.sent]
    assert any(key.startswith("closing:") for key in keys)

    second = scheduler.run_due(
        conn, {"whatsapp": fake}, now=evening + timedelta(minutes=10), with_alerts=True
    )
    assert second["alerts"]["queued"] == 0
    assert second["sent"]["sent"] == 0
    assert len(fake.sent) == 2


def test_the_tick_does_not_queue_alerts_unless_asked(conn):
    """`--no-alerts`, and every existing caller, keeps the old behaviour."""
    _saved_closing_soon(conn)
    outbox.subscribe(conn, "demo-fresher", "0712000111", now=NOW)
    report = scheduler.run_due(conn, {"whatsapp": FakeTransport()}, now=NOW)
    assert report["alerts"] is None
    assert conn.execute("SELECT COUNT(*) AS n FROM messages WHERE kind='closing'").fetchone()["n"] == 0
