"""Story W.6 — RecordedFlow → .robot emitter."""

from __future__ import annotations

import pytest

from src.recording.robot_emit import _emit_command, _render_selector, emit_robot
from src.recording.selector_schema import (
    FrameDescriptor,
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

    def test_click_without_selector_emits_pure_comment(self) -> None:
        # Defensive: a targeted keyword without selector used to emit
        # `Click    # WARNING: ...` which RF parsed as Click() + zero
        # args, crashing Browser-library replay with "expected 1
        # argument, got 0". Emit the entire line as an RF comment so
        # the gap is still visible but replay doesn't break.
        cmd = RecordedCommand(index=0, keyword="Click")
        out = emit_robot(_flow([cmd]))
        assert "# RBSCOPE: dropped Click — no selector captured" in out
        # Importantly: the keyword name does NOT appear at the start
        # of an executable line (every line that mentions Click is
        # behind the # comment marker).
        for line in out.splitlines():
            stripped = line.strip()
            if stripped.startswith("Click"):
                pytest.fail(
                    f"Expected Click line to be commented, got: {line!r}"
                )

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


# ─── RECORDER-IDMAP — position-independent command id ─────────────────


class TestCommandIdEmit:
    """Each emitted line carries `# rbs:<id>` so the FlowEditor can
    re-link selector groups to their step independent of position
    (reorder / delete / insert in the visual editor must not silently
    shift candidate groups onto the wrong rows)."""

    def test_click_line_carries_id_comment(self) -> None:
        cmd = RecordedCommand(
            id="abc123def456",
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="testid",
                    value='[data-testid="login"]',
                    quality_score=95,
                    verified_unique=True,
                ),
            ],
            active_candidate_index=0,
        )
        line = _emit_command(cmd)
        # Trailing comment must be present so the editor can match by id.
        assert line.rstrip().endswith("# rbs:abc123def456")
        # Standard arg ordering still intact (selector is between
        # keyword and the trailing comment).
        assert '[data-testid="login"]' in line

    def test_go_to_line_carries_id_comment(self) -> None:
        """`Go To` has no selector but still benefits from id-mapping
        in case the user reorders subsequent navigation."""
        cmd = RecordedCommand(
            id="navi5678",
            index=0,
            keyword="Go To",
            args={"url": "https://example.com"},
        )
        line = _emit_command(cmd)
        assert line.rstrip().endswith("# rbs:navi5678")

    def test_warning_line_bakes_id_into_comment(self) -> None:
        """When the recorder couldn't synthesise any selector, the
        whole line is a single `# RBSCOPE: dropped …` comment
        carrying the cmd id inline. Adding a second `# rbs:…` token
        would tail-pollute that comment, so the standalone token
        path is skipped."""
        cmd = RecordedCommand(
            id="should-not-leak",
            index=0,
            keyword="Click",
            # No selector_candidates → drop-into-comment path.
        )
        line = _emit_command(cmd)
        assert "# RBSCOPE: dropped Click" in line
        assert "cmd.id=should-not-leak" in line
        # No standalone `# rbs:` token appended.
        assert "# rbs:" not in line

    def test_id_default_is_short_and_collision_resistant(self) -> None:
        """Default factory generates a 12-char hex slice. Long enough
        to avoid collisions within a recording, short enough to not
        bloat every emitted line."""
        cmd_a = RecordedCommand(index=0, keyword="Click")
        cmd_b = RecordedCommand(index=1, keyword="Click")
        assert cmd_a.id != cmd_b.id
        assert len(cmd_a.id) == 12
        assert all(c in "0123456789abcdef" for c in cmd_a.id)

    def test_explicit_id_round_trips_through_emit(self) -> None:
        """The id is the user's identity for the row; sidecar load,
        FlowEditor edit, save back must preserve it. Emit-side check:
        whatever id is on the model lands verbatim in the line."""
        cmd = RecordedCommand(
            id="my-pinned-id",
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="css", value="button.x", quality_score=50
                ),
            ],
            active_candidate_index=0,
        )
        line = _emit_command(cmd)
        assert "# rbs:my-pinned-id" in line


