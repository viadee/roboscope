"""Story D.4 — RPA.Windows emitter for desktop recording flows."""

from __future__ import annotations

from src.recording.robot_emit import emit_robot
from src.recording.selector_schema import (
    RecordedCommand,
    RecordedFlow,
    SelectorCandidate,
)


def _desktop_flow(
    commands: list[RecordedCommand], name: str | None = "Desktop Flow"
) -> RecordedFlow:
    return RecordedFlow(
        transport="desktop_windows",
        session_id="sess-d-1",
        name=name,
        commands=commands,
    )


class TestSettingsBlock:
    def test_library_is_rpa_windows(self) -> None:
        out = emit_robot(_desktop_flow([]))
        assert "Library           RPA.Windows" in out

    def test_macos_also_uses_rpa_windows(self) -> None:
        flow = RecordedFlow(transport="desktop_macos", session_id="s", commands=[])
        out = emit_robot(flow)
        assert "RPA.Windows" in out


class TestSelectorSyntax:
    def test_automation_id_emits_id_prefix(self) -> None:
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="automation_id",
                    value="submitBtn",
                    quality_score=92,
                )
            ],
        )
        out = emit_robot(_desktop_flow([cmd]))
        assert "Click    id:submitBtn" in out

    def test_name_emits_name_prefix(self) -> None:
        cmd = RecordedCommand(
            index=0,
            keyword="Type Text",
            args={"text": "hello"},
            selector_candidates=[
                SelectorCandidate(strategy="uia_name", value="Email", quality_score=75)
            ],
        )
        out = emit_robot(_desktop_flow([cmd]))
        assert "Type Text    name:Email    hello" in out

    def test_class_name_emits_class_prefix(self) -> None:
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="uia_class_name",
                    value="MyCustomBtn",
                    quality_score=50,
                )
            ],
        )
        out = emit_robot(_desktop_flow([cmd]))
        assert "Click    class:MyCustomBtn" in out

    def test_xpath_emits_xpath_prefix(self) -> None:
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="xpath",
                    value="/Window/Pane/Button",
                    quality_score=22,
                )
            ],
        )
        out = emit_robot(_desktop_flow([cmd]))
        assert "Click    xpath:/Window/Pane/Button" in out


class TestDesktopKeywords:
    def test_select_from_combobox_is_targeted(self) -> None:
        cmd = RecordedCommand(
            index=0,
            keyword="Select From Combobox",
            args={"value": "Germany"},
            selector_candidates=[
                SelectorCandidate(strategy="automation_id", value="countryCombo", quality_score=92)
            ],
        )
        out = emit_robot(_desktop_flow([cmd]))
        assert "Select From Combobox    id:countryCombo    Germany" in out

    def test_control_window(self) -> None:
        cmd = RecordedCommand(
            index=0,
            keyword="Control Window",
            selector_candidates=[
                SelectorCandidate(strategy="uia_name", value="Login", quality_score=75)
            ],
        )
        out = emit_robot(_desktop_flow([cmd]))
        assert "Control Window    name:Login" in out

    def test_click_without_selector_emits_pure_comment(self) -> None:
        # Used to emit `Click    # WARNING: ...` which RPA.Windows
        # treated as a zero-arg call and crashed at replay. Now a
        # full RF comment so the gap is visible without breaking the
        # run.
        cmd = RecordedCommand(index=0, keyword="Click")
        out = emit_robot(_desktop_flow([cmd]))
        assert "# RBSCOPE: dropped Click" in out

    def test_click_without_selector_emits_server_warning(
        self, caplog
    ) -> None:
        """Companion to the placeholder check above: a missing
        desktop selector also emits a WARNING server-side so the
        recorder log stream surfaces the partial-failure during
        save POST instead of waiting for the user to discover the
        placeholder when they open the .robot."""
        cmd = RecordedCommand(
            id="deskmiss0001", index=2, keyword="Click",
        )
        caplog.set_level("WARNING", logger="roboscope.recording.emit")
        emit_robot(_desktop_flow([cmd]))
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1
        msg = warnings[0].getMessage()
        assert "Click" in msg
        assert "deskmiss0001" in msg
        assert "desktop" in msg.lower()


class TestWebTransportStillWorks:
    def test_web_flow_keeps_browser_library(self) -> None:
        flow = RecordedFlow(
            transport="web_playwright", session_id="s", commands=[],
        )
        out = emit_robot(flow)
        assert "Library           Browser" in out

    def test_chrome_extension_also_uses_browser(self) -> None:
        flow = RecordedFlow(
            transport="chrome_extension", session_id="s", commands=[],
        )
        out = emit_robot(flow)
        assert "Library           Browser" in out


class TestDesktopRbsComment:
    """RECORDER-IDMAP — desktop transport must emit the same trailing
    `# rbs:<id>` comment that web does, otherwise reorder / insert /
    delete in the visual editor silently regresses to positional
    matching for desktop heals."""

    def test_targeted_step_appends_rbs_comment(self) -> None:
        cmd = RecordedCommand(
            id="deskcmd00001",
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="automation_id", value="submitBtn", quality_score=92,
                )
            ],
        )
        out = emit_robot(_desktop_flow([cmd]))
        assert "Click    id:submitBtn    # rbs:deskcmd00001" in out

    def test_typed_step_appends_rbs_after_value(self) -> None:
        cmd = RecordedCommand(
            id="deskcmd00002",
            index=0,
            keyword="Type Text",
            args={"text": "alice@corp"},
            selector_candidates=[
                SelectorCandidate(
                    strategy="automation_id", value="userEdit", quality_score=92,
                )
            ],
        )
        out = emit_robot(_desktop_flow([cmd]))
        assert (
            "Type Text    id:userEdit    alice@corp    # rbs:deskcmd00002" in out
        )

    def test_warning_line_bakes_id_into_comment(self) -> None:
        # The selector-missing path now early-returns a pure RF
        # comment. The id is embedded inside that single comment
        # ("cmd.id=deskcmd00003"), not appended as a second
        # `# rbs:` token — the dropped step has no replay anchor
        # to tie back to anyway.
        cmd = RecordedCommand(id="deskcmd00003", index=0, keyword="Click")
        out = emit_robot(_desktop_flow([cmd]))
        assert "# RBSCOPE: dropped Click" in out
        assert "cmd.id=deskcmd00003" in out


class TestFullDesktopFlow:
    def test_roundtrip_three_step_windows_flow(self) -> None:
        flow = _desktop_flow(
            name="Login to payroll app",
            commands=[
                RecordedCommand(
                    index=0,
                    keyword="Control Window",
                    selector_candidates=[
                        SelectorCandidate(strategy="uia_name", value="Payroll", quality_score=75)
                    ],
                ),
                RecordedCommand(
                    index=1,
                    keyword="Type Text",
                    args={"text": "alice@corp"},
                    selector_candidates=[
                        SelectorCandidate(strategy="automation_id", value="userEdit", quality_score=92)
                    ],
                ),
                RecordedCommand(
                    index=2,
                    keyword="Click",
                    selector_candidates=[
                        SelectorCandidate(strategy="automation_id", value="loginBtn", quality_score=92)
                    ],
                ),
            ],
        )
        out = emit_robot(flow)
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        idx_test = lines.index("Login to payroll app")
        steps = lines[idx_test + 1 : idx_test + 4]
        assert steps[0].startswith("Control Window    name:Payroll")
        assert steps[1].startswith("Type Text    id:userEdit    alice@corp")
        assert steps[2].startswith("Click    id:loginBtn")
