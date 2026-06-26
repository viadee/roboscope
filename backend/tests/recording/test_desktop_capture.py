"""Story D-5 — pure desktop-capture logic.

These tests run on ANY OS: `desktop_capture` has no Windows imports. They
cover the element-snapshot extraction and the stateful event accumulator that
turns raw mouse/keyboard events into translator payloads.
"""

from __future__ import annotations

import threading

import pytest

from src.recording.desktop_capture import (
    DesktopEventAccumulator,
    RawFocus,
    RawKey,
    RawMouse,
    extract_snapshot,
    pump_raw_events,
)


# ---------------------------------------------------------------------------
# Fakes mimicking pywinauto's UIAElementInfo (attributes + `.parent` property).
# ---------------------------------------------------------------------------


class FakeInfo:
    def __init__(
        self,
        control_type="",
        automation_id=None,
        name=None,
        class_name=None,
        parent=None,
    ):
        self.control_type = control_type
        self.automation_id = automation_id
        self.name = name
        self.class_name = class_name
        self._parent = parent

    @property
    def parent(self):
        return self._parent


def _el(control_type="Button", automation_id=None, name=None, ancestors=None):
    """Build a snapshot dict directly (post-extraction shape)."""
    return {
        "control_type": control_type,
        "automation_id": automation_id,
        "name": name,
        "class_name": None,
        "ancestors": ancestors or [],
    }


class TestExtractSnapshot:
    def test_basic_properties(self) -> None:
        info = FakeInfo("Edit", automation_id="user", name="Username", class_name="TextBox")
        snap = extract_snapshot(info)
        assert snap["control_type"] == "Edit"
        assert snap["automation_id"] == "user"
        assert snap["name"] == "Username"
        assert snap["class_name"] == "TextBox"
        assert snap["ancestors"] == []

    def test_blank_strings_normalise_to_none(self) -> None:
        info = FakeInfo("Button", automation_id="   ", name="")
        snap = extract_snapshot(info)
        assert snap["automation_id"] is None
        assert snap["name"] is None

    def test_ancestor_chain_nearest_first(self) -> None:
        root = FakeInfo("Window", name="Payroll")
        pane = FakeInfo("Pane", automation_id="form", parent=root)
        leaf = FakeInfo("Button", automation_id="ok", parent=pane)
        snap = extract_snapshot(leaf)
        # Nearest ancestor first.
        assert [a["control_type"] for a in snap["ancestors"]] == ["Pane", "Window"]
        assert snap["ancestors"][0]["automation_id"] == "form"
        assert snap["ancestors"][1]["name"] == "Payroll"

    def test_ancestor_cap(self) -> None:
        node = FakeInfo("Window", name="root")
        for i in range(20):
            node = FakeInfo("Pane", automation_id=f"p{i}", parent=node)
        snap = extract_snapshot(node, max_ancestors=3)
        assert len(snap["ancestors"]) == 3

    def test_self_parent_cycle_guard(self) -> None:
        node = FakeInfo("Window", name="loop")
        node._parent = node  # pathological self-parent
        snap = extract_snapshot(node)
        assert snap["ancestors"] == []

    def test_callable_parent_form_supported(self) -> None:
        class CallableParentInfo:
            def __init__(self, ct, parent=None):
                self.control_type = ct
                self.automation_id = None
                self.name = None
                self.class_name = None
                self._p = parent

            def parent(self):
                return self._p

        leaf = CallableParentInfo("Button", parent=CallableParentInfo("Window"))
        snap = extract_snapshot(leaf)
        assert [a["control_type"] for a in snap["ancestors"]] == ["Window"]


