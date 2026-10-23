"""
Kazi Kasi Feature Enhancements — Research-Driven Improvements

Based on analysis of top job platforms:
- Indeed (61% market share): 1-click apply, salary transparency
- LinkedIn (13%): Profile-based matching, networking
- ZipRecruiter (6%): Fast applying, AI matching
- Glassdoor (4%): Salary data, company insights
"""

from datetime import datetime, timezone
from typing import Optional


def format_salary(min_salary: Optional[int], max_salary: Optional[int], currency: str = "KES") -> str:
    """Format salary range for display.
    
    Inspired by Indeed's salary transparency (400M visits, 61% market share).
    """
    if not min_salary and not max_salary:
        return ""
    
    def format_number(n):
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n/1_000:.0f}K"
        return str(n)
    
    if min_salary and max_salary:
        return f"{currency} {format_number(min_salary)} – {format_number(max_salary)}"
    elif min_salary:
        return f"From {currency} {format_number(min_salary)}"
    elif max_salary:
        return f"Up to {currency} {format_number(max_salary)}"
    return ""


def quick_apply_badge(has_cv: bool) -> str:
    """Generate quick apply badge HTML.
    
    Inspired by Indeed's 1-click apply and ZipRecruiter's fast applying.
    Reduces friction to absolute minimum.
    """
    if not has_cv:
        return ""
    
    return '''<span class="badge quick-apply-badge" title="Apply instantly with your saved CV">
        ⚡ Quick Apply
    </span>'''


def personalized_greeting(account: Optional[dict], cv_fields: dict) -> str:
    """Generate personalized greeting using Google profile data.
    
    Uses Google sign-in data (given_name, picture, email) to create
    tailored experience. Inspired by LinkedIn's profile-based personalization.
    """
    if not account:
        return "Welcome to Kazi Kasi"
    
    # Prefer given_name from Google profile
    given_name = account.get("given_name")
    if not given_name:
        # Fall back to first part of full name
        name = account.get("name", "")
        given_name = name.split()[0] if name else ""
    
    if given_name:
        return f"Hey {given_name}"
    
    return "Welcome back"


def profile_picture_html(account: Optional[dict], size: int = 32) -> str:
    """Generate profile picture HTML.
    
    Show Google profile picture in navigation and account page.
    """
    if not account or not account.get("picture"):
        return ""
    
    picture = account["picture"]
    return f'''<img src="{picture}" alt="Profile" 
                   style="width:{size}px;height:{size}px;border-radius:50%;
                          vertical-align:middle;margin-right:8px"
                   loading="lazy">'''


def job_card_enhancements(
    match,
    row: dict,
    account: Optional[dict],
    cv_fields: dict,
    source: Optional[dict],
    profile_id: str
) -> dict:
    """Generate enhanced job card data.
    
    Returns dict with:
    - salary_html: Salary range display
    - quick_apply_html: Quick apply button
    - match_score_html: Visual match score
    - trust_signals: Company trust indicators
    """
    enhancements = {
        "salary_html": "",
        "quick_apply_html": "",
        "match_score_html": "",
        "trust_signals": "",
    }
    
    # Salary transparency (from Indeed/Glassdoor)
    if row:
        salary_min = row.get("salary_min")
        salary_max = row.get("salary_max")
        salary_text = format_salary(salary_min, salary_max)
        if salary_text:
            enhancements["salary_html"] = f'<div class="salary">💰 {salary_text}</div>'
    
    # Quick apply (from Indeed/ZipRecruiter)
    if account and cv_fields:
        job_id = match.job_id if hasattr(match, 'job_id') else ""
        enhancements["quick_apply_html"] = f'''
            <button type="button" class="quick-apply-btn" 
                    data-job="{job_id}" 
                    title="Apply instantly with your saved CV">
                ⚡ Quick Apply
            </button>
        '''
    
    # Match score visualization
    if hasattr(match, 'score') and match.score:
        score = match.score
        score_color = "#6b8e7f" if score >= 0.8 else "#ff6b5b" if score >= 0.6 else "#2d3748"
        enhancements["match_score_html"] = f'''
            <div class="match-score" style="color:{score_color}" title="Match score: {score:.0%}">
                {score:.0%} match
            </div>
        '''
    
    return enhancements


