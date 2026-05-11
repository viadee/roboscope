"""Story S.3 — selector uniqueness verification."""

from __future__ import annotations

import pytest

from src.recording.selector_schema import SelectorCandidate
from src.recording.selector_verification import MatchInfo, verify_candidates


def _c(strategy: str, value: str, score: int = 80) -> SelectorCandidate:
    return SelectorCandidate(
        strategy=strategy,  # type: ignore[arg-type]
        value=value,
        quality_score=score,
        verified_unique=False,
    )


def _factory(counts: dict[str, int]):
    """Legacy int-returning factory — every match is treated as
    fully actionable (total == visible == actionable). Existing tests
    written before MatchInfo landed continue to pass via the
    backwards-compat coercion in `selector_verification`."""
    async def fn(cand: SelectorCandidate) -> int:
        return counts.get(cand.value, 0)
    return fn


def _info_factory(infos: dict[str, MatchInfo]):
    """MatchInfo-returning factory for tests that want to exercise
    the visible / actionable distinctions."""
    async def fn(cand: SelectorCandidate) -> MatchInfo:
        return infos.get(cand.value, MatchInfo(0, 0, 0))
    return fn


@pytest.mark.asyncio
async def test_unique_candidate_gets_verified_flag():
    out = await verify_candidates(
        [_c("testid", '[data-testid="x"]', 95)],
        _factory({'[data-testid="x"]': 1}),
    )
    assert len(out) == 1
    assert out[0].verified_unique is True


@pytest.mark.asyncio
async def test_zero_match_candidate_dropped():
    out = await verify_candidates(
        [_c("css", ".stale", 50)],
        _factory({".stale": 0}),
    )
    assert out == []


@pytest.mark.asyncio
async def test_multi_match_css_gets_nth_match_and_penalty():
    out = await verify_candidates(
        [_c("css", ".generic", 50)],
        _factory({".generic": 7}),
    )
    assert len(out) == 1
    assert out[0].value == ".generic:nth-match(1)"
    assert out[0].quality_score == 50 - 15
    assert out[0].verified_unique is True


@pytest.mark.asyncio
async def test_multi_match_xpath_gets_positional_wrapper():
    out = await verify_candidates(
        [_c("xpath", '//button', 25)],
        _factory({'//button': 3}),
    )
    assert out[0].value == '(//button)[1]'
    assert out[0].quality_score == 25 - 15


@pytest.mark.asyncio
async def test_multi_match_pw_locator_appends_first():
    out = await verify_candidates(
        [_c("pw_locator", 'getByRole("button")', 75)],
        _factory({'getByRole("button")': 4}),
    )
    assert out[0].value == 'getByRole("button").first'
    assert out[0].quality_score == 75 - 15


@pytest.mark.asyncio
async def test_multi_match_text_strategy_disambiguated_via_nth_zero():
    """Heise.de Sourcepoint banner reproduced this: `text=Zustimmen`
    matched 3 elements (one paragraph + two duplicate buttons), and
    Playwright strict-mode rejected the click. The original
    implementation returned text/aria/testid candidates unchanged
    with `verified_unique=False`; the verifier now appends Playwright's
    chained-locator `>> nth=0` to disambiguate."""
    out = await verify_candidates(
        [_c("text", "Submit", 70)],
        _factory({"Submit": 2}),
    )
    assert len(out) == 1
    assert out[0].value == "Submit >> nth=0"
    assert out[0].verified_unique is True
    assert out[0].quality_score == 70 - 15


@pytest.mark.asyncio
async def test_multi_match_aria_strategy_disambiguated_via_nth_zero():
    out = await verify_candidates(
        [_c("aria", '[aria-label="Zustimmen"]', 80)],
        _factory({'[aria-label="Zustimmen"]': 2}),
    )
    assert out[0].value == '[aria-label="Zustimmen"] >> nth=0'
    assert out[0].verified_unique is True


@pytest.mark.asyncio
async def test_multi_match_testid_strategy_disambiguated_via_nth_zero():
    """Two elements sharing a data-testid is a known anti-pattern;
    rather than reject the test, surface the first one with a
    quality-score penalty so the developer notices in the picker."""
    out = await verify_candidates(
        [_c("testid", '[data-testid="row"]', 90)],
        _factory({'[data-testid="row"]': 5}),
    )
    assert out[0].value == '[data-testid="row"] >> nth=0'
    assert out[0].verified_unique is True
    assert out[0].quality_score == 90 - 15


@pytest.mark.asyncio
async def test_factory_exception_preserves_candidate_as_unverified():
    """The factory raising means verification couldn't run — most
    commonly because a navigation-triggering click detached the
    frame between capture and verify. Preserve the candidate at the
    tail of the output with `verified_unique=False` rather than
    dropping it; synthesis produced it for a reason and a click on
    a link shouldn't silently empty the candidate list."""
    async def boom(_cand):
        raise ValueError("frame was detached after navigation")
    out = await verify_candidates(
        [_c("xpath", "///invalid[")],
        boom,
    )
    assert len(out) == 1
    assert out[0].verified_unique is False
    assert out[0].value == "///invalid["


@pytest.mark.asyncio
async def test_factory_none_return_preserves_candidate_as_unverified():
    """Explicit `None` return from the factory carries the same
    semantics as raising — couldn't verify, preserve as-is."""
    async def cant_decide(_cand):
        return None
    out = await verify_candidates(
        [_c("css", "button.maybe-real")],
        cant_decide,
    )
    assert len(out) == 1
    assert out[0].verified_unique is False


