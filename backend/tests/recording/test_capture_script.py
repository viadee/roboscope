"""Story W.3 — capture script surface + structure.

The script runs in the target browser, so unit-testing its actual
behaviour belongs in an e2e Playwright spec (phase4-gates.yml adds
one in the Recorder sprint). These Python tests only assert the
static surface area:

  - every AC-FR2 primitive has an emitter registered.
  - the emitted kinds match EMITTED_KINDS (regression guard — if we
    drop a listener, the build fails here).
  - the script is idempotent (second include is a no-op) per the
    `__roboscopeCaptureInstalled` flag.
  - init-script safety: no uncaught throws inside the `send` helper
    (leaks into the page otherwise).
  - `capture_script_for_session` returns the same content so future
    per-session tweaks can be added without changing the call-site.
"""

from __future__ import annotations

from src.recording.capture_script import (
    CAPTURE_SCRIPT,
    EMITTED_KINDS,
    capture_script_for_session,
)


class TestScriptStructure:
    def test_iife_wrapper(self) -> None:
        # The script is wrapped in an IIFE so it does not leak locals.
        assert CAPTURE_SCRIPT.strip().startswith("(() => {")
        assert CAPTURE_SCRIPT.strip().endswith("})();")

    def test_idempotency_guard(self) -> None:
        assert "__roboscopeCaptureInstalled" in CAPTURE_SCRIPT

    def test_send_is_safe_by_design(self) -> None:
        # The send helper swallows errors to avoid throwing into the page.
        assert "try {" in CAPTURE_SCRIPT and "catch (e)" in CAPTURE_SCRIPT


class TestEventHandlers:
    def test_click_handler_registered(self) -> None:
        assert 'addEventListener("click"' in CAPTURE_SCRIPT

    def test_dblclick_handler_registered(self) -> None:
        assert 'addEventListener("dblclick"' in CAPTURE_SCRIPT

    def test_text_input_handler_registered(self) -> None:
        # Uses 'change' on input/textarea/contenteditable.
        assert 'addEventListener("change"' in CAPTURE_SCRIPT

    def test_keydown_handler_registered(self) -> None:
        assert 'addEventListener("keydown"' in CAPTURE_SCRIPT

    def test_scroll_handler_registered(self) -> None:
        assert 'addEventListener("scroll"' in CAPTURE_SCRIPT

    def test_drag_drop_paired(self) -> None:
        assert 'addEventListener("dragstart"' in CAPTURE_SCRIPT
        assert 'addEventListener("drop"' in CAPTURE_SCRIPT

    def test_navigation_hooks(self) -> None:
        assert "history.pushState" in CAPTURE_SCRIPT
        assert "history.replaceState" in CAPTURE_SCRIPT
        assert 'addEventListener("popstate"' in CAPTURE_SCRIPT


class TestEmittedKinds:
    def test_all_kinds_appear_in_script(self) -> None:
        # Regression guard: if a new kind is added to EMITTED_KINDS but
        # not wired into the script (or vice versa), this test fires.
        for kind in EMITTED_KINDS:
            assert f'kind: "{kind}"' in CAPTURE_SCRIPT, f"missing kind={kind}"

    def test_expected_primitives_present(self) -> None:
        # AC-FR2: nav / click / type / scroll / drag-drop.
        for required in ("navigate", "click", "type", "scroll", "drag_drop"):
            assert required in EMITTED_KINDS


class TestHelperFunction:
    def test_per_session_helper_returns_same_content(self) -> None:
        a = capture_script_for_session(1)
        b = capture_script_for_session(42)
        assert a == b == CAPTURE_SCRIPT
