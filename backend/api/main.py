"""Kazi-Kasi API.

Run locally with ``uvicorn backend.api.main:app --host 0.0.0.0 --port 8001``.
The database and signing key are supplied through environment variables in
production; development gets a local database and an ephemeral signing key.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import sys
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kazikasi import db, graph, profile, ranking  # noqa: E402

APP_ENV = os.getenv("APP_ENV", "development").lower()
DB_PATH = os.getenv("KAZIKASI_DB_PATH", str(ROOT / "kazi.db"))
TOKEN_TTL_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
if not 5 <= TOKEN_TTL_MINUTES <= 1440:
    raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be between 5 and 1440")
if APP_ENV == "production" and not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL must be configured in production")


def load_secret_key(app_env: str, configured: str | None) -> str:
    key = configured or ""
    if not key:
        if app_env == "production":
            raise RuntimeError("KAZIKASI_SECRET_KEY must be configured in production")
        key = secrets.token_urlsafe(48)
        warnings.warn("KAZIKASI_SECRET_KEY unset; using an ephemeral development key", RuntimeWarning)
    if len(key) < 32:
        raise RuntimeError("KAZIKASI_SECRET_KEY must contain at least 32 characters")
    return key


SECRET_KEY = load_secret_key(APP_ENV, os.getenv("KAZIKASI_SECRET_KEY"))

ALGORITHM = "HS256"
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def safe_source_url(value: str | None) -> str:
    """Only expose absolute web URLs, never javascript/data or malformed links."""
    if not value:
        return ""
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return value.strip()


app = FastAPI(title="Kazi-Kasi API", version="2.1.0")
cors_config = os.getenv("KAZIKASI_CORS_ORIGINS", "")
if APP_ENV == "production" and not cors_config.strip():
    raise RuntimeError("KAZIKASI_CORS_ORIGINS must be configured in production")
origins = [origin.strip() for origin in (
    cors_config or "http://localhost:3000,http://127.0.0.1:3000"
).split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=256)
    name: str = Field(min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.fullmatch(value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.fullmatch(value):
            raise ValueError("Enter a valid email address")
        return value


class ProfileUpdate(BaseModel):
    role_families: list[str] = Field(default_factory=list, max_length=20)
    home_county: str = Field(default="Nairobi", min_length=1, max_length=80)
    max_commute_km: float | None = Field(default=25.0, ge=0, le=500)
    min_monthly_pay: float | None = Field(default=None, ge=0, le=100_000_000)

    @field_validator("role_families")
    @classmethod
    def clean_families(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(v.strip().lower() for v in values if v.strip()))
        allowed = set(profile.ROLE_FAMILIES)
        invalid = set(cleaned) - allowed
        if invalid:
            raise ValueError(f"Unsupported role families: {', '.join(sorted(invalid))}")
        return cleaned


def get_db() -> Generator:
    database_url = os.getenv("DATABASE_URL")
    conn = db.connect(url=database_url) if database_url else db.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def hash_password(password: str) -> str:
    """PBKDF2-SHA256 password hash with a per-password random salt."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        parts = stored.split("$")
        if len(parts) == 4 and parts[0] == "pbkdf2_sha256":
            _, iterations, salt_hex, digest_hex = parts
            expected = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
            ).hex()
            return hmac.compare_digest(expected, digest_hex)
        # One-time compatibility with accounts created by the previous
        # salt + raw SHA-256 implementation. Successful login upgrades it.
        if len(parts) == 2 and len(parts[0]) == 32 and len(parts[1]) == 64:
            salt, digest = parts
            legacy = hashlib.sha256((salt + password).encode()).hexdigest()
            return hmac.compare_digest(legacy, digest)
    except (ValueError, TypeError):
        return False
    return False


def create_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": user_id, "iat": now, "exp": now + timedelta(minutes=TOKEN_TTL_MINUTES)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def get_current_user(authorization: str | None = Header(default=None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(parts[1], SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not isinstance(user_id, str) or not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"}) from exc


@app.get("/api/health")
def health(db_conn=Depends(get_db)):
    db_conn.execute("SELECT 1")
    return {"status": "ok", "version": app.version, "backend": "real"}


