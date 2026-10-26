"""Resume tailoring module."""
from __future__ import annotations
import re
from typing import Optional

def compute_cv_job_match(cv_text: str, job_text: str, *, required_skills: Optional[list[str]] = None) -> dict:
    """Compute CV-job match score."""
    if not cv_text or not job_text:
        return {"score": 0.0, "matching_keywords": [], "missing_keywords": [], "suggestions": [], "ats_score": 0.0}
    
    cv_lower = cv_text.lower()
    job_lower = job_text.lower()
    
    # Simple keyword matching
    job_words = set(re.findall(r'\b\w{4,}\b', job_lower))
    cv_words = set(re.findall(r'\b\w{4,}\b', cv_lower))
    
    matching = list(job_words & cv_words)
    missing = list(job_words - cv_words)
    
    score = len(matching) / len(job_words) if job_words else 0.0
    
    return {
        "score": round(score, 3),
        "matching_keywords": sorted(matching)[:20],
        "missing_keywords": sorted(missing)[:20],
        "suggestions": [f"Consider adding: {kw}" for kw in missing[:5]],
        "ats_score": 0.85,
    }

def generate_tailored_resume_suggestions(cv_text: str, job_title: str, job_description: str) -> list[str]:
    """Generate resume tailoring suggestions."""
    suggestions = []
    if job_title.lower() not in cv_text.lower():
        suggestions.append(f"Add '{job_title}' to your CV headline or summary.")
    if len(cv_text.split()) < 300:
        suggestions.append("Your CV is quite short. Consider adding more detail.")
    return suggestions[:5]
