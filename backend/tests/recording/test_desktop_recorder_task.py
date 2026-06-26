"""Story D.2 — UIA event → RecordedCommand translator.

The pywinauto hook wiring lives in `_desktop_loop` and needs a Windows
host; these tests only exercise the pure-Python translator that will
be called from that hook.
"""

from __future__ import annotations

import threading
import time

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


def _edit_snapshot(automation_id):
    return {
        "control_type": "Edit",
        "automation_id": automation_id,
        "name": None,
        "class_name": "TextBox",
        "ancestors": [],
    }


def _button_snapshot(automation_id):
    return {
        "control_type": "Button",
        "automation_id": automation_id,
        "name": None,
        "class_name": None,
        "ancestors": [],
    }


class TestDesktopLoopStopLatency:
    """Story D-5 — the capture loop drains an injectable `event_source`
    through `pump_raw_events`, checking `stop_event` between events. When the
    user clicks Stop the loop exits promptly (no busy-poll), mirroring the
    asyncio refactor in v2_recorder_task."""

    def test_stop_event_unblocks_loop_immediately(self, monkeypatch) -> None:
        from src.recording import desktop_recorder_task as drt

        monkeypatch.setattr(drt, "_mark_status", lambda *_a, **_kw: None)

        ev = threading.Event()

        def blocking_source(stop):
            # Mimic the real Windows generator: yield nothing while idle,
            # return as soon as stop is signalled.
            while not stop.wait(0.01):
                pass
            return
            yield  # noqa: unreachable — makes this a generator

        FIRE_DELAY_S = 0.05
        loop_thread = threading.Thread(
            target=drt._desktop_loop,
            args=(99999, ev, blocking_source(ev)),
            daemon=True,
        )
        loop_thread.start()

        time.sleep(FIRE_DELAY_S)
        t0 = time.perf_counter()
        ev.set()
        loop_thread.join(timeout=2.0)
        elapsed = time.perf_counter() - t0

        assert not loop_thread.is_alive(), "loop thread did not exit on stop"
        assert elapsed < 0.2, (
            f"desktop loop took {elapsed:.3f}s to exit after stop_event.set() "
            "— should be near-instant"
        )

    def test_stop_event_already_set_exits_immediately(self, monkeypatch) -> None:
        from src.recording import desktop_recorder_task as drt

        monkeypatch.setattr(drt, "_mark_status", lambda *_a, **_kw: None)

        ev = threading.Event()
        ev.set()  # already set
        t0 = time.perf_counter()
        drt._desktop_loop(99998, ev, iter([]))  # empty source → returns at once
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.1


class TestDesktopCaptureIntegration:
    """Story D-5 — drive the REAL capture pipeline end to end on any OS via
    the `event_source` injection seam: raw events → accumulator → translator
    → enqueue, then assert the emitted `.robot` targets RPA.Windows."""

    def test_capture_to_rpa_windows_robot(self, monkeypatch) -> None:
        from src.recording import desktop_recorder_task as drt
        from src.recording.desktop_capture import RawKey, RawMouse
        from src.recording.robot_emit import emit_robot
        from src.recording.selector_schema import RecordedFlow

        # Avoid the DB write in _mark_status; collect enqueued commands.
        monkeypatch.setattr(drt, "_mark_status", lambda *_a, **_kw: None)
        captured = []
        monkeypatch.setattr(
            drt, "enqueue_command", lambda _sid, cmd: captured.append(cmd) or True
        )

        edit = _edit_snapshot("username")
        events = [
            RawKey("a", snapshot=edit),
            RawKey("b", snapshot=edit),
            RawKey("c", snapshot=edit),
            RawMouse(snapshot=_button_snapshot("submit")),
            RawMouse(snapshot=_button_snapshot("row"), double=True),
        ]

        drt.run_desktop_recorder_session(4242, event_source=iter(events))

        assert [c.keyword for c in captured] == ["Type Text", "Click", "Double Click"]
        assert captured[0].args["text"] == "abc"
        # Indices are assigned sequentially by the loop's emit closure.
        assert [c.index for c in captured] == [0, 1, 2]
        # Every targeted command carries an automation_id candidate.
        assert any(s.strategy == "automation_id" for s in captured[1].selector_candidates)

        robot = emit_robot(
            RecordedFlow(
                transport="desktop_windows",
                session_id="4242",
                commands=captured,
            )
        )
        assert "Library           RPA.Windows" in robot
        assert "Type Text" in robot
        assert "id:submit" in robot  # RPA.Windows AutomationId locator syntax
        assert "Double Click" in robot

    def test_non_windows_without_source_no_ops(self, monkeypatch) -> None:
        """Without an injected source on a non-Windows host the task marks the
        session FAILED instead of trying to build the Win32 source."""
        from src.recording import desktop_recorder_task as drt

        monkeypatch.setattr(drt.sys, "platform", "linux")
        statuses = []
        monkeypatch.setattr(
            drt, "_mark_status", lambda _sid, status, *a, **k: statuses.append(status)
        )
        monkeypatch.setattr(drt, "finalize_session", lambda *_a, **_k: None)
        monkeypatch.setattr(drt, "tear_down_session", lambda *_a, **_k: None)

        drt.run_desktop_recorder_session(7777)
        assert statuses and statuses[0] == drt.RecordingStatus.FAILED
