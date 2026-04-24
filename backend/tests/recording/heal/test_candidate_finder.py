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
