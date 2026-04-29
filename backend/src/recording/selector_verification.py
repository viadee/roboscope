"""Story S.3 — verify selector uniqueness against a live DOM.

Synthesis (Story S.2) produces candidates with `verified_unique=False`
by default. This module runs each candidate against the live page to
set the flag correctly — the inline-picker UI relies on it to show the
green ✓ indicator.

Non-unique candidates are handled per AR-7:
  - If exactly 0 matches → drop (selector no longer points to anything;
    probably a DOM mutation mid-capture).
  - If 1 match → set verified_unique=True.
  - If >1 matches → keep the candidate but inject `:nth-match(1)` for
    CSS / xpath / pw_locator so the emitted .robot line is
    unambiguous. Quality score is penalised by 15 to reflect the
    brittleness.

This module DOES NOT import playwright directly — it takes a `locator_
factory` callable that returns an awaitable count. The concrete
Playwright bridge (in v2_recorder_task.py) injects one that calls
`page.locator(candidate.value).count()`. Keeps this module testable
without a browser.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from src.recording.selector_schema import SelectorCandidate

LocatorFactory = Callable[[SelectorCandidate], Awaitable[int]]


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
    """Return a new list of candidates with `verified_unique` populated
    and multi-match candidates either disambiguated or dropped.

    Sort order honours the Story S.2 contract: verified_unique first,
    then quality_score descending.
    """
    out: list[SelectorCandidate] = []
    for cand in candidates:
        try:
            match_count = await locator_factory(cand)
        except Exception:
            # A broken selector (invalid xpath, CSS parse error, ...)
            # cannot be verified — drop rather than leave it as
            # verified=False (that would mislead the picker).
            continue

        if match_count == 0:
            continue
        if match_count == 1:
            out.append(
                SelectorCandidate(
                    strategy=cand.strategy,
                    value=cand.value,
                    quality_score=cand.quality_score,
                    verified_unique=True,
                )
            )
            continue
        # Multi-match: try disambiguating strategies, else keep as-is
        # with verified_unique still False so the UI flags it.
        disambiguated = _with_nth_match(cand)
        if disambiguated is cand:
            # Strategy doesn't support nth-match; keep but flag as
            # verified=False so the picker shows the amber warning.
            out.append(cand)
        else:
            out.append(disambiguated)

    out.sort(key=lambda c: (c.verified_unique, c.quality_score), reverse=True)
    return out
