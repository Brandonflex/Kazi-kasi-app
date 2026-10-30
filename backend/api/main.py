"""Kazi-Kasi API.

Run locally with ``uvicorn backend.api.main:app --host 0.0.0.0 --port 8001``.
The database and signing key are supplied through environment variables in
production; development gets a local database and an ephemeral signing key.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import sys
import warnings
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kazikasi import accounts, autofill, db, documents, graph, profile, ranking, sweep  # noqa: E402
from kazikasi.models import EMPLOYMENT_TYPES, ENTRY_FIT, WORK_MODES  # noqa: E402

logger = logging.getLogger("kazikasi.api")

def _is_managed_runtime(environ: dict[str, str] | None = None) -> bool:
    """Detect common serverless/container platforms when APP_ENV was omitted."""
    env = environ if environ is not None else os.environ
    markers = (
        "VERCEL", "AWS_LAMBDA_FUNCTION_NAME", "K_SERVICE", "RENDER_SERVICE_ID",
        "RAILWAY_ENVIRONMENT", "FLY_APP_NAME", "DYNO",
    )
    return any(env.get(marker) for marker in markers)


def _runtime_app_env(environ: dict[str, str] | None = None) -> str:
    env = environ if environ is not None else os.environ
    # Never let an explicit development setting silently weaken persistence or
    # signing-key requirements on a managed deployment.
    if _is_managed_runtime(env):
        return "production"
    return (env.get("APP_ENV") or "development").lower()


MANAGED_RUNTIME = _is_managed_runtime()
APP_ENV = _runtime_app_env()
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


def _sync_sources_once() -> None:
    """Run a bounded, idempotent source refresh against the configured database."""
    database_url = os.getenv("DATABASE_URL")
    conn = db.connect(url=database_url) if database_url else db.connect(DB_PATH)
    try:
        report = sweep.run_sweep(conn, timeout=20.0, limit=10)
        logger.info("source sweep completed: %s", report["totals"])
    finally:
        conn.close()


async def _source_refresh_loop() -> None:
    try:
        interval = max(3600, int(os.getenv("KAZIKASI_SOURCE_SYNC_INTERVAL_SECONDS", "21600")))
    except ValueError:
        logger.warning("invalid KAZIKASI_SOURCE_SYNC_INTERVAL_SECONDS; using six hours")
        interval = 21600
    while True:
        try:
            await asyncio.to_thread(_sync_sources_once)
        except Exception:
            logger.exception("background source refresh failed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(_: FastAPI):
    enabled = APP_ENV == "production" and os.getenv("KAZIKASI_AUTO_SYNC", "true").lower() not in {"0", "false", "no"}
    task = asyncio.create_task(_source_refresh_loop()) if enabled else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Kazi-Kasi API", version="2.2.0", lifespan=lifespan)
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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role_families: list[str] | None = Field(default=None, max_length=20)
    skills: list[str] | None = Field(default=None, max_length=40)
    home_county: str | None = Field(default=None, max_length=80)
    home_area: str | None = Field(default=None, max_length=120)
    max_commute_km: float | None = Field(default=None, ge=0, le=500)
    min_monthly_pay: float | None = Field(default=None, ge=0, le=100_000_000)
    entry_fits: list[str] | None = Field(default=None, max_length=4)
    employment_types: list[str] | None = Field(default=None, max_length=8)
    work_modes: list[str] | None = Field(default=None, max_length=4)
    deadline_within_days: int | None = Field(default=None, ge=1, le=365)
    include_remote: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned

    @field_validator("home_county", "home_area")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("role_families")
    @classmethod
    def clean_families(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        cleaned = list(dict.fromkeys(v.strip().lower() for v in values if v.strip()))
        invalid = set(cleaned) - set(profile.ROLE_FAMILIES)
        if invalid:
            raise ValueError(f"Unsupported role families: {', '.join(sorted(invalid))}")
        return cleaned

    @field_validator("skills")
    @classmethod
    def clean_skills(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        cleaned = list(dict.fromkeys(" ".join(v.split()) for v in values if v.strip()))
        if any(len(skill) > 50 for skill in cleaned):
            raise ValueError("Each skill must be 50 characters or fewer")
        return cleaned

    @field_validator("entry_fits")
    @classmethod
    def clean_entry_fits(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        invalid = set(values) - ENTRY_FIT
        if invalid:
            raise ValueError(f"Unsupported experience levels: {', '.join(sorted(invalid))}")
        return list(dict.fromkeys(values))

    @field_validator("employment_types")
    @classmethod
    def clean_employment_types(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        invalid = set(values) - EMPLOYMENT_TYPES
        if invalid:
            raise ValueError(f"Unsupported employment types: {', '.join(sorted(invalid))}")
        return list(dict.fromkeys(values))

    @field_validator("work_modes")
    @classmethod
    def clean_work_modes(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        invalid = set(values) - WORK_MODES
        if invalid:
            raise ValueError(f"Unsupported work modes: {', '.join(sorted(invalid))}")
        return list(dict.fromkeys(values))



def get_db() -> Generator:
    database_url = os.getenv("DATABASE_URL")
    conn = db.connect(url=database_url, check_same_thread=False) if database_url else db.connect(DB_PATH, check_same_thread=False)
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


@app.get("/api/sources")
def get_sources(db_conn=Depends(get_db)):
    """Public source catalog and ingestion freshness, with no internal errors exposed."""
    sweep.add_source_health_schema(db_conn)
    health_rows = db_conn.execute(
        "SELECT source_id, last_seen_at, status FROM source_health"
    ).fetchall()
    health = {row["source_id"]: dict(row) for row in health_rows}
    job_rows = db_conn.execute(
        """SELECT o.source_id, COUNT(DISTINCT m.job_id) AS jobs
           FROM observations o LEFT JOIN job_members m ON m.observation_id = o.id
           GROUP BY o.source_id"""
    ).fetchall()
    job_counts = {row["source_id"]: row["jobs"] for row in job_rows}

    from kazikasi.sources import REGISTRY

    sources = []
    for source_id, adapter_class in sorted(REGISTRY.items()):
        manifest = adapter_class.manifest
        state = health.get(source_id, {})
        configured = not (source_id == "reliefweb" and not os.getenv("RELIEFWEB_APPNAME"))
        sources.append({
            "id": manifest.id,
            "label": manifest.label,
            "listing_url": manifest.listing_urls[0] if manifest.listing_urls else None,
            "access": manifest.access,
            "tier": manifest.tier,
            "cadence_minutes": manifest.cadence_minutes,
            "status": manifest.status if configured else "needs_configuration",
            "last_sync_at": state.get("last_seen_at"),
            "health": state.get("status", "not_synced"),
            "jobs_seen": job_counts.get(source_id, 0),
        })
    return {"sources": sources, "active": sum(s["status"] == "active" for s in sources)}


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
    for field_name in update.model_fields_set:
        value = getattr(update, field_name)
        if value is not None or field_name in {"home_county", "home_area", "max_commute_km", "min_monthly_pay", "deadline_within_days"}:
            if field_name == "name":
                prof.name = value
            elif field_name in profile.Profile.__dataclass_fields__:
                setattr(prof, field_name, value)
    profile.save_profile(db_conn, prof)
    if "name" in update.model_fields_set and update.name:
        db_conn.execute("UPDATE accounts SET name = ? WHERE id = ?", (update.name, user_id))
        db_conn.commit()
    return prof.to_dict()


MAX_CV_BYTES = 5 * 1024 * 1024


def _cv_public_data(cv: dict | None) -> dict | None:
    if not cv:
        return None
    return {
        "id": cv["id"],
        "filename": cv.get("filename"),
        "chars": cv.get("chars", 0),
        "created_at": cv.get("created_at"),
        "fields": cv.get("fields", {}),
    }


@app.get("/api/profile/cv")
def get_profile_cv(user_id: str = Depends(get_current_user), db_conn=Depends(get_db)):
    return {"cv": _cv_public_data(accounts.latest_cv(db_conn, user_id))}


@app.post("/api/profile/cv")
async def upload_profile_cv(file: UploadFile = File(...), user_id: str = Depends(get_current_user), db_conn=Depends(get_db)):
    filename = (file.filename or "resume.pdf").replace("\\", "/").rsplit("/", 1)[-1][:200]
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Upload a PDF file")
    raw = await file.read(MAX_CV_BYTES + 1)
    if len(raw) > MAX_CV_BYTES:
        raise HTTPException(status_code=413, detail="The PDF must be 5 MB or smaller")
    if not raw.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="This file is not a readable PDF")
    try:
        text = documents.bytes_to_text(raw, "application/pdf")
    except documents.DocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    fields = autofill.parse(text)
    cv_id = accounts.store_cv(db_conn, user_id, filename=filename, text=text, fields=fields)
    prof = profile.load_profile(db_conn, user_id)
    if prof:
        extracted_skills = ((fields.get("skills") or {}).get("value") or [])
        if extracted_skills:
            prof.skills = list(dict.fromkeys(extracted_skills))[:40]
            profile.save_profile(db_conn, prof)
    stored = accounts.latest_cv(db_conn, user_id)
    return {
        "cv": _cv_public_data(stored),
        "suggestions": autofill.profile_suggestions(fields),
        "profile": prof.to_dict() if prof else None,
        "message": "CV processed. Check the extracted details and adjust your profile before relying on the matches.",
    }


@app.delete("/api/profile/cv")
def delete_profile_cv(user_id: str = Depends(get_current_user), db_conn=Depends(get_db)):
    cv = accounts.latest_cv(db_conn, user_id)
    if cv:
        db_conn.execute("DELETE FROM cvs WHERE id = ? AND account_id = ?", (cv["id"], user_id))
        db_conn.commit()
    return {"cv": _cv_public_data(accounts.latest_cv(db_conn, user_id)), "deleted": bool(cv)}



def _decode_evidence(row) -> dict:
    try:
        payload = row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"] or "{}")
    except (TypeError, json.JSONDecodeError):
        payload = {}
    payload.setdefault("source_url", row["source_url"])
    return payload


def _job_evidence(db_conn, job_id: str) -> dict:
    placeholder = "%s" if type(db_conn).__name__ == "Connection" and hasattr(db_conn, "info") else "?"
    row = db_conn.execute(
        f"""SELECT o.source_url, o.payload
            FROM job_members m JOIN observations o ON o.id = m.observation_id
            WHERE m.job_id = {placeholder} ORDER BY o.fetched_at DESC LIMIT 1""",
        (job_id,),
    ).fetchone()
    return _decode_evidence(row) if row else {}


def _job_evidence_map(db_conn, job_ids: list[str]) -> dict[str, dict]:
    """Load latest source payloads in bounded batches for skill-aware ranking."""
    evidence: dict[str, dict] = {}
    placeholder = "%s" if type(db_conn).__name__ == "Connection" and hasattr(db_conn, "info") else "?"
    for start in range(0, len(job_ids), 400):
        batch = job_ids[start:start + 400]
        marks = ",".join([placeholder] * len(batch))
        rows = db_conn.execute(
            f"""SELECT m.job_id, o.source_url, o.payload, o.fetched_at
                FROM job_members m JOIN observations o ON o.id = m.observation_id
                WHERE m.job_id IN ({marks}) ORDER BY o.fetched_at DESC""",
            tuple(batch),
        ).fetchall()
        for row in rows:
            evidence.setdefault(row["job_id"], _decode_evidence(row))
    return evidence


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
    evidence_by_id = _job_evidence_map(db_conn, [candidate["id"] for candidate in candidates])
    for candidate in candidates:
        candidate["description"] = evidence_by_id.get(candidate["id"], {}).get("description_md", "")
    matches = ranking.rank(candidates, prof, limit=total)
    page = matches[offset:offset + limit]
    jobs = []
    for match in page:
        row = graph.job_row(db_conn, match.job_id)
        if not row:
            continue
        item = dict(row)
        evidence = evidence_by_id.get(match.job_id, {})
        county = item.get("county")
        location = f"{county}, Kenya" if county and county.lower() != "kenya" else "Kenya"
        source_url = safe_source_url(evidence.get("source_url"))
        apply_url = safe_source_url(evidence.get("apply_url") or evidence.get("source_url"))
        jobs.append({
            "id": match.job_id, "title": match.title, "employer": match.employer,
            "location": location,
            "salary_min": item.get("pay_min"), "salary_max": item.get("pay_max"),
            "match_score": match.score, "match_reasons": match.reasons[:3],
            "deadline": item.get("deadline"),
            "posted": evidence.get("date_posted_claimed") or item.get("last_seen_at"),
            "url": apply_url, "source_url": source_url,
            "description": evidence.get("description_md") or "",
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
    evidence = _job_evidence(db_conn, job_id)
    item["description"] = evidence.get("description_md", "")
    match = ranking.score_job(item, prof)
    county = item.get("county")
    location = f"{county}, Kenya" if county and county.lower() != "kenya" else "Kenya"
    source_url = safe_source_url(evidence.get("source_url"))
    return {
        "id": job_id, "title": match.title, "employer": match.employer,
        "location": location,
        "description": evidence.get("description_md") or "", "salary_min": item.get("pay_min"),
        "salary_max": item.get("pay_max"), "match_score": match.score,
        "match_reasons": match.reasons, "deadline": item.get("deadline"),
        "posted": evidence.get("date_posted_claimed") or item.get("last_seen_at"),
        "url": safe_source_url(evidence.get("apply_url") or evidence.get("source_url")),
        "source_url": source_url, "requirements": [], "benefits": [],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8001")), reload=APP_ENV != "production")