@pytest.mark.asyncio
async def test_factory_unverifiable_tail_sorted_after_verified():
    """When SOME candidates verify cleanly and others can't be
    verified, the verified ones lead the list (in their classified
    order) and the unverifiable tail follows, ranked by their own
    quality_score so the best static heuristic candidate is the
    first unverified option."""
    async def factory(c):
        if c.value in ("good_a", "good_b"):
            return MatchInfo(total=1, visible=1, actionable=1)
        raise RuntimeError("locator died mid-flight")

    out = await verify_candidates(
        [
            _c("text", "boom_high", score=90),
            _c("css", "good_a", score=70),
            _c("xpath", "boom_low", score=30),
            _c("testid", "good_b", score=50),
        ],
        factory,
    )
    assert [c.value for c in out] == ["good_a", "good_b", "boom_high", "boom_low"]
    assert [c.verified_unique for c in out] == [True, True, False, False]


@pytest.mark.asyncio
async def test_sort_order_actionable_rank_then_quality():
    """With the visibility-aware ranking, gold candidates (actionable
    == 1) always come before disambiguated-multi-match ones, even
    when the disambiguated candidate has the higher quality_score.
    Within the same actionable rank, quality_score still wins."""
    cands = [
        _c("xpath", "/abs/path", 25),           # gold, low score
        _c("testid", '[data-testid="a"]', 95),  # gold, top score
        _c("text", "Go", 70),                   # disambiguated multi-match
    ]
    out = await verify_candidates(
        cands,
        _factory({
            "/abs/path": 1,
            '[data-testid="a"]': 1,
            # Multi-match — gets disambiguated to `Go >> nth=0` with
            # verified_unique=True and quality 70-15=55, but lands at
            # actionable_rank=1 (visible-only, post-nth=0 chain).
            "Go": 2,
        }),
    )
    # All three are verified after the disambiguation fix.
    assert all(c.verified_unique for c in out)
    # Gold rank first (testid 95, xpath 25), then visible-only (Go 55).
    assert [c.quality_score for c in out] == [95, 25, 55]
    assert out[2].value == "Go >> nth=0"


@pytest.mark.asyncio
async def test_unsupported_strategy_with_multi_match_keeps_unverified_flag():
    """Desktop-only strategies (`automation_id`, `uia_name`,
    `uia_class_name`) aren't disambiguated here — the desktop emitter
    handles them differently. Keep them as unverified to surface in
    the picker rather than dropping silently."""
    out = await verify_candidates(
        [_c("automation_id", "Btn1", 80)],
        _factory({"Btn1": 3}),
    )
    assert len(out) == 1
    assert out[0].value == "Btn1"
    assert out[0].verified_unique is False


# ---------------------------------------------------------------------
# Visibility / actionable-aware ranking
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gold_actionable_outranks_hidden_unique():
    """Recorded against a page with two equally-unique selectors —
    one resolves to a visible+enabled target, the other to a
    detached/hidden node. The gold one must come first regardless of
    quality_score so the user's recording defaults to the working
    locator."""
    out = await verify_candidates(
        [
            _c("xpath", "//hidden", 95),  # higher quality, hidden
            _c("css", "#visible-btn", 60),  # lower quality, gold
        ],
        _info_factory({
            "//hidden": MatchInfo(total=1, visible=0, actionable=0),
            "#visible-btn": MatchInfo(total=1, visible=1, actionable=1),
        }),
    )
    # Gold first, hidden second (both kept as fallbacks).
    assert out[0].value == "#visible-btn"
    assert out[1].value == "//hidden"


@pytest.mark.asyncio
async def test_visible_but_disabled_keeps_verified_flag():
    """Disabled buttons are still recordable (Type Text on a readonly
    field is a valid pattern). Verifier keeps verified_unique=True
    but applies a small penalty so a fully-actionable alternative
    outranks it."""
    out = await verify_candidates(
        [_c("css", "#disabled", 80)],
        _info_factory({
            "#disabled": MatchInfo(total=1, visible=1, actionable=0),
        }),
    )
    assert len(out) == 1
    assert out[0].verified_unique is True
    assert out[0].quality_score == 80 - 5


@pytest.mark.asyncio
async def test_hidden_unique_gets_heavy_penalty():
    """Single-match-but-hidden candidate keeps verified_unique=True
    so the picker doesn't show the amber warning, but takes a -25
    quality hit so any visible alternative ranks above it."""
    out = await verify_candidates(
        [_c("xpath", "//offscreen", 90)],
        _info_factory({
            "//offscreen": MatchInfo(total=1, visible=0, actionable=0),
        }),
    )
    assert len(out) == 1
    assert out[0].quality_score == 90 - 25


@pytest.mark.asyncio
async def test_zero_total_drops_even_when_visible_count_implausible():
    """Defensive: if a (broken) factory reports total=0 with non-zero
    visible/actionable, we still drop the candidate. The contract is
    'total is the source of truth for existence'."""
    out = await verify_candidates(
        [_c("css", "#nope", 50)],
        _info_factory({
            "#nope": MatchInfo(total=0, visible=2, actionable=2),
        }),
    )
    assert out == []


@pytest.mark.asyncio
async def test_legacy_int_factory_treated_as_fully_actionable():
    """Tests written before MatchInfo landed pass int counts. The
    coercion treats every match as visible+actionable, so a single
    match still ranks as gold — preserving the original Story-S.2
    sort behavior for the back-catalogue of test fixtures."""
    out = await verify_candidates(
        [_c("css", "#btn", 70)],
        _factory({"#btn": 1}),
    )
    assert len(out) == 1
    assert out[0].verified_unique is True
    assert out[0].quality_score == 70  # no penalty
