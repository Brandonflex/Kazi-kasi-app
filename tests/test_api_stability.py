"""Contract and security regressions for the product API."""
import os

os.environ.setdefault("KAZIKASI_SECRET_KEY", "test-only-signing-key-with-more-than-32-bytes")

from fastapi.testclient import TestClient

from backend.api import main


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
            "home_county": " Mombasa ",
            "max_commute_km": 40,
            "min_monthly_pay": 50000,
        })
        assert updated.status_code == 200
        assert updated.json()["role_families"] == ["it", "finance"]
        assert updated.json()["home_county"] == "Mombasa"

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
