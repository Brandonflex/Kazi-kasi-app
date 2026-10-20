"""Identity resolution and liveness on top of the observation store.

The rules, in order of strength:

1. **Exclusive keys** — a reference number, an ATS requisition, or the full
   cultural key (employer + normalised title + county + deadline). Two
   observations sharing one of these are the same posting.
2. **Shared keys, corroborated by title** — a careers inbox or an "apply here"
   URL. These prove an *employer*, not a job: a large employer posts twenty
   vacancies all pointing at `careers@company.co.ke`. They merge only when the
   titles agree and the deadlines do not contradict.
3. **Fuzzy title within the same employer and county** — merged only above a
   high threshold, with grade markers ("Analyst" vs "Analyst II") and deadlines
   treated as hard separators. Between the merge and review thresholds the pair
   goes to the review queue instead of being merged.

Everything that merges records *why* (``job_members.match_reason``), and
everything that nearly merged but did not is queued. A wrong merge hides a real
vacancy, which is the one failure this product cannot afford.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone

from .extract import normalize_title, title_tokens
from .identity import (
    IdentityKey,
    dedupe_key,
    employer_key,
    grade_marker,
    identity_keys,
)
from .models import JobCandidate

#: Title-token Jaccard at or above this merges without review.
FUZZY_MERGE = 0.75
#: At or above this, a human (or a later model) decides; below it, a new job.
FUZZY_REVIEW = 0.45

@dataclass
class Upsert:
    """What happened to one candidate."""

    observation_id: int
    job_id: str
    action: str  # created | attached | duplicate
    match_reason: str
    score: float = 1.0

    def to_dict(self) -> dict:
        return {
            "observation_id": self.observation_id,
            "job_id": self.job_id,
            "action": self.action,
            "match_reason": self.match_reason,
            "score": round(self.score, 3),
        }


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def job_id_for(candidate: JobCandidate) -> str:
    """Deterministic id from the cultural key, so a re-run cannot fork a job."""
    seed = dedupe_key(candidate)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def title_similarity_text(left_title: str, right_title: str) -> float:
    left, right = title_tokens(left_title), title_tokens(right_title)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def titles_merge(left_title: str, right_title: str) -> bool:
    """Strict title equality, honouring grade markers and token overlap."""
    if normalize_title(left_title) == normalize_title(right_title):
        return True
    if grade_marker(left_title) != grade_marker(right_title):
        return False
    return title_similarity_text(left_title, right_title) >= FUZZY_MERGE


def _deadline_iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat() if hasattr(value, "isoformat") else None


def _counties_compatible(left: str | None, right: str | None) -> bool:
    return left is None or right is None or left == right


def _queue_review(conn, observation_id: int, job_id: str, reason: str, score: float, now: datetime) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO review_queue
           (observation_id, candidate_job_id, reason, score, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (observation_id, job_id, reason, round(score, 3), _iso(now)),
    )


def deadlines_compatible(left, right) -> bool:
    """A missing deadline is compatible with anything; two different ones are not."""
    left_iso, right_iso = _deadline_iso(left), _deadline_iso(right)
    return left_iso is None or right_iso is None or left_iso == right_iso


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------


def record_observation(conn, candidate: JobCandidate, *, sha256: str | None = None) -> tuple[int, bool]:
    """Insert the observation if it is new. Returns ``(id, created)``.

    The unique key is the *interpretation fingerprint*, so re-parsing the same
    payload is a no-op while a changed page produces a new observation.
    """
    from .models import SourceRecord
    from .rawstore import PARSER_VERSION

    record = SourceRecord(
        source_id=candidate.source_id,
        source_job_id=candidate.source_job_id,
        source_url=candidate.source_url,
        fetched_at=candidate.first_seen_at,
        raw=None,  # type: ignore[arg-type]
        parsed=candidate.to_dict(),
        parser_version=PARSER_VERSION,
    )
    fingerprint = record.fingerprint()
    existing = conn.execute(
        "SELECT id FROM observations WHERE source_id = ? AND source_job_id = ? AND fingerprint = ?",
        (candidate.source_id, candidate.source_job_id, fingerprint),
    ).fetchone()
    if existing:
        return existing["id"], False

    cursor = conn.execute(
        """INSERT INTO observations
           (source_id, source_job_id, source_url, fetched_at, parser_version,
            fingerprint, sha256, payload)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            candidate.source_id,
            candidate.source_job_id,
            candidate.source_url,
            _iso(candidate.first_seen_at),
            PARSER_VERSION,
            fingerprint,
            sha256,
            json.dumps(candidate.to_dict(), ensure_ascii=False),
        ),
    )
    return int(cursor.lastrowid), True


