"""Contract and security regressions for the product API."""
import os

os.environ.setdefault("KAZIKASI_SECRET_KEY", "test-only-signing-key-with-more-than-32-bytes")

from fastapi.testclient import TestClient

from backend.api import main


def test_managed_runtime_is_detected_without_explicit_app_env():
    assert main._is_managed_runtime({}) is False
    assert main._is_managed_runtime({"VERCEL": "1"}) is True
    assert main._is_managed_runtime({"K_SERVICE": "kazi-api"}) is True
    assert main._runtime_app_env({"APP_ENV": "development", "VERCEL": "1"}) == "production"
    assert main._runtime_app_env({"APP_ENV": "test"}) == "test"


def test_register_login_and_profile_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "api.sqlite"))
    with TestClient(main.app) as client:
        response = client.post("/api/auth/register", json={
            "email": "  Test@Example.com ",
            "name": "Test User",
            "password": "a-correct-long-password",
        })
        assert response.status_code == 201
        assert client.post("/api/auth/register", json={
            "email": "test@example.com", "name": "Another Test", "password": "another-long-password",
        }).status_code == 409
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        assert client.get("/api/auth/me", headers=headers).json()["email"] == "test@example.com"
        profile = client.get("/api/profile", headers=headers)
        assert profile.status_code == 200

        updated = client.put("/api/profile", headers=headers, json={
            "role_families": ["it", "finance", "it"],
            "skills": ["Python"],
            "home_county": " Mombasa ",
            "max_commute_km": None,
            "min_monthly_pay": 50000,
        })
        assert updated.status_code == 200
        assert updated.json()["role_families"] == ["it", "finance"]
        assert updated.json()["home_county"] == "Mombasa"

        # The public API reads job text and provenance from the observation, not
        # from fabricated demo rows or fields absent from the jobs table.
        from datetime import date, datetime, timezone
        from kazikasi.models import JobCandidate, JobPay
        import_source_conn = main.db.connect(main.DB_PATH)
        candidate = JobCandidate(
            source_id="brightermonday", source_job_id="fixture-software-1",
            source_url="https://jobs.example.com/roles/123", apply_url="https://jobs.example.com/apply/123",
            title="Junior Software Engineer", employer_name="Example Tech",
            description_md="Build useful software with Python and the product team.", county="Mombasa",
            entry_fit="open_to_freshers", pay=JobPay(min_amount=60000, max_amount=85000, period="month"),
            deadline=date.today(), status="open",
        )
        main.sweep.write_job(candidate, import_source_conn, datetime.now(timezone.utc))
        import_source_conn.commit()
        import_source_conn.close()
        jobs = client.get("/api/jobs", headers=headers)
        assert jobs.status_code == 200
        assert jobs.json()["jobs"][0]["description"] == "Build useful software with Python and the product team."
        assert any("skills: Python" in reason for reason in jobs.json()["jobs"][0]["match_reasons"])
        assert jobs.json()["jobs"][0]["source_url"] == "https://jobs.example.com/roles/123"
        assert jobs.json()["jobs"][0]["url"] == "https://jobs.example.com/apply/123"

        login = client.post("/api/auth/login", json={
            "email": "test@example.com", "password": "a-correct-long-password",
        })
        assert login.status_code == 200
        # Newly created passwords are stored using the slow salted hash scheme.
        db_conn = main.db.connect(main.DB_PATH)
        try:
            stored = db_conn.execute("SELECT password_hash FROM accounts WHERE email = ?", ("test@example.com",)).fetchone()["password_hash"]
        finally:
            db_conn.close()
        assert stored.startswith("pbkdf2_sha256$")
        # Existing accounts from the retired SHA-256 scheme still sign in, and
        # are upgraded as part of that successful login.
        import hashlib
        legacy_salt = "a" * 32
        legacy_hash = hashlib.sha256((legacy_salt + "a-correct-long-password").encode()).hexdigest()
        db_conn = main.db.connect(main.DB_PATH)
        db_conn.execute("UPDATE accounts SET password_hash = ? WHERE email = ?", (f"{legacy_salt}${legacy_hash}", "test@example.com"))
        db_conn.commit()
        db_conn.close()
        assert client.post("/api/auth/login", json={
            "email": "test@example.com", "password": "a-correct-long-password",
        }).status_code == 200
        db_conn = main.db.connect(main.DB_PATH)
        try:
            upgraded = db_conn.execute("SELECT password_hash FROM accounts WHERE email = ?", ("test@example.com",)).fetchone()["password_hash"]
        finally:
            db_conn.close()
        assert upgraded.startswith("pbkdf2_sha256$")
        assert client.post("/api/auth/login", json={
            "email": "test@example.com", "password": "wrong-password",
        }).status_code == 401


def test_account_and_password_survive_a_new_api_client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "restart.sqlite"))
    with TestClient(main.app) as first_instance:
        created = first_instance.post("/api/auth/register", json={
            "email": "restart@example.com", "name": "Restart Test",
            "password": "safe-long-password-123",
        })
    assert created.status_code == 201

    # A fresh client models another worker/request after the first one is gone.
    with TestClient(main.app) as next_instance:
        signed_in = next_instance.post("/api/auth/login", json={
            "email": "restart@example.com", "password": "safe-long-password-123",
        })
        assert signed_in.status_code == 200
        assert next_instance.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {signed_in.json()['access_token']}"},
        ).status_code == 200