class TestAccumulatorClick:
    def test_single_click(self) -> None:
        acc = DesktopEventAccumulator()
        out = acc.feed(RawMouse(snapshot=_el(automation_id="ok")))
        assert [p["kind"] for p in out] == ["click"]

    def test_double_click_flag(self) -> None:
        acc = DesktopEventAccumulator()
        out = acc.feed(RawMouse(snapshot=_el(), double=True))
        assert out[0]["kind"] == "dblclick"

    def test_combobox_item_detected(self) -> None:
        acc = DesktopEventAccumulator()
        snap = _el(
            control_type="ListItem",
            name="Germany",
            ancestors=[{"control_type": "ComboBox", "automation_id": "country", "name": None}],
        )
        out = acc.feed(RawMouse(snapshot=snap))
        assert out[0]["kind"] == "combobox_select"
        assert out[0]["value"] == "Germany"

    def test_listitem_without_combobox_ancestor_is_plain_click(self) -> None:
        acc = DesktopEventAccumulator()
        snap = _el(control_type="ListItem", name="row 1", ancestors=[{"control_type": "List"}])
        out = acc.feed(RawMouse(snapshot=snap))
        assert out[0]["kind"] == "click"

    def test_menu_item_detected(self) -> None:
        acc = DesktopEventAccumulator()
        out = acc.feed(RawMouse(snapshot=_el(control_type="MenuItem", name="Export")))
        assert out[0]["kind"] == "menu_select"
        assert out[0]["value"] == "Export"


class TestAccumulatorTyping:
    def test_keys_buffer_then_flush_on_click(self) -> None:
        acc = DesktopEventAccumulator()
        edit = _el(control_type="Edit", automation_id="user")
        assert acc.feed(RawKey("h", snapshot=edit)) == []
        assert acc.feed(RawKey("i", snapshot=edit)) == []
        out = acc.feed(RawMouse(snapshot=_el(automation_id="ok")))
        # Type flushed first, then the click.
        assert [p["kind"] for p in out] == ["type", "click"]
        assert out[0]["text"] == "hi"
        assert out[0]["element"]["automation_id"] == "user"

    def test_typing_latches_first_element(self) -> None:
        acc = DesktopEventAccumulator()
        first = _el(control_type="Edit", automation_id="user")
        later = _el(control_type="Edit", automation_id="other")
        acc.feed(RawKey("a", snapshot=first))
        acc.feed(RawKey("b", snapshot=later))  # ignored — buffer already owns `first`
        out = acc.flush()
        assert out[0]["element"]["automation_id"] == "user"
        assert out[0]["text"] == "ab"

    def test_flush_on_focus_change(self) -> None:
        acc = DesktopEventAccumulator()
        edit = _el(control_type="Edit", automation_id="user")
        acc.feed(RawKey("x", snapshot=edit))
        out = acc.feed(RawFocus(snapshot=_el(control_type="Window", name="Other")))
        assert [p["kind"] for p in out] == ["type", "window_focus"]

    def test_explicit_flush_at_stop(self) -> None:
        acc = DesktopEventAccumulator()
        acc.feed(RawKey("z", snapshot=_el(control_type="Edit", automation_id="f")))
        assert [p["kind"] for p in acc.flush()] == ["type"]
        # Second flush is empty — buffer cleared.
        assert acc.flush() == []

    def test_empty_char_ignored(self) -> None:
        acc = DesktopEventAccumulator()
        acc.feed(RawKey("", snapshot=_el(control_type="Edit", automation_id="f")))
        assert acc.flush() == []


class TestPumpRawEvents:
    def test_full_sequence(self) -> None:
        edit = _el(control_type="Edit", automation_id="user")
        events = [
            RawKey("a", snapshot=edit),
            RawKey("b", snapshot=edit),
            RawMouse(snapshot=_el(automation_id="ok")),
            RawMouse(snapshot=_el(), double=True),
        ]
        emitted: list[dict] = []
        pump_raw_events(iter(events), emitted.append)
        assert [p["kind"] for p in emitted] == ["type", "click", "dblclick"]

    def test_trailing_text_flushed_at_end(self) -> None:
        edit = _el(control_type="Edit", automation_id="user")
        emitted: list[dict] = []
        pump_raw_events(iter([RawKey("q", snapshot=edit)]), emitted.append)
        assert [p["kind"] for p in emitted] == ["type"]
        assert emitted[0]["text"] == "q"

    def test_stop_event_halts_pump(self) -> None:
        stop = threading.Event()
        stop.set()
        emitted: list[dict] = []
        pump_raw_events(iter([RawMouse(snapshot=_el())]), emitted.append, stop)
        # Stop set before the first item → nothing processed, nothing buffered.
        assert emitted == []
