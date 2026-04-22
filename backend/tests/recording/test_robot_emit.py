"""Story W.6 — RecordedFlow → .robot emitter."""

from __future__ import annotations

from src.recording.robot_emit import emit_robot
from src.recording.selector_schema import (
    RecordedCommand,
    RecordedFlow,
    SelectorCandidate,
)


def _flow(commands: list[RecordedCommand], name: str | None = "Test Flow") -> RecordedFlow:
    return RecordedFlow(
        transport="web_playwright",
        session_id="sess-1",
        name=name,
        commands=commands,
    )


class TestSettingsAndTestBlock:
    def test_default_settings(self) -> None:
        out = emit_robot(_flow([]))
        assert "*** Settings ***" in out
        assert "Library           Browser" in out
        assert "*** Test Cases ***" in out

    def test_empty_flow_has_no_operation(self) -> None:
        out = emit_robot(_flow([]))
        assert "    No Operation" in out

    def test_name_used_as_test_case(self) -> None:
        out = emit_robot(_flow([], name="Login happy path"))
        assert "Login happy path" in out

    def test_fallback_name_when_missing(self) -> None:
        flow = RecordedFlow(transport="web_playwright", session_id="42")
        out = emit_robot(flow)
        assert "Recording 42" in out


class TestTargetedKeywords:
    def test_click_uses_testid_selector_verbatim(self) -> None:
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="testid",
                    value='[data-testid="submit"]',
                    quality_score=95,
                    verified_unique=True,
                )
            ],
        )
        out = emit_robot(_flow([cmd]))
        assert '    Click    [data-testid="submit"]' in out

    def test_click_with_xpath_gets_xpath_prefix(self) -> None:
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="xpath",
                    value='//button[text()="Submit"]',
                    quality_score=65,
                )
            ],
        )
        out = emit_robot(_flow([cmd]))
        assert 'Click    xpath=//button[text()="Submit"]' in out

    def test_click_without_selector_warns(self) -> None:
        # Defensive: a targeted keyword without selector is a bug upstream;
        # emit a visible warning rather than silently producing an invalid line.
        cmd = RecordedCommand(index=0, keyword="Click")
        out = emit_robot(_flow([cmd]))
        assert "# WARNING: no selector captured" in out

    def test_type_text_renders_text_arg(self) -> None:
        cmd = RecordedCommand(
            index=0,
            keyword="Type Text",
            args={"text": "hello@example.com"},
            selector_candidates=[
                SelectorCandidate(
                    strategy="css", value="#email", quality_score=60
                )
            ],
        )
        out = emit_robot(_flow([cmd]))
        assert "Type Text    #email    hello@example.com" in out


class TestGlobalKeywords:
    def test_go_to_does_not_need_selector(self) -> None:
        cmd = RecordedCommand(
            index=0,
            keyword="Go To",
            args={"url": "https://example.com"},
        )
        out = emit_robot(_flow([cmd]))
        assert "Go To    https://example.com" in out


class TestArgOrdering:
    def test_ordered_args_come_before_extras(self) -> None:
        cmd = RecordedCommand(
            index=0,
            keyword="Wait For Elements State",
            args={"custom_flag": True, "state": "visible"},
            selector_candidates=[
                SelectorCandidate(strategy="css", value="#x", quality_score=60)
            ],
        )
        out = emit_robot(_flow([cmd]))
        # 'state' is in the ordered list, custom_flag is not
        line = [ln for ln in out.splitlines() if "Wait For Elements State" in ln][0]
        state_idx = line.index("visible")
        flag_idx = line.index("${TRUE}")
        assert state_idx < flag_idx


class TestActiveSelectorIsHonoured:
    def test_picks_the_active_index(self) -> None:
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(strategy="testid", value="[data-testid=\"a\"]", quality_score=95),
                SelectorCandidate(strategy="css", value=".b", quality_score=50),
            ],
            active_candidate_index=1,
        )
        out = emit_robot(_flow([cmd]))
        assert ".b" in out
        assert "data-testid=\"a\"" not in out


class TestMultiStepFlow:
    def test_full_login_flow_round_trip(self) -> None:
        flow = _flow(
            name="Login happy path",
            commands=[
                RecordedCommand(
                    index=0,
                    keyword="Go To",
                    args={"url": "https://example.com/login"},
                ),
                RecordedCommand(
                    index=1,
                    keyword="Type Text",
                    args={"text": "user@example.com"},
                    selector_candidates=[
                        SelectorCandidate(strategy="testid", value='[data-testid="email"]', quality_score=95)
                    ],
                ),
                RecordedCommand(
                    index=2,
                    keyword="Type Text",
                    args={"text": "secret"},
                    selector_candidates=[
                        SelectorCandidate(strategy="testid", value='[data-testid="password"]', quality_score=95)
                    ],
                ),
                RecordedCommand(
                    index=3,
                    keyword="Click",
                    selector_candidates=[
                        SelectorCandidate(strategy="testid", value='[data-testid="login-btn"]', quality_score=95)
                    ],
                ),
                RecordedCommand(
                    index=4,
                    keyword="Wait For Elements State",
                    args={"state": "visible"},
                    selector_candidates=[
                        SelectorCandidate(strategy="text", value="Welcome", quality_score=70)
                    ],
                ),
            ],
        )
        out = emit_robot(flow)
        # All five keywords + the test-case header are present, in order.
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        idx_test = lines.index("Login happy path")
        steps = lines[idx_test + 1 : idx_test + 6]
        assert steps[0].startswith("Go To")
        assert steps[1].startswith("Type Text    [data-testid=\"email\"]")
        assert steps[2].startswith("Type Text    [data-testid=\"password\"]")
        assert steps[3].startswith("Click    [data-testid=\"login-btn\"]")
        assert steps[4].startswith("Wait For Elements State    text=Welcome")