def test_cv_upload_extracts_profile_evidence_and_never_stores_pdf_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "cv.sqlite"))
    cv_text = """Amina Otieno\namina@example.com\n+254712345678\nNairobi\n
Skills: Python, SQL, AWS, Docker\nBSc Computer Science\nSoftware Developer, 2021 - Present\n"""
    monkeypatch.setattr(main.documents, "bytes_to_text", lambda data, content_type: cv_text)
    with TestClient(main.app) as client:
        created = client.post("/api/auth/register", json={
            "email": "amina@example.com", "name": "Amina Otieno", "password": "another-long-password",
        })
        headers = {"Authorization": f"Bearer {created.json()['access_token']}"}
        response = client.post(
            "/api/profile/cv", headers=headers,
            files={"file": ("amina-cv.pdf", b"%PDF-1.7 test bytes", "application/pdf")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["cv"]["filename"] == "amina-cv.pdf"
        assert body["cv"]["fields"]["email"]["value"] == "amina@example.com"
        assert {"python", "sql", "aws", "docker"} <= set(body["profile"]["skills"])
        assert client.get("/api/profile/cv", headers=headers).json()["cv"]["id"] == body["cv"]["id"]
        db_conn = main.db.connect(main.DB_PATH)
        try:
            row = db_conn.execute("SELECT filename, fields FROM cvs WHERE account_id = ?", (body["profile"]["id"],)).fetchone()
            assert row["filename"] == "amina-cv.pdf"
            assert b"%PDF" not in row["fields"].encode()
        finally:
            db_conn.close()
        removed = client.delete("/api/profile/cv", headers=headers)
        assert removed.status_code == 200 and removed.json()["deleted"] is True


def test_actual_text_pdf_passes_through_the_upload_path(tmp_path, monkeypatch):
    from pathlib import Path

    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "real-pdf.sqlite"))
    pdf = Path(__file__).parent / "fixtures" / "nairobi-advert.pdf"
    with TestClient(main.app) as client:
        created = client.post("/api/auth/register", json={
            "email": "actual-pdf@example.com", "name": "PDF Reader", "password": "another-long-password",
        })
        headers = {"Authorization": f"Bearer {created.json()['access_token']}"}
        response = client.post("/api/profile/cv", headers=headers, files={
            "file": ("profile.pdf", pdf.read_bytes(), "application/pdf"),
        })
        assert response.status_code == 200
        assert response.json()["cv"]["chars"] > 1000


def test_cv_upload_rejects_non_pdf_and_oversized_documents(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "cv-validation.sqlite"))
    with TestClient(main.app) as client:
        created = client.post("/api/auth/register", json={
            "email": "pdf@example.com", "name": "PDF User", "password": "another-long-password",
        })
        headers = {"Authorization": f"Bearer {created.json()['access_token']}"}
        wrong_type = client.post("/api/profile/cv", headers=headers, files={
            "file": ("resume.txt", b"not a pdf", "text/plain"),
        })
        assert wrong_type.status_code == 415
        not_pdf = client.post("/api/profile/cv", headers=headers, files={
            "file": ("resume.pdf", b"not really pdf", "application/pdf"),
        })
        assert not_pdf.status_code == 415
        oversized = client.post("/api/profile/cv", headers=headers, files={
            "file": ("large.pdf", b"%PDF-" + b"x" * main.MAX_CV_BYTES, "application/pdf"),
        })
        assert oversized.status_code == 413


def test_source_catalog_reports_verified_state_without_leaking_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "sources.sqlite"))
    with TestClient(main.app) as client:
        response = client.get("/api/sources")
        assert response.status_code == 200
        rows = {source["id"]: source for source in response.json()["sources"]}
        assert rows["brightermonday"]["status"] == "active"
        assert rows["careerpoint"]["status"] == "unverified"
        assert rows["brightermonday"]["health"] == "not_synced"
        assert "last_error" not in rows["brightermonday"]


def test_auth_input_and_bearer_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "validation.sqlite"))
    with TestClient(main.app) as client:
        assert client.post("/api/auth/register", json={
            "email": "not-an-email", "name": "Test", "password": "long-enough-password",
        }).status_code == 422
        assert client.post("/api/auth/register", json={
            "email": "test@example.com", "name": "Test", "password": "short",
        }).status_code == 422
        assert client.get("/api/auth/me").status_code == 401
        assert client.get("/api/auth/me", headers={"Authorization": "Bearer malformed"}).status_code == 401
        assert client.get("/api/jobs?limit=999").status_code == 401


def test_external_application_links_only_allow_web_schemes():
    assert main.safe_source_url("https://example.com/apply") == "https://example.com/apply"
    assert main.safe_source_url("http://example.com") == "http://example.com"
    assert main.safe_source_url("javascript:alert(1)") == ""
    assert main.safe_source_url("//example.com/apply") == ""
    assert main.safe_source_url(None) == ""


def test_production_requires_secret():
    import pytest

    with pytest.raises(RuntimeError, match="must be configured"):
        main.load_secret_key("production", None)
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        main.load_secret_key("production", "too-short")
    assert len(main.load_secret_key("production", "x" * 40)) == 40
