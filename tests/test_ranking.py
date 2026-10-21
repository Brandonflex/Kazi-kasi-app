"""Matching: gates before scores, and every score explained.

The important cases are the exclusions — showing an impossible job at 4% is
worse than not showing it — and the reasons, because a tailored feed nobody can
audit is just an opaque feed.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from kazikasi import db, graph, ranking
from kazikasi.corpus import load_corpus
from kazikasi.profile import Profile, families_for, seed_profiles

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


def row(**kwargs) -> dict:
    base = {
        "id": "j1",
        "title": "Software Support Analyst",
        "employer_name": "Haba Data Systems Ltd",
        "county": "Nairobi",
        "sub_county": "Westlands",
        "entry_fit": "open_to_freshers",
        "employment_type": "full_time",
        "work_mode": "onsite",
        "deadline": (NOW.date() + timedelta(days=10)).isoformat(),
        "pay_min": 55000.0,
        "pay_max": 75000.0,
        "pay_period": "month",
        "source_count": 1,
        "scam_flags": "[]",
        "status": "open",
        "last_seen_at": NOW.isoformat(),
    }
    base.update(kwargs)
    return base


def profile(**kwargs) -> Profile:
    base = dict(
        id="p1",
        name="Test",
        home_county="Nairobi",
        home_area="Kasarani",
        max_commute_km=25.0,
        role_families=["it"],
        entry_fits=["open_to_freshers", "some_experience"],
    )
    base.update(kwargs)
    return Profile(**base)


class TestFamilies:
    @pytest.mark.parametrize(
        "title,families",
        [
            ("Software Support Analyst", {"it", "customer"}),
            ("Records Management Assistant", {"admin"}),
            ("Data Entry Clerk", {"admin"}),
            ("Finance Assistant", {"finance"}),
            ("Programme Assistant", {"programme"}),
            ("Marketing Intern", {"marketing"}),
        ],
    )
    def test_classification(self, title, families):
        assert set(families_for(title)) == families

    def test_unclassifiable_titles_are_empty_not_guessed(self):
        assert families_for("Driver") == []
        assert families_for("") == []


class TestGates:
    def test_open_to_freshers_passes(self):
        assert ranking.constraints(row(), profile(), NOW) == []

    def test_experienced_role_is_blocked_with_a_readable_reason(self):
        blockers = ranking.constraints(row(entry_fit="experienced"), profile(), NOW)
        assert blockers == ["needs 3+ years"]

    def test_unknown_eligibility_is_not_blocked(self):
        # Unstated is not disqualifying; it is a gap in the advert.
        assert ranking.constraints(row(entry_fit="unknown"), profile(), NOW) == []

    def test_work_mode_constraint(self):
        p = profile(work_modes=["remote"])
        assert any("role" in blocker for blocker in ranking.constraints(row(), p, NOW))

    def test_deadline_window(self):
        p = profile(deadline_within_days=5)
        blockers = ranking.constraints(row(), p, NOW)
        assert any("beyond your window" in blocker for blocker in blockers)

    def test_distance_cap(self):
        p = profile(home_area="Karen", max_commute_km=5)
        blockers = ranking.constraints(row(), p, NOW)
        assert any("beyond your" in blocker and "km limit" in blocker for blocker in blockers)

    def test_remote_jobs_ignore_the_distance_cap(self):
        p = profile(home_area="Karen", max_commute_km=1)
        assert ranking.constraints(row(work_mode="remote"), p, NOW) == []

    def test_unknown_location_is_not_a_blocker(self):
        p = profile(max_commute_km=1)
        assert ranking.constraints(row(county=None, sub_county=None), p, NOW) == []

    def test_pay_floor_is_not_a_gate(self):
        # A pay floor informs ranking; it must not silently hide jobs, because
        # most Kenyan adverts do not state pay at all.
        p = profile(min_monthly_pay=500000)
        assert ranking.constraints(row(), p, NOW) == []


class TestScores:
    def test_relevance_prefers_the_matching_family(self):
        match_it = ranking.score_job(row(), profile(role_families=["it"]), NOW)
        match_hr = ranking.score_job(row(), profile(role_families=["hr"]), NOW)
        assert match_it.relevance > match_hr.relevance

    def test_urgency_raises_utility(self):
        soon = ranking.score_job(
            row(deadline=(NOW.date() + timedelta(days=1)).isoformat()), profile(), NOW
        )
        far = ranking.score_job(
            row(deadline=(NOW.date() + timedelta(days=60)).isoformat()), profile(), NOW
        )
        assert soon.utility > far.utility
        assert "closes tomorrow" in soon.reasons

    def test_staleness_lowers_utility_and_says_so(self):
        stale = ranking.score_job(row(last_seen_at=(NOW - timedelta(days=9)).isoformat()), profile(), NOW)
        fresh = ranking.score_job(row(), profile(), NOW)
        assert stale.utility < fresh.utility
        assert any("not re-checked" in reason for reason in stale.reasons)

    def test_corroboration_is_a_reason(self):
        match = ranking.score_job(row(source_count=3), profile(), NOW)
        assert any("confirmed on 3 sources" in reason for reason in match.reasons)

    def test_scam_flags_cost_points_and_say_so(self):
        flagged = ranking.score_job(row(scam_flags='["fee_requested"]'), profile(), NOW)
        clean = ranking.score_job(row(), profile(), NOW)
        assert flagged.utility < clean.utility
        assert any("flagged for review" in reason for reason in flagged.reasons)

    def test_pay_floor_is_reported_when_it_is_met(self):
        match = ranking.score_job(row(), profile(min_monthly_pay=40000), NOW)
        assert any("above your KES 40,000 floor" in reason for reason in match.reasons)

    def test_distance_is_a_reason_and_a_band(self):
        match = ranking.score_job(row(), profile(), NOW)
        assert match.distance is not None
        assert any("km away" in reason for reason in match.reasons)

    def test_score_is_zero_for_blocked_jobs(self):
        match = ranking.score_job(row(entry_fit="experienced"), profile(), NOW)
        assert match.eligible is False and match.score == 0.0

    def test_every_eligible_match_has_reasons(self):
        for entry_fit in ("open_to_freshers", "some_experience", "unknown"):
            match = ranking.score_job(row(entry_fit=entry_fit), profile(), NOW)
            assert match.reasons

    def test_scores_stay_in_range(self):
        match = ranking.score_job(row(source_count=5, pay_min=900000, pay_max=900000), profile(), NOW)
        assert 0.0 <= match.score <= 1.0


class TestRanking:
    def test_blocked_jobs_are_dropped_by_default(self):
        rows = [row(), row(id="j2", title="Senior Finance Manager", entry_fit="experienced")]
        matches = ranking.rank(rows, profile(), now=NOW)
        assert [match.job_id for match in matches] == ["j1"]

    def test_blocked_jobs_can_be_asked_for(self):
        rows = [row(), row(id="j2", title="Senior Finance Manager", entry_fit="experienced")]
        matches = ranking.rank(rows, profile(), now=NOW, include_blocked=True)
        assert len(matches) == 2
        assert matches[-1].eligible is False

    def test_better_match_sorts_first(self):
        rows = [
            row(id="far", title="Software Support Analyst", county="Machakos", sub_county=None),
            row(id="near", title="Software Support Analyst", sub_county="Kasarani"),
        ]
        matches = ranking.rank(rows, profile(), now=NOW)
        assert matches[0].job_id == "near"

    def test_explain_is_one_readable_line(self):
        match = ranking.score_job(row(), profile(), NOW)
        line = ranking.explain(match)
        assert line.startswith("Software Support Analyst")
        assert "matches it" in line


class TestAgainstTheCorpus:
    @pytest.fixture
    def loaded(self):
        conn = db.connect()
        load_corpus(conn, now=NOW)
        seed_profiles(conn)
        yield conn
        conn.close()

    def test_a_fresher_sees_no_experienced_jobs(self, loaded):
        from kazikasi.profile import load_profile

        p = load_profile(loaded, "demo-fresher")
        rows = [dict(r) for r in graph.feed(loaded, limit=500, include_stale=True)]
        matches = ranking.rank(rows, p, now=NOW, limit=500)
        assert matches
        assert all((m.row or {}).get("entry_fit") != "experienced" for m in matches)

    def test_two_profiles_get_differently_ordered_feeds(self, loaded):
        # The eligible set legitimately overlaps — this market is small — but a
        # tailored feed has to reorder it, not just filter it.
        from kazikasi.profile import load_profile

        rows = [dict(r) for r in graph.feed(loaded, limit=500, include_stale=True)]
        fresher = [m.job_id for m in ranking.rank(rows, load_profile(loaded, "demo-fresher"), now=NOW)]
        finance = [m.job_id for m in ranking.rank(rows, load_profile(loaded, "demo-two-years"), now=NOW)]
        assert fresher != finance
        assert fresher[:3] != finance[:3]
        assert fresher[0] != finance[0]

    def test_pay_floor_actually_reorders(self, loaded):
        from dataclasses import replace

        from kazikasi.profile import load_profile

        rows = [dict(r) for r in graph.feed(loaded, limit=500, include_stale=True)]
        fresher = load_profile(loaded, "demo-fresher")
        base = ranking.rank(rows, fresher, now=NOW, limit=8)
        paid = ranking.rank(rows, replace(fresher, min_monthly_pay=60000), now=NOW, limit=8)
        assert [m.job_id for m in base] != [m.job_id for m in paid]
