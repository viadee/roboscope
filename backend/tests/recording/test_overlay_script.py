"""Story W.4 — hover overlay surface."""

from __future__ import annotations

from src.recording.overlay_script import OVERLAY_SCRIPT, overlay_script


class TestOverlayStructure:
    def test_iife_wrapper(self) -> None:
        assert OVERLAY_SCRIPT.strip().startswith("(() => {")
        assert OVERLAY_SCRIPT.strip().endswith("})();")

    def test_idempotency_guard(self) -> None:
        assert "__roboscopeOverlayInstalled" in OVERLAY_SCRIPT

    def test_pointer_events_none(self) -> None:
        # Overlay must never intercept clicks (AC-FR3).
        assert "pointer-events: none" in OVERLAY_SCRIPT

    def test_aria_hidden(self) -> None:
        # Overlay never surfaces in the accessibility tree.
        assert 'setAttribute("aria-hidden", "true")' in OVERLAY_SCRIPT

    def test_reduced_motion_branch(self) -> None:
        assert "prefers-reduced-motion: reduce" in OVERLAY_SCRIPT


class TestEventHandlers:
    def test_mousemove_handler(self) -> None:
        assert 'addEventListener("mousemove"' in OVERLAY_SCRIPT

    def test_mouseout_hides(self) -> None:
        assert 'addEventListener("mouseout"' in OVERLAY_SCRIPT

    def test_scroll_repositions(self) -> None:
        # Scroll must keep the overlay aligned with the target.
        assert 'addEventListener("scroll"' in OVERLAY_SCRIPT

    def test_toggle_hotkey(self) -> None:
        # Ctrl+Shift+X shows/hides without re-recording (AC-FR3).
        assert "ev.ctrlKey && ev.shiftKey" in OVERLAY_SCRIPT
        assert 'ev.key.toLowerCase() === "x"' in OVERLAY_SCRIPT


class TestLabelContents:
    def test_label_shows_tag_and_dimensions(self) -> None:
        assert "tagName.toLowerCase()" in OVERLAY_SCRIPT
        assert "Math.round(r.width)" in OVERLAY_SCRIPT
        assert "Math.round(r.height)" in OVERLAY_SCRIPT


class TestHelper:
    def test_helper_returns_overlay_script(self) -> None:
        assert overlay_script() == OVERLAY_SCRIPT
