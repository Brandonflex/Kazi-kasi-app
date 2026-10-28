"""
Kazi-Kasi v2 API - Real Backend with Kazi-Kasi modules
"""
import sys
sys.path.insert(0, '/home/user/Kazi-kasi-app/src')

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from jose import jwt, JWTError
import hashlib
import secrets
import sqlite3

from kazikasi import db, graph, ranking, profile

app = FastAPI(title="Kazi-Kasi API", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config
SECRET_KEY = "kazi-kasi-secret-key-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours
DB_PATH = "/home/user/Kazi-kasi-app/kazi.db"

# Database connection
def get_db():
    conn = db.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

# Models
class UserCreate(BaseModel):
    email: str
    password: str
    name: str

class LoginRequest(BaseModel):
    email: str
    password: str

class ProfileUpdate(BaseModel):
    role_families: list[str] = []
    home_county: str = "Nairobi"
    max_commute_km: float = 25.0
    min_monthly_pay: Optional[float] = None

# Password helpers
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hash_val = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${hash_val}"

def verify_password(password: str, hashed: str) -> bool:
    salt = hashed.split('$')[0]
    expected = hashlib.sha256((salt + password).encode()).hexdigest()
    actual = hashed.split('$')[1]
    return expected == actual

def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header")

# Public endpoints
@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0", "backend": "real"}

@app.post("/api/auth/register")
def register(user: UserCreate, db_conn: sqlite3.Connection = Depends(get_db)):
    # Check if user exists
    existing = db_conn.execute(
        "SELECT id FROM accounts WHERE email = ?", (user.email,)
    ).fetchone()
    
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user_id = f"user_{secrets.token_hex(8)}"
    password_hash = hash_password(user.password)
    now = datetime.utcnow().isoformat()
    
    db_conn.execute(
        """INSERT INTO accounts (id, kind, provider, email, name, password_hash, 
           email_verified, created_at, last_seen_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, "member", "password", user.email, user.name, password_hash, 
         1, now, now)
    )
    
    # Create default profile
    default_profile = profile.Profile(
        id=user_id,
        name=user.name,
        home_county="Nairobi",
        role_families=["it"],
        entry_fits=["open_to_freshers", "some_experience", "experienced"]
    )
    profile.save_profile(db_conn, default_profile)
    
    db_conn.commit()
    
    return {"access_token": create_token(user_id), "token_type": "bearer"}

@app.post("/api/auth/login")
def login(data: LoginRequest, db_conn: sqlite3.Connection = Depends(get_db)):
    user = db_conn.execute(
        "SELECT id, email, name, password_hash FROM accounts WHERE email = ?",
        (data.email,)
    ).fetchone()
    
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {
        "access_token": create_token(user["id"]),
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"]
        }
    }

# Protected endpoints
@app.get("/api/auth/me")
def get_me(
    user_id: str = Depends(get_current_user),
    db_conn: sqlite3.Connection = Depends(get_db)
):
    user = db_conn.execute(
        "SELECT id, email, name FROM accounts WHERE id = ?", (user_id,)
    ).fetchone()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"]
    }

@app.get("/api/profile")
def get_profile(
    user_id: str = Depends(get_current_user),
    db_conn: sqlite3.Connection = Depends(get_db)
):
    prof = profile.load_profile(db_conn, user_id)
    if not prof:
        # Create default profile if it doesn't exist
        user = db_conn.execute(
            "SELECT name FROM accounts WHERE id = ?", (user_id,)
        ).fetchone()
        prof = profile.Profile(
            id=user_id,
            name=user["name"] if user else "User",
            home_county="Nairobi"
        )
        profile.save_profile(db_conn, prof)
    
    return prof.to_dict()

@app.put("/api/profile")
def update_profile(
    update: ProfileUpdate,
    user_id: str = Depends(get_current_user),
    db_conn: sqlite3.Connection = Depends(get_db)
):
    prof = profile.load_profile(db_conn, user_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Update fields
    prof.role_families = update.role_families
    prof.home_county = update.home_county
    prof.max_commute_km = update.max_commute_km
    prof.min_monthly_pay = update.min_monthly_pay
    
    profile.save_profile(db_conn, prof)
    db_conn.commit()
    
    return prof.to_dict()

@app.get("/api/jobs")
def get_jobs(
    limit: int = 20,
    offset: int = 0,
    user_id: str = Depends(get_current_user),
    db_conn: sqlite3.Connection = Depends(get_db)
):
    """Get ranked jobs for the user"""
    # Load user profile
    prof = profile.load_profile(db_conn, user_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Get all jobs from the feed
    all_jobs = graph.feed(db_conn, limit=1000)
    
    # Rank jobs using the real ranking module
    matches = ranking.rank(all_jobs, prof, limit=limit + offset)
    
    # Apply pagination
    matches = matches[offset:offset + limit]
    
    # Format response
    jobs = []
    for match in matches:
        job_data = match.to_dict()
        
        # Get full job details
        job_row = graph.job_row(db_conn, match.job_id)
        if job_row:
            # Convert sqlite3.Row to dict
            row_dict = dict(job_row)
            job_data.update({
                "id": match.job_id,
                "title": match.title,
                "employer": match.employer,
                "location": f"{row_dict.get('county', 'Unknown')}, Kenya",
                "salary_min": row_dict.get('pay_min'),
                "salary_max": row_dict.get('pay_max'),
                "match_score": match.score,
                "match_reasons": match.reasons[:3],
                "deadline": row_dict.get('deadline'),
                "posted": "Recently",
                "source_url": row_dict.get('source_url', ''),
                "description": row_dict.get('description', ''),
            })
            jobs.append(job_data)
    
    return {
        "jobs": jobs,
        "total": len(matches),
        "limit": limit,
        "offset": offset
    }

@app.get("/api/jobs/{job_id}")
def get_job(
    job_id: str,
    user_id: str = Depends(get_current_user),
    db_conn: sqlite3.Connection = Depends(get_db)
):
    """Get job details with match score"""
    # Load user profile
    prof = profile.load_profile(db_conn, user_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Get job
    job_row = graph.job_row(db_conn, job_id)
    if not job_row:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Convert sqlite3.Row to dict
    row_dict = dict(job_row)
    
    # Score the job
    match = ranking.score_job(row_dict, prof)
    
    return {
        "id": job_id,
        "title": match.title,
        "employer": match.employer,
        "location": f"{row_dict.get('county', 'Unknown')}, Kenya",
        "description": row_dict.get('description', ''),
        "salary_min": row_dict.get('pay_min'),
        "salary_max": row_dict.get('pay_max'),
        "match_score": match.score,
        "match_reasons": match.reasons,
        "deadline": row_dict.get('deadline'),
        "posted": "Recently",
        "source_url": row_dict.get('source_url', ''),
        "requirements": [],
        "benefits": []
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