class TestEmitMissingSelectorObservability:
    """When a targeted keyword (Click, Type Text, etc.) reaches the
    emitter without any selector candidate, the emitter writes a
    pure `# RBSCOPE: dropped …` comment line AND emits a server-side
    WARNING. Pure-comment instead of `Keyword    # WARNING:` because
    RF parsed the latter as a zero-arg call which crashed Browser
    library at replay ("expected 1 argument, got 0"). Operators
    monitoring the recorder log stream still get the diagnostic via
    the WARNING record."""

    def test_targeted_keyword_without_selector_emits_warning_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        cmd = RecordedCommand(
            id="missingfp001",
            index=3,
            keyword="Click",
            selector_candidates=[],
            active_candidate_index=0,
            frame_url="https://message-eu.sp-prod.net/?id=42",
        )
        caplog.set_level("WARNING", logger="roboscope.recording.emit")
        line = _emit_command(cmd)
        # Line is now a pure RF comment so replay doesn't crash.
        assert line.lstrip().startswith("# RBSCOPE: dropped Click")
        assert "missingfp001" in line
        # And exactly one warning carrying the diagnostic context.
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1
        msg = warnings[0].getMessage()
        assert "Click" in msg
        assert "missingfp001" in msg
        assert "message-eu.sp-prod.net" in msg

    def test_targeted_keyword_with_selector_emits_no_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        cmd = RecordedCommand(
            id="happypath001",
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="testid",
                    value='[data-testid="x"]',
                    quality_score=95,
                    verified_unique=True,
                ),
            ],
            active_candidate_index=0,
        )
        caplog.set_level("WARNING", logger="roboscope.recording.emit")
        _emit_command(cmd)
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert warnings == []

    def test_global_keyword_without_selector_emits_no_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # `Go To` legitimately has no selector — it carries a URL.
        # The emitter must NOT mistake that for a missing-selector
        # case and warn.
        cmd = RecordedCommand(
            id="goto00000001",
            index=0,
            keyword="Go To",
            args={"url": "https://example.com"},
            selector_candidates=[],
            active_candidate_index=0,
        )
        caplog.set_level("WARNING", logger="roboscope.recording.emit")
        _emit_command(cmd)
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert warnings == []


# ──────────────────────────────────────────────────────────────────────
# Story RECORDER-FRAMES-2 — `frame_chain` overrides the legacy URL-only
# `iframe[src*="<host>"]` strategy, falls back gracefully on partial
# chains, and stacks across nested iframes.
# ──────────────────────────────────────────────────────────────────────


class TestFrameChainEmit:
    def test_chain_with_id_candidate_replaces_legacy_host_match(self) -> None:
        """When `frame_chain[0]` carries a verified-unique `iframe#id`
        candidate, the emitter prefers it over the URL-derived
        `iframe[src*="<host>"]` legacy locator."""
        from src.recording.selector_schema import FrameDescriptor
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="css", value="button.accept",
                    quality_score=80, verified_unique=True,
                ),
            ],
            active_candidate_index=0,
            frame_url="https://cmp.example.com/consent",
            frame_chain=[
                FrameDescriptor(
                    url="https://cmp.example.com/consent",
                    selector_candidates=[
                        SelectorCandidate(
                            strategy="css", value="iframe#cmp-banner",
                            quality_score=90, verified_unique=True,
                        ),
                        SelectorCandidate(
                            strategy="css",
                            value='iframe[src*="cmp.example.com"]',
                            quality_score=65, verified_unique=True,
                        ),
                    ],
                ),
            ],
        )
        line = _emit_command(cmd)
        assert "iframe#cmp-banner >>> button.accept" in line
        # The legacy URL-host pattern is NOT used when a better
        # iframe candidate exists.
        assert 'iframe[src*="cmp.example.com"]' not in line

    def test_chain_empty_falls_back_to_legacy_url_host(self) -> None:
        """No frame_chain → legacy `iframe[src*="<host>"]` path
        unchanged. Confirms backward compat for pre-FRAMES-2 sidecars."""
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="css", value="button.accept",
                    quality_score=80, verified_unique=True,
                ),
            ],
            active_candidate_index=0,
            frame_url="https://cmp.example.com/consent",
        )
        line = _emit_command(cmd)
        assert 'iframe[src*="cmp.example.com"] >>> button.accept' in line

    def test_chain_rung_without_candidates_falls_back_to_rung_url(self) -> None:
        """`FrameDescriptor` with empty `selector_candidates` (iframe
        detached mid-capture) falls back to its OWN url-derived
        `iframe[src*="<host>"]` for that rung. Rest of the chain is
        unaffected."""
        from src.recording.selector_schema import FrameDescriptor
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="css", value="button.accept",
                    quality_score=80, verified_unique=True,
                ),
            ],
            active_candidate_index=0,
            frame_url="https://cmp.example.com/consent",
            frame_chain=[
                FrameDescriptor(
                    url="https://cmp.example.com/consent",
                    selector_candidates=[],  # detached, couldn't synth
                ),
            ],
        )
        line = _emit_command(cmd)
        assert 'iframe[src*="cmp.example.com"] >>> button.accept' in line

    def test_chain_nested_iframes_compose_outer_to_inner(self) -> None:
        """Two-rung chain (outer iframe wraps inner iframe) composes
        as `outer >>> inner >>> element` — the index 0 rung is the
        outermost."""
        from src.recording.selector_schema import FrameDescriptor
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="css", value="button.accept",
                    quality_score=80, verified_unique=True,
                ),
            ],
            active_candidate_index=0,
            frame_url="https://inner.example.com/",
            frame_chain=[
                FrameDescriptor(
                    url="https://outer.example.com/",
                    selector_candidates=[
                        SelectorCandidate(
                            strategy="css", value="iframe#outer-host",
                            quality_score=90, verified_unique=True,
                        ),
                    ],
                ),
                FrameDescriptor(
                    url="https://inner.example.com/",
                    selector_candidates=[
                        SelectorCandidate(
                            strategy="css", value="iframe[name=consent]",
                            quality_score=85, verified_unique=True,
                        ),
                    ],
                ),
            ],
        )
        line = _emit_command(cmd)
        assert "iframe#outer-host >>> iframe[name=consent] >>> button.accept" in line


