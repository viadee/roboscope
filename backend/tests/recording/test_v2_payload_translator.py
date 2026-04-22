"""Story W.1 full — capture-script payload → RecordedCommand translator."""

from __future__ import annotations

from src.recording.v2_payload_translator import translate_payload


def _el(
    tag: str = "button",
    attrs: dict | None = None,
    text: str = "",
    aria_role: str | None = None,
    aria_name: str | None = None,
) -> dict:
    return {
        "tag": tag,
        "attributes": attrs or {},
        "text": text,
        "aria_role": aria_role,
        "aria_name": aria_name,
        "ancestors": [],
    }


class TestNavigate:
    def test_go_to_has_url_arg(self) -> None:
        cmd = translate_payload({"kind": "navigate", "url": "https://example.com"}, 0)
        assert cmd is not None
        assert cmd.keyword == "Go To"
        assert cmd.args["url"] == "https://example.com"
        assert cmd.selector_candidates == []

    def test_navigate_without_url_returns_none(self) -> None:
        assert translate_payload({"kind": "navigate"}, 0) is None

    def test_non_string_url_returns_none(self) -> None:
        assert translate_payload({"kind": "navigate", "url": 42}, 0) is None


class TestClick:
    def test_click_with_testid_gets_selector(self) -> None:
        cmd = translate_payload(
            {"kind": "click", "element": _el(attrs={"data-testid": "go"})},
            0,
        )
        assert cmd is not None
        assert cmd.keyword == "Click"
        assert any(c.strategy == "testid" for c in cmd.selector_candidates)

    def test_dblclick_maps_to_double_click(self) -> None:
        cmd = translate_payload(
            {"kind": "dblclick", "element": _el(attrs={"data-testid": "go"})},
            0,
        )
        assert cmd is not None
        assert cmd.keyword == "Double Click"


class TestType:
    def test_type_carries_text_arg(self) -> None:
        cmd = translate_payload(
            {
                "kind": "type",
                "text": "hello@example.com",
                "element": _el(tag="input", attrs={"data-testid": "email"}),
            },
            0,
        )
        assert cmd is not None
        assert cmd.keyword == "Type Text"
        assert cmd.args["text"] == "hello@example.com"


class TestPress:
    def test_enter_press(self) -> None:
        cmd = translate_payload(
            {"kind": "press", "key": "Enter", "element": _el(tag="input", attrs={"id": "x"})},
            0,
        )
        assert cmd is not None
        assert cmd.keyword == "Press Keys"
        assert cmd.args["key"] == "Enter"


class TestScroll:
    def test_scroll_with_element_uses_scroll_to_element(self) -> None:
        cmd = translate_payload(
            {"kind": "scroll", "element": _el(tag="div", attrs={"id": "pane"})},
            0,
        )
        assert cmd is not None
        assert cmd.keyword == "Scroll To Element"
        # "id" on a div → #pane CSS candidate, plus the absolute-xpath fallback.
        values = {c.value for c in cmd.selector_candidates}
        assert "#pane" in values

    def test_page_scroll_has_no_candidates(self) -> None:
        cmd = translate_payload({"kind": "scroll", "element": None}, 0)
        assert cmd is not None
        assert cmd.args.get("target") == "page"
        assert cmd.selector_candidates == []


class TestDragDrop:
    def test_drag_drop_captures_both_endpoints(self) -> None:
        cmd = translate_payload(
            {
                "kind": "drag_drop",
                "from": _el(attrs={"data-testid": "src"}),
                "to": _el(attrs={"data-testid": "dst"}),
            },
            0,
        )
        assert cmd is not None
        assert cmd.keyword == "Drag And Drop"
        # Active selector is the source; target endpoint is stored in args.
        assert any("src" in c.value for c in cmd.selector_candidates)
        assert "dst" in cmd.args["value"]


class TestCustomAction:
    def test_custom_action_from_context_menu(self) -> None:
        cmd = translate_payload(
            {
                "kind": "custom_action",
                "keyword": "Get Element Value",
                "args": {},
                "element": _el(attrs={"data-testid": "x"}),
            },
            5,
        )
        assert cmd is not None
        assert cmd.index == 5
        assert cmd.keyword == "Get Element Value"

    def test_custom_action_with_value_arg(self) -> None:
        cmd = translate_payload(
            {
                "kind": "custom_action",
                "keyword": "Should Be Equal",
                "args": {"value": "expected text"},
                "element": _el(attrs={"data-testid": "x"}),
            },
            0,
        )
        assert cmd is not None
        assert cmd.args["value"] == "expected text"

    def test_custom_action_without_keyword_returns_none(self) -> None:
        cmd = translate_payload(
            {"kind": "custom_action", "args": {}, "element": _el()},
            0,
        )
        assert cmd is None


class TestUnknownKind:
    def test_unknown_kind_returns_none(self) -> None:
        assert translate_payload({"kind": "teleport"}, 0) is None

    def test_missing_kind_returns_none(self) -> None:
        assert translate_payload({}, 0) is None

    def test_non_dict_returns_none_gracefully(self) -> None:
        # The translator should not crash on non-string `kind`.
        assert translate_payload({"kind": 42}, 0) is None


class TestIndexPropagation:
    def test_index_passes_through(self) -> None:
        for i in (0, 1, 42):
            cmd = translate_payload({"kind": "navigate", "url": "https://x"}, i)
            assert cmd is not None
            assert cmd.index == i
