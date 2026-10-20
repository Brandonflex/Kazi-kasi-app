"""Search: the feed, narrowed by hand.

The feed answers "what should I look at first?". This answers "show me the
internships in Nairobi closing in the next ten days that pay something" — which
is what someone asks when the ranked five are not what they had in mind.

Two rules get the most attention here, because both are easy to get wrong in a
direction that quietly lies:

* a pay floor keeps adverts that state no pay, and the page *says how many* —
  silently dropping them would hide most of the market; silently passing them off
  as paid would be worse;
* roles outside the person's constraints are excluded by default, and when asked
  for they are labelled with the blocker that failed and kept out of the main
  count.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from kazikasi import search, serve, shortlist, tracking
from kazikasi.serve import handle

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    connection = serve.demo_connection(now=NOW)
    yield connection
    connection.close()


@pytest.fixture
def profile(conn):
    return serve._profile_or_default(conn, "demo-fresher")


def page(conn, query=None, *, profile_id="demo-fresher"):
    params = {"profile": [profile_id], **(query or {})}
    return handle(conn, "GET", "/search", params, demo=True, now=NOW).body


class TestTheQuery:
    def test_terms_are_lower_cased_deduplicated_and_capped(self):
        assert search.terms("  Software  software NAIROBI ") == ["software", "nairobi"]
        assert search.terms("a ab abc") == ["ab", "abc"]  # single letters are noise
        assert len(search.terms(" ".join(f"w{index}" for index in range(20)))) == search.MAX_TERMS

    def test_a_term_can_match_the_employer_or_the_area(self, conn, profile):
        by_employer = search.run(conn, profile, query="haba", now=NOW)
        by_area = search.run(conn, profile, query="westlands", now=NOW)
        assert by_employer.matches and by_area.matches
        assert by_employer.matches[0].row["employer_name"].startswith("Haba")
        assert by_area.matches[0].row["sub_county"] == "Westlands"

    def test_two_words_both_have_to_match(self, conn, profile):
        both = search.run(conn, profile, query="software nairobi", now=NOW)
        assert both.matches
        for item in both.matches:
            document = search.haystack(item.row)
            assert "software" in document and "nairobi" in document

    def test_an_unknown_word_returns_nothing_rather_than_something(self, conn, profile):
        assert search.run(conn, profile, query="astrophysics", now=NOW).is_empty

    def test_the_empty_query_returns_the_whole_scope(self, conn, profile):
        everything = search.run(conn, profile, now=NOW)
        assert everything.total >= 5
        assert not everything.is_filtered


class TestTheFilters:
    def test_county_is_exact_not_fuzzy(self, conn, profile):
        nairobi = search.run(conn, profile, county="Nairobi", now=NOW)
        assert nairobi.matches
        assert all(item.row["county"] == "Nairobi" for item in nairobi.matches)
        assert search.run(conn, profile, county="Mombasa", now=NOW).is_empty

    def test_role_family_filters_on_the_rankers_own_answer(self, conn, profile):
        it_roles = search.run(conn, profile, family="it", now=NOW)
        assert it_roles.matches
        assert all("it" in item.match.families for item in it_roles.matches)

    def test_a_deadline_horizon_excludes_undated_and_distant_roles(self, conn, profile):
        soon = search.run(conn, profile, deadline_days=7, now=NOW)
        horizon = NOW + timedelta(days=7)
        for item in soon.matches:
            assert item.row["deadline"]
            day = datetime.fromisoformat(item.row["deadline"][:10])
            assert day.replace(tzinfo=timezone.utc) <= horizon

    def test_remote_means_remote_or_hybrid(self, conn, profile):
        remote = search.run(conn, profile, remote=True, now=NOW)
        assert remote.matches
        assert all(item.row["work_mode"] in ("remote", "hybrid") for item in remote.matches)

    def test_a_pay_floor_drops_low_pay_and_keeps_the_unstated_with_a_count(self, conn, profile):
        floored = search.run(conn, profile, pay_floor=80000, now=NOW)
        for item in floored.matches:
            if item.row.get("pay_min") is not None:
                assert item.row["pay_min"] >= 80000
        assert floored.pay_unstated == sum(
            1 for item in floored.matches if item.row.get("pay_min") is None
        )

    def test_employment_type_is_a_fact_filter(self, conn, profile):
        internships = search.run(conn, profile, employment_type="internship", now=NOW)
        assert internships.matches
        assert all(item.row["employment_type"] == "internship" for item in internships.matches)


class TestTheScope:
    def test_a_blocked_role_is_not_in_the_results_by_default(self, conn, profile):
        default = search.run(conn, profile, now=NOW)
        assert all(not item.blocked for item in default.matches)

    def test_it_is_returned_separately_when_asked_for(self, conn, profile):
        wide = search.run(conn, profile, include_blocked=True, now=NOW)
        assert wide.blocked, "the demo corpus has roles a fresher cannot take"
        assert all(item.blocked and item.match.blockers for item in wide.blocked)
        assert all(not item.blocked for item in wide.matches)

    def test_blocked_roles_are_counted_separately_but_still_counted(self, conn, profile):
        wide = search.run(conn, profile, include_blocked=True, now=NOW)
        narrow = search.run(conn, profile, now=NOW)
        assert len(wide.matches) == wide.narrowed - len(wide.blocked)
        # The count survives even when the rows are not rendered: the page can say
        # "8 outside your constraints" without listing them.
        assert narrow.blocked_count == len(wide.blocked)
        assert narrow.narrowed == wide.narrowed

    def test_a_dismissed_job_never_appears(self, conn, profile):
        first = search.run(conn, profile, now=NOW).matches[0]
        tracking.record(conn, profile.id, first.match.job_id, "dismissed")
        after = search.run(conn, profile, now=NOW)
        assert first.match.job_id not in {item.match.job_id for item in after.matches}

    def test_saved_and_applied_travel_with_the_row(self, conn, profile):
        job = search.run(conn, profile, now=NOW).matches[0].match.job_id
        shortlist.save(conn, profile.id, job)
        tracking.record(conn, profile.id, job, "applied")
        found = search.run(conn, profile, query="", now=NOW)
        item = next(entry for entry in found.matches if entry.match.job_id == job)
        assert item.saved and item.applied


class TestTheFacets:
    def test_facets_come_from_the_corpus_not_a_hard_coded_list(self, conn, profile):
        found = search.run(conn, profile, now=NOW)
        assert found.counties and found.families
        assert sum(count for _, count in found.counties) == len(found.matches)
        assert all(isinstance(name, str) and name for name, _ in found.families)

    def test_facets_exclude_out_of_scope_roles(self, conn, profile):
        narrow = search.run(conn, profile, now=NOW)
        wide = search.run(conn, profile, include_blocked=True, now=NOW)
        assert narrow.counties == wide.counties


class TestThePage:
    def test_it_renders_server_side_with_a_form(self, conn):
        body = page(conn)
        assert '<form method="get" action="/search"' in body
        assert 'name="q"' in body and 'name="pay"' in body and 'name="days"' in body

    def test_it_echoes_the_query_back(self, conn):
        assert 'value="software"' in page(conn, {"q": ["software"]})

    def test_the_count_is_on_the_page(self, conn):
        body = page(conn, {"q": ["software"]})
        assert "live roles match" in body

    def test_an_empty_result_explains_itself_and_offers_a_way_out(self, conn):
        body = page(conn, {"q": ["astrophysics"]})
        assert "Nothing matches that" in body
        assert "drop the pay floor" not in body  # no floor was set
        assert "every live role in" in body

    def test_a_pay_floor_that_keeps_unstated_pay_says_so(self, conn):
        body = page(conn, {"pay": ["80000"]})
        assert "do not state pay" in body

    def test_out_of_scope_roles_are_behind_a_toggle(self, conn):
        default = page(conn)
        assert "Outside your constraints" not in default
        assert "outside my scope" in default or "outside my constraints" in default
        wide = page(conn, {"blocked": ["1"]})
        assert "Outside your constraints" in wide
        assert "Out of reach because" in wide

    def test_it_is_noindex(self, conn):
        assert 'name="robots" content="noindex"' in page(conn)

    def test_it_is_not_in_the_sitemap_or_robots(self, conn):
        sitemap = handle(conn, "GET", "/sitemap.xml", {}, now=NOW).body
        assert "/search" not in sitemap
        assert "Disallow: /search" in handle(conn, "GET", "/robots.txt", {}, now=NOW).body

    def test_a_partial_or_junk_number_does_not_five_hundred(self, conn):
        for value in ("abc", "-4", "1e9", ""):
            response = handle(conn, "GET", "/search", {"days": [value], "pay": [value]}, demo=True, now=NOW)
            assert response.status == 200