def _jobs_for_keys(conn, keys: list[IdentityKey]) -> list[tuple[IdentityKey, object]]:
    """Return ``(key, job_row)`` for every key that already resolves to a job."""
    if not keys:
        return []
    placeholders = ",".join("?" for _ in keys)
    rows = conn.execute(
        f"""SELECT k.key AS matched_key, j.* FROM job_keys k
            JOIN jobs j ON j.id = k.job_id
            WHERE k.key IN ({placeholders}) AND j.status != 'closed'
            ORDER BY j.last_seen_at DESC""",
        [key.value for key in keys],
    ).fetchall()
    by_value = {key.value: key for key in keys}
    return [(by_value[row["matched_key"]], row) for row in rows]


def _block(conn, candidate: JobCandidate) -> list:
    """Jobs worth a fuzzy comparison: same employer, non-contradicting county."""
    emp = employer_key(candidate.employer_name, candidate.employer_domain)
    if emp == "unknown":
        return []
    rows = conn.execute(
        """SELECT * FROM jobs
           WHERE status != 'closed'
             AND (county IS NULL OR ? IS NULL OR county = ?)""",
        (candidate.county, candidate.county),
    ).fetchall()
    return [
        row
        for row in rows
        if employer_key(row["employer_name"], row["employer_domain"]) == emp
    ]


def upsert_candidate(
    conn,
    candidate: JobCandidate,
    *,
    now: datetime | None = None,
    sha256: str | None = None,
    merge_threshold: float = FUZZY_MERGE,
    review_threshold: float = FUZZY_REVIEW,
) -> Upsert:
    """Attach one candidate to a job, or create one. Idempotent."""
    now = _now(now)
    if not candidate.first_seen_at:
        candidate.first_seen_at = now

    observation_id, _ = record_observation(conn, candidate, sha256=sha256)
    existing_link = conn.execute(
        "SELECT job_id, match_reason FROM job_members WHERE observation_id = ?", (observation_id,)
    ).fetchone()
    if existing_link:
        # We have already placed this exact observation. Re-running an ingest
        # must never fork or double-count a job.
        conn.commit()
        return Upsert(observation_id, existing_link["job_id"], "duplicate", existing_link["match_reason"])

    keys = identity_keys(candidate)
    exclusive = [key for key in keys if key.exclusive]
    shared = [key for key in keys if not key.exclusive]

    # 1. An exclusive key is proof.
    for key, row in _jobs_for_keys(conn, exclusive):
        return _attach(conn, row["id"], candidate, observation_id, f"key_{key.kind}", 1.0, now, keys)

    # 2. A shared key plus agreeing titles is proof enough — unless the two
    #    contradict each other on a field that distinguishes real posts.
    for key, row in _jobs_for_keys(conn, shared):
        if not titles_merge(candidate.title, row["title"]):
            continue
        if not _counties_compatible(candidate.county, row["county"]):
            continue
        if deadlines_compatible(candidate.deadline, row["deadline"]):
            return _attach(
                conn, row["id"], candidate, observation_id, f"shared_{key.kind}+title", 0.95, now, keys
            )
        # Same inbox, same title, different closing date: this is exactly the
        # public-sector "one advert, N posts" shape, or a re-advert. Ask.
        _queue_review(conn, observation_id, row["id"], "shared_key_deadline_conflict", 0.6, now)

    # 3. Fuzzy title inside the same employer block.
    best_row, best_score = None, 0.0
    for row in _block(conn, candidate):
        if normalize_title(row["title"]) == normalize_title(candidate.title):
            score = 1.0
        else:
            score = title_similarity_text(candidate.title, row["title"])
        if grade_marker(row["title"]) != grade_marker(candidate.title):
            score = min(score, FUZZY_REVIEW)  # never auto-merge a different grade
        if score > best_score:
            best_row, best_score = row, score

    if (
        best_row is not None
        and best_score >= merge_threshold
        and deadlines_compatible(candidate.deadline, best_row["deadline"])
    ):
        return _attach(
            conn, best_row["id"], candidate, observation_id, "employer_title_county", best_score, now, keys
        )

    if (
        best_row is not None
        and best_score >= review_threshold
        and deadlines_compatible(candidate.deadline, best_row["deadline"])
    ):
        # Only ask a human about pairs that are genuinely ambiguous. Two posts
        # with different closing dates are already separated by the key.
        _queue_review(conn, observation_id, best_row["id"], "fuzzy_title", best_score, now)

    return _create(conn, candidate, observation_id, keys, now)


