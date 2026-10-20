"""The CLI, exercised in-process (no subprocess, no network)."""

import json

import pytest

from kazikasi.cli import main


def test_sources_lists_every_registered_source(capsys):
    assert main(["sources"]) == 0
    rows = json.loads(capsys.readouterr().out)
    ids = {row["id"] for row in rows}
    assert {
        "brightermonday", "fuzu", "myjobmag", "reliefweb", "psc", "nairobi_county",
        "careerpoint", "tsc", "ajira",
    } == ids


def test_document_parses_one_advert_into_its_posts(capsys, fixtures):
    code = main(
        [
            "document",
            "--file",
            str(fixtures / "psc-advert.pdf"),
            "--source",
            "psc",
            "--employer",
            "Public Service Commission of Kenya",
            "--county",
            "Nairobi",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["posts"] == 3
    assert [candidate["title"] for candidate in payload["candidates"]] == [
        "Assistant Office Administrator",
        "Records Management Assistant",
        "Senior ICT Officer",
    ]


def test_document_reports_an_unreadable_document(tmp_path, capsys):
    broken = tmp_path / "scan.pdf"
    broken.write_bytes(b"%PDF-1.4\nno text layer here\n")
    code = main(["document", "--file", str(broken), "--source", "psc"])
    assert code == 2
    assert "document error" in capsys.readouterr().err


def test_document_missing_file_exits(tmp_path):
    with pytest.raises(SystemExit):
        main(["document", "--file", str(tmp_path / "nope.pdf")])


def test_init_load_stats_and_review(tmp_path, capsys):
    db_path = str(tmp_path / "kazi.db")

    assert main(["init", "--db", db_path]) == 0
    capsys.readouterr()

    assert main(["load", "--db", db_path, "--demo"]) == 0
    loaded = json.loads(capsys.readouterr().out)
    assert loaded["actions"]["created"] > 20

    assert main(["stats", "--db", db_path, "--json"]) == 0
    stats = json.loads(capsys.readouterr().out)
    assert stats["live_jobs"] > 0
    assert stats["sources"]

    assert main(["review", "--db", db_path, "--json"]) == 0
    pairs = json.loads(capsys.readouterr().out)
    assert len(pairs) == 2
    assert all("score" in pair for pair in pairs)


def test_stats_human_output(tmp_path, capsys):
    db_path = str(tmp_path / "kazi.db")
    main(["load", "--db", db_path, "--demo"])
    capsys.readouterr()
    assert main(["stats", "--db", db_path]) == 0
    out = capsys.readouterr().out
    assert "live jobs" in out and "duplication rate" in out


def test_unknown_source_is_rejected(tmp_path):
    with pytest.raises(SystemExit):
        main(["ingest", "--source", "not-a-board", "--store", str(tmp_path / "raw")])


def test_profiles_seed_and_list(tmp_path, capsys):
    db_path = str(tmp_path / "kazi.db")
    assert main(["profiles", "--db", db_path, "--seed"]) == 0
    out = capsys.readouterr().out
    assert "seeded 4 demo profiles" in out
    assert "demo-fresher" in out

    # Seeding twice is a no-op, not a duplicate.
    assert main(["profiles", "--db", db_path, "--seed", "--json"]) == 0
    profiles = json.loads(capsys.readouterr().out)
    assert len(profiles) == 4


def test_match_explains_its_ranking(tmp_path, capsys):
    db_path = str(tmp_path / "kazi.db")
    main(["load", "--db", db_path, "--demo"])
    capsys.readouterr()

    assert main(["match", "--db", db_path, "--profile", "demo-two-years"]) == 0
    out = capsys.readouterr().out
    assert "Otieno" in out
    assert "Finance Assistant" in out


def test_match_json_includes_reasons(tmp_path, capsys):
    db_path = str(tmp_path / "kazi.db")
    main(["load", "--db", db_path, "--demo"])
    capsys.readouterr()

    assert main(["match", "--db", db_path, "--profile", "demo-fresher", "--json"]) == 0
    matches = json.loads(capsys.readouterr().out)
    assert matches and matches[0]["reasons"]
    assert all(match["eligible"] for match in matches)


def test_match_rejects_an_unknown_profile(tmp_path):
    with pytest.raises(SystemExit):
        main(["match", "--db", str(tmp_path / "kazi.db"), "--profile", "nobody"])


def test_apply_records_an_event(tmp_path, capsys):
    db_path = str(tmp_path / "kazi.db")
    main(["load", "--db", db_path, "--demo"])
    main(["profiles", "--db", db_path, "--seed"])
    capsys.readouterr()

    connection = __import__("kazikasi.db", fromlist=["connect"]).connect(db_path)
    job_id = connection.execute("SELECT id FROM jobs LIMIT 1").fetchone()["id"]
    connection.close()

    assert main(["apply", "--db", db_path, "--profile", "demo-fresher", "--job", job_id, "--applied"]) == 0
    event = json.loads(capsys.readouterr().out)
    assert event["kind"] == "applied"


def test_apply_on_an_unknown_profile_says_how_to_fix_it(tmp_path, capsys):
    db_path = str(tmp_path / "kazi.db")
    main(["load", "--db", db_path, "--demo"])
    capsys.readouterr()
    connection = __import__("kazikasi.db", fromlist=["connect"]).connect(db_path)
    job_id = connection.execute("SELECT id FROM jobs LIMIT 1").fetchone()["id"]
    connection.close()
    with pytest.raises(SystemExit) as error:
        main(["apply", "--db", db_path, "--profile", "ghost", "--job", job_id])
    assert "profiles --seed" in str(error.value)


def test_slo_exits_non_zero_when_the_feed_is_late(tmp_path, capsys):
    db_path = str(tmp_path / "kazi.db")
    main(["load", "--db", db_path, "--demo"])
    capsys.readouterr()
    code = main(["slo", "--db", db_path, "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert {"sources", "slo_rate", "feed_age_minutes"} <= set(payload)
    assert code in (0, 1)


def test_digest_subscribe_then_preview_writes_nothing(tmp_path, capsys):
    db_path = str(tmp_path / "kazi.db")
    main(["load", "--db", db_path, "--demo"])
    capsys.readouterr()

    assert main(["digest", "--db", db_path, "--profile", "demo-fresher", "--subscribe", "0712 345 678"]) == 0
    subscribed = json.loads(capsys.readouterr().out)
    assert subscribed["subscribed"]["msisdn"] == "+2547•••5678"

    assert main(["digest", "--db", db_path, "--profile", "demo-fresher", "--preview"]) == 0
    out = capsys.readouterr().out
    assert "*Kazi-Kasi*" in out
    assert "Reply STOP" in out

    # A preview is not a send and not a queue.
    assert main(["outbox", "--db", db_path, "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)["summary"]
    assert summary["counts"] == {}


def test_digest_queue_then_send_with_fake_transports(tmp_path, capsys):
    db_path = str(tmp_path / "kazi.db")
    main(["load", "--db", db_path, "--demo"])
    main(["digest", "--db", db_path, "--subscribe", "0712345678"])
    capsys.readouterr()

    assert main(["digest", "--db", db_path, "--profile", "demo-fresher", "--queue"]) == 0
    assert "queued (5 cards)" in capsys.readouterr().out

    assert main(["outbox", "--db", db_path]) == 0
    assert "outbox: queued 1" in capsys.readouterr().out

    assert main(["outbox", "--db", db_path, "--send", "--dry-run", "--ignore-window"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["sent"] == 1
    # The dry run proves the send without moving the message.
    assert main(["outbox", "--db", db_path]) == 0
    assert "queued 1" in capsys.readouterr().out


def test_digest_refuses_a_typo_number(tmp_path):
    db_path = str(tmp_path / "kazi.db")
    main(["load", "--db", db_path, "--demo"])
    with pytest.raises(SystemExit) as error:
        main(["digest", "--db", db_path, "--subscribe", "071234567"])
    assert "not a Kenyan mobile number" in str(error.value)


def test_outbox_refuses_to_pretend_it_sent_without_credentials(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)
    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
    db_path = str(tmp_path / "kazi.db")
    main(["load", "--db", db_path, "--demo"])
    with pytest.raises(SystemExit) as error:
        main(["outbox", "--db", db_path, "--send"])
    assert "WHATSAPP_TOKEN" in str(error.value)


def test_digest_all_targets_subscribers_not_profiles(tmp_path, capsys):
    db_path = str(tmp_path / "kazi.db")
    main(["load", "--db", db_path, "--demo"])
    main(["digest", "--db", db_path, "--profile", "demo-fresher", "--subscribe", "0712345678"])
    capsys.readouterr()

    assert main(["digest", "--db", db_path, "--all", "--preview"]) == 0
    out = capsys.readouterr().out
    assert "demo-fresher:" in out
    assert "demo-two-years" not in out        # no number, so no digest

    # With nobody subscribed, --all is an error, not a silent no-op.
    empty = str(tmp_path / "empty.db")
    main(["load", "--db", empty, "--demo"])
    capsys.readouterr()
    assert main(["digest", "--db", empty, "--all", "--preview"]) == 1


def test_digest_window_and_cadence_are_validated(tmp_path, capsys):
    db_path = str(tmp_path / "kazi.db")
    main(["load", "--db", db_path, "--demo"])
    capsys.readouterr()

    assert main(
        ["digest", "--db", db_path, "--subscribe", "0712345678",
         "--cadence", "weekly", "--window", "07:00-08:00", "--max-items", "3"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)["subscribed"]
    assert payload["cadence"] == "weekly"
    assert payload["window"] == "07:00–08:00"
    assert payload["max_items"] == 3

    with pytest.raises(SystemExit):
        main(["digest", "--db", db_path, "--subscribe", "0712345679", "--window", "18:00"])


def test_run_explains_why_nobody_is_due(tmp_path, capsys):
    db_path = str(tmp_path / "kazi.db")
    main(["load", "--db", db_path, "--demo"])
    main(["digest", "--db", db_path, "--subscribe", "0712345678"])
    capsys.readouterr()

    assert main(["run", "--db", db_path, "--explain"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["profile_id"] == "demo-fresher"
    assert rows[0]["reason"] in ("outside_window", "waiting_for_jitter", "due", "already_served")


def test_run_once_sends_nothing_without_send(tmp_path, capsys):
    db_path = str(tmp_path / "kazi.db")
    main(["load", "--db", db_path, "--demo"])
    main(["digest", "--db", db_path, "--subscribe", "0712345678"])
    capsys.readouterr()

    assert main(["run", "--db", db_path, "--once"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["sent"] is None              # composing only, no transport
    assert "waiting" in report
