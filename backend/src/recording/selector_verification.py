"""Story S.3 — verify selector uniqueness against a live DOM.

Synthesis (Story S.2) produces candidates with `verified_unique=False`
by default. This module runs each candidate against the live page to
set the flag correctly — the inline-picker UI relies on it to show the
green ✓ indicator.

The verifier ranks candidates against three signals:
  - **total**: all DOM matches (count() on the locator)
  - **visible**: matches that are paint-visible (offsetParent != null,
    no display:none / visibility:hidden ancestor)
  - **actionable**: visible AND enabled (Playwright considers them
    valid click targets — this is the gold standard for a recorded
    interaction)

A candidate qualifies as **gold** when `actionable == 1`. Gold
candidates are sorted ahead of merely-unique-but-hidden candidates
so the picker's default selection is always the cleanest one. If a
candidate matches multiple elements but exactly one is visible and
actionable, we disambiguate to `>> visible=true >> nth=0`-style
chains (or strategy-specific equivalents) so the emitted .robot line
is unambiguous.

Drop / disambiguation rules (replaces AR-7):
  - 0 total → drop (selector points at nothing)
  - actionable == 1 → verified, no penalty (gold)
  - visible == 1 (but actionable == 0, e.g. disabled button) →
    verified, slight quality penalty (-5)
  - visible > 1 → multi-match, disambiguate via strategy-specific
    nth=0 rewrite, penalty -15
  - visible == 0 but total >= 1 → element is hidden; keep with -25
    penalty so it's recorded as a fallback but ranks below any
    visible alternative

This module DOES NOT import playwright directly — it takes a
`locator_factory` callable that resolves each candidate to a
`MatchInfo`. The concrete Playwright bridge (in v2_recorder_task.py)
injects one that calls `is_visible()` / `is_enabled()` on every
match. Keeps this module testable without a browser.

Backwards-compat: a factory that returns a plain `int` is still
accepted — it's coerced to `MatchInfo(total=n, visible=n,
actionable=n)`. Existing tests written against the old contract
continue to pass.
"""

from __future__ import annotations

from typing import Awaitable, Callable, NamedTuple, Union

from src.recording.selector_schema import SelectorCandidate


class MatchInfo(NamedTuple):
    """Resolution result for one selector candidate against a live DOM."""

    total: int       # all DOM matches
    visible: int     # paint-visible (offsetParent + no hidden ancestor)
    actionable: int  # visible AND enabled (Playwright click target)


LocatorFactory = Callable[
    [SelectorCandidate],
    Awaitable[Union[int, MatchInfo, None]],
]


def _coerce_match_info(value: Union[int, MatchInfo]) -> MatchInfo:
    """Accept legacy int-returning factories by treating every match
    as fully actionable. Older tests + any in-tree callers that only
    care about uniqueness keep working without rewrites."""
    if isinstance(value, MatchInfo):
        return value
    return MatchInfo(total=value, visible=value, actionable=value)


def _with_nth_match(candidate: SelectorCandidate) -> SelectorCandidate:
    """Return a new candidate that picks the first match where the
    strategy allows.

    The original Story-S.3 implementation only handled CSS / XPath /
    pw_locator. text / aria / testid passed through unchanged with
    `verified_unique=False`, because the comment claimed "Playwright's
    text= and role= don't compose with :nth-match". That's true for
    the CSS pseudo-class `:nth-match()`, but Playwright (and Browser
    library, which passes locators through verbatim) DOES support the
    chained-locator `<base> >> nth=0` syntax for every strategy.

    Concrete failure that motivated this fix: the recorder produced
    `text=Zustimmen` for a Sourcepoint banner where two buttons AND a
    paragraph all matched. At replay, Playwright strict-mode rejected
    the click. With this change, multi-match text/aria/testid now
    disambiguate to `text=Zustimmen >> nth=0` and the click works.

    Quality score is penalised by 15 in every disambiguation branch
    so verified-but-needs-disambiguation candidates rank below truly-
    unique ones in the picker.
    """
    if candidate.strategy == "css":
        value = f"{candidate.value}:nth-match(1)"
    elif candidate.strategy == "xpath":
        # XPath has [1] positional predicate.
        value = f"({candidate.value})[1]"
    elif candidate.strategy == "pw_locator":
        value = f"{candidate.value}.first"
    elif candidate.strategy in ("text", "aria", "testid"):
        # Playwright/Browser-library chained locator. `nth=0` selects
        # the first of N matches. Same semantics as `.first()` on a
        # JS Locator.
        value = f"{candidate.value} >> nth=0"
    else:
        return candidate
    return SelectorCandidate(
        strategy=candidate.strategy,
        value=value,
        quality_score=max(0, candidate.quality_score - 15),
        verified_unique=True,
    )


