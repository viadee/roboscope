"""Story W.6 — RecordedFlow → .robot emitter."""

from __future__ import annotations

from src.recording.robot_emit import _emit_command, emit_robot
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
        # RECORDER-RF-ESCAPE — `#email` would be a comment for RF;
        # emitter prepends `\` so the lexer treats it as literal.
        assert "Type Text    \\#email    hello@example.com" in out


class TestGlobalKeywords:
    def test_go_to_does_not_need_selector(self) -> None:
        # RECORDER-1C: a `Go To` at index 0 is consumed as the initial-URL
        # input to the New Browser/New Context/New Page bootstrap so the
        # generated `.robot` is replayable through RF Browser without
        # additional setup. Any subsequent Go Tos are kept verbatim.
        cmd = RecordedCommand(
            index=0,
            keyword="Go To",
            args={"url": "https://example.com"},
        )
        out = emit_robot(_flow([cmd]))
        assert "New Browser    chromium" in out
        assert "New Context" in out
        # Story RECORDER-NAV-1 — `wait_until=domcontentloaded` is
        # required so real-world pages (heise.de etc.) don't time out
        # on the 10s `load` event waiting for ads/trackers. Run 32
        # hit exactly that bug with the default `wait_until=load`.
        assert "New Page    https://example.com    wait_until=domcontentloaded" in out
        assert "Go To" not in out  # the first Go To was folded into New Page
        # The bootstrap references `${HEADLESS}`; the suite MUST also
        # define it under `*** Variables ***`, otherwise Robot Framework
        # refuses to start with "Variable '${HEADLESS}' not found."
        assert "*** Variables ***" in out
        # Default value: `false` — recorded tests come from clicking a
        # real page; running them headed by default matches user intent.
        import re
        assert re.search(r"\$\{HEADLESS\}\s+false", out) is not None


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
        # The first Go To is consumed by the New Page bootstrap; the
        # remaining four user actions follow in order.
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        idx_test = lines.index("Login happy path")
        steps = lines[idx_test + 1 : idx_test + 8]
        assert steps[0] == "New Browser    chromium    headless=${HEADLESS}"
        assert steps[1] == "New Context"
        # See note in TestGlobalKeywords — `wait_until=domcontentloaded`
        # is the regression guard for the 10s `load`-event timeout.
        assert steps[2] == "New Page    https://example.com/login    wait_until=domcontentloaded"
        assert steps[3].startswith("Type Text    [data-testid=\"email\"]")
        assert steps[4].startswith("Type Text    [data-testid=\"password\"]")
        assert steps[5].startswith("Click    [data-testid=\"login-btn\"]")
        assert steps[6].startswith("Wait For Elements State    text=Welcome")


# ─── RECORDER-RF-ESCAPE — Robot-Framework token escaping ──────────────


class TestRfTokenEscape:
    """A Robot Framework token that STARTS with `#` is treated as a
    comment — everything from there is dropped. The recorder must
    backslash-escape leading `#` so CSS-ID selectors and similar
    survive the lexer.
    """

    def test_css_id_selector_gets_leading_hash_escaped(self) -> None:
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="css",
                    value="#login-form",
                    quality_score=90,
                    verified_unique=True,
                ),
            ],
            active_candidate_index=0,
        )
        line = _emit_command(cmd)
        # Without the escape, `Click    #login-form` becomes
        # `Click` + comment, and Click runs without args.
        assert "\\#login-form" in line
        assert " #login-form" not in line.replace("\\#", "<esc>")

    def test_text_selector_no_escape_needed(self) -> None:
        """Token starts with `t` (text=...), not `#` — must not be
        touched. Escaping unnecessarily would break Browser library."""
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="text",
                    value='text="Zustimmen"',
                    quality_score=70,
                    verified_unique=True,
                ),
            ],
            active_candidate_index=0,
        )
        line = _emit_command(cmd)
        assert 'text="Zustimmen"' in line
        assert "\\text" not in line  # no spurious escape

    def test_iframe_wrapped_selector_inner_hash_escaped(self) -> None:
        """When the inner selector is `#login-form` AND we add the
        iframe wrapper, the FINAL composite token starts with `i`
        (iframe[src...]). No leading-`#` escape needed because the
        composite token doesn't start with `#`. Sanity check the
        escape doesn't mangle the iframe path."""
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="css",
                    value="#login-form",
                    quality_score=90,
                    verified_unique=True,
                ),
            ],
            active_candidate_index=0,
            frame_url="https://message-eu.sp-prod.net/i?id=xxx",
        )
        line = _emit_command(cmd)
        assert 'iframe[src*="message-eu.sp-prod.net"] >>> #login-form' in line
        # Composite token starts with `i`, no escape needed.
        assert "\\iframe" not in line

    def test_arg_starting_with_hash_gets_escaped(self) -> None:
        """`Type Text    selector    #fancy-tag` — the third arg
        starts with `#`. Without escape it'd be a comment and
        Type Text would receive only the selector."""
        cmd = RecordedCommand(
            index=0,
            keyword="Type Text",
            args={"text": "#fancy-tag"},
            selector_candidates=[
                SelectorCandidate(
                    strategy="testid",
                    value='[data-testid="search"]',
                    quality_score=95,
                    verified_unique=True,
                ),
            ],
            active_candidate_index=0,
        )
        line = _emit_command(cmd)
        assert "\\#fancy-tag" in line

    def test_url_with_hash_fragment_not_escaped(self) -> None:
        """A URL like `https://example.com/#section` doesn't START
        with `#`, so it isn't a comment — escape would be wrong."""
        cmd = RecordedCommand(
            index=0,
            keyword="Go To",
            args={"url": "https://example.com/#section"},
        )
        line = _emit_command(cmd)
        assert "https://example.com/#section" in line
        assert "\\https" not in line
        assert "\\#section" not in line  # no spurious mid-string escape

    def test_none_value_emits_robot_none_variable(self) -> None:
        """Sanity — non-string args route through `_render_arg` and
        must NOT trip the escape (None ⇒ `${None}`, no leading-#)."""
        cmd = RecordedCommand(
            index=0,
            keyword="Set Variable",
            args={"value": None},
        )
        line = _emit_command(cmd)
        assert "${None}" in line
