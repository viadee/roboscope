"""Story D.3 — Windows UIA selector synthesis."""

from __future__ import annotations

from src.recording.desktop_selector_synthesis import (
    DesktopAncestor,
    DesktopElementSnapshot,
    synthesise_desktop_selectors,
)


def _snap(**kwargs) -> DesktopElementSnapshot:
    kwargs.setdefault("control_type", "Button")
    return DesktopElementSnapshot(**kwargs)


class TestAutomationId:
    def test_stable_automation_id_wins(self) -> None:
        cands = synthesise_desktop_selectors(_snap(automation_id="submitBtn"))
        aid = [c for c in cands if c.strategy == "automation_id"]
        assert len(aid) == 1
        assert aid[0].quality_score == 92
        assert aid[0].value == "submitBtn"

    def test_autogen_automation_id_penalised(self) -> None:
        cands = synthesise_desktop_selectors(
            _snap(automation_id="K8aB9cD1eF2gH3iJ4kL5mNopQ")
        )
        aid = [c for c in cands if c.strategy == "automation_id"][0]
        assert aid.quality_score == 92 - 25

    def test_no_automation_id_no_candidate(self) -> None:
        cands = synthesise_desktop_selectors(_snap())
        assert not [c for c in cands if c.strategy == "automation_id"]


class TestUiaName:
    def test_name_emits_candidate(self) -> None:
        cands = synthesise_desktop_selectors(_snap(name="Save as..."))
        nms = [c for c in cands if c.strategy == "uia_name"]
        assert len(nms) == 1
        assert nms[0].quality_score == 75

    def test_numeric_only_name_heavily_penalised(self) -> None:
        cands = synthesise_desktop_selectors(_snap(name="42"))
        nms = [c for c in cands if c.strategy == "uia_name"][0]
        assert nms.quality_score == 75 - 30

    def test_time_like_name_penalised(self) -> None:
        cands = synthesise_desktop_selectors(_snap(name="Updated 12:34"))
        nms = [c for c in cands if c.strategy == "uia_name"][0]
        assert nms.quality_score == 75 - 15


class TestUiaClassName:
    def test_stable_class_name(self) -> None:
        cands = synthesise_desktop_selectors(_snap(class_name="MyCustomButton"))
        cn = [c for c in cands if c.strategy == "uia_class_name"][0]
        assert cn.quality_score == 50

    def test_generic_class_name_penalised(self) -> None:
        cands = synthesise_desktop_selectors(_snap(class_name="Button"))
        cn = [c for c in cands if c.strategy == "uia_class_name"][0]
        assert cn.quality_score == 50 - 15


class TestUiaXpath:
    def test_anchors_on_automation_id_ancestor(self) -> None:
        cands = synthesise_desktop_selectors(
            _snap(
                control_type="Edit",
                ancestors=[
                    DesktopAncestor(control_type="Pane"),
                    DesktopAncestor(control_type="Window", automation_id="LoginDlg"),
                ],
            )
        )
        anchored = [
            c for c in cands
            if c.strategy == "xpath" and "AutomationId" in c.value
        ]
        assert len(anchored) == 1
        assert 'AutomationId' in anchored[0].value and 'LoginDlg' in anchored[0].value
        assert anchored[0].quality_score == 55

    def test_falls_back_to_name_anchor(self) -> None:
        cands = synthesise_desktop_selectors(
            _snap(
                control_type="Edit",
                ancestors=[
                    DesktopAncestor(control_type="Pane"),
                    DesktopAncestor(control_type="Window", name="Login"),
                ],
            )
        )
        anchored = [
            c for c in cands
            if c.strategy == "xpath" and "Name" in c.value
        ]
        assert len(anchored) == 1
        assert anchored[0].quality_score == 50

    def test_absolute_fallback_always_present(self) -> None:
        cands = synthesise_desktop_selectors(
            _snap(ancestors=[DesktopAncestor(control_type="Window")])
        )
        abs_x = [
            c for c in cands
            if c.strategy == "xpath" and c.value.startswith("/Window/Button")
        ]
        assert abs_x[0].quality_score == 22


class TestSortOrder:
    def test_highest_quality_first(self) -> None:
        cands = synthesise_desktop_selectors(
            _snap(
                automation_id="submit",
                name="Submit",
                class_name="Button",
            )
        )
        scores = [c.quality_score for c in cands]
        assert scores == sorted(scores, reverse=True)
        assert cands[0].strategy == "automation_id"


class TestQualityFloor:
    def test_elements_with_no_info_only_produce_absolute_xpath(self) -> None:
        cands = synthesise_desktop_selectors(_snap())
        assert len(cands) == 1
        assert cands[0].strategy == "xpath"
        assert cands[0].quality_score == 22
