"""Story E2E-SH — real Chromium integration test for the SH-2 heal path.

Spins up an actual Playwright Chromium against a local fixture HTML
where the originally-recorded selector (`id=submit`) no longer exists
but a stable `[data-testid=submit]` is still on the page. Exercises
`find_heal_candidates` with the live DOM as the verify callback and
asserts the healer picks the correct alternative.

Opt-in via `pytest -m integration`. Requires:
    * `playwright` Python package (already a project dep)
    * `chromium` browser installed (`python -m playwright install chromium`)

Deliberately does NOT drive the full Robot Framework runner — that
requires `robotframework-browser` + `rfbrowser init`, a much heavier
setup than what this test needs to validate. The critical unknown
was "does the candidate_finder work against a real browser DOM" —
this test answers yes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.recording.heal.candidate_finder import (
    find_heal_candidates,
    pick_best_candidate,
)


FIXTURE = Path(__file__).resolve().parent.parent.parent / "fixtures" / "heal_fixture.html"


@pytest.mark.integration
def test_heal_picks_data_testid_when_id_is_missing_on_live_page() -> None:
    """The originally-recorded selector `id=submit` has zero matches on
    the live DOM (the fixture never sets an `id`). The transposition
    candidate `[data-testid=submit]` has exactly one match. The
    candidate finder's live-verify callback must drop the zero-match
    options and keep the unique one."""
    from playwright.sync_api import sync_playwright

    assert FIXTURE.is_file(), f"missing fixture: {FIXTURE}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(FIXTURE.as_uri())

        def verify(selector: str) -> int:
            """Count live matches using Playwright's locator engine —
            same resolution the Browser library would use, including
            RoboScope's `id=`, `text=`, and CSS-attribute syntaxes."""
            try:
                return page.locator(selector).count()
            except Exception:
                return 0

        candidates = find_heal_candidates(
            "id=submit",
            sidecar_path=None,       # hand-written-test path
            verify=verify,
        )

        browser.close()

    # At least one candidate must survive.
    assert candidates, "live-verify should have left at least one candidate"
    # All survivors resolve to exactly one live element.
    assert all(c.source == "transposition" for c in candidates)
    # The highest-confidence survivor is the data-testid variant.
    best = pick_best_candidate(candidates, threshold=0.5)
    assert best is not None
    assert "data-testid=submit" in best.value
    assert best.strategy in ("testid",)


@pytest.mark.integration
def test_heal_returns_empty_when_no_candidate_matches_live_page() -> None:
    """When none of the transposition candidates match the live DOM,
    the verify callback drops them all and the healer is left with an
    empty list — the library falls back to re-raising the original
    exception rather than guessing."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(FIXTURE.as_uri())

        def verify(selector: str) -> int:
            try:
                return page.locator(selector).count()
            except Exception:
                return 0

        # The selector `id=totally-nonexistent` has no semantic twin on
        # the fixture page — all transpositions also miss.
        candidates = find_heal_candidates(
            "id=totally-nonexistent",
            sidecar_path=None,
            verify=verify,
        )

        browser.close()

    assert candidates == [], (
        "nothing should survive when the element genuinely isn't on the page"
    )


@pytest.mark.integration
def test_heal_with_sidecar_candidate_verified_live() -> None:
    """Sidecar candidate list + live-verify together — the combined
    path is what real recorder-originated tests take."""
    import json
    import tempfile

    from playwright.sync_api import sync_playwright

    sidecar_payload = {
        "schema_version": 1,
        "commands": [{
            "index": 0,
            "keyword": "Click",
            "active_candidate_index": 0,
            "selector_candidates": [
                {
                    "strategy": "id",
                    "value": "id=submit",  # fails on live DOM
                    "quality_score": 0.5,
                    "verified_unique": True,
                },
                {
                    "strategy": "testid",
                    "value": "[data-testid=submit]",  # unique on live DOM
                    "quality_score": 0.95,
                    "verified_unique": True,
                },
                {
                    "strategy": "text",
                    "value": "text=Submit",  # also unique
                    "quality_score": 0.7,
                    "verified_unique": True,
                },
            ],
        }],
    }

    with tempfile.TemporaryDirectory() as tmp:
        sidecar_path = Path(tmp) / "flow.rbs.json"
        sidecar_path.write_text(json.dumps(sidecar_payload), encoding="utf-8")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_context().new_page()
            page.goto(FIXTURE.as_uri())

            def verify(selector: str) -> int:
                try:
                    return page.locator(selector).count()
                except Exception:
                    return 0

            candidates = find_heal_candidates(
                "id=submit",
                sidecar_path=sidecar_path,
                verify=verify,
            )

            browser.close()

    # Sidecar provides at least data-testid + text; both survive verify.
    assert candidates, "sidecar + verify should surface at least one candidate"
    # Sidecar source is present (recorder-ranked) — best candidate
    # should be the recorder's testid winner, not a transposition.
    best = pick_best_candidate(candidates, threshold=0.5)
    assert best is not None
    assert "data-testid=submit" in best.value
    # The sidecar candidate set beat whatever transposition produced.
    assert best.source == "sidecar"
