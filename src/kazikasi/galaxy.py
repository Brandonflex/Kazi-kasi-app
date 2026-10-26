"""The Job Verse — 3D spatial job search experience.

This is not a feed. This is a universe.
Jobs are celestial bodies. Skills are stars. You navigate by warping through space.
"""

from __future__ import annotations

import json
import math
import random
from datetime import datetime, timezone
from typing import Optional


def prepare_galaxy_data(
    matches: list,
    profile_skills: list[str],
    *,
    max_jobs: int = 50,
) -> dict:
    """Prepare job data for 3D galaxy visualization.
    
    Returns:
        {
            "jobs": [
                {
                    "id": "...",
                    "title": "...",
                    "employer": "...",
                    "position": [x, y, z],  # 3D position
                    "size": 1.5,  # based on salary/match
                    "color": "#E9A23B",  # based on industry
                    "match_score": 0.85,
                    "salary": "...",
                    "deadline": "...",
                    "skills": ["python", "remote"],
                    "connections": ["skill-id-1", "skill-id-2"]
                },
                ...
            ],
            "skills": [
                {
                    "id": "...",
                    "name": "Python",
                    "position": [x, y, z],
                    "connections": 12
                },
                ...
            ],
            "nebulae": [
                {
                    "id": "...",
                    "name": "Tech",
                    "position": [x, y, z],
                    "color": "#166E5C",
                    "jobs": ["job-id-1", "job-id-2"]
                },
                ...
            ]
        }
    """
    jobs = []
    skills_map = {}
    nebulae = {}
    
    # Color palette by industry
    industry_colors = {
        "tech": "#E9A23B",      # Ember Gold
        "finance": "#166E5C",    # Safari Green
        "healthcare": "#C85C3E", # Rift Clay
        "education": "#0C3B43",  # Nairobi Dark
        "other": "#8B90A4",      # Slate
    }
    
    # Generate skill stars in a ring around the center
    skill_ring_radius = 80
    for i, skill in enumerate(profile_skills[:20]):
        angle = (i / 20) * 2 * math.pi
        x = math.cos(angle) * skill_ring_radius
        z = math.sin(angle) * skill_ring_radius
        y = random.uniform(-20, 20)
        
        skill_id = f"skill-{i}"
        skills_map[skill_id] = {
            "id": skill_id,
            "name": skill,
            "position": [x, y, z],
            "connections": 0,
        }
    
    # Generate job orbs in 3D space
    # Higher match = closer to center
    # Salary = size
    # Industry = color
    for i, match in enumerate(matches[:max_jobs]):
        match_score = match.score if hasattr(match, 'score') else 0.5
        row = match.row if hasattr(match, 'row') else {}
        
        # Position: inverse of match score (higher match = closer to center)
        distance = (1 - match_score) * 150 + random.uniform(-30, 30)
        angle = random.uniform(0, 2 * math.pi)
        elevation = random.uniform(-60, 60)
        
        x = math.cos(angle) * distance
        z = math.sin(angle) * distance
        y = elevation
        
        # Size based on salary or default
        salary_min = row.get("salary_min", 0) or 0
        size = 2 + (salary_min / 100000) if salary_min else 2 + (match_score * 3)
        size = max(1.5, min(size, 6))
        
        # Color by industry (simplified)
        title_lower = (match.title or "").lower()
        if any(word in title_lower for word in ["software", "developer", "engineer", "tech"]):
            color = industry_colors["tech"]
            industry = "tech"
        elif any(word in title_lower for word in ["finance", "account", "bank"]):
            color = industry_colors["finance"]
            industry = "finance"
        elif any(word in title_lower for word in ["health", "medical", "nurse", "doctor"]):
            color = industry_colors["healthcare"]
            industry = "healthcare"
        elif any(word in title_lower for word in ["teach", "education", "trainer"]):
            color = industry_colors["education"]
            industry = "education"
        else:
            color = industry_colors["other"]
            industry = "other"
        
        # Create nebula if doesn't exist
        if industry not in nebulae:
            nebulae[industry] = {
                "id": f"nebula-{industry}",
                "name": industry.title(),
                "position": [0, 0, 0],  # Will calculate centroid later
                "color": color,
                "jobs": [],
                "job_count": 0,
            }
        nebulae[industry]["jobs"].append(match.job_id)
        nebulae[industry]["job_count"] += 1
        
        # Extract skills from job
        job_skills = []
        title_words = (match.title or "").lower().split()
        for word in title_words:
            if len(word) > 4 and word not in {"manager", "assistant", "coordinator"}:
                job_skills.append(word)
        
        # Find matching skills
        connections = []
        for skill_id, skill_data in skills_map.items():
            if skill_data["name"].lower() in title_lower:
                connections.append(skill_id)
                skills_map[skill_id]["connections"] += 1
        
        jobs.append({
            "id": match.job_id,
            "title": match.title,
            "employer": match.employer,
            "position": [x, y, z],
            "size": size,
            "color": color,
            "match_score": match_score,
            "salary": row.get("salary_min") or row.get("salary_max") or None,
            "deadline": row.get("deadline") or None,
            "industry": industry,
            "connections": connections,
        })
    
    # Calculate nebula centroids
    for industry, nebula in nebulae.items():
        if nebula["job_count"] > 0:
            job_positions = [j["position"] for j in jobs if j["industry"] == industry]
            centroid = [
                sum(p[0] for p in job_positions) / len(job_positions),
                sum(p[1] for p in job_positions) / len(job_positions),
                sum(p[2] for p in job_positions) / len(job_positions),
            ]
            nebula["position"] = centroid
    
    return {
        "jobs": jobs,
        "skills": list(skills_map.values()),
        "nebulae": list(nebulae.values()),
        "meta": {
            "total_jobs": len(jobs),
            "total_skills": len(skills_map),
            "total_nebulae": len(nebulae),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def generate_autopilot_scan(
    conn,
    profile_id: str,
    *,
    now: Optional[datetime] = None,
) -> dict:
    """Simulate autopilot daily scan results.
    
    In production, this would query job sources and find new matches.
    For demo, returns synthetic results.
    """
    now = now or datetime.now(timezone.utc)
    
    # Get existing matches
    from . import graph, profile as profile_module
    
    prof = profile_module.load(conn, profile_id)
    if prof is None:
        return {"new_jobs": [], "scan_time": now.isoformat()}
    
    matches, _ = _ranked(conn, prof, now=now, limit=20)
    
    new_jobs = []
    for match in matches[:5]:  # Top 5 new matches
        row = match.row or {}
        new_jobs.append({
            "id": match.job_id,
            "title": match.title,
            "employer": match.employer,
            "match_score": match.score,
            "reason": match.reasons[0] if match.reasons else "Strong match",
            "salary": row.get("salary_min"),
        })
    
    return {
        "new_jobs": new_jobs,
        "scan_time": now.isoformat(),
        "total_scanned": 234,
        "new_matches": len(new_jobs),
    }


def _ranked(conn, profile, *, now, limit=40):
    """Import from serve module to avoid circular import."""
    # This is a simplified version; in production, import from serve
    from . import graph
    
    matches = []
    rows = conn.execute(
        "SELECT * FROM jobs WHERE status = 'live' ORDER BY first_seen_at DESC LIMIT ?",
        (limit * 2,),
    ).fetchall()
    
    for row in rows[:limit]:
        match = type('Match', (), {
            'job_id': row['id'],
            'title': row['title'],
            'employer': row['employer'],
            'score': 0.7,  # Simplified
            'reasons': ['matches profile'],
            'row': dict(row),
        })()
        matches.append(match)
    
    return matches, set()
