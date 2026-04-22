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
async def test_multi_match_text_strategy_left_alone_with_warning_flag():
    # text= / role= / testid= selectors don't compose with :nth-match —
    # keep verified_unique=False so the UI flags the ambiguity.
    out = await verify_candidates(
        [_c("text", "Submit", 70)],
        _factory({"Submit": 2}),
    )
    assert len(out) == 1
    assert out[0].value == "Submit"
    assert out[0].verified_unique is False


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
            "Go": 2,  # multi-match, stays unverified
        }),
    )
    # Verified (2) first, then unverified (1).
    assert out[0].verified_unique and out[1].verified_unique
    assert out[2].verified_unique is False
    # Within verified: quality 95 before 25.
    assert out[0].quality_score > out[1].quality_score
