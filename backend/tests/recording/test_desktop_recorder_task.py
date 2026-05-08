"""Story D.2 — UIA event → RecordedCommand translator.

The pywinauto hook wiring lives in `_desktop_loop` and needs a Windows
host; these tests only exercise the pure-Python translator that will
be called from that hook.
"""

from __future__ import annotations

import sys
import threading
import time
import types

import pytest

from src.recording.desktop_recorder_task import translate_uia_event


def _el(**kwargs):
    kwargs.setdefault("control_type", "Button")
    return {
        "control_type": kwargs["control_type"],
        "automation_id": kwargs.get("automation_id"),
        "name": kwargs.get("name"),
        "class_name": kwargs.get("class_name"),
        "ancestors": [],
    }


class TestClick:
    def test_click_emits_click_keyword_with_candidates(self) -> None:
        cmd = translate_uia_event(
            {"kind": "click", "element": _el(automation_id="submit")}, 0
        )
        assert cmd is not None
        assert cmd.keyword == "Click"
        assert any(c.strategy == "automation_id" for c in cmd.selector_candidates)

    def test_dblclick_maps_to_double_click(self) -> None:
        cmd = translate_uia_event(
            {"kind": "dblclick", "element": _el(automation_id="row")}, 0
        )
        assert cmd is not None
        assert cmd.keyword == "Double Click"


class TestType:
    def test_type_has_text_arg(self) -> None:
        cmd = translate_uia_event(
            {
                "kind": "type",
                "text": "alice@corp",
                "element": _el(control_type="Edit", automation_id="user"),
            },
            0,
        )
        assert cmd is not None
        assert cmd.keyword == "Type Text"
        assert cmd.args["text"] == "alice@corp"


class TestSelectFromCombobox:
    def test_value_arg_present(self) -> None:
        cmd = translate_uia_event(
            {
                "kind": "combobox_select",
                "value": "Germany",
                "element": _el(control_type="ComboBox", automation_id="country"),
            },
            0,
        )
        assert cmd is not None
        assert cmd.keyword == "Select From Combobox"
        assert cmd.args["value"] == "Germany"


class TestSelectFromMenu:
    def test_menu_item_captured(self) -> None:
        cmd = translate_uia_event(
            {
                "kind": "menu_select",
                "value": "File>Export>PDF",
                "element": _el(control_type="MenuItem", name="PDF"),
            },
            0,
        )
        assert cmd is not None
        assert cmd.keyword == "Select From Menu"
        assert cmd.args["value"] == "File>Export>PDF"


class TestWindowFocus:
    def test_control_window(self) -> None:
        cmd = translate_uia_event(
            {"kind": "window_focus", "element": _el(control_type="Window", name="Payroll")},
            0,
        )
        assert cmd is not None
        assert cmd.keyword == "Control Window"


class TestUnknownKind:
    def test_unknown_returns_none(self) -> None:
        assert translate_uia_event({"kind": "teleport"}, 0) is None

    def test_missing_kind_returns_none(self) -> None:
        assert translate_uia_event({}, 0) is None


class TestIndexPropagation:
    def test_index_passes_through(self) -> None:
        for i in (0, 5, 42):
            cmd = translate_uia_event(
                {"kind": "click", "element": _el(automation_id="x")}, i
            )
            assert cmd is not None
            assert cmd.index == i


class TestCandidatesShape:
    def test_empty_element_still_yields_some_xpath(self) -> None:
        # The absolute-control-type xpath from D.3 is always present.
        cmd = translate_uia_event({"kind": "click", "element": _el()}, 0)
        assert cmd is not None
        assert any(c.strategy == "xpath" for c in cmd.selector_candidates)


class TestDesktopLoopStopLatency:
    """`_desktop_loop` previously polled the stop event at 2Hz
    (`stop_event.wait(timeout=0.5)` in a `while` loop). That added up
    to half a second of latency between the user clicking Stop and
    the desktop recorder thread exiting. The current implementation
    is `stop_event.wait()` (no timeout) — blocks until the event
    fires and returns instantly. Same UX win as the asyncio refactor
    in v2_recorder_task (commit 06ee6d1)."""

    @pytest.fixture
    def _fake_pywinauto(self, monkeypatch: pytest.MonkeyPatch):
        """Inject a stub `pywinauto` module so the deferred import
        inside `_desktop_loop` resolves on non-Windows test hosts.
        The loop never CALLS into pywinauto until the D.1-full hook
        wiring lands, so a bare module is enough."""
        fake = types.ModuleType("pywinauto")
        monkeypatch.setitem(sys.modules, "pywinauto", fake)

    def test_stop_event_unblocks_loop_immediately(
        self, _fake_pywinauto, monkeypatch
    ) -> None:
        from src.recording import desktop_recorder_task as drt

        # Spy on _mark_status so the loop's COMPLETED side effect
        # doesn't try to touch a real DB session.
        monkeypatch.setattr(drt, "_mark_status", lambda *_a, **_kw: None)

        ev = threading.Event()
        # Run the loop in a thread; signal stop after a short delay
        # and measure total elapsed time. Legacy 2Hz polling would
        # mean ~500ms baseline lag; event-driven wait should be
        # near-zero (just thread scheduling overhead).
        FIRE_DELAY_S = 0.05
        loop_thread = threading.Thread(
            target=drt._desktop_loop, args=(99999, ev), daemon=True,
        )
        loop_thread.start()

        time.sleep(FIRE_DELAY_S)
        t0 = time.perf_counter()
        ev.set()
        loop_thread.join(timeout=2.0)
        elapsed = time.perf_counter() - t0

        assert not loop_thread.is_alive(), "loop thread did not exit on stop"
        # Generous 200ms ceiling — covers thread scheduling on slow
        # CI; the legacy 2Hz polling would routinely exceed this.
        assert elapsed < 0.2, (
            f"desktop loop took {elapsed:.3f}s to exit after stop_event.set() "
            "— should be near-instant under the event-driven wait"
        )

    def test_stop_event_already_set_exits_immediately(
        self, _fake_pywinauto, monkeypatch
    ) -> None:
        """If `stop_event` is set BEFORE the loop runs, `Event.wait()`
        returns immediately — the loop must exit without a poll
        round-trip."""
        from src.recording import desktop_recorder_task as drt

        monkeypatch.setattr(drt, "_mark_status", lambda *_a, **_kw: None)

        ev = threading.Event()
        ev.set()  # already set
        t0 = time.perf_counter()
        drt._desktop_loop(99998, ev)  # synchronous; runs to completion
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.1, (
            f"loop with already-set event took {elapsed:.3f}s — must "
            "return immediately, not after a poll tick"
        )
