"""A deterministic synthetic corpus.

**This is not real data.** It exists so that the graph, the dedupe metrics and
the feed can be exercised end-to-end without a network, and so the preview shows
something shaped like Kenya rather than four fixture jobs.

It is built to contain the awkward cases on purpose:

* the same advert on two boards with the same apply email (must merge);
* two adverts for the same employer and title with **different deadlines**
  (must *not* merge — these are separate public-sector posts);
* a title variant that is close but not identical (must go to review, not merge);
* an expired advert, a scam-flagged advert, and a posting with no location.

Anything generated here is labelled ``synthetic`` in the feed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import JobCandidate, JobPay

SYNTHETIC = True


def _pay(amount: int, period: str = "month") -> JobPay:
    return JobPay(
        min_amount=float(amount),
        max_amount=float(amount),
        currency="KES",
        period=period,
        source="stated",
        confidence=0.9,
    )


def _make(
    *,
    source: str,
    source_id: str,
    title: str,
    employer: str,
    county: str | None,
    sub_county: str | None,
    description: str,
    entry_fit: str,
    evidence: str,
    employment_type: str = "full_time",
    work_mode: str = "onsite",
    days_to_deadline: int | None = 14,
    pay: int | None = None,
    email: str | None = None,
    reference: str | None = None,
    domain: str | None = None,
    scam: list[str] | None = None,
    now: datetime | None = None,
) -> JobCandidate:
    now = now or datetime.now(timezone.utc)
    deadline = (now.date() + timedelta(days=days_to_deadline)) if days_to_deadline is not None else None
    return JobCandidate(
        source_id=source,
        source_job_id=source_id,
        source_url=f"https://example.{source}.co.ke/job/{source_id}",
        title=title,
        employer_name=employer,
        employer_domain=domain,
        description_md=description,
        extraction_confidence=0.9,
        entry_fit=entry_fit,
        entry_fit_evidence=evidence,
        employment_type=employment_type,
        work_mode=work_mode,
        work_mode_source="posting" if work_mode != "onsite" else "inferred_from_location",
        county=county,
        sub_county=sub_county,
        location_raw=(f"{sub_county}, {county}" if sub_county else county) or None,
        pay=_pay(pay) if pay else JobPay(),
        date_posted_claimed=now.date() - timedelta(days=2),
        deadline=deadline,
        apply_emails=[email] if email else [],
        reference=reference,
        scam_flags=scam or [],
        scam_evidence={flag: "synthetic example" for flag in (scam or [])},
        first_seen_at=now,
        status="extracted",
    )


def build_corpus(now: datetime | None = None) -> list[JobCandidate]:
    """Return the synthetic candidates in ingest order."""
    now = now or datetime.now(timezone.utc)
    jobs: list[JobCandidate] = []

    def add(**kwargs):
        jobs.append(_make(now=now, **kwargs))

    # --- unique postings, one source each --------------------------------
    add(
        source="brightermonday",
        source_id="BM-1001",
        title="Software Support Analyst",
        employer="Haba Data Systems Ltd",
        county="Nairobi",
        sub_county="Westlands",
        domain="habadata.co.ke",
        email="careers@habadata.co.ke",
        pay=65000,
        entry_fit="open_to_freshers",
        evidence="Fresh graduates are encouraged to apply. No prior work experience required.",
        description=(
            "Haba Data Systems is hiring a Software Support Analyst to join our Westlands team. "
            "You will triage tickets from county health facilities, reproduce issues and escalate "
            "to engineering. Fresh graduates are encouraged to apply. No prior work experience "
            "required. Send your CV to careers@habadata.co.ke."
        ),
        days_to_deadline=9,
    )
    add(
        source="myjobmag",
        source_id="MJM-2001",
        title="Marketing Intern",
        employer="Mwangaza Logistics",
        county="Nairobi",
        sub_county="Starehe",
        domain="mwangazalogistics.co.ke",
        email="internships@mwangazalogistics.co.ke",
        pay=20000,
        employment_type="internship",
        entry_fit="open_to_freshers",
        evidence="This is an internship; candidates with no experience are welcome.",
        description=(
            "Six-month marketing internship at our Industrial Area depot. This is an internship "
            "placement; candidates with no experience are welcome. A stipend of KSh 20,000 per "
            "month is provided. Deadline for applications: 30 November 2026."
        ),
        days_to_deadline=41,
    )
    add(
        source="fuzu",
        source_id="FZ-3001",
        title="Finance Assistant",
        employer="Mwangaza Logistics",
        county="Nairobi",
        sub_county="Starehe",
        domain="mwangazalogistics.co.ke",
        email="hr@mwangazalogistics.co.ke",
        pay=55000,
        entry_fit="some_experience",
        evidence="A minimum of one year of experience in a finance or audit role.",
        description=(
            "Reporting to the Finance Manager, the Finance Assistant will handle payables, petty "
            "cash and monthly reconciliations. A minimum of one year of experience in a finance "
            "or audit role is required. CPA Part II is an added advantage."
        ),
        days_to_deadline=6,
    )
    add(
        source="brightermonday",
        source_id="BM-1002",
        title="Operations Assistant",
        employer="Sanaa Capital",
        county="Nairobi",
        sub_county="Kilimani",
        domain="sanaacapital.co.ke",
        email="jobs@sanaacapital.co.ke",
        pay=48000,
        entry_fit="some_experience",
        evidence="One to two years of experience in a similar operations role.",
        description=(
            "Sanaa Capital seeks an Operations Assistant to support client onboarding and "
            "reporting. One to two years of experience in a similar operations role is expected."
        ),
        days_to_deadline=12,
    )
    add(
        source="myjobmag",
        source_id="MJM-2002",
        title="Records Clerk",
        employer="Kiambu County Government",
        county="Kiambu",
        sub_county=None,
        reference="KCG/HR/07/2026",
        email="recruitment@kiambu.go.ke",
        pay=42000,
        entry_fit="open_to_freshers",
        evidence="Diploma holders with no prior experience are encouraged to apply.",
        description=(
            "The County Government of Kiambu invites applications from qualified persons for the "
            "position of Records Clerk. Diploma holders with no prior experience are encouraged "
            "to apply. Ref: KCG/HR/07/2026. Applications close on 5 November 2026."
        ),
        days_to_deadline=16,
    )
    add(
        source="reliefweb",
        source_id="RW-4100231",
        title="Programme Assistant",
        employer="UN Office for the Coordination of Humanitarian Affairs",
        county="Nairobi",
        sub_county=None,
        domain="unocha.org",
        pay=140000,
        entry_fit="some_experience",
        evidence="A minimum of one year of relevant experience is desirable.",
        description=(
            "The Country Office in Nairobi seeks a Programme Assistant to support the humanitarian "
            "response portfolio. A minimum of one year of relevant experience is desirable. "
            "Recent graduates with strong organisational skills are encouraged to apply."
        ),
        days_to_deadline=11,
    )
    add(
        source="brightermonday",
        source_id="BM-1003",
        title="Human Resources Officer",
        employer="Tumaini Health Group",
        county="Nairobi",
        sub_county="Upper Hill",
        domain="tumainihealth.co.ke",
        email="hr@tumainihealth.co.ke",
        entry_fit="experienced",
        evidence="At least three years of HR generalist experience is required.",
        description=(
            "Tumaini Health Group is recruiting an HR Officer for its Nairobi hospital network. "
            "At least three years of HR generalist experience is required. CIPD or IHRM "
            "membership is an added advantage."
        ),
        days_to_deadline=20,
    )
    add(
        source="fuzu",
        source_id="FZ-3002",
        title="Sales Associate",
        employer="Rafiki Retail",
        county="Nairobi",
        sub_county="Embakasi",
        domain="rafikiretail.co.ke",
        email="talent@rafikiretail.co.ke",
        pay=35000,
        entry_fit="open_to_freshers",
        evidence="Entry level; full training provided.",
        description=(
            "Rafiki Retail is hiring Sales Associates for its Embakasi branch. Entry level role; "
            "full training provided. Candidates should have a KCSE certificate or above."
        ),
        days_to_deadline=8,
    )
    add(
        source="myjobmag",
        source_id="MJM-2003",
        title="Data Entry Clerk",
        employer="Jumuia Data Services",
        county="Nairobi",
        sub_county="Starehe",
        domain="jumuia.co.ke",
        email="apply@jumuia.co.ke",
        pay=32000,
        entry_fit="open_to_freshers",
        evidence="No experience required; training on the job.",
        description=(
            "Jumuia Data Services seeks data entry clerks for a six-month project. No experience "
            "required; training on the job. Typing speed of 40 wpm preferred."
        ),
        days_to_deadline=5,
    )
    add(
        source="brightermonday",
        source_id="BM-1004",
        title="Accounts Intern",
        employer="Kilele Audit LLP",
        county="Nairobi",
        sub_county="Westlands",
        domain="kileleaudit.co.ke",
        email="interns@kileleaudit.co.ke",
        employment_type="internship",
        entry_fit="open_to_freshers",
        evidence="Attachment and internship applicants welcome.",
        description=(
            "Kilele Audit LLP offers a three-month accounts internship in Westlands. Attachment "
            "and internship applicants welcome; a small transport allowance is provided."
        ),
        days_to_deadline=25,
    )
    add(
        source="fuzu",
        source_id="FZ-3003",
        title="Customer Support Associate",
        employer="Pesaflow Technologies",
        county="Nairobi",
        sub_county="Westlands",
        domain="pesaflow.co.ke",
        email="careers@pesaflow.co.ke",
        pay=52000,
        work_mode="hybrid",
        entry_fit="some_experience",
        evidence="Up to two years of experience in customer support.",
        description=(
            "Pesaflow is hiring a Customer Support Associate to help merchants resolve payment "
            "issues. This is a hybrid role, three days a week in the Westlands office. Up to two "
            "years of experience in customer support is expected."
        ),
        days_to_deadline=10,
    )
    add(
        source="brightermonday",
        source_id="BM-1005",
        title="Junior Data Analyst",
        employer="Haba Data Systems Ltd",
        county="Nairobi",
        sub_county="Westlands",
        domain="habadata.co.ke",
        email="careers@habadata.co.ke",
        pay=70000,
        entry_fit="some_experience",
        evidence="One year of experience with SQL and dashboards.",
        description=(
            "Haba Data Systems is hiring a Junior Data Analyst to build county dashboards. One "
            "year of experience with SQL and dashboards is expected. Recent graduates with strong "
            "SQL coursework will be considered."
        ),
        days_to_deadline=14,
    )
    add(
        source="myjobmag",
        source_id="MJM-2004",
        title="Administrative Assistant",
        employer="Wanjiku & Associates Advocates",
        county="Nairobi",
        sub_county="Starehe",
        email="office@wanjikuadvocates.co.ke",
        pay=38000,
        entry_fit="some_experience",
        evidence="At least two years of experience in a law firm.",
        description=(
            "A Nairobi law firm seeks an Administrative Assistant. At least two years of "
            "experience in a law firm is required. Secretarial qualifications are an advantage."
        ),
        days_to_deadline=18,
    )
    add(
        source="reliefweb",
        source_id="RW-4100299",
        title="Finance Officer",
        employer="International Rescue Committee",
        county="Nairobi",
        sub_county=None,
        domain="rescue.org",
        pay=180000,
        entry_fit="experienced",
        evidence="A minimum of four years of finance experience.",
        description=(
            "The IRC Kenya country programme is recruiting a Finance Officer. A minimum of four "
            "years of finance experience, including donor reporting, is required. CPA(K) is an "
            "added advantage."
        ),
        days_to_deadline=22,
    )
    add(
        source="fuzu",
        source_id="FZ-3004",
        title="Software Engineering Intern",
        employer="Mkuki Software",
        county="Nairobi",
        sub_county="Ngong Road",
        domain="mkuki.dev",
        email="interns@mkuki.dev",
        employment_type="internship",
        work_mode="remote",
        entry_fit="open_to_freshers",
        evidence="Students and recent graduates with no professional experience are eligible.",
        description=(
            "Mkuki Software runs a six-month remote software engineering internship. Students and "
            "recent graduates with no professional experience are eligible. A laptop is required."
        ),
        days_to_deadline=30,
    )
    add(
        source="brightermonday",
        source_id="BM-1006",
        title="Procurement Assistant",
        employer="Machakos County Government",
        county="Machakos",
        sub_county=None,
        reference="MCG/ADM/33/2026",
        email="procurement@machakos.go.ke",
        pay=47000,
        entry_fit="some_experience",
        evidence="At least one year of experience in public procurement.",
        description=(
            "Machakos County Government invites applications for Procurement Assistant. At least "
            "one year of experience in public procurement is required. Ref: MCG/ADM/33/2026."
        ),
        days_to_deadline=15,
    )
    add(
        source="myjobmag",
        source_id="MJM-2005",
        title="Graduate Trainee Programme 2027",
        employer="Sanaa Capital",
        county="Nairobi",
        sub_county="Kilimani",
        domain="sanaacapital.co.ke",
        email="graduate@sanaacapital.co.ke",
        pay=40000,
        entry_fit="open_to_freshers",
        evidence="Final-year students and recent graduates, no experience required.",
        description=(
            "Sanaa Capital's Graduate Trainee Programme 2027 is open to final-year students and "
            "recent graduates. No experience required. Rotations across operations and client "
            "services."
        ),
        days_to_deadline=45,
    )
    add(
        source="fuzu",
        source_id="FZ-3005",
        title="Community Manager",
        employer="Zidi Media",
        county="Nairobi",
        sub_county=None,
        domain="zidimedia.com",
        email="hello@zidimedia.com",
        work_mode="remote",
        entry_fit="some_experience",
        evidence="One year of experience managing online communities.",
        description=(
            "Zidi Media is hiring a fully remote Community Manager. One year of experience "
            "managing online communities is expected. Strong written English required."
        ),
        days_to_deadline=13,
    )
    add(
        source="brightermonday",
        source_id="BM-1007",
        title="ICT Attachment",
        employer="Kajiado County Government",
        county="Kajiado",
        sub_county=None,
        email="ict@kajiado.go.ke",
        employment_type="attachment",
        entry_fit="open_to_freshers",
        evidence="Industrial attachment for diploma and degree students.",
        description=(
            "Kajiado County Government offers industrial attachment placements in the ICT "
            "department for diploma and degree students. No prior work experience is required."
        ),
        days_to_deadline=28,
    )
    add(
        source="myjobmag",
        source_id="MJM-2006",
        title="Accounts Assistant",
        employer="Tumaini Health Group",
        county="Nairobi",
        sub_county="Upper Hill",
        domain="tumainihealth.co.ke",
        email="hr@tumainihealth.co.ke",
        pay=45000,
        entry_fit="some_experience",
        evidence="Two years of accounting experience.",
        description=(
            "Tumaini Health Group seeks an Accounts Assistant. Two years of accounting experience "
            "is required. The role reports to the Finance Manager."
        ),
        days_to_deadline=7,
    )

    # --- the same advert on two boards (must merge) -----------------------
    shared_email = "recruitment@kisaju.go.ke"
    shared_description = (
        "The County Government of Nairobi invites applications for the position of Clerical "
        "Officer. Diploma holders with no prior experience are encouraged to apply. "
        "Ref: NCG/HR/12/2026. Applications close on 12 November 2026."
    )
    for source, source_id in (("brightermonday", "BM-1100"), ("myjobmag", "MJM-2100")):
        jobs.append(
            _make(
                source=source,
                source_id=source_id,
                title="Clerical Officer",
                employer="Nairobi County Government",
                county="Nairobi",
                sub_county="Starehe",
                reference="NCG/HR/12/2026",
                email=shared_email,
                pay=41000,
                entry_fit="open_to_freshers",
                evidence="Diploma holders with no prior experience are encouraged to apply.",
                description=shared_description,
                days_to_deadline=23,
                now=now,
            )
        )

    for source, source_id in (("fuzu", "FZ-3100"), ("brightermonday", "BM-1101")):
        jobs.append(
            _make(
                source=source,
                source_id=source_id,
                title="Business Development Associate",
                employer="Pesaflow Technologies",
                county="Nairobi",
                sub_county="Westlands",
                domain="pesaflow.co.ke",
                email="careers@pesaflow.co.ke",
                pay=60000,
                entry_fit="some_experience",
                evidence="One to two years of experience in B2B sales.",
                description=(
                    "Pesaflow is hiring a Business Development Associate for the SME segment. "
                    "One to two years of experience in B2B sales is expected."
                ),
                days_to_deadline=17,
                now=now,
            )
        )

    # --- two posts at the same employer with different deadlines --------
    for source, source_id, closing, sub in (
        ("myjobmag", "MJM-2200", 19, "Kasarani"),
        ("myjobmag", "MJM-2201", 33, "Embakasi"),
    ):
        jobs.append(
            _make(
                source=source,
                source_id=source_id,
                title="Nurse",
                employer="Tumaini Health Group",
                county="Nairobi",
                sub_county=sub,
                domain="tumainihealth.co.ke",
                email="hr@tumainihealth.co.ke",
                pay=68000,
                entry_fit="some_experience",
                evidence="At least one year of clinical experience.",
                description=(
                    "Tumaini Health Group is recruiting nurses for its Nairobi facilities. At "
                    "least one year of clinical experience is required."
                ),
                days_to_deadline=closing,
                now=now,
            )
        )

    # --- near-duplicates: close titles, same employer, same deadline -------
    # These must land in the review queue, never in an automatic merge.
    jobs.append(
        _make(
            source="fuzu",
            source_id="FZ-3200",
            title="Software Support Analyst II",
            employer="Haba Data Systems Ltd",
            county="Nairobi",
            sub_county="Westlands",
            domain="habadata.co.ke",
            email="careers@habadata.co.ke",
            pay=80000,
            entry_fit="some_experience",
            evidence="Two years of experience supporting enterprise software.",
            description=(
                "Haba Data Systems is hiring a Software Support Analyst II to own the escalation "
                "queue. Two years of experience supporting enterprise software is expected."
            ),
            days_to_deadline=9,  # same closing date as the Analyst role
            now=now,
        )
    )
    jobs.append(
        _make(
            source="brightermonday",
            source_id="BM-1200",
            title="Marketing & Communications Intern",
            employer="Mwangaza Logistics",
            county="Nairobi",
            sub_county="Starehe",
            domain="mwangazalogistics.co.ke",
            email="internships@mwangazalogistics.co.ke",
            employment_type="internship",
            entry_fit="open_to_freshers",
            evidence="Open to recent graduates with no experience.",
            description=(
                "Mwangaza Logistics seeks a Marketing & Communications Intern. Open to recent "
                "graduates with no experience. Six-month placement."
            ),
            days_to_deadline=41,
            now=now,
        )
    )

    # --- awkward cases ---------------------------------------------------
    jobs.append(
        _make(
            source="myjobmag",
            source_id="MJM-2300",
            title="Field Sales Representative",
            employer="Rafiki Retail",
            county="Nairobi",
            sub_county="Embakasi",
            domain="rafikiretail.co.ke",
            email="talent@rafikiretail.co.ke",
            pay=30000,
            entry_fit="open_to_freshers",
            evidence="No experience required.",
            description="Field sales role covering Embakasi and Kayole. No experience required.",
            days_to_deadline=-3,  # already closed
            now=now,
        )
    )
    jobs.append(
        _make(
            source="myjobmag",
            source_id="MJM-2400",
            title="Urgent Data Entry Clerks",
            employer=None,
            county=None,
            sub_county=None,
            email=None,
            pay=None,
            entry_fit="unknown",
            evidence=None,
            description=(
                "Urgent data entry clerks wanted. Immediate start, no interview required. Send a "
                "registration fee of KSh 500 via M-Pesa. WhatsApp only: 0712 345 678."
            ),
            days_to_deadline=4,
            scam=["fee_requested", "whatsapp_only", "no_employer_identity"],
            now=now,
        )
    )
    jobs.append(
        _make(
            source="brightermonday",
            source_id="BM-1300",
            title="Office Assistant",
            employer="Baraka Foods",
            county=None,
            sub_county=None,
            email=None,
            entry_fit="unknown",
            evidence=None,
            description="Office assistant needed. Salary negotiable.",
            days_to_deadline=None,
            now=now,
        )
    )

    return jobs


def load_corpus(conn, *, now: datetime | None = None) -> dict:
    """Upsert the whole corpus into a connection. Returns the action counts."""
    from collections import Counter

    from .graph import apply_liveness, upsert_candidate

    now = now or datetime.now(timezone.utc)
    actions = Counter()
    for candidate in build_corpus(now=now):
        actions[upsert_candidate(conn, candidate, now=now).action] += 1
    liveness = apply_liveness(conn, now=now)
    return {"actions": dict(actions), "liveness": liveness}