def _create(conn, candidate: JobCandidate, observation_id: int, keys: list[IdentityKey], now: datetime) -> Upsert:
    job_id = job_id_for(candidate)
    while conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone():
        job_id = hashlib.sha256(f"{job_id}-{observation_id}".encode()).hexdigest()[:24]

    status = "open" if not candidate.missing_required() else "needs_review"
    if candidate.deadline and candidate.deadline < now.date():
        status = "closed"

    conn.execute(
        """INSERT INTO jobs
           (id, title, employer_name, employer_domain, county, sub_county, entry_fit,
            employment_type, work_mode, deadline, pay_min, pay_max, pay_period,
            first_seen_at, last_seen_at, status, confidence, scam_flags, source_count,
            primary_observation_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            job_id,
            candidate.title,
            candidate.employer_name,
            candidate.employer_domain,
            candidate.county,
            candidate.sub_county,
            candidate.entry_fit,
            candidate.employment_type,
            candidate.work_mode,
            candidate.deadline.isoformat() if candidate.deadline else None,
            candidate.pay.min_amount,
            candidate.pay.max_amount,
            candidate.pay.period,
            _iso(candidate.first_seen_at),
            _iso(now),
            status,
            candidate.extraction_confidence,
            json.dumps(candidate.scam_flags),
            1,
            observation_id,
        ),
    )
    conn.execute(
        "INSERT INTO job_members (job_id, observation_id, match_reason, confidence, added_at) VALUES (?,?,?,?,?)",
        (job_id, observation_id, "new", 1.0, _iso(now)),
    )
    _store_keys(conn, job_id, keys)
    _event(conn, job_id, "opened", now, {"source_id": candidate.source_id})
    conn.commit()
    return Upsert(observation_id, job_id, "created", "new")


def _store_keys(conn, job_id: str, keys: list[IdentityKey]) -> None:
    for key in keys:
        conn.execute(
            "INSERT OR IGNORE INTO job_keys (key, job_id, kind) VALUES (?,?,?)",
            (key.value, job_id, key.kind),
        )


def _attach(
    conn,
    job_id: str,
    candidate: JobCandidate,
    observation_id: int,
    reason: str,
    score: float,
    now: datetime,
    keys: list[IdentityKey],
) -> Upsert:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.execute(
        "INSERT OR IGNORE INTO job_members (job_id, observation_id, match_reason, confidence, added_at) VALUES (?,?,?,?,?)",
        (job_id, observation_id, reason, round(score, 3), _iso(now)),
    )
    _store_keys(conn, job_id, keys)

    source_count = conn.execute(
        "SELECT COUNT(DISTINCT o.source_id) AS c FROM job_members m JOIN observations o ON o.id = m.observation_id WHERE m.job_id = ?",
        (job_id,),
    ).fetchone()["c"]

    updates: dict[str, object] = {"last_seen_at": _iso(now), "source_count": source_count}
    if candidate.deadline and not row["deadline"]:
        updates["deadline"] = candidate.deadline.isoformat()
    if candidate.employer_domain and not row["employer_domain"]:
        updates["employer_domain"] = candidate.employer_domain
    if candidate.pay.min_amount is not None and row["pay_min"] is None:
        updates.update(
            pay_min=candidate.pay.min_amount,
            pay_max=candidate.pay.max_amount,
            pay_period=candidate.pay.period,
        )
    if candidate.entry_fit != "unknown" and row["entry_fit"] == "unknown":
        updates["entry_fit"] = candidate.entry_fit
    if candidate.sub_county and not row["sub_county"]:
        updates["sub_county"] = candidate.sub_county
    if len(candidate.scam_flags) > len(json.loads(row["scam_flags"])):
        updates["scam_flags"] = json.dumps(candidate.scam_flags)
    if row["pay_min"] is None and candidate.pay.min_amount is not None:
        updates["primary_observation_id"] = observation_id
    if row["status"] in ("stale", "suspect_closed"):
        updates["status"] = "open"
        _event(conn, job_id, "reopened", now, {"source_id": candidate.source_id})

    assignments = ", ".join(f"{name} = ?" for name in updates)
    conn.execute(f"UPDATE jobs SET {assignments} WHERE id = ?", (*updates.values(), job_id))

    if source_count > row["source_count"]:
        _event(conn, job_id, "source_added", now, {"source_id": candidate.source_id, "count": source_count})

    conn.commit()
    return Upsert(observation_id, job_id, "attached", reason, score)


def _event(conn, job_id: str, kind: str, at: datetime, detail: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO job_events (job_id, kind, at, detail) VALUES (?,?,?,?)",
        (job_id, kind, _iso(at), json.dumps(detail) if detail else None),
    )


# --------------------------------------------------------------------------
# Liveness
# --------------------------------------------------------------------------


def apply_liveness(
    conn,
    *,
    now: datetime | None = None,
    stale_days: int = 3,
    suspect_days: int = 7,
    closed_grace_days: int = 2,
) -> dict[str, int]:
    """Move jobs along the freshness ladder and record why.

    ``open`` → ``stale`` after ``stale_days`` without a sighting → ``closed``
    after ``suspect_days``, with a grace period past the stated deadline so a
    board that lags its own closing date does not lose a live job.

    A job is only *closed* by evidence: a passed deadline, or it disappeared
    from every source for longer than the suspect window.
    """
    now = _now(now)
    counts = {"stale": 0, "suspect_closed": 0, "closed": 0}

    for row in conn.execute(
        "SELECT * FROM jobs WHERE status IN ('open', 'needs_review', 'stale', 'suspect_closed')"
    ):
        last_seen = datetime.fromisoformat(row["last_seen_at"])
        age = (now - last_seen).days
        deadline = date.fromisoformat(row["deadline"]) if row["deadline"] else None

        new_status = row["status"]
        if deadline and (now.date() - deadline).days > closed_grace_days:
            new_status = "closed"
        elif row["status"] == "needs_review":
            # Missing fields are a data problem, not a freshness problem: this
            # job stays visible until its deadline or a human decides.
            continue
        elif age >= suspect_days:
            new_status = "suspect_closed"
        elif age >= stale_days:
            new_status = "stale"

        if new_status != row["status"]:
            conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (new_status, row["id"]))
            _event(conn, row["id"], new_status, now, {"from": row["status"], "age_days": age})
            if new_status in counts:
                counts[new_status] += 1

    conn.commit()
    return counts


# --------------------------------------------------------------------------
# Review queue
# --------------------------------------------------------------------------


def merge_jobs(conn, keep_job_id: str, drop_job_id: str, *, now: datetime | None = None) -> None:
    """Human decision: these are the same job. Keeps the older job's id."""
    now = _now(now)
    keeper = conn.execute("SELECT * FROM jobs WHERE id = ?", (keep_job_id,)).fetchone()
    dropped = conn.execute("SELECT * FROM jobs WHERE id = ?", (drop_job_id,)).fetchone()
    if keeper is None or dropped is None:
        raise ValueError("merge_jobs: unknown job id")

    conn.execute("UPDATE OR IGNORE job_members SET job_id = ? WHERE job_id = ?", (keep_job_id, drop_job_id))
    conn.execute("DELETE FROM job_members WHERE job_id = ?", (drop_job_id,))
    conn.execute("UPDATE job_keys SET job_id = ? WHERE job_id = ?", (keep_job_id, drop_job_id))
    # History and open questions follow the surviving job rather than vanishing.
    conn.execute("UPDATE job_events SET job_id = ? WHERE job_id = ?", (keep_job_id, drop_job_id))
    conn.execute("UPDATE review_queue SET candidate_job_id = ? WHERE candidate_job_id = ?", (keep_job_id, drop_job_id))
    # Any open question about an observation that now belongs to the keeper is
    # answered by the merge itself.
    conn.execute(
        """UPDATE review_queue SET resolved_at = ?, resolution = 'merged'
           WHERE resolved_at IS NULL
             AND observation_id IN (SELECT observation_id FROM job_members WHERE job_id = ?)""",
        (_iso(now), keep_job_id),
    )
    source_count = conn.execute(
        "SELECT COUNT(DISTINCT o.source_id) AS c FROM job_members m JOIN observations o ON o.id = m.observation_id WHERE m.job_id = ?",
        (keep_job_id,),
    ).fetchone()["c"]
    conn.execute(
        """UPDATE jobs SET last_seen_at = ?, source_count = ?, deadline = COALESCE(deadline, ?)
           WHERE id = ?""",
        (max(keeper["last_seen_at"], dropped["last_seen_at"]), source_count, dropped["deadline"], keep_job_id),
    )
    conn.execute("DELETE FROM jobs WHERE id = ?", (drop_job_id,))
    _event(conn, keep_job_id, "merged", now, {"absorbed": drop_job_id})
    conn.commit()


def reject_pair(conn, review_id: int, *, now: datetime | None = None) -> None:
    """Human decision: these are different jobs. Recorded so it is not re-asked."""
    conn.execute(
        "UPDATE review_queue SET resolved_at = ?, resolution = 'rejected' WHERE id = ?",
        (_iso(_now(now)), review_id),
    )
    conn.commit()


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------


def open_reviews(conn, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        """SELECT r.*, j.title AS job_title, j.employer_name AS job_employer
           FROM review_queue r JOIN jobs j ON j.id = r.candidate_job_id
           WHERE r.resolved_at IS NULL ORDER BY r.score DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    out = []
    for row in rows:
        observation = conn.execute(
            "SELECT payload FROM observations WHERE id = ?", (row["observation_id"],)
        ).fetchone()
        payload = json.loads(observation["payload"]) if observation else {}
        out.append(
            {
                **dict(row),
                "incoming_title": payload.get("title"),
                "incoming_employer": payload.get("employer_name"),
                "incoming_source": payload.get("source_id"),
            }
        )
    return out


def job_row(conn, job_id: str):
    return conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()


def job_sources(conn, job_id: str) -> list[dict]:
    rows = conn.execute(
        """SELECT o.source_id, o.source_url, o.fetched_at, m.match_reason, m.confidence
           FROM job_members m JOIN observations o ON o.id = m.observation_id
           WHERE m.job_id = ? ORDER BY o.fetched_at""",
        (job_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def job_events(conn, job_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT kind, at, detail FROM job_events WHERE job_id = ? ORDER BY at", (job_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def feed(
    conn,
    *,
    county: str | None = None,
    entry_fit: str | None = None,
    include_stale: bool = False,
    include_flagged: bool = False,
    limit: int = 100,
) -> list[dict]:
    """The read model for the feed: live jobs, soonest deadline first."""
    statuses = ["open"] + (["stale"] if include_stale else [])
    placeholders = ",".join("?" for _ in statuses)
    clauses = [f"status IN ({placeholders})"]
    params: list[object] = list(statuses)
    if not include_flagged:
        # A flagged posting is not shown as a normal card; it only appears with
        # its warnings in the review surface.
        clauses.append("scam_flags = '[]'")
    if county:
        clauses.append("county = ?")
        params.append(county)
    if entry_fit:
        clauses.append("entry_fit = ?")
        params.append(entry_fit)
    params.append(limit)
    rows = conn.execute(
        f"""SELECT * FROM jobs WHERE {' AND '.join(clauses)}
            ORDER BY (deadline IS NULL), deadline, last_seen_at DESC LIMIT ?""",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def jobs_in_review(conn, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM jobs WHERE status = 'needs_review' ORDER BY last_seen_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def days_since(iso_timestamp: str, now: datetime | None = None) -> int:
    return max(0, (_now(now) - datetime.fromisoformat(iso_timestamp)).days)


def freshness_band(row, now: datetime | None = None) -> str:
    """What the card says. Deliberately blunt: today, then days."""
    age = days_since(row["last_seen_at"], now)
    if age == 0:
        return "checked today"
    if age == 1:
        return "checked yesterday"
    return f"checked {age} days ago"


def deadline_band(row, now: datetime | None = None) -> str | None:
    if not row["deadline"]:
        return None
    today = _now(now).date()
    days = (date.fromisoformat(row["deadline"]) - today).days
    if days < 0:
        return "closed"
    if days == 0:
        return "closes today"
    if days == 1:
        return "closes tomorrow"
    if days <= 7:
        return f"closes in {days} days"
    return f"closes {date.fromisoformat(row['deadline']).strftime('%d %b')}"


def bump_seen(conn, job_ids: list[str], *, now: datetime | None = None) -> int:
    """Record that a source still shows these jobs (used by the ingest loop)."""
    now = _now(now)
    count = 0
    for job_id in job_ids:
        cursor = conn.execute(
            "UPDATE jobs SET last_seen_at = ?, status = CASE WHEN status = 'stale' THEN 'open' ELSE status END WHERE id = ?",
            (_iso(now), job_id),
        )
        count += cursor.rowcount
    conn.commit()
    return count