@app.post("/api/auth/register", status_code=201)
def register(user: UserCreate, db_conn=Depends(get_db)):
    existing = db_conn.execute(
        "SELECT id FROM accounts WHERE lower(email) = ? AND deleted_at IS NULL AND provider = 'password'",
        (user.email,),
    ).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = f"user_{secrets.token_urlsafe(16)}"
    now = datetime.now(timezone.utc).isoformat()
    try:
        db_conn.execute(
            """INSERT INTO accounts (id, kind, provider, email, name, password_hash,
               email_verified, created_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, "member", "password", user.email, user.name, hash_password(user.password), 0, now, now),
        )
        default_profile = profile.Profile(
            id=user_id, name=user.name, home_county="Nairobi", role_families=["it"],
            entry_fits=["open_to_freshers", "some_experience", "experienced"],
        )
        profile.save_profile(db_conn, default_profile)
        db_conn.commit()
    except sqlite3.IntegrityError as exc:
        db_conn.rollback()
        raise HTTPException(status_code=409, detail="Account could not be created") from exc
    return {"access_token": create_token(user_id), "token_type": "bearer"}


@app.post("/api/auth/login")
def login(data: LoginRequest, db_conn=Depends(get_db)):
    user = db_conn.execute(
        "SELECT id, email, name, password_hash FROM accounts WHERE email = ? AND deleted_at IS NULL",
        (data.email,),
    ).fetchone()
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    now = datetime.now(timezone.utc).isoformat()
    if user["password_hash"] and not user["password_hash"].startswith("pbkdf2_sha256$"):
        db_conn.execute("UPDATE accounts SET password_hash = ? WHERE id = ?", (hash_password(data.password), user["id"]))
    db_conn.execute("UPDATE accounts SET last_seen_at = ? WHERE id = ?", (now, user["id"]))
    db_conn.commit()
    return {
        "access_token": create_token(user["id"]), "token_type": "bearer",
        "user": {"id": user["id"], "email": user["email"], "name": user["name"]},
    }


@app.get("/api/auth/me")
def get_me(user_id: str = Depends(get_current_user), db_conn=Depends(get_db)):
    user = db_conn.execute(
        "SELECT id, email, name FROM accounts WHERE id = ? AND deleted_at IS NULL", (user_id,)
    ).fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists")
    return dict(user)


@app.get("/api/profile")
def get_profile(user_id: str = Depends(get_current_user), db_conn=Depends(get_db)):
    prof = profile.load_profile(db_conn, user_id)
    if not prof:
        user = db_conn.execute("SELECT name FROM accounts WHERE id = ? AND deleted_at IS NULL", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Account no longer exists")
        prof = profile.Profile(id=user_id, name=user["name"], home_county="Nairobi")
        profile.save_profile(db_conn, prof)
        db_conn.commit()
    return prof.to_dict()


@app.put("/api/profile")
def update_profile(update: ProfileUpdate, user_id: str = Depends(get_current_user), db_conn=Depends(get_db)):
    prof = profile.load_profile(db_conn, user_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    prof.role_families = update.role_families
    prof.home_county = update.home_county.strip()
    prof.max_commute_km = update.max_commute_km
    prof.min_monthly_pay = update.min_monthly_pay
    profile.save_profile(db_conn, prof)
    db_conn.commit()
    return prof.to_dict()


@app.get("/api/jobs")
def get_jobs(
    limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0, le=100_000),
    user_id: str = Depends(get_current_user), db_conn=Depends(get_db),
):
    prof = profile.load_profile(db_conn, user_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    total = db_conn.execute(
        "SELECT COUNT(*) AS count FROM jobs WHERE status = 'open' AND scam_flags = '[]'"
    ).fetchone()["count"]
    candidates = graph.feed(db_conn, limit=min(total, 5000))
    matches = ranking.rank(candidates, prof, limit=total)
    page = matches[offset:offset + limit]
    jobs = []
    for match in page:
        row = graph.job_row(db_conn, match.job_id)
        if not row:
            continue
        item = dict(row)
        jobs.append({
            "id": match.job_id, "title": match.title, "employer": match.employer,
            "location": f"{item.get('county') or 'Kenya'}, Kenya",
            "salary_min": item.get("pay_min"), "salary_max": item.get("pay_max"),
            "match_score": match.score, "match_reasons": match.reasons[:3],
            "deadline": item.get("deadline"), "posted": item.get("last_seen_at"),
            "url": safe_source_url(item.get("source_url")), "source_url": safe_source_url(item.get("source_url")),
            "description": item.get("description") or "",
        })
    return {"jobs": jobs, "total": total, "limit": limit, "offset": offset}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, user_id: str = Depends(get_current_user), db_conn=Depends(get_db)):
    prof = profile.load_profile(db_conn, user_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    row = graph.job_row(db_conn, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    item = dict(row)
    match = ranking.score_job(item, prof)
    return {
        "id": job_id, "title": match.title, "employer": match.employer,
        "location": f"{item.get('county') or 'Kenya'}, Kenya",
        "description": item.get("description") or "", "salary_min": item.get("pay_min"),
        "salary_max": item.get("pay_max"), "match_score": match.score,
        "match_reasons": match.reasons, "deadline": item.get("deadline"),
        "posted": item.get("last_seen_at"), "url": safe_source_url(item.get("source_url")),
        "source_url": safe_source_url(item.get("source_url")), "requirements": [], "benefits": [],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8001")), reload=APP_ENV != "production")