async def verify_candidates(
    candidates: list[SelectorCandidate],
    locator_factory: LocatorFactory,
) -> list[SelectorCandidate]:
    """Return a new list of candidates ranked by how well each one
    resolves to a single visible + actionable element on the live page.

    Sort order: actionable-rank first (0 = gold, 1 = visible-only,
    2 = hidden, 3 = unverified-multi), then quality_score descending.

    Three outcomes per candidate:
      - `locator_factory` returns `MatchInfo` with `total >= 1` → the
        candidate is classified (gold / visible-only / hidden / multi-
        match) and joins the ranked output.
      - returns `MatchInfo(total=0, …)` → the selector resolves to
        nothing on the live page; drop.
      - returns `None` OR raises → the candidate could NOT be verified
        (frame detached after a navigation-triggering click, page
        already closed, transient browser-side error). Synthesis
        produced this candidate for a reason and the user pointed at
        SOMETHING when the click was captured — preserving it as
        unverified at the bottom of the list is far less destructive
        than silently dropping every selector whenever the user
        clicks a link or dismisses a cookie banner that removes its
        own iframe.
    """
    # Collect (candidate, MatchInfo) tuples first so we can rank
    # against the full picture instead of making one-shot decisions.
    resolved: list[tuple[SelectorCandidate, MatchInfo]] = []
    # Candidates the factory couldn't decide on — preserved at the
    # tail of the output, unverified.
    unverifiable: list[SelectorCandidate] = []
    for cand in candidates:
        try:
            raw = await locator_factory(cand)
        except Exception:
            unverifiable.append(cand)
            continue
        if raw is None:
            unverifiable.append(cand)
            continue
        info = _coerce_match_info(raw)
        if info.total == 0:
            # Selector ran but resolved to nothing on the live DOM —
            # truly stale, drop.
            continue
        resolved.append((cand, info))

    # Build the ranked output with score adjustments + verified flag.
    # `actionable_rank` is 0..3 with 0 best, surfaced via a synthetic
    # tie-break key during sort.
    def _classify(cand: SelectorCandidate, info: MatchInfo) -> tuple[
        SelectorCandidate, int,
    ]:
        if info.actionable == 1:
            # Gold standard — exactly one visible + clickable match.
            return (
                SelectorCandidate(
                    strategy=cand.strategy,
                    value=cand.value,
                    quality_score=cand.quality_score,
                    verified_unique=True,
                ),
                0,
            )
        if info.visible == 1:
            # Visible but not enabled (disabled button, readonly input,
            # …). Still recordable for non-click flows. Slight penalty.
            return (
                SelectorCandidate(
                    strategy=cand.strategy,
                    value=cand.value,
                    quality_score=max(0, cand.quality_score - 5),
                    verified_unique=True,
                ),
                1,
            )
        if info.visible == 0 and info.total >= 1:
            # Hidden element — only kept as a desperate fallback so a
            # later auto-heal can try it. Big penalty so a visible
            # alternative outranks it whenever one exists.
            return (
                SelectorCandidate(
                    strategy=cand.strategy,
                    value=cand.value,
                    quality_score=max(0, cand.quality_score - 25),
                    verified_unique=True,
                ),
                2,
            )
        # info.visible >= 2 — multi-match. Try strategy-specific
        # nth=0 rewrite. If the strategy doesn't support it, keep
        # raw with verified_unique=False so the picker flags it.
        disambiguated = _with_nth_match(cand)
        if disambiguated is cand:
            return (cand, 3)
        return (disambiguated, 1)  # disambiguated → effectively visible-1

    classified: list[tuple[SelectorCandidate, int]] = [
        _classify(c, i) for c, i in resolved
    ]
    # Sort: lower actionable_rank first, then higher quality_score
    # first, then verified_unique=True first (latter mostly redundant
    # but keeps the original Story-S.2 ordering for ties at rank 3).
    classified.sort(key=lambda t: (
        t[1],
        -t[0].quality_score,
        not t[0].verified_unique,
    ))
    # Unverifiable candidates (locator_factory raised or returned
    # None) land at the tail with their synthesis-time
    # `verified_unique=False` intact — sorted within the tail by
    # quality_score so the best-static-heuristic candidate ends up at
    # the top of the tail. The user sees them in the picker without
    # the green check, but synthesis still gets the benefit of the
    # doubt when verification couldn't happen.
    unverifiable.sort(key=lambda c: -c.quality_score)
    return [c for c, _ in classified] + unverifiable
