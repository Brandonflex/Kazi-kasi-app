"""
Kazi-Kasi v2 API - Clean Simple Version
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from jose import jwt
import hashlib
import secrets

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

# Mock data
MOCK_JOBS = [
    {
        "id": "1",
        "title": "Senior Software Engineer",
        "employer": "Safaricom PLC",
        "location": "Nairobi, Kenya",
        "salary_min": 250000,
        "salary_max": 350000,
        "match_score": 0.94,
        "match_reasons": ["Python, FastAPI", "Cloud infrastructure"],
        "deadline": "2024-02-15",
        "posted": "2 days ago",
        "source_url": "https://careers.safaricom.co.ke",
        "description": "Senior Software Engineer role at Safaricom.",
        "requirements": ["5+ years backend", "Python/FastAPI", "Cloud"],
        "benefits": ["Competitive salary", "Health insurance", "Flexible work"]
    },
    {
        "id": "2",
        "title": "Full Stack Developer",
        "employer": "Andela",
        "location": "Remote - Kenya",
        "salary_min": 180000,
        "salary_max": 280000,
        "match_score": 0.89,
        "match_reasons": ["Full stack", "React/Node.js"],
        "deadline": "2024-02-20",
        "posted": "5 days ago",
        "source_url": "https://andela.com/careers",
        "description": "Full stack developer role at Andela.",
        "requirements": ["3+ years full stack", "React", "Node.js"],
        "benefits": ["Remote work", "Learning budget", "Equity"]
    },
    {
        "id": "3",
        "title": "Backend Engineer",
        "employer": "Cellulant",
        "location": "Nairobi, Kenya",
        "salary_min": 200000,
        "salary_max": 300000,
        "match_score": 0.87,
        "match_reasons": ["API development", "Database"],
        "deadline": "2024-02-18",
        "posted": "1 day ago",
        "source_url": "https://www.cellulant.com/careers",
        "description": "Backend engineer at Cellulant.",
        "requirements": ["Backend", "PostgreSQL", "APIs"],
        "benefits": ["Salary", "Health", "Growth"]
    }
]

USERS_DB = {}

# Models
class UserCreate(BaseModel):
    email: str
    password: str
    name: str

class LoginRequest(BaseModel):
    email: str
    password: str

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

# Public endpoints
@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0"}

@app.post("/api/auth/register")
def register(user: UserCreate):
    if any(u["email"] == user.email for u in USERS_DB.values()):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = f"user_{len(USERS_DB) + 1}"
    USERS_DB[user_id] = {
        "id": user_id,
        "email": user.email,
        "name": user.name,
        "password_hash": hash_password(user.password)
    }
    
    return {"access_token": create_token(user_id), "token_type": "bearer"}

@app.post("/api/auth/login")
def login(data: LoginRequest):
    user = next((u for u in USERS_DB.values() if u["email"] == data.email), None)
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {"access_token": create_token(user["id"]), "token_type": "bearer"}

@app.get("/api/jobs")
def get_jobs(limit: int = 20, offset: int = 0):
    return {
        "jobs": MOCK_JOBS[:limit],
        "total": len(MOCK_JOBS),
        "limit": limit,
        "offset": offset
    }

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = next((j for j in MOCK_JOBS if j["id"] == job_id), None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
