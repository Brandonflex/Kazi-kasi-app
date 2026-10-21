"""Employer dossiers and the year page.

The dossiers exist because a job card cannot answer "does this employer actually
hire". The tests hold three lines:

* **A merge is visible.** Two spellings of one employer become one page that
  *lists* the names it merged, and a name that does not match is a 404, not a
  guess.
* **A number carries its sample.** A median with n=1 is printed with n=1, and an
  employer that never states pay is reported as never having stated it.
* **Nothing is for sale and nothing is invented** — no employer rating, no
  interview rate, no guessed contact.

The year page is private: not in the sitemap, `noindex`, and its shareable card
never names an employer you applied to.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kazikasi import dossier, recap, serve, tracking
from kazikasi.serve import handle

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
HTML = {"accept": "text/html"}


@pytest.fixture
def conn():
    connection = serve.demo_connection(now=NOW, history=True)
    yield connection
    connection.close()


@pytest.fixture
def plain():
    connection = serve.demo_connection(now=NOW)
    yield connection
    connection.close()


def get(conn, path, query=None, headers=None):
    return handle(
        conn, "GET", path, query or {}, headers=headers or HTML, demo=True, now=NOW
    )


def text(body: str) -> str:
    import re

    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body.split("<main")[-1]))


class TestIdentity:
    def test_legal_form_is_not_identity(self):
        assert dossier.normalise("Haba Data Systems Ltd") == dossier.normalise("HABA DATA SYSTEMS")
        assert dossier.normalise("Sanaa Capital Limited") == "sanaa capital"

    def test_a_real_difference_is_kept(self):
        assert dossier.normalise("Tumaini Health Group") != dossier.normalise("Tumaini Health")

    def test_slugs_are_stable_and_url_safe(self):
        assert dossier.slug("Wanjiku & Associates Advocates") == "wanjiku-associates-advocates"
        assert "/" not in dossier.slug("A/B Ltd")

    def test_resolve_accepts_name_and_slug(self, plain):
        assert dossier.resolve(plain, "Haba Data Systems Ltd") == "haba data systems"
        assert dossier.resolve(plain, "haba-data-systems") == "haba data systems"

    def test_resolve_refuses_to_guess(self, plain):
        assert dossier.resolve(plain, "Definitely Not An Employer") is None
        assert dossier.resolve(plain, "") is None


class TestReport:
    def test_it_counts_what_is_open_and_what_was_seen(self, conn):
        report = dossier.report(conn, "haba-data-systems", now=NOW)
        assert report.live == 3
        assert report.total == 3

    def test_pay_carries_its_sample(self, conn):
        report = dossier.report(conn, "haba-data-systems", now=NOW)
        assert report.pay["stated"] == 3
        assert report.pay["median"] == 70000
        assert report.pay["share"] == 1.0

    def test_an_employer_that_never_states_pay_says_so(self, conn):
        target = None
        for entry in dossier.index(conn, now=NOW):
            report = dossier.report(conn, entry["slug"], now=NOW)
            if report.pay["stated"] == 0:
                target = report
                break
        assert target is not None, "the demo corpus should contain an employer that states no pay"
        assert target.pay["median"] is None
        assert "never stated" in text(get(conn, f"/employer/{target.key.replace(' ', '-')}").body)

    def test_closing_times_are_measured_from_first_sighting(self, conn):
        report = dossier.report(conn, "haba-data-systems", now=NOW)
        assert report.closing["n"] >= 1
        assert report.closing["median_days"] >= 0

    def test_the_families_come_from_our_own_corpus(self, conn):
        report = dossier.report(conn, "haba-data-systems", now=NOW)
        assert ("it", 3) in report.families

    def test_a_flagged_advert_is_counted_not_hidden(self, conn):
        """The flagged advert names nobody, so an employer only gets one if we add it."""
        conn.execute(
            "INSERT INTO jobs (id, title, employer_name, county, status, deadline, "
            "first_seen_at, last_seen_at, scam_flags, source_count) VALUES "
            "('flag-1', 'Urgent Clerk', 'Haba Data Systems Ltd', 'Nairobi', 'open', "
            "'2026-11-01', '2026-10-02T00:00:00+00:00', '2026-10-19T00:00:00+00:00', "
            "'[\"fee_requested\"]', 1)"
        )
        report = dossier.report(conn, "haba-data-systems", now=NOW)
        assert report.flagged == 1
        body = text(get(conn, "/employer/haba-data-systems").body)
        assert "Flagged adverts 1" in body

    def test_an_unknown_employer_returns_nothing(self, conn):
        assert dossier.report(conn, "no-such-employer", now=NOW) is None


class TestIndex:
    def test_it_is_ordered_by_open_roles_then_name(self, conn):
        index = dossier.index(conn, now=NOW)
        assert index[0]["live"] >= index[-1]["live"]
        for left, right in zip(index, index[1:]):
            if left["live"] == right["live"]:
                assert left["name"] <= right["name"]

    def test_it_only_lists_employers_with_a_live_role(self, conn):
        for entry in dossier.index(conn, now=NOW):
            assert entry["live"] >= 1


class TestEmployerPage:
    def test_it_renders_with_the_sample_sizes(self, conn):
        body = get(conn, "/employer/haba-data-systems", {"profile": ["demo-fresher"]}).body
        assert "Haba Data Systems" in body
        assert "n=3" in body
        assert "Never" not in body

    def test_it_says_what_it_cannot_tell_you(self, conn):
        body = text(get(conn, "/employer/haba-data-systems").body)
        assert "Whether they reply" in body
        assert "cannot" in body.lower()

    def test_it_is_not_for_sale(self, conn):
        body = text(get(conn, "/employer/haba-data-systems").body)
        assert "cannot pay to change it" in body

    def test_a_merged_name_is_disclosed(self, conn):
        conn.execute(
            "INSERT INTO jobs (id, title, employer_name, county, status, deadline, "
            "pay_min, pay_max, pay_period, first_seen_at, last_seen_at, scam_flags, "
            "source_count) VALUES ('var-1', 'Records Clerk', 'Haba Data Systems', "
            "'Nairobi', 'open', '2026-11-30', 50000, 50000, 'month', "
            "'2026-10-01T00:00:00+00:00', '2026-10-19T00:00:00+00:00', '[]', 1)"
        )
        body = get(conn, "/employer/haba-data-systems").body
        assert "merges the names" in body
        assert "Haba Data Systems Ltd" in body and "Haba Data Systems," in body

    def test_an_unknown_employer_is_a_404(self, conn):
        assert get(conn, "/employer/not-a-real-employer").status == 404

    def test_the_employers_index_lists_everyone_hiring(self, conn):
        body = get(conn, "/employers").body
        assert "Who is actually hiring" in body
        for entry in dossier.index(conn, now=NOW)[:5]:
            assert f"/employer/{entry['slug']}" in body

    def test_a_job_page_links_to_its_employer(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        body = get(conn, f"/job/{job_id}", {"profile": ["demo-fresher"]}).body
        assert "/employer/" in body


class TestCrawlability:
    def test_employer_pages_are_in_the_sitemap(self, conn):
        body = get(conn, "/sitemap.xml").body
        assert "/employer/haba-data-systems" in body

    def test_the_year_page_never_is(self, conn):
        assert "/year" not in get(conn, "/sitemap.xml").body


class TestTheYear:
    def test_it_counts_what_was_recorded(self, conn):
        profile = serve._profile_or_default(conn, "demo-fresher")
        data = recap.build(conn, profile, now=NOW)
        assert data.seen == 7
        assert data.saved + data.applied <= data.seen
        assert data.has_history

    def test_the_activity_page_and_the_year_agree(self, conn):
        profile = serve._profile_or_default(conn, "demo-fresher")
        data = recap.build(conn, profile, now=NOW)
        body = text(get(conn, "/activity", {"profile": [profile.id]}).body)
        assert f"Activity · {data.seen} jobs touched" in body
        assert f"Applied {data.applied}" in body
        assert f"Saved {data.saved}" in body

    def test_it_names_the_month_you_were_busiest(self, conn):
        profile = serve._profile_or_default(conn, "demo-fresher")
        data = recap.build(conn, profile, now=NOW)
        assert data.most_active in recap.MONTHS
        assert max(data.months, key=lambda pair: pair[1])[0][5:7] in (
            str(recap.MONTHS.index(data.most_active) + 1).zfill(2),
        )

    def test_the_band_is_advertised_minimums_with_an_n(self, conn):
        profile = serve._profile_or_default(conn, "demo-fresher")
        data = recap.build(conn, profile, now=NOW)
        assert data.band_aimed and data.band_aimed_n
        assert data.band_in_scope and data.band_in_scope_n

    def test_the_one_you_almost_took_was_never_applied_to(self, conn):
        profile = serve._profile_or_default(conn, "demo-fresher")
        data = recap.build(conn, profile, now=NOW)
        assert data.almost is not None
        applied = {
            row["job_id"]
            for row in conn.execute(
                "SELECT job_id FROM apply_events WHERE profile_id = ? AND kind = 'applied'",
                (profile.id,),
            )
        }
        assert data.almost["job_id"] not in applied

    def test_it_refuses_to_invent_outcomes(self, conn):
        body = get(conn, "/year", {"profile": ["demo-fresher"]}).body
        assert "No rejection count" in body
        assert "we never learn what anyone was offered" in body.lower() or "We never learn" in body

    def test_the_share_card_names_no_employer(self, conn):
        profile = serve._profile_or_default(conn, "demo-fresher")
        data = recap.build(conn, profile, now=NOW)
        card = "\n".join(recap.card_lines(data))
        employers = {
            row["employer_name"]
            for row in conn.execute("SELECT DISTINCT employer_name FROM jobs")
            if row["employer_name"]
        }
        for employer in employers:
            assert employer not in card
        assert "applied" in card.lower()

    def test_it_is_private(self, conn):
        body = get(conn, "/year", {"profile": ["demo-fresher"]}).body
        assert 'name="robots" content="noindex"' in body

    def test_an_empty_year_explains_itself(self, plain):
        body = get(plain, "/year", {"profile": ["demo-remote"]}).body
        assert "Your year starts when you do" in body
        assert "Nothing recorded yet" in body

    def test_a_year_with_no_data_is_not_a_breakdown(self, plain):
        body = get(plain, "/year", {"profile": ["demo-fresher"], "year": ["2024"]}).body
        assert "Your year starts when you do" in body

    def test_it_is_reachable_from_the_record(self, conn):
        body = get(conn, "/activity", {"profile": ["demo-fresher"]}).body
        assert '/year?profile=demo-fresher' in body


class TestTheDemoHasAPast:
    def test_history_is_opt_in(self, plain):
        assert plain.execute("SELECT COUNT(*) AS c FROM apply_events").fetchone()["c"] == 0

    def test_the_demo_history_is_deterministic(self, conn):
        first = [tuple(row) for row in conn.execute("SELECT job_id, kind, at FROM apply_events ORDER BY id")]
        other = serve.demo_connection(now=NOW, history=True)
        second = [tuple(row) for row in other.execute("SELECT job_id, kind, at FROM apply_events ORDER BY id")]
        other.close()
        assert first == second

    def test_it_only_touches_events(self, conn):
        before = conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"]
        assert before == 0
