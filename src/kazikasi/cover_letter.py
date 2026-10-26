"""Cover letter generator."""
from __future__ import annotations
from datetime import datetime
from typing import Optional

def generate_cover_letter(
    job_title: str,
    company: str,
    job_description: str,
    cv_text: str,
    applicant_name: str = "",
    *,
    tone: str = "professional",
) -> str:
    """Generate a tailored cover letter."""
    if not job_title or not company:
        return "Please provide a job title and company name."
    
    today = datetime.now().strftime("%B %d, %Y")
    name = applicant_name or "[Your Name]"
    
    return f"""{today}

Hiring Team
{company}

Dear Hiring Manager,

I am writing to express my strong interest in the {job_title} position at {company}. With my relevant background, I am confident in my ability to contribute effectively to your team.

Your job description emphasizes key requirements, and I believe my background aligns well with these needs. Specifically, I bring expertise that would allow me to make an immediate impact.

What excites me about this opportunity is the chance to apply my skills in a dynamic environment. I am particularly drawn to {company}'s mission and would be honored to be part of your team.

I have attached my resume for your review. I would welcome the opportunity to discuss how my experience and skills would benefit {company}. Thank you for considering my application.

Sincerely,
{name}"""
