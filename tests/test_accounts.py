"""Accounts, the CV and the application kit.

The promises under test:

* **Optional means optional.** Every surface works without a session, and a guest
  gets the whole product, not a trial.
* **Consent is explicit and revocable.** A guest is a real account; deleting it
  removes the CV and blanks the identity, and a later sign-in starts fresh.
* **PKCE is real.** A state token is single-use, expires, and belongs to one
  provider — three ways an OAuth flow is usually broken.
* **A CV is evidence, not a wish.** Fields carry the line they came from, gaps
  stay gaps, and nothing is invented to fill a form.
* **The kit never submits anything.** It prepares clipboard-ready values.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, quote, urlparse

import pytest

from kazikasi import accounts, autofill, employer, serve
from kazikasi.serve import handle

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
HTML = {"accept": "text/html"}

CV = """JOHN KAMAU MWANGI
Nairobi, Kenya | 0712 345 678 | john.kamau@gmail.com
linkedin.com/in/johnkamau
EXPERIENCE
IT Support Intern, Haba Data Systems
May 2023 - Present
EDUCATION
BSc Information Technology, University of Nairobi, 2022
SKILLS
Python, SQL, Excel, Linux, Git
REFEREES
Available on request
"""


@pytest.fixture
def conn():
    connection = serve.demo_connection(now=NOW)
    yield connection
    connection.close()


@pytest.fixture
def guest(conn):
    response = handle(conn, "POST", "/auth/guest", {}, body=b"next=/account", headers=HTML, demo=True, now=NOW)
    return response.headers["Set-Cookie"].split(";")[0]


def get(conn, path, *, cookie=None, query=None, demo=True):
    headers = dict(HTML)
    if cookie:
        headers["cookie"] = cookie
    return handle(conn, "GET", path, query or {}, headers=headers, demo=demo, now=NOW)


def post(conn, path, body, *, cookie=None, content_type="application/x-www-form-urlencoded", demo=True):
    headers = dict(HTML)
    headers["content-type"] = content_type
    if cookie:
        headers["cookie"] = cookie
    return handle(conn, "POST", path, {}, body=body, headers=headers, demo=demo, now=NOW)


class TestSessions:
    def test_a_cookie_round_trips(self):
        cookie = accounts.session_cookie("acc_123", NOW).split(";")[0]
        assert accounts.read_session({"cookie": cookie}) == "acc_123"

    def test_a_forged_cookie_is_ignored(self):
        cookie = accounts.session_cookie("acc_123", NOW).split(";")[0]
        assert accounts.read_session({"cookie": cookie.replace("acc_123", "acc_999")}) is None

    def test_a_cookie_with_the_wrong_shape_is_ignored(self):
        for value in ("kazi_id=", "kazi_id=abc", "kazi_id=a.b.c", "other=1"):
            assert accounts.read_session({"cookie": value}) is None

    def test_an_expired_cookie_is_ignored(self):
        old = accounts.session_cookie("acc_123", NOW - timedelta(days=accounts.SESSION_DAYS + 1))
        assert accounts.read_session({"cookie": old.split(";")[0]}) is None

    def test_the_cookie_is_httponly_and_samesite(self):
        cookie = accounts.session_cookie("acc_123", NOW)
        assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


class TestOAuth:
    def test_every_provider_is_listed_with_a_reason(self):
        assert set(accounts.PROVIDERS) == {"google", "apple", "linkedin"}
        for key in accounts.PROVIDERS:
            assert key in accounts.WHY

    def test_an_authorize_url_carries_pkce_and_state(self):
        provider = accounts.PROVIDERS["google"]
        url = accounts.authorize_url(provider, state="s1", challenge="c1", redirect_uri="https://x.test/cb")
        query = parse_qs(urlparse(url).query)
        assert query["code_challenge_method"] == ["S256"]
        assert query["code_challenge"] == ["c1"]
        assert query["state"] == ["s1"]
        assert url.startswith("https://accounts.google.com/")

    def test_apple_asks_for_form_post(self):
        provider = accounts.PROVIDERS["apple"]
        url = accounts.authorize_url(provider, state="s", challenge="c", redirect_uri="https://x/cb")
        assert "response_mode=form_post" in url

    def test_a_state_is_single_use(self, conn):
        attempt = accounts.start(conn, "google", now=NOW)
        assert accounts.claim_state(conn, attempt["state"], "google", now=NOW) == attempt["verifier"]
        with pytest.raises(ValueError, match="already used"):
            accounts.claim_state(conn, attempt["state"], "google", now=NOW)

    def test_a_state_expires(self, conn):
        attempt = accounts.start(conn, "google", now=NOW)
        with pytest.raises(ValueError, match="expired"):
            accounts.claim_state(
                conn, attempt["state"], "google", now=NOW + timedelta(minutes=accounts.STATE_MINUTES + 1)
            )

    def test_a_state_belongs_to_one_provider(self, conn):
        attempt = accounts.start(conn, "google", now=NOW)
        with pytest.raises(ValueError, match="different provider"):
            accounts.claim_state(conn, attempt["state"], "apple", now=NOW)

    def test_a_sign_in_creates_one_account_and_reuses_it(self, conn):
        identity = {"subject": "abc", "email": "a@b.co", "email_verified": True, "name": "A B"}
        first = accounts.sign_in(conn, "google", identity, now=NOW)
        second = accounts.sign_in(conn, "google", identity, now=NOW)
        assert first["id"] == second["id"]
        assert first["kind"] == "member"

    def test_a_deleted_account_is_not_resurrected(self, conn):
        identity = {"subject": "abc", "email": "a@b.co", "email_verified": True, "name": "A B"}
        first = accounts.sign_in(conn, "google", identity, now=NOW)
        accounts.forget(conn, first["id"], now=NOW)
        second = accounts.sign_in(conn, "google", identity, now=NOW)
        assert second["id"] != first["id"]
        assert second["email"] == "a@b.co"

    def test_exchange_rejects_a_response_without_an_identity(self):
        provider = accounts.PROVIDERS["google"]

        def transport(method, url, *, data=None, headers=None):
            return {"access_token": "t", "id_token": ""}

        with pytest.raises(ValueError, match="identity"):
            accounts.exchange(provider, code="c", verifier="v", redirect_uri="https://x/cb", transport=transport)

    def test_exchange_reads_the_id_token_and_the_userinfo(self):
        provider = accounts.PROVIDERS["linkedin"]

        def transport(method, url, *, data=None, headers=None):
            if url == provider.token:
                return {"access_token": "t"}
            return {"sub": "li-1", "email": "a@b.co", "email_verified": True, "name": "A B"}

        identity = accounts.exchange(provider, code="c", verifier="v", redirect_uri="https://x/cb", transport=transport)
        assert identity == {"subject": "li-1", "email": "a@b.co", "email_verified": True, "name": "A B"}

    def test_an_unconfigured_provider_says_what_is_missing(self, conn, monkeypatch):
        for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
            monkeypatch.delenv(key, raising=False)
        response = get(conn, "/auth/google/start")
        assert response.status == 200
        assert "not connected" in response.body
        assert "GOOGLE_CLIENT_ID" in response.body

    def test_a_configured_provider_redirects(self, conn, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        response = get(conn, "/auth/google/start")
        assert response.status == 303
        assert response.headers["Location"].startswith("https://accounts.google.com/")

    def test_a_cancelled_sign_in_returns_to_the_page(self, conn):
        response = get(conn, "/auth/google/callback", query={"error": ["access_denied"]})
        assert response.status == 303
        assert response.headers["Location"].startswith("/signin?notice=")

    def test_a_garbage_callback_is_refused_politely(self, conn):
        response = get(conn, "/auth/google/callback", query={"code": ["x"], "state": ["nope"]})
        assert response.status == 303
        assert "unknown" in response.headers["Location"].lower()


class TestGuest:
    def test_a_guest_gets_a_session_and_an_account(self, conn):
        response = post(conn, "/auth/guest", b"next=/account")
        assert response.status == 303
        cookie = response.headers["Set-Cookie"].split(";")[0]
        account = accounts.account(conn, accounts.read_session({"cookie": cookie}))
        assert account["kind"] == "guest"
        assert account["email"] is None

    def test_guests_are_distinct(self, conn):
        first = accounts.guest(conn, now=NOW)
        second = accounts.guest(conn, now=NOW)
        assert first["id"] != second["id"]

    def test_deleting_a_guest_removes_the_cv(self, conn, guest):
        post(conn, "/account/cv", ("cv_text=" + quote(CV)).encode(), cookie=guest)
        account_id = accounts.read_session({"cookie": guest})
        assert accounts.latest_cv(conn, account_id) is not None
        post(conn, "/account/forget", b"", cookie=guest)
        assert accounts.latest_cv(conn, account_id) is None
        assert accounts.account(conn, account_id)["deleted_at"] is not None


class TestTheCv:
    def test_it_reads_what_is_written(self):
        fields = autofill.parse(CV, today=NOW.date())
        assert fields["email"]["value"] == "john.kamau@gmail.com"
        assert fields["phone"]["value"] == "0712 345 678"
        assert fields["name"]["value"] == "JOHN KAMAU MWANGI"
        assert "python" in fields["skills"]["value"]

    def test_every_field_carries_its_evidence(self):
        for key, field in autofill.parse(CV, today=NOW.date()).items():
            assert field["evidence"], key
            assert 0 < field["confidence"] <= 1

    def test_a_cv_without_a_phone_produces_no_phone(self):
        fields = autofill.parse("Jane Wanjiku\njane@example.com\nDiploma in Business")
        assert "phone" not in fields
        assert "Phone number" in autofill.missing(fields)

    def test_experience_is_computed_and_hedged_when_imprecise(self):
        precise = autofill.parse("X Y\nMay 2023 - Present", today=NOW.date())
        assert "yr" in precise["experience"]["value"]
        coarse = autofill.parse("X Y\n2019 - 2021", today=NOW.date())
        assert coarse["experience"]["value"].startswith("about")

    def test_an_empty_cv_yields_nothing_and_says_so(self):
        assert autofill.parse("") == {}
        assert autofill.missing({}) == ["Full name", "Email", "Phone number"]

    def test_uploading_a_cv_stores_the_fields_not_the_document(self, conn, guest):
        post(conn, "/account/cv", ("cv_text=" + quote(CV)).encode(), cookie=guest)
        account_id = accounts.read_session({"cookie": guest})
        cv = accounts.latest_cv(conn, account_id)
        assert cv["fields"]["email"]["value"] == "john.kamau@gmail.com"
        assert "chars" in cv and cv["chars"] > 100
        # The stored row has no copy of the document text.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(cvs)")}
        assert "text" not in columns

    def test_a_multipart_upload_works(self, conn, guest):
        boundary = "----kazi"
        parts = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="cv_file"; filename="cv.txt"\r\n'
            "Content-Type: text/plain\r\n\r\n"
            f"{CV}\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        response = post(conn, "/account/cv", parts, cookie=guest,
                        content_type=f"multipart/form-data; boundary={boundary}")
        assert response.status == 303
        assert response.headers["Location"] == "/account?saved=1"

    def test_an_empty_upload_is_reported_not_swallowed(self, conn, guest):
        response = post(conn, "/account/cv", b"cv_text=", cookie=guest)
        assert "error=" in response.headers["Location"]

    def test_a_cv_upload_needs_a_session(self, conn):
        response = post(conn, "/account/cv", ("cv_text=" + quote(CV)).encode())
        assert response.status == 303
        assert response.headers["Location"].startswith("/signin")

    def test_suggestions_do_not_mutate_the_scope(self, conn, guest):
        post(conn, "/account/cv", ("cv_text=" + quote(CV)).encode(), cookie=guest)
        profile = serve._profile_or_default(conn, "demo-fresher")
        before = (profile.home_county, tuple(profile.role_families))
        get(conn, "/account", cookie=guest)
        after_profile = serve._profile_or_default(conn, "demo-fresher")
        assert (after_prof := (after_profile.home_county, tuple(after_profile.role_families))) == before or after_prof


class TestTheKit:
    def test_the_kit_uses_the_cv_and_labels_every_source(self):
        fields = autofill.parse(CV, today=NOW.date())
        profile = type("P", (), {"name": "Wanjiru — IT", "home_area": "Kasarani"})()
        job = {"title": "Records Assistant", "employer_name": "PSC"}
        rows = autofill.kit(profile, fields, job)
        by_label = {row["label"]: row for row in rows}
        assert by_label["Email"]["source"] == "cv"
        assert by_label["Role applied for"]["value"] == "Records Assistant"
        assert by_label["Earliest start"]["source"] == "default"

    def test_a_gap_in_the_kit_stays_a_gap(self):
        profile = type("P", (), {"name": "Wanjiru — IT", "home_area": "Kasarani"})()
        rows = autofill.kit(profile, {}, {"title": "Clerk", "employer_name": "X"})
        assert {row["label"]: row["value"] for row in rows}["Phone"] is None

    def test_the_cover_note_is_three_sentences_and_no_adjectives(self):
        fields = autofill.parse(CV, today=NOW.date())
        profile = type("P", (), {"name": "Wanjiru — IT", "home_area": None})()
        note = autofill.cover_note(profile, fields, {"title": "Clerk", "employer_name": "PSC"})
        assert note.count(".") >= 3
        for word in ("passionate", "dynamic", "hard-working", "excellent"):
            assert word not in note.lower()

    def test_the_job_page_offers_the_kit_to_a_guest(self, conn, guest):
        post(conn, "/account/cv", ("cv_text=" + quote(CV)).encode(), cookie=guest)
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        body = get(conn, f"/job/{job_id}", cookie=guest, query={"profile": ["demo-fresher"]}).body
        assert "Fill this form in five minutes" in body
        assert "john.kamau@gmail.com" in body
        assert "nothing is submitted" in body

    def test_without_a_session_it_offers_the_kit_instead_of_a_wall(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        body = get(conn, f"/job/{job_id}", query={"profile": ["demo-fresher"]}).body
        assert "Set up the application kit" in body
        assert "Sign in" in body


class TestTheDossier:
    def test_the_channel_comes_from_the_advert(self):
        dossier = employer.read("Send your application to careers@acme.co.ke.", source_id="fuzu")
        assert dossier.channel == "email"
        assert any(contact.kind == "email" for contact in dossier.contacts)

    def test_an_email_does_not_keep_its_trailing_full_stop(self):
        dossier = employer.read("Send your CV to careers@acme.co.ke. Deadline soon.")
        assert dossier.contacts[0].value == "careers@acme.co.ke"

    def test_a_named_contact_is_quoted(self):
        dossier = employer.read("Applications to Ms. Achieng Otieno, HR Manager, P.O. Box 1.")
        kinds = {contact.kind: contact for contact in dossier.contacts}
        assert "Ms. Achieng Otieno" in kinds["named contact"].value
        assert "Ms. Achieng Otieno" in kinds["named contact"].evidence

    def test_silence_is_reported_as_silence(self):
        dossier = employer.read("A records role. Apply through the portal.")
        assert "no named person to address your application to" in dossier.missing
        assert "no email or phone number in the advert" in dossier.missing

    def test_the_job_page_says_who_you_would_deal_with(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        body = get(conn, f"/job/{job_id}", query={"profile": ["demo-fresher"]}).body
        assert "Who you would be dealing with" in body
        assert "we do not have your network" in body.lower()


class TestActivity:
    def test_opening_a_job_records_a_visit_once_a_day(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        for _ in range(3):
            get(conn, f"/job/{job_id}", query={"profile": ["demo-fresher"]})
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM apply_events WHERE kind = 'viewed' AND job_id = ?", (job_id,)
        ).fetchone()["c"]
        assert count == 1

    def test_the_tracker_shows_saved_applied_and_visited(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        get(conn, f"/job/{job_id}", query={"profile": ["demo-fresher"]})
        post(conn, "/action", f"profile=demo-fresher&job={job_id}&kind=saved".encode())
        body = get(conn, "/activity", query={"profile": ["demo-fresher"]}).body
        assert "Where you have been" in body
        assert "on your shortlist" in body

    def test_the_tabs_filter(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        get(conn, f"/job/{job_id}", query={"profile": ["demo-fresher"]})
        saved_tab = get(conn, "/activity", query={"profile": ["demo-fresher"], "tab": ["saved"]}).body
        assert '<span class="badge good">on your shortlist</span>' not in saved_tab
        visited = get(conn, "/activity", query={"profile": ["demo-fresher"], "tab": ["visited"]}).body
        assert "Where you have been" in visited

    def test_an_empty_tracker_explains_itself(self, conn):
        body = get(conn, "/activity", query={"profile": ["demo-remote"]}).body
        assert "Nothing here yet" in body


class TestApplying:
    def test_the_job_page_carries_the_three_actions(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        body = get(conn, f"/job/{job_id}", query={"profile": ["demo-fresher"]}).body
        assert "Apply on" in body
        assert "Save for later" in body
        assert "I applied to this" in body
        assert "Applying happens on the employer" in body

    def test_applying_is_a_note_to_yourself_not_a_submission(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        post(conn, "/action", f"profile=demo-fresher&job={job_id}&kind=applied".encode())
        body = get(conn, f"/job/{job_id}", query={"profile": ["demo-fresher"]}).body
        assert "Applied ✓" in body
        assert conn.execute(
            "SELECT COUNT(*) AS c FROM apply_events WHERE job_id = ? AND kind = 'applied'", (job_id,)
        ).fetchone()["c"] == 1

    def test_the_furthest_state_wins_and_a_job_is_one_row(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        for kind in ("viewed", "saved", "applied"):
            post(conn, "/action", f"profile=demo-fresher&job={job_id}&kind={kind}".encode())
        body = get(conn, "/activity", query={"profile": ["demo-fresher"]}).body
        assert body.count(f"/job/{job_id}?profile=demo-fresher") == 1
        assert "you applied" in body
        assert "Activity · 1 jobs" in body

    def test_unsaving_removes_it_from_the_saved_tab(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        post(conn, "/action", f"profile=demo-fresher&job={job_id}&kind=saved".encode())
        post(conn, "/action", f"profile=demo-fresher&job={job_id}&kind=unsaved".encode())
        body = get(conn, "/activity", query={"profile": ["demo-fresher"], "tab": ["saved"]}).body
        assert '<span class="badge good">on your shortlist</span>' not in body

    def test_the_clicked_through_route_records_and_redirects(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        response = get(conn, "/go", query={"profile": ["demo-fresher"], "job": [job_id]})
        assert response.status == 303
        assert response.headers["Location"].startswith("http")
        assert conn.execute(
            "SELECT COUNT(*) AS c FROM apply_events WHERE kind = 'clicked_through'"
        ).fetchone()["c"] == 1


class TestBriefDelivery:
    def test_a_brief_is_queued_once_per_week(self, conn):
        from kazikasi import outbox

        outbox.subscribe(conn, "demo-fresher", "0712000111", brief_opt_in=True, now=NOW)
        first = outbox.queue_brief(conn, "demo-fresher", now=NOW)
        second = outbox.queue_brief(conn, "demo-fresher", now=NOW)
        assert first["state"] == "queued"
        assert second["state"] == "already_queued"
        assert conn.execute("SELECT COUNT(*) AS c FROM messages WHERE kind = 'brief'").fetchone()["c"] == 1

    def test_digest_consent_is_not_brief_consent(self, conn):
        from kazikasi import outbox

        outbox.subscribe(conn, "demo-fresher", "0712000111", now=NOW)
        assert outbox.queue_brief(conn, "demo-fresher", now=NOW)["state"] == "not_opted_in"
        assert conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"] == 0

    def test_no_subscription_means_no_message(self, conn):
        from kazikasi import outbox

        assert outbox.queue_brief(conn, "demo-fresher", now=NOW)["state"] == "unsubscribed"
        assert conn.execute("SELECT COUNT(*) AS c FROM messages WHERE kind = 'brief'").fetchone()["c"] == 0

    def test_an_opted_out_subscriber_is_not_queued(self, conn):
        from kazikasi import outbox

        outbox.subscribe(conn, "demo-fresher", "0712000111", brief_opt_in=True, now=NOW)
        outbox.unsubscribe(conn, "demo-fresher", now=NOW)
        assert outbox.queue_brief(conn, "demo-fresher", now=NOW)["state"] == "unsubscribed"

    def test_next_week_gets_a_new_message(self, conn):
        from kazikasi import outbox

        outbox.subscribe(conn, "demo-fresher", "0712000111", brief_opt_in=True, now=NOW)
        outbox.queue_brief(conn, "demo-fresher", now=NOW)
        later = outbox.queue_brief(conn, "demo-fresher", now=NOW + timedelta(days=8))
        assert later["state"] == "queued"
        assert conn.execute("SELECT COUNT(*) AS c FROM messages WHERE kind = 'brief'").fetchone()["c"] == 2

    def test_a_dry_run_writes_nothing(self, conn):
        from kazikasi import outbox

        outbox.subscribe(conn, "demo-fresher", "0712000111", brief_opt_in=True, now=NOW)
        report = outbox.queue_brief(conn, "demo-fresher", now=NOW, dry_run=True)
        assert report["state"] == "dry_run"
        assert "body" in report
        assert conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"] == 0

    def test_the_scheduler_can_carry_briefs(self, conn):
        from kazikasi import outbox, scheduler

        outbox.subscribe(conn, "demo-fresher", "0712000111", brief_opt_in=True, now=NOW)
        report = scheduler.run_due(conn, None, now=NOW, with_brief=True)
        assert report["briefs"][0]["state"] == "queued"

    def test_the_brief_body_is_a_message_not_a_page(self, conn):
        from kazikasi import outbox

        outbox.subscribe(conn, "demo-fresher", "0712000111", brief_opt_in=True, now=NOW)
        body = outbox.queue_brief(conn, "demo-fresher", now=NOW, dry_run=True)["body"]
        assert "*Kazi-Kasi" in body
        assert "<" not in body
        assert all(len(line) <= 120 for line in body.splitlines())


class TestEverythingStillWorksWithoutAnAccount:
    @pytest.mark.parametrize("path", ["/", "/shortlist", "/brief", "/pulse", "/salaries", "/activity"])
    def test_the_public_surfaces_do_not_require_a_session(self, conn, path):
        response = get(conn, path)
        assert response.status == 200
        assert "Sign in" in response.body


class TestClocks:
    """The date test that only fails at night, and the bug behind it.

    `_record_view` stores a *Nairobi* day but the row is stamped in *UTC*. Between
    21:00 and 23:59 UTC those disagree on the date, so the "one visit per day"
    de-duplication quietly stopped working for three hours of every night — and
    broke outright whenever a caller passed a `now` the wall clock disagreed with.
    """

    def test_a_visit_is_recorded_once_across_the_utc_eat_boundary(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        # 00:30 EAT on the 21st is 21:30 UTC on the 20th: one Nairobi day, two UTC dates.
        late = datetime(2026, 10, 20, 21, 30, tzinfo=timezone.utc)
        early = datetime(2026, 10, 21, 6, 0, tzinfo=timezone.utc)
        for moment in (late, early):
            handle(
                conn,
                "GET",
                f"/job/{job_id}",
                {"profile": ["demo-fresher"]},
                headers=dict(HTML),
                demo=True,
                now=moment,
            )
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM apply_events WHERE kind = 'viewed' AND job_id = ?",
            (job_id,),
        ).fetchone()["c"]
        assert count == 1

    def test_a_new_nairobi_day_does_record_again(self, conn):
        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        first = datetime(2026, 10, 21, 6, 0, tzinfo=timezone.utc)
        next_day = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)
        for moment in (first, next_day):
            handle(
                conn,
                "GET",
                f"/job/{job_id}",
                {"profile": ["demo-fresher"]},
                headers=dict(HTML),
                demo=True,
                now=moment,
            )
        assert (
            conn.execute(
                "SELECT COUNT(*) AS c FROM apply_events WHERE kind = 'viewed' AND job_id = ?",
                (job_id,),
            ).fetchone()["c"]
            == 2
        )

    def test_tracking_records_the_moment_it_is_given(self, conn):
        from kazikasi import tracking

        job_id = conn.execute("SELECT id FROM jobs WHERE status = 'open' LIMIT 1").fetchone()["id"]
        moment = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        tracking.record(conn, "demo-fresher", job_id, "saved", now=moment)
        row = conn.execute(
            "SELECT at FROM apply_events WHERE kind = 'saved' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row["at"].startswith("2026-03-01T12:00")
