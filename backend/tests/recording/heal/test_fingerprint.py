"""Story SH-3 — fingerprint scorer + walker unit tests."""

from __future__ import annotations

import pytest

from src.recording.heal.fingerprint import (
    DEFAULT_WALKER_THRESHOLD,
    find_best_by_fingerprint,
    score_fingerprint_similarity,
)


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------


class TestScorerEdgeCases:
    def test_both_empty_scores_zero(self) -> None:
        assert score_fingerprint_similarity(None, None) == 0.0
        assert score_fingerprint_similarity({}, {}) == 0.0

    def test_one_empty_scores_zero(self) -> None:
        assert score_fingerprint_similarity({"tag": "button"}, None) == 0.0
        assert score_fingerprint_similarity(None, {"tag": "button"}) == 0.0


class TestScorerSingleSignal:
    def test_testid_only(self) -> None:
        s = {"testid": "submit"}
        l_ = {"testid": "submit"}
        # Testid weight = 0.45.
        assert score_fingerprint_similarity(s, l_) == pytest.approx(0.45, abs=1e-6)

    def test_id_only(self) -> None:
        assert score_fingerprint_similarity(
            {"id": "x"}, {"id": "x"},
        ) == pytest.approx(0.20, abs=1e-6)

    def test_tag_and_role_match_but_no_other_signal(self) -> None:
        s = {"tag": "button", "role": "button"}
        l_ = {"tag": "button", "role": "button"}
        # Tag + role weight = 0.10.
        assert score_fingerprint_similarity(s, l_) == pytest.approx(0.10, abs=1e-6)

    def test_tag_matches_but_role_differs(self) -> None:
        s = {"tag": "button", "role": "button"}
        l_ = {"tag": "button", "role": "link"}
        # Tag alone → half the role+tag weight.
        assert score_fingerprint_similarity(s, l_) == pytest.approx(0.05, abs=1e-6)


class TestScorerCombinations:
    def test_all_fields_match_approaches_one(self) -> None:
        s = {
            "tag": "button", "id": "submit", "testid": "submit",
            "name": "submitBtn", "role": "button",
            "classes": ["primary", "cta"],
            "text": "Submit",
            "ancestors": [
                {"tag": "form", "id": "login", "testid": None},
                {"tag": "div", "id": None, "testid": "login-card"},
            ],
        }
        score = score_fingerprint_similarity(s, s)
        # All weights land → very close to 1.0.
        assert score >= 0.95

    def test_testid_plus_text_clears_walker_threshold(self) -> None:
        # testid (0.45) + full text (0.10) + tag+role (0.10) = 0.65 ≥ 0.6.
        s = {
            "tag": "button", "testid": "submit", "role": "button",
            "text": "Submit",
        }
        score = score_fingerprint_similarity(s, s)
        assert score >= DEFAULT_WALKER_THRESHOLD

    def test_single_strong_signal_stays_below_threshold(self) -> None:
        # Just testid = 0.45, below the 0.6 walker bar. Multi-signal
        # required. This is the cautious-by-design behaviour.
        s = {"testid": "submit"}
        assert score_fingerprint_similarity(s, s) < DEFAULT_WALKER_THRESHOLD


class TestJaccardOnClasses:
    def test_class_overlap_proportional(self) -> None:
        s = {"classes": ["a", "b", "c"]}
        l_ = {"classes": ["b", "c", "d"]}
        # Jaccard 2/4 = 0.5; weight 0.08 → 0.04 contribution.
        assert score_fingerprint_similarity(s, l_) == pytest.approx(0.04, abs=1e-6)

    def test_identical_class_lists(self) -> None:
        s = {"classes": ["x", "y"]}
        l_ = {"classes": ["x", "y"]}
        assert score_fingerprint_similarity(s, l_) == pytest.approx(0.08, abs=1e-6)


class TestTextOverlap:
    def test_case_insensitive_exact_match(self) -> None:
        s = {"text": "Submit"}
        l_ = {"text": "submit"}
        # Case-insensitive → 1.0 overlap contribution scaled by weight.
        assert score_fingerprint_similarity(s, l_) == pytest.approx(0.10, abs=1e-6)

    def test_partial_text_overlap_partial_score(self) -> None:
        s = {"text": "Submit Order"}
        l_ = {"text": "Submit"}
        total = score_fingerprint_similarity(s, l_)
        # Some overlap but not full — landing somewhere in (0, 0.10).
        assert 0.0 < total < 0.10

    def test_disjoint_text(self) -> None:
        s = {"text": "Checkout"}
        l_ = {"text": "Cancel"}
        assert score_fingerprint_similarity(s, l_) == 0.0


class TestAncestors:
    def test_ancestor_tag_id_match_counts(self) -> None:
        s = {"ancestors": [
            {"tag": "form", "id": "login", "testid": None},
            {"tag": "div",  "id": "container", "testid": None},
        ]}
        l_ = {"ancestors": [
            {"tag": "form", "id": "login", "testid": None},
            {"tag": "div",  "id": "container", "testid": None},
        ]}
        assert score_fingerprint_similarity(s, l_) == pytest.approx(0.07, abs=1e-6)

    def test_ancestor_testid_match_counts(self) -> None:
        s = {"ancestors": [{"tag": "div", "id": None, "testid": "card"}]}
        l_ = {"ancestors": [{"tag": "div", "id": None, "testid": "card"}]}
        assert score_fingerprint_similarity(s, l_) == pytest.approx(0.07, abs=1e-6)

    def test_empty_ancestors_contribute_nothing(self) -> None:
        s = {"ancestors": []}
        l_ = {"ancestors": []}
        assert score_fingerprint_similarity(s, l_) == 0.0


# ---------------------------------------------------------------------------
# Walker
# ---------------------------------------------------------------------------


class TestWalker:
    def test_none_stored_returns_none(self) -> None:
        assert find_best_by_fingerprint(None, [("css=x", {"tag": "button"})]) is None

    def test_empty_candidates_returns_none(self) -> None:
        assert find_best_by_fingerprint({"testid": "s"}, []) is None

    def test_picks_highest_above_threshold(self) -> None:
        stored = {
            "tag": "button", "testid": "submit", "role": "button",
            "text": "Submit",
        }
        cands = [
            ("css=button.other", {"tag": "button", "role": "button"}),
            # Strong match — testid + tag + role + text = 0.65+.
            ("[data-testid=submit]", stored),
            # Weak match — just tag+role.
            ("button", {"tag": "button", "role": "button"}),
        ]
        match = find_best_by_fingerprint(stored, cands)
        assert match is not None
        assert match.selector == "[data-testid=submit]"
        assert match.score >= DEFAULT_WALKER_THRESHOLD

    def test_all_below_threshold_returns_none(self) -> None:
        stored = {"testid": "submit", "role": "button"}
        # Everything matches poorly → weighted sum below 0.6.
        cands = [
            ("other1", {"tag": "button"}),
            ("other2", {"classes": ["a"]}),
        ]
        assert find_best_by_fingerprint(stored, cands) is None

    def test_custom_threshold_respected(self) -> None:
        stored = {"testid": "submit"}
        # Testid-only = 0.45. With a 0.3 threshold it should match.
        match = find_best_by_fingerprint(
            stored, [("sel", {"testid": "submit"})], threshold=0.3,
        )
        assert match is not None
        assert match.score == pytest.approx(0.45, abs=1e-6)