def smart_search_suggestions(query: str, cv_fields: dict) -> list[dict]:
    """Generate smart search suggestions based on CV data.
    
    Inspired by LinkedIn's intelligent search and Jooble's clean UX.
    """
    suggestions = []
    
    if not cv_fields:
        return suggestions
    
    # Suggest based on extracted skills
    skills = cv_fields.get("skills", {})
    if skills and skills.get("value"):
        skill_list = skills["value"] if isinstance(skills["value"], list) else [skills["value"]]
        for skill in skill_list[:3]:
            suggestions.append({
                "text": skill,
                "type": "skill",
                "icon": "🛠️"
            })
    
    # Suggest based on location
    location = cv_fields.get("location", {})
    if location and location.get("value"):
        suggestions.append({
            "text": location["value"],
            "type": "location",
            "icon": "📍"
        })
    
    # Suggest based on experience level
    experience = cv_fields.get("experience", {})
    if experience and experience.get("value"):
        years = experience["value"]
        if years < 2:
            suggestions.append({"text": "Entry level", "type": "level", "icon": "🌱"})
        elif years < 5:
            suggestions.append({"text": "Mid-level", "type": "level", "icon": "📈"})
        else:
            suggestions.append({"text": "Senior", "type": "level", "icon": "⭐"})
    
    return suggestions[:5]  # Limit to 5 suggestions


def cv_parsing_progress(phase: str, progress: float) -> dict:
    """Generate CV parsing progress data.
    
    Inspired by modern CV parsers with real-time progress indication.
    
    Args:
        phase: Current parsing phase (uploading, extracting, analyzing, complete)
        progress: Progress percentage (0-100)
    
    Returns:
        Dict with progress HTML and status
    """
    phases = {
        "uploading": ("📤 Uploading your CV...", "#2d3748"),
        "extracting": ("🔍 Extracting text...", "#ff6b5b"),
        "analyzing": ("🧠 Analyzing content...", "#6b8e7f"),
        "complete": ("✓ Complete!", "#6b8e7f"),
        "error": ("✗ Error parsing CV", "#ff6b5b"),
    }
    
    message, color = phases.get(phase, ("Processing...", "#2d3748"))
    
    return {
        "html": f'''
            <div class="cv-progress">
                <div class="progress-bar" style="width:{progress}%;background:{color}"></div>
                <div class="progress-message">{message}</div>
            </div>
        ''',
        "phase": phase,
        "progress": progress,
    }


def confidence_badge(field_name: str, confidence: float) -> str:
    """Generate confidence badge for extracted CV fields.
    
    Shows user how confident we are in each extracted field.
    Inspired by best-in-class CV parsers with verification workflows.
    """
    if confidence >= 0.9:
        color = "#6b8e7f"
        label = "High confidence"
        icon = "✓"
    elif confidence >= 0.7:
        color = "#ff6b5b"
        label = "Medium confidence"
        icon = "~"
    else:
        color = "#2d3748"
        label = "Low confidence — please verify"
        icon = "?"
    
    return f'''
        <span class="confidence-badge" style="color:{color}" 
              title="{label}: {confidence:.0%} confident">
            {icon} {field_name}
        </span>
    '''


def mobile_optimized_card() -> str:
    """CSS for mobile-optimized job cards.
    
    Inspired by Hellowork (fastest growing, 29% YoY) and ZipRecruiter
    (81% mobile traffic). Mobile-first responsive design.
    """
    return '''
    @media (max-width: 768px) {
        .card {
            padding: 1rem;
            margin: 0.5rem 0;
        }
        .card h2 {
            font-size: 1.1rem;
            line-height: 1.3;
        }
        .employer {
            font-size: 0.95rem;
        }
        .badges {
            flex-wrap: wrap;
            gap: 0.25rem;
        }
        .salary {
            font-size: 0.9rem;
            margin: 0.5rem 0;
        }
        .quick-apply-btn {
            width: 100%;
            padding: 0.75rem;
            font-size: 1rem;
        }
        .match-score {
            font-size: 0.85rem;
        }
    }
    '''
