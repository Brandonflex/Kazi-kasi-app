"""
Kazi-Kasi v2 API
FastAPI backend with proper structure
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import sqlite3
from datetime import datetime

# Import working backend logic
import sys
sys.path.append('../../src')
from kazikasi import db, graph, ranking, profile

app = FastAPI(title="Kazi-Kasi API", version="2.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    """Get database connection"""
    return db.connect(":memory:")  # Will be configured properly

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0"}

@app.get("/api/jobs")
def get_jobs(
    limit: int = 20,
    offset: int = 0,
    county: Optional[str] = None,
    search: Optional[str] = None
):
    """Get job feed with match scores"""
    try:
        conn = get_db()
        
        # Get profile (demo for now)
        prof = profile.Profile(
            id="demo",
            name="Demo User",
            skills=["software", "engineering", "python"],
            experience_years=3
        )
        
        # Get jobs from graph
        jobs = graph.feed(conn, limit=100)
        
        # Rank jobs
        matches = ranking.rank(jobs, prof, limit=limit)
        
        return {
            "jobs": [
                {
                    "id": m.job_id,
                    "title": m.title,
                    "employer": m.employer,
                    "location": m.location,
                    "salary_min": m.salary_min,
                    "salary_max": m.salary_max,
                    "match_score": round(m.score, 2),
                    "match_reasons": m.reasons[:3],
                    "deadline": m.deadline,
                    "posted": m.posted,
                    "url": m.source_url
                }
                for m in matches
            ],
            "total": len(matches),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    """Get job details"""
    try:
        conn = get_db()
        row = graph.job_row(conn, job_id)
        
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return {
            "id": row["id"],
            "title": row["title"],
            "employer": row["employer_name"],
            "location": f"{row.get('sub_county', '')}, {row.get('county', '')}".strip(", "),
            "description": row.get("description", ""),
            "salary_min": row.get("salary_min"),
            "salary_max": row.get("salary_max"),
            "deadline": row.get("deadline"),
            "posted": row.get("posted"),
            "source_url": row.get("source_url"),
            "requirements": row.get("requirements", []),
            "benefits": row.get("benefits", [])
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
