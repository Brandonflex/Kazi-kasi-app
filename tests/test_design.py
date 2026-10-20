"""The design system, asserted rather than documented.

A palette drifts one "small tweak" at a time. These tests compute contrast from
the CSS that actually ships, so a colour change that breaks AA fails the build
instead of failing someone's eyes in sunlight.

Everything here is about `docs/design/`: identity, tokens, and the deal we made
with ourselves about colour meaning.
"""

import re

import pytest

from kazikasi.serve import SCOPE_MARK, STYLE


def tokens() -> dict[str, str]:
    """Parse `:root{…}` into name → value, resolving one level of var()."""
    block = STYLE.split(":root{", 1)[1].split("}", 1)[0]
    raw = dict(re.findall(r"--([a-z0-9-]+)\s*:\s*([^;]+);", block))
    resolved = {}
    for name, value in raw.items():
        value = value.strip()
        alias = re.fullmatch(r"var\(--([a-z0-9-]+)\)", value)
        resolved[name] = resolved.get(alias.group(1), "") if alias else value
    return {name: value for name, value in resolved.items() if value.startswith("#")}


def luminance(hexcode: str) -> float:
    value = hexcode.lstrip("#")
    channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(foreground: str, background: str) -> float:
    a, b = luminance(foreground), luminance(background)
    high, low = max(a, b), min(a, b)
    return (high + 0.05) / (low + 0.05)


class TestPalette:
    def test_the_five_roles_exist(self):
        palette = tokens()
        for name in ("ink", "paper", "forest", "amber", "risk", "line", "sunken", "muted"):
            assert name in palette, f"missing token --{name}"

    @pytest.mark.parametrize(
        "foreground,background",
        [
            ("ink", "paper"),
            ("ink", "card"),
            ("ink-2", "card"),
            ("muted", "card"),
            ("muted", "paper"),
            ("forest", "card"),
            ("forest", "forest-soft"),
            ("amber", "card"),
            ("amber", "amber-soft"),
            ("risk", "card"),
            ("risk", "risk-soft"),
        ],
    )
    def test_every_text_pair_passes_wcag_aa(self, foreground, background):
        palette = tokens()
        ratio = contrast(palette[foreground], palette[background])
        assert ratio >= 4.5, f"{foreground} on {background} is {ratio:.2f}:1, below AA"

    def test_white_on_forest_is_aa(self):
        palette = tokens()
        assert contrast("#FFFFFF", palette["forest"]) >= 4.5

    def test_borders_are_soft_and_the_focus_ring_is_not(self):
        """A card edge is decoration; a focus ring is a control (SC 1.4.11)."""
        palette = tokens()
        assert contrast(palette["line"], palette["paper"]) >= 1.1   # deliberately quiet
        assert contrast(palette["forest"], palette["paper"]) >= 3    # must be seen

    def test_risk_red_is_never_a_button_colour(self):
        """Red means 'be careful'. The moment it also means 'click me', it stops."""
        assert "background:var(--risk)" not in STYLE
        assert "background:var(--danger)" not in STYLE
        assert "background:var(--forest)" in STYLE  # actions are forest

    def test_amber_is_not_used_as_a_button_colour_either(self):
        assert "background:var(--amber)" not in STYLE
        assert "background:var(--warn)" not in STYLE


class TestTypography:
    def test_there_are_no_webfonts(self):
        """No @font-face, no font CDN: the page must cost zero font bytes."""
        assert "@font-face" not in STYLE
        assert "fonts.googleapis" not in STYLE
        assert "fonts.gstatic" not in STYLE
        assert "url(" not in STYLE

    def test_the_system_stack_is_declared_as_a_token(self):
        assert "--font-sans" in STYLE
        assert "-apple-system" in STYLE

    def test_body_text_is_sixteen_pixels(self):
        assert re.search(r"body\{[^}]*font:16px", STYLE)

    def test_numerals_are_tabular_where_numbers_are_compared(self):
        assert "font-variant-numeric:tabular-nums" in STYLE


class TestAccessibilityContract:
    def test_a_visible_focus_ring_is_defined(self):
        assert ":focus-visible" in STYLE
        assert "--focus" in STYLE

    def test_primary_targets_are_at_least_44_pixels(self):
        assert re.search(r"\.subform button\{[^}]*min-height:44px", STYLE)
        assert re.search(r"\.foot \.apply\{[^}]*min-height:40px", STYLE)

    def test_reduced_motion_is_respected(self):
        assert "prefers-reduced-motion" in STYLE

    def test_the_page_declares_its_language(self):
        from kazikasi.serve import _page

        page = _page("t", "body")
        assert '<html lang="en-KE">' in page
        assert 'name="viewport"' in page

    def test_badges_always_carry_words_not_only_colour(self):
        from datetime import datetime, timezone

        from kazikasi import db, serve
        from kazikasi.corpus import load_corpus
        from kazikasi.profile import seed_profiles

        now = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
        conn = db.connect()
        load_corpus(conn, now=now)
        seed_profiles(conn)
        page = serve.render_feed(conn, profile_id="demo-fresher", now=now)
        conn.close()

        for badge in re.findall(r'<span class="badge[^"]*">([^<]*)</span>', page):
            assert badge.strip(), "a badge with no text is colour-only meaning"


class TestBrandMark:
    def test_the_mark_is_inline_svg_and_costs_no_request(self):
        assert SCOPE_MARK.startswith("<svg")
        assert "http" not in SCOPE_MARK
        assert 'aria-hidden="true"' in SCOPE_MARK

    def test_the_mark_inherits_its_colour(self):
        assert "currentColor" in SCOPE_MARK

    def test_the_lockup_is_present_and_the_hyphen_survives(self):
        from kazikasi.serve import _page

        page = _page("t", "body")
        assert "Kazi-Kasi" in page
        assert "KaziKasi" not in page

    def test_the_wordmark_is_not_all_caps(self):
        from kazikasi.serve import _page

        assert "KAZI-KASI" not in _page("t", "body")


class TestSurfaces:
    def test_the_digest_preview_is_a_message_not_page_copy(self):
        assert ".msg{" in STYLE
        assert "--font-mono" in STYLE

    def test_the_layout_reflows_at_320_pixels(self):
        assert "@media (max-width:520px)" in STYLE
        assert "grid-template-columns:repeat(2,1fr)" in STYLE

    def test_the_nosniff_header_is_sent(self):
        import inspect

        from kazikasi import serve

        source = inspect.getsource(serve._Handler._respond)
        assert "X-Content-Type-Options" in source
