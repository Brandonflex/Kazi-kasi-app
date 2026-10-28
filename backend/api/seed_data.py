"""Seed the database with sample jobs for testing"""
import sys
sys.path.insert(0, '/home/user/Kazi-kasi-app/src')

from datetime import date, timedelta
from kazikasi import db
from kazikasi.models import JobCandidate, JobPay
from kazikasi.graph import upsert_candidate

def seed_database(db_path="kazi.db"):
    """Create a database with sample jobs"""
    conn = db.connect(db_path)
    
    # Clear existing data
    conn.execute("DELETE FROM jobs")
    conn.execute("DELETE FROM observations")
    conn.commit()
    
    # Sample jobs
    jobs = [
        JobCandidate(
            source_id="safaricom",
            source_job_id="SWE-2024-01",
            source_url="https://careers.safaricom.co.ke/jobs/swe-2024",
            title="Senior Software Engineer",
            employer_name="Safaricom PLC",
            employer_domain="safaricom.co.ke",
            description_md="Looking for a senior software engineer with Python and cloud experience.",
            county="Nairobi",
            sub_county="Westlands",
            employment_type="full_time",
            work_mode="hybrid",
            entry_fit="experienced",
            pay=JobPay(min_amount=250000, max_amount=350000, currency="KES", period="month"),
            deadline=date.today() + timedelta(days=30),
            status="open",
        ),
        JobCandidate(
            source_id="andela",
            source_job_id="FS-2024-02",
            source_url="https://andela.com/careers/fullstack",
            title="Full Stack Developer",
            employer_name="Andela",
            employer_domain="andela.com",
            description_md="Full stack developer role with React and Node.js experience.",
            county="Nairobi",
            employment_type="full_time",
            work_mode="remote",
            entry_fit="some_experience",
            pay=JobPay(min_amount=180000, max_amount=280000, currency="KES", period="month"),
            deadline=date.today() + timedelta(days=45),
            status="open",
        ),
        JobCandidate(
            source_id="cellulant",
            source_job_id="BE-2024-03",
            source_url="https://cellulant.com/careers/backend",
            title="Backend Engineer",
            employer_name="Cellulant",
            employer_domain="cellulant.com",
            description_md="Backend engineer for payment systems. PostgreSQL and API experience required.",
            county="Nairobi",
            sub_county="Kilimani",
            employment_type="full_time",
            work_mode="onsite",
            entry_fit="some_experience",
            pay=JobPay(min_amount=200000, max_amount=300000, currency="KES", period="month"),
            deadline=date.today() + timedelta(days=20),
            status="open",
        ),
        JobCandidate(
            source_id="microsoft",
            source_job_id="PE-2024-04",
            source_url="https://careers.microsoft.com/platform-engineer",
            title="Platform Engineer",
            employer_name="Microsoft ADC",
            employer_domain="microsoft.com",
            description_md="Platform engineer for Azure services. Kubernetes and DevOps experience.",
            county="Nairobi",
            employment_type="full_time",
            work_mode="hybrid",
            entry_fit="experienced",
            pay=JobPay(min_amount=300000, max_amount=450000, currency="KES", period="month"),
            deadline=date.today() + timedelta(days=60),
            status="open",
        ),
        JobCandidate(
            source_id="twiga",
            source_job_id="DE-2024-05",
            source_url="https://twigafoods.com/careers/data-engineer",
            title="Data Engineer",
            employer_name="Twiga Foods",
            employer_domain="twigafoods.com",
            description_md="Data engineer for supply chain analytics. Python, SQL, and ETL experience.",
            county="Nairobi",
            employment_type="full_time",
            work_mode="onsite",
            entry_fit="some_experience",
            pay=JobPay(min_amount=150000, max_amount=250000, currency="KES", period="month"),
            deadline=date.today() + timedelta(days=35),
            status="open",
        ),
    ]
    
    # Insert jobs
    for job in jobs:
        result = upsert_candidate(conn, job)
        print(f"Inserted job: {job.title} at {job.employer_name} (job_id: {result.job_id})")
    
    conn.commit()
    conn.close()
    print(f"\nDatabase seeded with {len(jobs)} jobs at {db_path}")

if __name__ == "__main__":
    seed_database()
