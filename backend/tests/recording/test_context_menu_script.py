"""Story W.5 — right-click context menu surface + catalog invariants."""

from __future__ import annotations

from src.recording.context_menu_script import (
    CONTEXT_MENU_SCRIPT,
    KEYWORD_CATALOG,
    context_menu_script,
    keyword_catalog,
)


class TestCatalog:
    def test_four_families_present(self) -> None:
        # AR-6 fixed families.
        assert set(KEYWORD_CATALOG.keys()) == {
            "Assert / Read",
            "Wait",
            "Interact",
            "State",
        }

    def test_fifteen_keywords_frozen_for_mvp(self) -> None:
        # Architecture doc says "15 keywords total" for MVP.
        total = sum(len(v) for v in KEYWORD_CATALOG.values())
        assert total == 15

    def test_all_items_have_keyword_name(self) -> None:
        for family, items in KEYWORD_CATALOG.items():
            for item in items:
                assert "keyword" in item and item["keyword"], (family, item)

    def test_keywords_are_title_cased_robot_style(self) -> None:
        # Robot Framework keywords are always Title Case with spaces.
        for items in KEYWORD_CATALOG.values():
            for item in items:
                parts = item["keyword"].split()
                assert all(p[0].isupper() for p in parts), item["keyword"]

    def test_get_attribute_prompts_for_attribute_name(self) -> None:
        # The AR-6 reference keyword with a required arg.
        for item in KEYWORD_CATALOG["Assert / Read"]:
            if item["keyword"] == "Get Attribute":
                assert item["arg_prompt"] is not None
                assert "attribute" in item["arg_prompt"].lower()


class TestMenuStructure:
    def test_iife_wrapper(self) -> None:
        assert CONTEXT_MENU_SCRIPT.strip().startswith("(() => {")
        assert CONTEXT_MENU_SCRIPT.strip().endswith("})();")

    def test_idempotency_guard(self) -> None:
        assert "__roboscopeContextMenuInstalled" in CONTEXT_MENU_SCRIPT

    def test_contextmenu_is_prevented(self) -> None:
        # Native menu must be suppressed (AC-FR4).
        assert "preventDefault()" in CONTEXT_MENU_SCRIPT
        assert 'addEventListener("contextmenu"' in CONTEXT_MENU_SCRIPT

    def test_outside_click_closes_menu(self) -> None:
        assert 'addEventListener("click"' in CONTEXT_MENU_SCRIPT
        assert "menu.contains" in CONTEXT_MENU_SCRIPT

    def test_escape_closes_menu(self) -> None:
        assert "Escape" in CONTEXT_MENU_SCRIPT

    def test_brand_amber_accent(self) -> None:
        # PRD UX spec: the menu has an amber left-accent so it's
        # unmistakably RoboScope (and not a fake page overlay).
        assert "#D4883E" in CONTEXT_MENU_SCRIPT

    def test_binding_name_matches_capture_script(self) -> None:
        # The menu emits through the same binding the capture script
        # registered (__roboscopeCapture). Keep them in lockstep.
        assert "__roboscopeCapture" in CONTEXT_MENU_SCRIPT


class TestAccessibility:
    def test_menu_has_role_menu(self) -> None:
        assert 'setAttribute("role", "menu")' in CONTEXT_MENU_SCRIPT

    def test_aria_label_present(self) -> None:
        assert 'aria-label", "RoboScope Recorder actions"' in CONTEXT_MENU_SCRIPT

    def test_menuitems_role(self) -> None:
        assert 'setAttribute("role", "menuitem")' in CONTEXT_MENU_SCRIPT


class TestHelpers:
    def test_helper_returns_menu_script(self) -> None:
        assert context_menu_script() == CONTEXT_MENU_SCRIPT

    def test_catalog_helper_returns_catalog(self) -> None:
        assert keyword_catalog() is KEYWORD_CATALOG
