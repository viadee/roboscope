"""Story S.3 — selector uniqueness verification."""

from __future__ import annotations

import pytest

from src.recording.selector_schema import SelectorCandidate
from src.recording.selector_verification import verify_candidates


def _c(strategy: str, value: str, score: int = 80) -> SelectorCandidate:
    return SelectorCandidate(
        strategy=strategy,  # type: ignore[arg-type]
        value=value,
        quality_score=score,
        verified_unique=False,
    )


def _factory(counts: dict[str, int]):
    async def fn(cand: SelectorCandidate) -> int:
        return counts.get(cand.value, 0)
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
async def test_factory_exception_drops_candidate():
    """Broken selector (invalid xpath, etc.) raises inside count() —
    the function swallows and drops rather than poisoning the list."""
    async def boom(_cand):
        raise ValueError("unparseable selector")
    out = await verify_candidates(
        [_c("xpath", "///invalid[")],
        boom,
    )
    assert out == []


@pytest.mark.asyncio
async def test_sort_order_verified_then_quality():
    cands = [
        _c("xpath", "/abs/path", 25),
        _c("testid", '[data-testid="a"]', 95),
        _c("text", "Go", 70),
    ]
    out = await verify_candidates(
        cands,
        _factory({
            "/abs/path": 1,
            '[data-testid="a"]': 1,
            # Multi-match — gets disambiguated to `Go >> nth=0` with
            # verified_unique=True and quality 70-15=55.
            "Go": 2,
        }),
    )
    # All three are verified after the disambiguation fix.
    assert all(c.verified_unique for c in out)
    # Sort order honours quality: testid(95) > text(55) > xpath(25).
    assert [c.quality_score for c in out] == [95, 55, 25]
    assert out[1].value == "Go >> nth=0"


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