# ──────────────────────────────────────────────────────────────────────
# RECORDER-FRAMES-2 defensive disambiguation — when the verifier
# couldn't run (iframe detached at verify time, Sourcepoint-banner
# race) the active selector lands `verified_unique=False`. For risky
# strategies (text, generic css, role, aria) we wrap with `>> nth=0`
# at emit time so Browser library's strict mode doesn't crash with
# "locator resolved to N elements" at replay.
# ──────────────────────────────────────────────────────────────────────


class TestDefensiveDisambiguation:
    def test_unverified_text_gets_nth0_wrap(self) -> None:
        """The heise.de Sourcepoint case: `text="Zustimmen"` matches
        3 elements (button + 2 paragraphs), verifier couldn't run
        because the iframe detached, candidate landed at slot 0
        with `verified_unique=False`. Without this wrap, replay
        crashes."""
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="text", value='text="Zustimmen"',
                    quality_score=70, verified_unique=False,
                ),
            ],
            active_candidate_index=0,
        )
        line = _emit_command(cmd)
        assert 'text="Zustimmen" >> nth=0' in line

    def test_verified_text_does_not_get_wrapped(self) -> None:
        """When verification ran cleanly and the candidate is
        `verified_unique=True`, emit it bare. Disambiguation is
        only a safety net for the unverified case."""
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="text", value='text="OnlyOne"',
                    quality_score=70, verified_unique=True,
                ),
            ],
            active_candidate_index=0,
        )
        line = _emit_command(cmd)
        assert 'text="OnlyOne"' in line
        assert ">> nth=0" not in line

    def test_unverified_css_with_id_skips_wrap(self) -> None:
        """A CSS selector with `#` is unique enough in practice that
        wrapping would be noisy. Skip the defensive wrap."""
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="css", value="#login-form",
                    quality_score=85, verified_unique=False,
                ),
            ],
            active_candidate_index=0,
        )
        line = _emit_command(cmd)
        # `\#` is the comment-escape — unrelated to our wrap.
        assert ">> nth=0" not in line

    def test_unverified_xpath_does_not_get_wrap(self) -> None:
        """Xpath strategies aren't in the risky-strategy set — xpath
        is usually written explicit enough by the synthesis layer
        not to need defensive disambiguation."""
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="xpath",
                    value="//button[normalize-space()='Click me']",
                    quality_score=60, verified_unique=False,
                ),
            ],
            active_candidate_index=0,
        )
        line = _emit_command(cmd)
        assert ">> nth=0" not in line

    def test_already_disambiguated_selector_is_not_double_wrapped(self) -> None:
        """If the verifier already produced `text=X >> nth=0` (via
        `_with_nth_match`), don't bolt a second `>> nth=0` on top."""
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="text", value='text="Zustimmen" >> nth=0',
                    quality_score=55, verified_unique=False,
                ),
            ],
            active_candidate_index=0,
        )
        line = _emit_command(cmd)
        # Exactly one `nth=0` in the output line.
        assert line.count("nth=0") == 1

    def test_unverified_generic_css_class_gets_wrap(self) -> None:
        """A pure-class CSS selector is the textbook multi-match
        risk — wrap defensively."""
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="css", value="button.primary",
                    quality_score=50, verified_unique=False,
                ),
            ],
            active_candidate_index=0,
        )
        line = _emit_command(cmd)
        assert "button.primary >> nth=0" in line


