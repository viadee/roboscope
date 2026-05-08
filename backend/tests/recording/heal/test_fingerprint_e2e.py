"""Story SH-3 — real-browser integration test for the fingerprint walker.

The drift fixture renames the button id + moves it into a different
wrapper, so neither the original selector nor its strategy
transpositions hit. The fingerprint walker should still pick it via
multi-signal similarity (testid + role + text).
"""

from __future__ import annotations

from pathlib import Path

import pytest


DRIFT_FIXTURE = (
    Path(__file__).resolve().parent.parent.parent
    / "fixtures" / "heal_drift_fixture.html"
)


@pytest.mark.integration
def test_fingerprint_walker_finds_drifted_element_on_real_dom() -> None:
    from playwright.sync_api import sync_playwright

    from src.recording.heal.fingerprint import (
        DEFAULT_WALKER_THRESHOLD,
        find_best_by_fingerprint,
    )

    assert DRIFT_FIXTURE.is_file(), f"missing fixture: {DRIFT_FIXTURE}"

    # Fingerprint captured at the original recording — note the *old*
    # id (`submit-v1`) that no longer exists on the live page. The
    # stable signals (testid + role + text) survive.
    stored_fp = {
        "tag": "button",
        "id": "submit-v1",
        "testid": "submit",
        "classes": ["primary-cta"],
        "name": None,
        "role": "button",
        "text": "Submit",
        "ancestors": [
            {"tag": "form", "id": None, "testid": "login-form"},
        ],
    }

    # JS copied verbatim from RoboScopeHeal._LIVE_CANDIDATE_JS. Keeps
    # the integration test honest about what the runtime would see.
    LIVE_JS = """
    (() => {
      const out = [];
      const sel = 'button, a, input, select, textarea, [data-testid], [role]';
      const nodes = Array.from(document.querySelectorAll(sel)).slice(0, 500);
      for (const n of nodes) {
        const fp = {
          tag: (n.tagName || '').toLowerCase(),
          id: n.id || null,
          testid: n.getAttribute('data-testid') || null,
          classes: Array.from(n.classList || []),
          name: n.getAttribute('name') || null,
          role: n.getAttribute('role') || null,
          text: (n.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 80),
          ancestors: [],
        };
        let p = n.parentElement;
        while (p && fp.ancestors.length < 4) {
          fp.ancestors.push({
            tag: (p.tagName || '').toLowerCase(),
            id: p.id || null,
            testid: p.getAttribute && p.getAttribute('data-testid') || null,
          });
          p = p.parentElement;
        }
        let locator;
        if (fp.testid) locator = '[data-testid=' + fp.testid + ']';
        else if (fp.id) locator = 'id=' + fp.id;
        else if (fp.classes.length) locator = fp.tag + '.' + fp.classes[0];
        else locator = fp.tag;
        out.push({ selector: locator, fingerprint: fp });
      }
      return out;
    })()
    """

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_context().new_page()
        page.goto(DRIFT_FIXTURE.as_uri())
        live = page.evaluate(LIVE_JS)
        browser.close()

    pairs = [(i["selector"], i["fingerprint"]) for i in live]
    # Sanity: the walker must see multiple candidates from the fixture.
    assert len(pairs) >= 4, f"live collection should pull several nodes, got {len(pairs)}"

    match = find_best_by_fingerprint(
        stored_fp, pairs, threshold=DEFAULT_WALKER_THRESHOLD,
    )
    assert match is not None, (
        "fingerprint walker should still find the drifted Submit button"
    )
    # The winner must be the Submit button, not the Cancel button.
    # Testid is the strongest signal.
    assert "data-testid=submit" in match.selector or "submit-v2" in match.selector
    assert match.score >= DEFAULT_WALKER_THRESHOLD
