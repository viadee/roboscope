"""RECORDER-FRAMES — symmetry contract between iframe wrap emit and unwrap.

The cross-frame piercing wrap is generated in `robot_emit._iframe_locator_from_url`
and consumed by `candidate_finder._split_iframe_wrap` (and its delegate
`RoboScopeHeal._unwrap_iframe_prefix`). They live in different modules
and were written months apart. If the emit shape ever drifts (e.g. a
maintainer switches from ``iframe[src*="X"]`` to ``iframe[src="X"]`` or
to ``iframe[name=...]``), the unwrap silently keeps "succeeding" with
wrong results, and every iframe heal regresses to the pre-fix behavior:
sidecar lookup misses, candidates resolve in the top frame, all heals
get dropped as count==0.

These tests pin the round-trip:

  url + inner   ─emit→  composite_disk_form
  composite     ─split→ (prefix, inner_back)

…such that ``prefix == iframe_loc + " >>> "`` and ``inner_back ==
inner``. If a future commit changes either side without the other,
the symmetry test fires.
"""

from __future__ import annotations

import pytest

from src.recording.heal.candidate_finder import _split_iframe_wrap
from src.recording.heal.library import RoboScopeHeal
from src.recording.robot_emit import _iframe_locator_from_url


CASES = [
    # (label, frame_url, expected iframe_loc shape)
    ("sourcepoint", "https://message-eu.sp-prod.net/?id=42",
        'iframe[src*="message-eu.sp-prod.net"]'),
    ("onetrust", "https://cdn-ukwest.onetrust.com/consent/abc-def",
        'iframe[src*="cdn-ukwest.onetrust.com"]'),
    ("port-and-path", "https://localhost:8443/auth/realms/x",
        'iframe[src*="localhost:8443"]'),
]


class TestEmitToUnwrapSymmetry:
    @pytest.mark.parametrize("label,url,expected_loc", CASES, ids=[c[0] for c in CASES])
    def test_iframe_locator_shape_matches_unwrap_pattern(
        self, label: str, url: str, expected_loc: str
    ) -> None:
        """The emit-side shape must be exactly what the unwrap-side
        regex / parser recognises. We assert the literal shape so a
        future "let me make this match more iframes" tweak fails the
        contract before it ships."""
        loc = _iframe_locator_from_url(url)
        assert loc == expected_loc, (
            f"emit shape drifted for {label}: got {loc!r} (expected "
            f"{expected_loc!r}) — the heal-side unwrap will silently miss"
        )

    @pytest.mark.parametrize("label,url,_loc", CASES, ids=[c[0] for c in CASES])
    def test_round_trip_single_iframe(
        self, label: str, url: str, _loc: str
    ) -> None:
        """Build the on-disk composite the same way `_emit_command`
        does and verify the unwrap restores the inner selector
        exactly. Inner has no special chars to keep this focused on
        the wrap; the RF-escape symmetry has its own pin."""
        iframe_loc = _iframe_locator_from_url(url)
        assert iframe_loc is not None
        inner = "#accept-all"
        composite = f"{iframe_loc} >>> {inner}"

        prefix, inner_back = _split_iframe_wrap(composite)
        assert prefix == f"{iframe_loc} >>> "
        assert inner_back == inner
        # And the library-side delegate stays in sync.
        assert RoboScopeHeal._unwrap_iframe_prefix(composite) == inner

    def test_round_trip_chained_iframes(self) -> None:
        """Chained iframes (`iframe[a] >>> iframe[b] >>> #foo`) — used
        when a banner lives inside an iframe inside another iframe —
        must round-trip the FULL chain through the prefix and leave
        the deepest inner intact."""
        outer = _iframe_locator_from_url("https://outer.example/")
        inner_iframe = _iframe_locator_from_url("https://inner.example/")
        assert outer is not None and inner_iframe is not None
        target = "[data-testid=accept]"
        composite = f"{outer} >>> {inner_iframe} >>> {target}"

        prefix, inner_back = _split_iframe_wrap(composite)
        assert prefix == f"{outer} >>> {inner_iframe} >>> "
        assert inner_back == target

    def test_unwrappable_url_returns_none(self) -> None:
        """``data:`` and other schemes without a meaningful host must
        emit None — the caller (`_emit_command`) then falls back to
        a non-wrapped selector. If the helper ever returned a bogus
        ``iframe[src*=""]`` shape, the unwrap would also "match" that
        and falsely treat top-frame selectors as iframe-wrapped."""
        assert _iframe_locator_from_url("data:text/html,foo") is None
        assert _iframe_locator_from_url("") is None

    def test_unwrap_passthrough_for_top_frame_selectors(self) -> None:
        """The unwrap MUST be a no-op for any selector that doesn't
        start with `iframe[`. A regression here would silently
        reinterpret the leading characters of every top-frame
        selector as a partial wrap — disaster."""
        for sel in (
            "#submit",
            "[data-testid=login]",
            "text=Click me",
            "xpath=//button",
            "role=button[name=\"Save\"]",
            # Pathological: contains the word `iframe` but isn't the wrap dialect.
            "css=div.iframe-wrapper button",
        ):
            assert _split_iframe_wrap(sel) == ("", sel), (
                f"unwrap altered a non-wrapped selector: {sel!r}"
            )
            assert RoboScopeHeal._unwrap_iframe_prefix(sel) == sel
