"""The CLI, exercised in-process (no subprocess, no network)."""

import json

import pytest

from kazikasi.cli import main


def test_sources_lists_every_registered_source(capsys):
    assert main(["sources"]) == 0
    rows = json.loads(capsys.readouterr().out)
    ids = {row["id"] for row in rows}
    assert {"brightermonday", "fuzu", "myjobmag", "reliefweb", "psc", "nairobi_county"} == ids


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
