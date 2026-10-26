"""The Job Verse - 3D spatial job search experience.

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
    max_jobs: int = 150,
) -> dict:
    """Prepare job data for 3D galaxy visualization.
    
    Returns:
        {
            "jobs": [...],
            "skills": [...],
            "nebulae": [...],
            "meta": {...}
        }
    """
    jobs = []
    skills_map = {}
    nebulae = {}
    
    # Color palette by industry
    industry_colors = {
        "tech": "#E9A23B",
        "finance": "#166E5C",
        "healthcare": "#C85C3E",
        "education": "#0C3B43",
        "other": "#8B90A4",
    }
    
    # Generate skill stars in a ring
    skill_ring_radius = 90
    for i, skill in enumerate(profile_skills[:25]):
        angle = (i / 25) * 2 * math.pi
        x = math.cos(angle) * skill_ring_radius
        z = math.sin(angle) * skill_ring_radius
        y = random.uniform(-25, 25)
        
        skill_id = f"skill-{i}"
        skills_map[skill_id] = {
            "id": skill_id,
            "name": skill,
            "position": [x, y, z],
            "connections": 0,
        }
    
    # Generate job orbs
    for i, match in enumerate(matches[:max_jobs]):
        match_score = match.score if hasattr(match, 'score') else 0.5
        row = match.row if hasattr(match, 'row') else {}
        
        # Position: inverse of match score
        distance = (1 - match_score) * 180 + random.uniform(-40, 40)
        angle = random.uniform(0, 2 * math.pi)
        elevation = random.uniform(-80, 80)
        
        x = math.cos(angle) * distance
        z = math.sin(angle) * distance
        y = elevation
        
        # Size based on salary or match
        salary_min = row.get("salary_min", 0) or 0
        size = 2.5 + (salary_min / 100000) if salary_min else 2.5 + (match_score * 3.5)
        size = max(1.8, min(size, 7))
        
        # Color by industry
        title_lower = (match.title or "").lower()
        if any(word in title_lower for word in ["software", "developer", "engineer", "tech", "data", "ai", "ml"]):
            color = industry_colors["tech"]
            industry = "tech"
        elif any(word in title_lower for word in ["finance", "account", "bank", "investment", "trading"]):
            color = industry_colors["finance"]
            industry = "finance"
        elif any(word in title_lower for word in ["health", "medical", "nurse", "doctor", "clinical"]):
            color = industry_colors["healthcare"]
            industry = "healthcare"
        elif any(word in title_lower for word in ["teach", "education", "trainer", "school", "university"]):
            color = industry_colors["education"]
            industry = "education"
        else:
            color = industry_colors["other"]
            industry = "other"
        
        # Create nebula
        if industry not in nebulae:
            nebulae[industry] = {
                "id": f"nebula-{industry}",
                "name": industry.title(),
                "position": [0, 0, 0],
                "color": color,
                "jobs": [],
                "job_count": 0,
            }
        nebulae[industry]["jobs"].append(match.job_id)
        nebulae[industry]["job_count"] += 1
        
        # Extract skills
        job_skills = []
        title_words = (match.title or "").lower().split()
        for word in title_words:
            if len(word) > 4 and word not in {"manager", "assistant", "coordinator", "specialist"}:
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
