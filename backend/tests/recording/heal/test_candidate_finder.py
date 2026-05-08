"""Story SH-2 — candidate finder / transposition unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.recording.heal.candidate_finder import (
    HealCandidate,
    find_heal_candidates,
    pick_best_candidate,
    transpose_selector,
)


# ---------------------------------------------------------------------------
# Transposition
# ---------------------------------------------------------------------------


class TestTransposition:
    def test_id_produces_testid_aria_text_variants(self) -> None:
        out = transpose_selector("id=submit")
        strategies = [c.strategy for c in out]
        assert "testid" in strategies
        assert "aria" in strategies
        assert "text" in strategies
        # Testid should rank higher than xpath / raw css fallbacks.
        testid = next(c for c in out if c.strategy == "testid")
        xpath_candidates = [c for c in out if c.strategy == "xpath"]
        assert testid.confidence > 0.7
        if xpath_candidates:
            assert testid.confidence > xpath_candidates[0].confidence

    def test_testid_transposes_to_id_and_aria(self) -> None:
        out = transpose_selector("[data-testid=submit]")
        strategies = {c.strategy for c in out}
        # Should offer id fallback — common drift pattern.
        assert "id" in strategies or any(
            c.strategy == "css" and "#submit" in c.value for c in out
        )
        assert any(c.strategy == "aria" for c in out)

    def test_text_produces_case_insensitive_and_role_variants(self) -> None:
        out = transpose_selector("text=Submit")
        values = [c.value for c in out]
        # At least one case-insensitive regex variant
        assert any("/i" in v for v in values)
        assert any(c.strategy == "aria" for c in out)

    def test_css_with_nth_child_strips_index(self) -> None:
        out = transpose_selector("css=.items > li:nth-child(2)")
        values = [c.value for c in out]
        assert any("nth-child" not in v for v in values)

    def test_css_id_with_trailing_digits_gets_stripped(self) -> None:
        out = transpose_selector("css=#user-avatar-17")
        values = [c.value for c in out]
        assert any(v == "#user-avatar" for v in values)

    def test_xpath_strips_trailing_position_predicate(self) -> None:
        out = transpose_selector("xpath=//div[@class='x']/button[2]")
        assert out, "xpath transposition should offer at least one variant"
        assert not any("[2]" in c.value.rsplit("/", 1)[-1] for c in out)

    def test_empty_selector_returns_empty(self) -> None:
        assert transpose_selector("") == []
        assert transpose_selector("id=") == []

    def test_unknown_strategy_treated_as_css(self) -> None:
        # No strategy prefix → CSS. Returns either stripped variants or
        # at worst empty — important: never crashes.
        out = transpose_selector("plain-selector")
        assert isinstance(out, list)

    def test_failed_selector_never_appears_in_candidates(self) -> None:
        for seed in ("id=submit", "[data-testid=go]", "text=Hello"):
            out = transpose_selector(seed)
            assert seed not in {c.value for c in out}

    def test_candidates_are_deduplicated(self) -> None:
        out = transpose_selector("id=submit")
        values = [c.value for c in out]
        assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# Sidecar integration
# ---------------------------------------------------------------------------


@pytest.fixture
def sidecar(tmp_path: Path) -> Path:
    payload = {
        "schema_version": 1,
        "commands": [
            {
                "index": 0,
                "keyword": "Click",
                "active_candidate_index": 0,
                "selector_candidates": [
                    {"strategy": "testid", "value": "id=submit", "quality_score": 0.9},
                    {"strategy": "aria",   "value": "role=button[name='Go']", "quality_score": 0.8},
                    {"strategy": "text",   "value": "text=Go", "quality_score": 0.6},
                ],
            }
        ],
    }
    p = tmp_path / "flow.rbs.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


class TestFindHealCandidates:
    def test_sidecar_match_returns_other_candidates_first(
        self, sidecar: Path
    ) -> None:
        out = find_heal_candidates("id=submit", sidecar_path=sidecar)
        # First candidates should be sidecar-sourced (aria/text),
        # then transpositions. De-duplication means the originally
        # failed value is never returned.
        assert out, "expected at least the aria+text sidecar siblings"
        sidecar_first = [c for c in out if c.source == "sidecar"]
        assert sidecar_first, "sidecar source should be present"
        assert sidecar_first[0].strategy in ("aria", "text", "testid")

    def test_no_sidecar_falls_back_to_transposition_only(
        self, tmp_path: Path
    ) -> None:
        out = find_heal_candidates("id=submit", sidecar_path=tmp_path / "missing.json")
        assert out, "transposition should still return candidates"
        assert all(c.source == "transposition" for c in out)

    def test_verify_filters_non_unique_candidates(
        self, tmp_path: Path
    ) -> None:
        # `verify` returns the "live count" — drop 0 and >1 matches.
        def verify(_value: str) -> int:
            counts = {
                "[data-testid=submit]": 1,   # OK
                "role=button[name=\"submit\"]": 2,  # drop
                "text=submit": 0,            # drop
            }
            return counts.get(_value, 0)

        out = find_heal_candidates(
            "id=submit",
            sidecar_path=None,
            verify=verify,
        )
        assert [c.value for c in out] == ["[data-testid=submit]"]

    def test_malformed_sidecar_is_silent(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.rbs.json"
        p.write_text("not json", encoding="utf-8")
        out = find_heal_candidates("id=x", sidecar_path=p)
        # No crash; returns pure transposition candidates.
        assert all(c.source == "transposition" for c in out)


# ---------------------------------------------------------------------------
# RECORDER-FRAMES — iframe-wrapped failed selectors must round-trip
# through both sidecar lookup and transposition with the wrap intact.
# ---------------------------------------------------------------------------


class TestIframeWrappedSelectors:
    """Sourcepoint / OneTrust / TCF consent banners live inside cross-
    origin iframes. The recorder emits clicks on them as
    ``iframe[src*="<host>"] >>> <inner>``. At heal time the failed
    selector still carries the wrap, but the sidecar stores only the
    inner selector on each candidate, and verify probes the live page
    via ``Get Element Count`` — without the wrap baked back into every
    candidate, sidecar lookup misses, transposition runs against the
    top frame, and verify rejects everything as count==0."""

    def test_split_iframe_wrap_unwraps_single(self) -> None:
        from src.recording.heal.candidate_finder import _split_iframe_wrap
        prefix, inner = _split_iframe_wrap(
            'iframe[src*="message-eu.sp-prod.net"] >>> #accept-all'
        )
        assert prefix == 'iframe[src*="message-eu.sp-prod.net"] >>> '
        assert inner == "#accept-all"

    def test_split_iframe_wrap_unwraps_chain(self) -> None:
        from src.recording.heal.candidate_finder import _split_iframe_wrap
        prefix, inner = _split_iframe_wrap(
            'iframe[src*="outer.example"] >>> '
            'iframe[src*="inner.example"] >>> #accept-all'
        )
        assert prefix == (
            'iframe[src*="outer.example"] >>> '
            'iframe[src*="inner.example"] >>> '
        )
        assert inner == "#accept-all"

    def test_split_iframe_wrap_passthrough_for_plain_selector(self) -> None:
        from src.recording.heal.candidate_finder import _split_iframe_wrap
        assert _split_iframe_wrap("id=submit") == ("", "id=submit")
        assert _split_iframe_wrap("text=Login") == ("", "text=Login")

    def test_sidecar_match_under_iframe_wrap_returns_inner_alternatives(
        self, tmp_path: Path
    ) -> None:
        # Sidecar stores the INNER selector on each candidate, plus
        # `frame_url` separately on the parent command. The lookup must
        # strip the iframe wrap from the failed selector before
        # comparing, otherwise the match always misses.
        payload = {
            "schema_version": 1,
            "commands": [
                {
                    "index": 0,
                    "keyword": "Click",
                    "active_candidate_index": 0,
                    "frame_url": "https://message-eu.sp-prod.net/?id=42",
                    "selector_candidates": [
                        {"strategy": "text", "value": "text=Accept all", "quality_score": 0.7},
                        {"strategy": "aria", "value": 'role=button[name="Accept all"]', "quality_score": 0.85},
                        {"strategy": "css",  "value": "#accept-all", "quality_score": 0.55},
                    ],
                }
            ],
        }
        sc = tmp_path / "flow.rbs.json"
        sc.write_text(json.dumps(payload), encoding="utf-8")

        composite = 'iframe[src*="message-eu.sp-prod.net"] >>> text=Accept all'
        out = find_heal_candidates(composite, sidecar_path=sc)

        sidecar_hits = [c for c in out if c.source == "sidecar"]
        assert len(sidecar_hits) >= 2, (
            "iframe-wrapped lookup should find the inner-selector "
            "siblings the recorder synthesised"
        )
        # Every sidecar candidate must carry the iframe prefix back so
        # the click lands in the SAME frame the user originally clicked.
        for c in sidecar_hits:
            assert c.value.startswith(
                'iframe[src*="message-eu.sp-prod.net"] >>> '
            ), f"sidecar candidate dropped iframe wrap: {c.value!r}"

    def test_transposition_under_iframe_wrap_keeps_wrap(
        self, tmp_path: Path
    ) -> None:
        composite = 'iframe[src*="x.example"] >>> id=submit'
        out = find_heal_candidates(composite, sidecar_path=None)
        assert out, "transposition should still produce candidates"
        # The original failed value must NOT appear (de-dup guarantee).
        assert all(c.value != composite for c in out)
        # Every candidate carries the iframe wrap.
        for c in out:
            assert c.value.startswith('iframe[src*="x.example"] >>> '), (
                f"transposition candidate dropped iframe wrap: {c.value!r}"
            )
        # Inner selectors are valid transpositions of `id=submit`.
        inner_values = [c.value.split(" >>> ", 1)[1] for c in out]
        assert any("data-testid=submit" in v for v in inner_values)

    def test_verify_runs_against_wrapped_candidate(self, tmp_path: Path) -> None:
        # The verify callback must receive the iframe-wrapped value, not
        # the bare inner selector — the same value the heal library will
        # later pass to ``Click`` / ``Get Element Count``. Without this
        # contract, verify probes the wrong DOM and every alternative
        # is silently dropped.
        seen_values: list[str] = []

        def verify(value: str) -> int:
            seen_values.append(value)
            return 1  # accept all

        composite = 'iframe[src*="x.example"] >>> id=submit'
        out = find_heal_candidates(composite, sidecar_path=None, verify=verify)

        assert out
        # Whatever was kept must have been verified under the wrap.
        for v in seen_values:
            assert v.startswith('iframe[src*="x.example"] >>> '), (
                f"verify saw a candidate without the iframe wrap: {v!r}"
            )

    def test_unwrapped_selector_path_unchanged_for_top_frame(self) -> None:
        # Backward compatibility — failed selectors WITHOUT an iframe
        # qualifier keep their existing behavior verbatim. No prefix
        # accidentally tacked on, no candidate dropped.
        out = find_heal_candidates("id=submit", sidecar_path=None)
        assert out
        assert all(not c.value.startswith("iframe[") for c in out)


class TestVerifyExceptionLogging:
    """When the verify callback throws, the candidate is dropped (the
    pre-existing safe behavior — can't verify means can't trust). But
    operators looking at "why didn't the heal happen?" deserve a log
    line. Two-tier emission:
      - per-failure debug log (low noise)
      - one summary WARNING per heal-call when ALL candidates failed
        verify due to exceptions (signals environment-wide trouble:
        Browser library timeout, page navigation mid-verify, etc.)
    """

    def test_per_candidate_debug_log_on_verify_exception(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        def verify(value: str) -> int:
            if value == "[data-testid=submit]":
                raise RuntimeError("playwright timeout")
            return 1

        caplog.set_level("DEBUG", logger="roboscope.recording.heal")
        out = find_heal_candidates(
            "id=submit", sidecar_path=None, verify=verify,
        )
        # The other candidates still survive — only the throwing one
        # was dropped.
        assert out
        assert all(c.value != "[data-testid=submit]" for c in out)
        debug_msgs = [r for r in caplog.records if r.levelname == "DEBUG"]
        assert any(
            "heal-verify exception" in r.getMessage()
            and "[data-testid=submit]" in r.getMessage()
            for r in debug_msgs
        ), "expected debug log naming the throwing candidate"

    def test_warning_when_all_candidates_throw(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Total environment failure — every verify call throws.
        def verify(_value: str) -> int:
            raise RuntimeError("browser disconnected")

        caplog.set_level("WARNING", logger="roboscope.recording.heal")
        out = find_heal_candidates(
            "id=submit", sidecar_path=None, verify=verify,
        )
        assert out == []
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1, (
            "expected ONE summary warning per heal-call, not per "
            f"candidate: {[r.getMessage() for r in warnings]}"
        )
        assert "id=submit" in warnings[0].getMessage()
        assert "candidates" in warnings[0].getMessage()

    def test_no_warning_when_at_least_one_candidate_survives(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Mixed: some throw, some return real counts. As long as ANY
        # candidate survives the verify gate, the warning is
        # suppressed — heal will pick the survivor and the run
        # proceeds; nothing for the operator to investigate.
        def verify(value: str) -> int:
            if value.startswith("role="):
                raise RuntimeError("flaky strict-mode")
            return 1

        caplog.set_level("WARNING", logger="roboscope.recording.heal")
        out = find_heal_candidates(
            "id=submit", sidecar_path=None, verify=verify,
        )
        assert out
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert warnings == []

    def test_no_warning_when_no_candidates_throw_but_all_drop_via_count(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Every verify call returns 0 — legitimate "no live element
        # matches anymore" outcome. Don't emit a warning; this is
        # the expected silent path when a flow's selectors have all
        # genuinely drifted.
        def verify(_value: str) -> int:
            return 0

        caplog.set_level("WARNING", logger="roboscope.recording.heal")
        out = find_heal_candidates(
            "id=submit", sidecar_path=None, verify=verify,
        )
        assert out == []
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert warnings == []


class TestLegacyStrategyFilter:
    """Sidecars saved before commit 0c62c7a contain `pw_locator`
    candidates whose values are Playwright JS API syntax — Browser
    library cannot parse them. Verify drops these in production,
    but the heal path that runs verify=None (offline tests, future
    refactors) could otherwise surface a 0.80-confidence pw_locator
    row as the picked heal. The filter in `_sidecar_candidates`
    drops them before they ever enter the candidate list."""

    def test_pw_locator_sibling_excluded_from_heal_candidates(
        self, tmp_path: Path
    ) -> None:
        # Legacy sidecar — failed selector matches a `testid` row;
        # the siblings include both a `text` candidate (legitimate)
        # and a `pw_locator` candidate (legacy, must be dropped).
        payload = {
            "schema_version": 1,
            "commands": [
                {
                    "index": 0,
                    "keyword": "Click",
                    "active_candidate_index": 0,
                    "selector_candidates": [
                        {"strategy": "testid", "value": "id=submit", "quality_score": 0.9},
                        {"strategy": "text",   "value": "text=Submit", "quality_score": 0.7},
                        {"strategy": "pw_locator", "value": 'getByRole("button", { name: "Submit" })', "quality_score": 0.75},
                    ],
                }
            ],
        }
        sc = tmp_path / "flow.rbs.json"
        sc.write_text(json.dumps(payload), encoding="utf-8")

        out = find_heal_candidates("id=submit", sidecar_path=sc)

        sidecar_hits = [c for c in out if c.source == "sidecar"]
        # The text candidate survives, the pw_locator sibling does not.
        strategies = [c.strategy for c in sidecar_hits]
        assert "text" in strategies
        assert "pw_locator" not in strategies
        # And no candidate value carries the JS API syntax.
        assert all("getByRole" not in c.value for c in out)
        assert all("getByText" not in c.value for c in out)

    def test_pw_locator_sibling_filter_still_returns_other_candidates(
        self, tmp_path: Path
    ) -> None:
        # If pw_locator was the ONLY sibling, the result is empty —
        # that's preferable to surfacing a known-broken alternative
        # (the transposition fallback in `find_heal_candidates`
        # still adds top-frame transposition candidates afterwards).
        payload = {
            "schema_version": 1,
            "commands": [
                {
                    "index": 0,
                    "keyword": "Click",
                    "active_candidate_index": 0,
                    "selector_candidates": [
                        {"strategy": "css", "value": "#failed", "quality_score": 0.55},
                        {"strategy": "pw_locator", "value": 'getByText("X")', "quality_score": 0.7},
                    ],
                }
            ],
        }
        sc = tmp_path / "flow.rbs.json"
        sc.write_text(json.dumps(payload), encoding="utf-8")

        out = find_heal_candidates("#failed", sidecar_path=sc)

        sidecar_hits = [c for c in out if c.source == "sidecar"]
        assert sidecar_hits == [], (
            "the only sibling was pw_locator — heal must surface "
            "no sidecar candidate at all rather than the broken one"
        )


# ---------------------------------------------------------------------------
# Threshold picker
# ---------------------------------------------------------------------------


class TestPickBestCandidate:
    def test_below_threshold_returns_none(self) -> None:
        cands = [HealCandidate("a", "xpath", 0.3, "transposition")]
        assert pick_best_candidate(cands, threshold=0.7) is None

    def test_returns_highest_above_threshold(self) -> None:
        cands = [
            HealCandidate("low", "xpath", 0.4, "transposition"),
            HealCandidate("mid", "css",   0.75, "transposition"),
            HealCandidate("top", "testid", 0.9, "sidecar"),
        ]
        best = pick_best_candidate(cands, threshold=0.7)
        assert best is not None
        assert best.value == "top"

    def test_empty_input(self) -> None:
        assert pick_best_candidate([], threshold=0.5) is None
