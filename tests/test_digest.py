"""The digest is editorial: five cards, closing soonest, nothing repeated.

Most of these tests are about what a person *doesn't* receive — a re-sent job, a
second copy of a message, a card that repeats its own facts — because a push
notification is judged by its worst day, not its best.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from kazikasi import digest as dg
from kazikasi.digest import EAT

NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
TODAY = date(2026, 10, 20)


class Match:
    """The little bit of ``ranking.Match`` the selector actually touches."""

    def __init__(self, job_id, title="Data Entry Clerk", score=0.5, eligible=True, reasons=None, **row):
        self.job_id = job_id
        self.title = title
        self.employer = "Jumuia Data Services"
        self.score = score
        self.eligible = eligible
        self.reasons = reasons if reasons is not None else ["matches admin"]
        self.row = {
            "id": job_id,
            "title": title,
            "employer_name": self.employer,
            "county": "Nairobi",
            "sub_county": "Starehe",
            "entry_fit": "open_to_freshers",
            "deadline": None,
            "pay_min": None,
            "pay_max": None,
            "pay_period": "month",
            "scam_flags": "[]",
            "status": "open",
            **row,
        }


def pick(matches, **kwargs):
    kwargs.setdefault("profile_id", "demo-fresher")
    kwargs.setdefault("profile_name", "Achieng")
    kwargs.setdefault("for_date", TODAY)
    return dg.select(matches, **kwargs)


class TestNormalisation:
    @pytest.mark.parametrize(
        "given",
        ["0712345678", "0712 345 678", "+254712345678", "254712345678", "712345678", "+254 712 345 678"],
    )
    def test_accepts_the_shapes_people_actually_type(self, given):
        assert dg.normalise_msisdn(given) == "+254712345678"

    def test_safaricom_and_airtel_prefixes(self):
        assert dg.normalise_msisdn("0110000000") == "+254110000000"

    @pytest.mark.parametrize(
        "given",
        [
            "071234567",      # one digit short — a typo
            "07123456789",    # one digit long
            "0812345678",     # not a Kenyan mobile prefix
            "+447700900123",  # a UK number
            "",
            "not a number",
        ],
    )
    def test_refuses_anything_it_would_have_to_guess(self, given):
        with pytest.raises(ValueError):
            dg.normalise_msisdn(given)

    def test_mask_keeps_the_last_four_only(self):
        masked = dg.mask_msisdn("+254712345678")
        assert masked == "+2547•••5678"
        assert "1234" not in masked

    def test_hash_is_stable_and_not_the_number(self):
        one = dg.hash_msisdn("+254712345678")
        assert one == dg.hash_msisdn("+254712345678")
        assert one != dg.hash_msisdn("+254712345679")
        assert "254" not in one


class TestQuoting:
    def test_shorten_cuts_at_a_word_boundary(self):
        assert dg.shorten("Assistant Records Management Officer", 20) == "Assistant Records…"

    def test_shorten_leaves_short_text_alone(self):
        assert dg.shorten("Clerk", 20) == "Clerk"

    def test_one_line_flattens_newlines_and_zero_width(self):
        assert dg.one_line("Data\nEntry\u200b  Clerk\t") == "Data Entry Clerk"

    @pytest.mark.parametrize(
        "days,expected",
        [
            (-1, "closed"),
            (0, "closes today"),
            (1, "closes tomorrow"),
            (5, "closes in 5 days"),
            (7, "closes in 7 days"),
            (16, "closes 05 Nov"),
        ],
    )
    def test_deadline_phrases(self, days, expected):
        row = {"deadline": (TODAY + timedelta(days=days)).isoformat()}
        assert dg.deadline_phrase(row, TODAY) == expected

    def test_no_deadline_is_not_invented(self):
        assert dg.deadline_phrase({"deadline": None}, TODAY) is None
        assert dg.deadline_phrase({"deadline": "sometime"}, TODAY) is None

    def test_pay_line_handles_ranges_and_single_values(self):
        assert dg.pay_line({"pay_min": 32000, "pay_max": 45000}) == "KES 32,000–45,000/month"
        assert dg.pay_line({"pay_min": 41000, "pay_max": 41000}) == "KES 41,000/month"
        assert dg.pay_line({}) is None


class TestSelection:
    def test_caps_the_list(self):
        matches = [Match(f"j{i}", score=0.9 - i / 100) for i in range(12)]
        assert len(pick(matches).items) == dg.DEFAULT_MAX_ITEMS

    def test_never_re_sends_a_job(self):
        digest = pick([Match("j1"), Match("j2")], already_sent={"j1"})
        assert [item.job_id for item in digest.items] == ["j2"]
        assert digest.skipped["already_sent"] == 1

    def test_skips_what_was_acted_on_or_dismissed(self):
        digest = pick(
            [Match("j1"), Match("j2"), Match("j3")],
            acted_on={"j1"},
            dismissed={"j2"},
        )
        assert [item.job_id for item in digest.items] == ["j3"]

    def test_skips_scam_flagged_and_closed(self):
        digest = pick(
            [
                Match("j1", scam_flags='["asks_for_fee"]'),
                Match("j2", status="closed"),
                Match("j3"),
            ]
        )
        assert [item.job_id for item in digest.items] == ["j3"]
        assert digest.skipped["flagged"] == 1

    def test_blocked_matches_never_reach_a_phone(self):
        digest = pick([Match("j1", eligible=False), Match("j2")])
        assert [item.job_id for item in digest.items] == ["j2"]

    def test_closing_soonest_comes_first(self):
        matches = [
            Match("later", score=0.8, deadline="2026-11-15"),
            Match("soon", score=0.4, deadline="2026-10-24"),
            Match("undated", score=0.9, deadline=None),
        ]
        assert [item.job_id for item in pick(matches).items] == ["soon", "later", "undated"]

    def test_same_deadline_falls_back_to_score(self):
        matches = [
            Match("low", score=0.3, deadline="2026-10-25"),
            Match("high", score=0.7, deadline="2026-10-25"),
        ]
        assert [item.job_id for item in pick(matches).items] == ["high", "low"]

    def test_a_duplicate_job_id_is_counted_once(self):
        digest = pick([Match("j1"), Match("j1")])
        assert len(digest.items) == 1

    def test_positions_are_one_based_for_reading(self):
        digest = pick([Match("j1"), Match("j2")])
        assert [item.position for item in digest.items] == [1, 2]

    def test_empty_is_empty_not_an_apology(self):
        digest = pick([])
        assert digest.is_empty
        assert dg.render_digest(digest) == ""


class TestRendering:
    def test_a_card_is_four_short_lines(self):
        card = dg.render_card(
            dg.DigestItem(
                job_id="j1",
                title="Data Entry Clerk",
                employer="Jumuia Data Services",
                score=0.6,
                reasons=["matches admin", "pays above your KES 40,000 floor"],
                row={
                    "county": "Nairobi",
                    "sub_county": "Starehe",
                    "deadline": "2026-10-25",
                    "entry_fit": "open_to_freshers",
                    "pay_min": 32000,
                    "pay_max": None,
                    "pay_period": "month",
                },
            ),
            TODAY,
            number=1,
        )
        lines = card.split("\n")
        assert lines[0] == "1. *Data Entry Clerk*"
        assert "Starehe, Nairobi" in lines[2]
        assert "closes in 5 days" in lines[2]
        assert "open to freshers" in lines[2]
        assert lines[3] == "pays above your KES 40,000 floor"

    def test_the_reason_never_repeats_a_fact_already_on_the_card(self):
        item = dg.DigestItem(
            job_id="j1",
            title="Clerk",
            employer="County",
            score=0.5,
            reasons=["closes in 5 days", "matches admin"],
            row={"county": "Nairobi", "deadline": "2026-10-25"},
        )
        card = dg.render_card(item, TODAY)
        assert card.count("closes in 5 days") == 1

    def test_a_long_reason_is_trimmed_not_wrapped(self):
        item = dg.DigestItem(
            job_id="j1",
            title="Clerk",
            employer=None,
            score=0.5,
            reasons=["matches " + "very " * 60],
            row={"county": "Nairobi"},
        )
        card = dg.render_card(item, TODAY)
        assert all(len(line) <= 100 for line in card.split("\n"))

    def test_no_reason_means_no_blank_line(self):
        item = dg.DigestItem(
            job_id="j1",
            title="Clerk",
            employer=None,
            score=0.5,
            reasons=["checked against 31 live jobs"],
            row={"county": "Nairobi"},
        )
        assert not dg.render_card(item, TODAY).endswith("\n")

    def test_digest_opens_with_the_count_and_closes_with_stop(self):
        digest = pick([Match("j1"), Match("j2")])
        body = dg.render_digest(digest, link_base="https://kazi.example")
        assert body.splitlines()[0] == "*Kazi-Kasi* — 2 jobs for you today"
        assert body.endswith("Reply STOP to stop these. Reply HELP for the web feed.")
        assert body.count("https://kazi.example/job/") == 2

    def test_one_job_reads_as_one_job(self):
        body = dg.render_digest(pick([Match("j1")]))
        assert "1 job for you today" in body

    def test_no_link_base_means_no_links(self):
        body = dg.render_digest(pick([Match("j1")]))
        assert "http" not in body

    def test_sms_fallback_is_one_segment_and_says_how_to_stop(self):
        digest = pick([Match("j1", deadline="2026-10-24")])
        sms = dg.render_sms(digest, today=TODAY)
        assert len(sms) <= dg.SMS_SEGMENT
        assert "Kazi-Kasi: 1 new job" in sms
        assert "closes in 4 days" in sms
        assert "Reply STOP" in sms


class TestSplitting:
    def test_a_short_body_is_one_message(self):
        assert dg.split_message("hello") == ["hello"]

    def test_an_empty_body_produces_nothing_to_send(self):
        assert dg.split_message("") == []

    def test_long_body_splits_at_card_boundaries(self):
        matches = [Match(f"j{i}", title=f"Clerk {i}", deadline="2026-11-20") for i in range(5)]
        body = dg.render_digest(pick(matches), link_base="https://kazi.example")
        chunks = dg.split_message(body, limit=300)
        assert len(chunks) > 1
        assert all(len(chunk) <= 300 for chunk in chunks)
        # Nothing lost, and no card cut in half.
        for chunk in chunks:
            for block in chunk.split("\n\n"):
                assert block.count("*") % 2 == 0

    def test_a_single_pathological_block_is_hard_split_rather_than_dropped(self):
        chunks = dg.split_message("x" * 700, limit=300)
        assert [len(chunk) for chunk in chunks] == [300, 300, 100]

    def test_full_digest_fits_one_whatsapp_message_in_normal_cases(self):
        matches = [Match(f"j{i}", title=f"Data Entry Clerk {i}") for i in range(5)]
        body = dg.render_digest(pick(matches), link_base="https://kazikasi.app")
        assert len(body) < dg.WHATSAPP_TEXT_LIMIT
        assert len(dg.split_message(body)) == 1


class TestMessages:
    def test_one_key_per_profile_day_channel_and_part(self):
        assert dg.idempotency_key("demo-fresher", TODAY, "whatsapp", 1) == "demo-fresher:2026-10-20:whatsapp:1"
        assert dg.idempotency_key("demo-fresher", TODAY, "whatsapp", 2) != dg.idempotency_key(
            "demo-fresher", TODAY, "whatsapp", 1
        )
        assert dg.idempotency_key("demo-fresher", TODAY, "sms") != dg.idempotency_key(
            "demo-fresher", TODAY, "whatsapp"
        )

    def test_whatsapp_messages_carry_the_body_the_links_and_a_masked_number(self):
        digest = pick([Match("j1")])
        messages = dg.build_messages(digest, channel="whatsapp", msisdn="+254712345678", link_base="https://k.app")
        assert len(messages) == 1
        payload = messages[0].to_dict()
        assert payload["to"] == "+2547•••5678"
        assert payload["characters"] > 0

    def test_sms_is_marked_as_a_fallback_not_a_digest(self):
        messages = dg.build_messages(pick([Match("j1")]), channel="sms", msisdn="+254712345678")
        assert messages[0].kind == "fallback"
        assert messages[0].channel == "sms"

    def test_empty_digest_builds_no_messages(self):
        assert dg.build_messages(pick([]), channel="whatsapp", msisdn="+254712345678") == []


class TestTiming:
    def test_window_is_nairobi_time_not_utc(self):
        # 15:30 UTC is 18:30 in Nairobi: inside the default evening window.
        assert dg.in_window(datetime(2026, 10, 20, 15, 30, tzinfo=timezone.utc))
        # 13:00 UTC is 16:00 EAT: before it.
        assert not dg.in_window(datetime(2026, 10, 20, 13, 0, tzinfo=timezone.utc))

    def test_window_edges_are_half_open(self):
        assert dg.in_window(datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc))       # 18:00
        assert not dg.in_window(datetime(2026, 10, 20, 17, 0, tzinfo=timezone.utc))   # 20:00

    def test_a_window_can_cross_midnight(self):
        assert dg.in_window(datetime(2026, 10, 20, 21, 30, tzinfo=timezone.utc), "18:00", "02:00")
        assert dg.in_window(datetime(2026, 10, 20, 22, 30, tzinfo=timezone.utc), "20:00", "06:00")
        assert not dg.in_window(datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc), "18:00", "02:00")

    def test_eat_has_no_daylight_saving(self):
        assert dg.eat_now(datetime(2026, 1, 15, 12, tzinfo=timezone.utc)).hour == 15
        assert dg.eat_now(datetime(2026, 7, 15, 12, tzinfo=timezone.utc)).hour == 15

    def test_the_digest_date_is_nairobis_date(self):
        # 22:00 UTC on the 20th is already the 21st in Nairobi.
        assert dg.local_date(datetime(2026, 10, 20, 22, 0, tzinfo=timezone.utc)) == date(2026, 10, 21)
        assert dg.eat_now(datetime(2026, 10, 20, 9, tzinfo=timezone.utc)).tzinfo.utcoffset(None) == timedelta(hours=3)
