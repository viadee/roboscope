"""Wire-up regression for `_verify_command_candidates`.

Story S.3 implemented `verify_candidates` (uniqueness check against the
live page) months ago, but the v2 recorder's `on_capture` never called
it — every recorded command landed with `verified_unique=False` for
every candidate, even ones that were genuinely unique.

User reported it on a heise.de recording: the picker should default to
the unique selector, not whatever ranked first by static heuristics.

This test pins the wire-up: a fake `page.locator(value).count()` is
plumbed in, and we check that:

1. Unique candidates come back with `verified_unique=True`.
2. Zero-match candidates get dropped.
3. The verified list is sorted so `active_candidate_index=0` lands on
   the best candidate.
4. Commands without selector candidates (e.g. `Go To`) pass through
   untouched.
"""

from __future__ import annotations

import pytest

from src.recording.selector_schema import RecordedCommand, SelectorCandidate
from src.recording.v2_recorder_task import _verify_command_candidates


class _FakeLocator:
    def __init__(self, count: int) -> None:
        self._count = count

    async def count(self) -> int:
        return self._count


class _FakePage:
    def __init__(self, counts: dict[str, int]) -> None:
        self.counts = counts

    def locator(self, value: str) -> _FakeLocator:
        return _FakeLocator(self.counts.get(value, 0))


def _cand(value: str, score: int = 50, strategy: str = "css") -> SelectorCandidate:
    return SelectorCandidate(
        strategy=strategy,  # type: ignore[arg-type]
        value=value,
        quality_score=score,
        verified_unique=False,
    )


@pytest.mark.asyncio
async def test_unique_candidate_gets_flagged_and_promoted() -> None:
    cmd = RecordedCommand(
        index=0,
        keyword="Click",
        selector_candidates=[
            _cand(".some-class", score=40),  # >1 match → demoted
            _cand("[data-testid=login]", score=70, strategy="testid"),  # unique
        ],
        active_candidate_index=0,
    )
    page = _FakePage({".some-class": 5, "[data-testid=login]": 1})

    out = await _verify_command_candidates(cmd, page)

    # Verified candidate is now FIRST (sort order: verified > non-verified).
    assert out.selector_candidates[0].value == "[data-testid=login]"
    assert out.selector_candidates[0].verified_unique is True
    # active_candidate_index is reset to 0 so the picker auto-selects the unique one.
    assert out.active_candidate_index == 0


@pytest.mark.asyncio
async def test_zero_match_candidates_are_dropped() -> None:
    cmd = RecordedCommand(
        index=0,
        keyword="Click",
        selector_candidates=[
            _cand(".gone", score=80),  # 0 matches — drop
            _cand("button#real", score=60),  # 1 match — keep
        ],
        active_candidate_index=0,
    )
    page = _FakePage({".gone": 0, "button#real": 1})

    out = await _verify_command_candidates(cmd, page)

    assert len(out.selector_candidates) == 1
    assert out.selector_candidates[0].value == "button#real"
    assert out.selector_candidates[0].verified_unique is True


@pytest.mark.asyncio
async def test_command_without_candidates_passes_through() -> None:
    """`Go To` / `Switch Page` carry no selector — must round-trip
    unchanged. The check `if not cmd.selector_candidates` short-
    circuits before any locator call."""
    cmd = RecordedCommand(
        index=0,
        keyword="Go To",
        args={"url": "https://example.com"},
        selector_candidates=[],
        active_candidate_index=0,
    )
    page = _FakePage({})  # would 0-match anything anyway

    out = await _verify_command_candidates(cmd, page)
    assert out is cmd  # exact same object — no copy needed


@pytest.mark.asyncio
async def test_invalid_selector_syntax_is_dropped_not_kept_unverified() -> None:
    """If `page.locator(value).count()` raises (invalid CSS / xpath /
    pw_locator syntax), the candidate is treated as 0-match and
    dropped. Critical that we don't silently keep it as
    `verified_unique=False` — that would mislead the picker into
    showing it as a viable option."""

    class _BoomLocator(_FakeLocator):
        async def count(self) -> int:  # type: ignore[override]
            raise ValueError("invalid selector syntax")

    class _BoomPage(_FakePage):
        def locator(self, value: str) -> _FakeLocator:
            if value == "boom":
                return _BoomLocator(0)
            return super().locator(value)

    cmd = RecordedCommand(
        index=0,
        keyword="Click",
        selector_candidates=[
            _cand("boom", score=90),
            _cand("button.real", score=40),
        ],
        active_candidate_index=0,
    )
    page = _BoomPage({"button.real": 1})

    out = await _verify_command_candidates(cmd, page)
    assert [c.value for c in out.selector_candidates] == ["button.real"]


@pytest.mark.asyncio
async def test_no_page_object_returns_command_unchanged() -> None:
    """Defensive: if `source.page` is somehow None (test contexts /
    edge timings), the helper returns the cmd unchanged rather than
    crashing the on_capture handler (which would kill the recording)."""
    cmd = RecordedCommand(
        index=0,
        keyword="Click",
        selector_candidates=[_cand("button.x", score=50)],
        active_candidate_index=0,
    )
    out = await _verify_command_candidates(cmd, page=None)
    assert out is cmd
