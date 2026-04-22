"""Story D.2 — UIA event → RecordedCommand translator.

The pywinauto hook wiring lives in `_desktop_loop` and needs a Windows
host; these tests only exercise the pure-Python translator that will
be called from that hook.
"""

from __future__ import annotations

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