class TestEffectiveOverride:
    """User-supplied verbatim emit-form (set via the FlowEditor
    SelectorPicker's ✏ Effektiv field) MUST short-circuit the
    iframe-chain wrap + renderSelector prefix + defensive nth
    composition. The override string lands in the .robot line
    exactly as typed (modulo the RF-token escape on leading `#`)."""

    def test_override_skips_iframe_wrap_and_nth(self) -> None:
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="text", value='text="Zustimmen"',
                    quality_score=70, verified_unique=False,
                    # User wants to drop the auto-composed
                    # `iframe#auto-synth >>> text="Zustimmen" >> nth=0`
                    # in favour of a hand-tuned chain.
                    effective_override='iframe.consent >>> text="Zustimmen"',
                ),
            ],
            active_candidate_index=0,
            frame_chain=[
                FrameDescriptor(url="https://cmp.example/", selector_candidates=[
                    SelectorCandidate(
                        strategy="css", value="iframe#auto-synth",
                        quality_score=90, verified_unique=True,
                    ),
                ]),
            ],
        )
        line = _emit_command(cmd)
        assert 'iframe.consent >>> text="Zustimmen"' in line
        # The auto-composed prefix is gone — user override fully replaces.
        assert "iframe#auto-synth" not in line
        assert ">> nth=0" not in line

    def test_empty_override_falls_back_to_auto_compose(self) -> None:
        """`effective_override=None` AND empty / whitespace-only
        strings are treated as 'no override' — the emitter walks the
        normal compose path (iframe-chain + render + defensive nth)."""
        for empty in (None, "", "   "):
            cmd = RecordedCommand(
                index=0,
                keyword="Click",
                selector_candidates=[
                    SelectorCandidate(
                        strategy="text", value="text=Welcome",
                        quality_score=50, verified_unique=False,
                        effective_override=empty,
                    ),
                ],
                active_candidate_index=0,
            )
            line = _emit_command(cmd)
            assert "text=Welcome >> nth=0" in line, (
                f"empty override {empty!r} should not block auto-compose"
            )

    def test_override_round_trips_through_json(self) -> None:
        """Sidecars persist as JSON — the field MUST round-trip
        unchanged so a save → reload preserves the user's override."""
        cmd = RecordedCommand(
            index=0,
            keyword="Click",
            selector_candidates=[
                SelectorCandidate(
                    strategy="css", value="button.x",
                    quality_score=50, verified_unique=False,
                    effective_override="iframe#x >>> button.x",
                ),
            ],
            active_candidate_index=0,
        )
        payload = cmd.model_dump_json()
        round_tripped = RecordedCommand.model_validate_json(payload)
        assert round_tripped.selector_candidates[0].effective_override == \
            "iframe#x >>> button.x"

    def test_legacy_sidecar_without_field_loads_with_none(self) -> None:
        """JSON from a sidecar saved before this field shipped must
        still validate — the field defaults to None and the emitter
        falls back to auto-compose."""
        legacy_json = (
            '{"strategy": "css", "value": "button.x", '
            '"quality_score": 70, "verified_unique": true}'
        )
        cand = SelectorCandidate.model_validate_json(legacy_json)
        assert cand.effective_override is None


class TestGoToWaitUntil:
    """M2: every Go To (not just the synthesised New Page) gets
    wait_until=domcontentloaded so a multi-navigation recording doesn't hang
    at replay on the default wait_until=load."""

    def test_subsequent_go_to_gets_domcontentloaded(self) -> None:
        flow = _flow([
            RecordedCommand(index=0, keyword="Go To", args={"url": "https://a.example"}),
            RecordedCommand(index=1, keyword="Go To", args={"url": "https://b.example"}),
        ])
        out = emit_robot(flow)
        assert "New Page    https://a.example    wait_until=domcontentloaded" in out
        assert "Go To    https://b.example    wait_until=domcontentloaded" in out

    def test_emit_command_go_to_has_wait_until(self) -> None:
        line = _emit_command(
            RecordedCommand(index=0, keyword="Go To", args={"url": "https://x.example"})
        )
        assert "Go To    https://x.example    wait_until=domcontentloaded" in line


class TestChainedSelectorDisambiguation:
    """H5: a chained pierce (>>) is NOT a disambiguator — an unverified
    multi-match chained selector must still get a trailing nth=0, or Browser
    strict mode crashes at replay."""

    def test_chained_css_without_nth_gets_wrapped(self) -> None:
        cand = SelectorCandidate(
            strategy="css", value=".host >> .inner",
            quality_score=50, verified_unique=False,
        )
        assert _render_selector(cand) == ".host >> .inner >> nth=0"

    def test_chained_with_existing_nth_not_double_wrapped(self) -> None:
        cand = SelectorCandidate(
            strategy="css", value=".host >> .inner >> nth=0",
            quality_score=50, verified_unique=False,
        )
        assert _render_selector(cand).count("nth=0") == 1

    def test_verified_chained_not_wrapped(self) -> None:
        cand = SelectorCandidate(
            strategy="css", value=".host >> .inner",
            quality_score=90, verified_unique=True,
        )
        assert _render_selector(cand) == ".host >> .inner"
