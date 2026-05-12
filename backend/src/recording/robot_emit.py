"""Story W.6 — Robot Framework emitter for Recorder v2 flows.

Pure function: `emit_robot(flow)` → .robot file contents (str). No file I/O,
no DB. The save endpoint composes this with file writing + audit.

Keyword mapping is the 15-keyword set frozen in architecture doc AR-6
(`Browser` library family groups). Future keywords can be added to
_KEYWORD_EMITTERS without breaking existing flows.
"""

from __future__ import annotations

import logging

from src.recording.selector_schema import (
    RecordedCommand,
    RecordedFlow,
    SelectorCandidate,
)


_logger = logging.getLogger("roboscope.recording.emit")


# Keywords that target an element and therefore need the active selector
# appended as the first argument.
_TARGETED_KEYWORDS = {
    "Click",
    "Double Click",
    "Focus",
    "Hover",
    "Press Keys",
    "Scroll To Element",
    "Take Screenshot",
    "Highlight Elements",
    "Wait For Elements State",
    "Get Element Value",
    "Get Text",
    "Get Attribute",
    "Should Be Equal",
    "Should Contain",
    "Type Text",
}

# Keywords that do not target an element (no selector arg).
_GLOBAL_KEYWORDS = {
    "Go To",
    "Wait Until Network Is Idle",
    "Wait For Condition",
}


def _escape_rf_token(s: str) -> str:
    """Escape Robot Framework special characters at the TOKEN level.

    Robot Framework's lexer (space-separated format) treats any token
    that STARTS with `#` as a comment — everything from there to end
    of line is dropped. So a recorded CSS-ID selector `#login-form`
    naively rendered as `Click    #login-form` makes the entire
    Click silently run without arguments.

    Escape sequence is RF-defined: `\\#` → literal `#`. The leading
    backslash is consumed by RF's lexer before the value reaches
    Browser library, so the eventual `page.locator('#login-form')`
    call sees the raw selector unchanged.

    Other RF token-level traps (TAB or 2+ spaces inside the value,
    leading whitespace, literal `\\`) are NOT handled here yet —
    they're rare in recorded selectors / text labels and would
    require per-character escaping that risks over-correction. If a
    new failure mode shows up, extend here.
    """
    if not s:
        return s
    if s.startswith("#"):
        return "\\" + s
    return s


# Strategies that MAY resolve to multiple matches if not unique by ID
# or testid. When the recorder couldn't verify uniqueness (iframe race,
# detached frame at verify time), we wrap the value with `>> nth=0` to
# force a first-match resolution and avoid strict-mode-violation
# crashes at replay. Cosmetic noise, but safer-by-default for the
# real-world Sourcepoint / OneTrust / TCF-banner case where the iframe
# disappears between click and verify.
#
# The wrap is suppressed when the selector already carries `nth=` /
# `:nth-match(` (already disambiguated) or `>>` (chained pierce) so we
# don't double-wrap or interfere with hand-edited chains.
_RISKY_UNVERIFIED_STRATEGIES = {"text", "css", "role", "aria"}


def _is_already_disambiguated(value: str) -> bool:
    return (
        ">> nth=" in value
        or ":nth-match(" in value
        or ":nth-of-type(" in value
        or ">>>" in value
        or ">>" in value
    )


def _render_selector(cand: SelectorCandidate) -> str:
    """Return the on-disk representation of a selector for a Robot line.

    Browser library selectors are plain strings (it accepts css, xpath,
    text, role, and id= prefixes). We emit `strategy=value` only where
    Browser requires an explicit prefix; otherwise use the raw value.

    Defensive disambiguation: when the candidate is `verified_unique=
    False` AND uses a strategy known to be multi-match-prone (text,
    role, aria, generic css without an id), we append `>> nth=0` so
    Browser library's strict-mode picks the first match deterministically
    instead of raising "locator resolved to N elements". The case this
    catches is the heise.de Sourcepoint banner: `text="Zustimmen"`
    matches 3 elements (button + two paragraphs), the iframe detached
    before the verifier could disambiguate, and the candidate landed
    unverified at slot 0. Without this wrap the recording is unrunnable.
    """
    value = cand.value
    if cand.strategy == "xpath":
        out = f"xpath={value}"
    elif cand.strategy == "text":
        out = value if value.startswith("text=") else f"text={value}"
    else:
        # testid / css / aria / pw_locator / desktop strategies keep
        # their value verbatim — Browser library + test-author both
        # read them clearly.
        out = value

    if (
        not cand.verified_unique
        and cand.strategy in _RISKY_UNVERIFIED_STRATEGIES
        and not _is_already_disambiguated(out)
        # css-with-id is unique enough that wrapping is overkill —
        # `#login-form` rarely matches multiple elements in practice.
        and not (cand.strategy == "css" and "#" in value)
    ):
        out = f"{out} >> nth=0"
    return out


def _iframe_chain_locator(cmd: RecordedCommand) -> str | None:
    """Story RECORDER-FRAMES-2 — compose the iframe-wrapper portion of
    a cross-frame Browser-library locator from `cmd.frame_chain`.

    Each rung in `frame_chain` contributes `selector_candidates[0]`
    (the highest-ranked one, since the list is pre-sorted by
    `verified_unique DESC, quality_score DESC`). Rungs without
    candidates fall back to the legacy `iframe[src*="<host>"]`
    derived from the rung's URL — the same shape the URL-only path
    in `_iframe_locator_from_url` emits, kept here so a partially-
    captured chain (some rungs verified, some not) still produces a
    valid composite locator instead of dropping the entire wrapper.

    Returns the composed prefix `<outer> >>> <inner-iframe>` (no
    trailing separator — the caller adds `>>> <element>` after).
    Returns None when the chain is empty so the caller knows to fall
    back to the legacy URL-only strategy.
    """
    if not cmd.frame_chain:
        return None
    pieces: list[str] = []
    for rung in cmd.frame_chain:
        if rung.selector_candidates:
            pieces.append(rung.selector_candidates[0].value)
        else:
            # Rung without verified candidates — synthesise the
            # legacy URL-based fallback so the chain doesn't break.
            fallback = _iframe_locator_from_url(rung.url) if rung.url else None
            if fallback is None:
                # No URL either (unlikely but possible) — bail out;
                # we can't safely compose a partial chain.
                return None
            pieces.append(fallback)
    return " >>> ".join(pieces)


def _iframe_locator_from_url(frame_url: str) -> str | None:
    """Build a Browser-library iframe locator that targets a frame by
    its host. Returns None if the URL has no usable host (data:, empty,
    parse failure).

    `iframe[src*="<host>"]` matches any iframe whose `src` contains
    the host substring — robust to query-string variation between
    consent flows (Sourcepoint, OneTrust et al. embed
    session/consent-id query params that change every visit).

    Composed at the call site as
    `<iframe-locator> >>> <inner-selector>` (Browser library cross-
    frame piercing dialect). For replay this resolves the iframe by
    src match, descends into its document, then finds the inner
    selector — so a recorded click on a Sourcepoint "Accept all"
    button comes back as something like
    `iframe[src*="message-eu.sp-prod.net"] >>> button.message-component`.
    """
    from urllib.parse import urlparse
    try:
        parsed = urlparse(frame_url)
    except Exception:
        return None
    host = parsed.netloc
    if not host:
        return None
    return f'iframe[src*="{host}"]'


def _render_arg(value: object) -> str:
    """Render a keyword argument for a Robot line."""
    if isinstance(value, str):
        return _escape_rf_token(value)
    if isinstance(value, bool):
        return "${TRUE}" if value else "${FALSE}"
    if value is None:
        return "${None}"
    return _escape_rf_token(str(value))


def _emit_command(cmd: RecordedCommand) -> str:
    """Return one indented line of Robot syntax."""
    parts: list[str] = [cmd.keyword]

    selector_needed = cmd.keyword in _TARGETED_KEYWORDS
    if selector_needed:
        active = (
            cmd.selector_candidates[cmd.active_candidate_index]
            if cmd.selector_candidates
            else None
        )
        if active is None:
            # Targeted keyword without a selector — the previous
            # behavior was to emit `<Keyword>    # WARNING: no
            # selector captured` to make the gap visible in the
            # .robot. Problem: RF parses that as `<Keyword>` with
            # zero args, which crashes Browser-library keywords like
            # `Scroll To Element` at replay with "expected 1
            # argument, got 0". Emit the whole line as a single RF
            # comment instead — the gap is still visible but the
            # test no longer breaks.
            _logger.warning(
                "emit: targeted keyword %r has no selector candidate "
                "(cmd.id=%s, index=%d, frame_url=%s) — emitting as a "
                "comment so replay doesn't crash on a zero-arg call",
                cmd.keyword, cmd.id or "<none>", cmd.index, cmd.frame_url,
            )
            comment_line = (
                f"    # RBSCOPE: dropped {cmd.keyword} — no selector "
                f"captured (cmd.id={cmd.id or '<none>'})"
            )
            return comment_line
        else:
            # User-supplied verbatim override — the SelectorPicker's
            # ✏ edit lets users set this when the auto-composed form
            # is wrong (synthesised iframe rung that doesn't match,
            # unwanted `>> nth=0` for a candidate they know is
            # unique, hand-tuned cross-frame chain). When set, skip
            # the chain + render + nth composition entirely and emit
            # the override as-is. The RF-token escape still runs so a
            # bare-`#`-prefixed override is parsed correctly by RF's
            # lexer.
            if active.effective_override is not None and active.effective_override.strip():
                parts.append(_escape_rf_token(active.effective_override))
            else:
                inner = _render_selector(active)
                # Story RECORDER-FRAMES — events captured inside an iframe
                # carry their originating URL on the command; wrap the
                # inner selector with `iframe[…] >>> ` so the replay
                # locates the right document.
                #
                # Story RECORDER-FRAMES-2 — when `frame_chain` is present,
                # pick each rung's best selector candidate (verified-
                # unique > quality_score) so the user gets the ID-based
                # iframe locator when available, falls back through
                # name/src-exact/src-host/class as appropriate. Old
                # sidecars without `frame_chain` keep using the legacy
                # URL-derived `iframe[src*="<host>"]` strategy.
                chain_prefix = _iframe_chain_locator(cmd)
                if chain_prefix:
                    inner = f"{chain_prefix} >>> {inner}"
                elif cmd.frame_url:
                    legacy = _iframe_locator_from_url(cmd.frame_url)
                    if legacy is not None:
                        inner = f"{legacy} >>> {inner}"
                # RF-token escape — a CSS-ID selector `#login-form` would
                # be parsed as a comment by Robot Framework. The escape
                # `\#login-form` is consumed by RF's lexer before the
                # value reaches Browser library.
                parts.append(_escape_rf_token(inner))

    # Ordered args by convention: `url` first for navigation, `text` for
    # type/assert, `state` for wait, generic `value` last.
    ordered = (
        "url",
        "text",
        "value",
        "key",
        "state",
        "attribute_name",
        "expected",
        "ms",
    )
    for key in ordered:
        if key in cmd.args:
            parts.append(_render_arg(cmd.args[key]))

    # Any remaining args (extensibility for stretch keywords).
    for key, val in cmd.args.items():
        if key not in ordered:
            parts.append(_render_arg(val))

    # Story RECORDER-IDMAP — trailing comment with the command's
    # position-independent id. RF treats it as a regular line comment
    # (token starts with `#`); the FlowEditor parses it back out so
    # selector groups stay linked to their step even after
    # reorder / delete / insert in the visual editor. Skip when the
    # command has no candidates AND no id-bearing payload to map to —
    # the warning line above is its own comment.
    line = "    " + "    ".join(parts)
    if cmd.id and not (selector_needed and not cmd.selector_candidates):
        line += f"    # rbs:{cmd.id}"
    return line


def _library_for_transport(transport: str) -> str:
    """Pick the Robot library import line for a given recording transport."""
    if transport in ("desktop_windows", "desktop_macos"):
        return "RPA.Windows"
    # web_playwright, chrome_extension, default → Browser library.
    return "Browser"


# Desktop keywords mapped from AR-8 captured events. Shared with the
# web set for anything that overlaps (Click, Type Text, Double Click).
_DESKTOP_TARGETED_KEYWORDS = {
    "Click",
    "Double Click",
    "Type Text",
    "Select From Combobox",
    "Select From Menu",
    "Control Window",
    "Take Screenshot",
}


def _render_desktop_selector(cand: SelectorCandidate) -> str:
    """RPA.Windows locator syntax is `strategy:value` with the strategy
    aliases `id`, `name`, `class`, `xpath`.
    """
    if cand.strategy == "automation_id":
        return f"id:{cand.value}"
    if cand.strategy == "uia_name":
        return f"name:{cand.value}"
    if cand.strategy == "uia_class_name":
        return f"class:{cand.value}"
    if cand.strategy == "xpath":
        return f"xpath:{cand.value}"
    # Unexpected strategy for desktop — emit verbatim.
    return cand.value


def _emit_desktop_command(cmd: RecordedCommand) -> str:
    parts: list[str] = [cmd.keyword]

    targeted = cmd.keyword in _DESKTOP_TARGETED_KEYWORDS
    if targeted:
        active = (
            cmd.selector_candidates[cmd.active_candidate_index]
            if cmd.selector_candidates
            else None
        )
        if active is None:
            # Same fix as the web _emit_command: emit the entire
            # line as a pure RF comment instead of `<Keyword> # …`,
            # otherwise RPA.Windows would receive a zero-arg call
            # and crash at replay. Diagnostic still goes through
            # the recorder log stream at WARNING.
            _logger.warning(
                "emit (desktop): targeted keyword %r has no selector "
                "candidate (cmd.id=%s, index=%d) — emitting as a "
                "comment so replay doesn't crash on a zero-arg call",
                cmd.keyword, cmd.id or "<none>", cmd.index,
            )
            return (
                f"    # RBSCOPE: dropped {cmd.keyword} — no selector "
                f"captured (cmd.id={cmd.id or '<none>'})"
            )
        else:
            # Same override contract as web: a user-supplied verbatim
            # form bypasses the strategy-prefix logic and lands in
            # the emit as-is. Desktop has no iframe-chain wrapping
            # to skip — the prefix mapping (`name:`, `id:`, `class:`,
            # `xpath:`) is what would otherwise be applied.
            if active.effective_override is not None and active.effective_override.strip():
                parts.append(active.effective_override)
            else:
                parts.append(_render_desktop_selector(active))

    ordered = ("text", "value", "key")
    for key in ordered:
        if key in cmd.args:
            parts.append(_render_arg(cmd.args[key]))
    for key, val in cmd.args.items():
        if key not in ordered:
            parts.append(_render_arg(val))

    # RECORDER-IDMAP — desktop transport gets the same trailing
    # `# rbs:<id>` comment as web so reorder / insert / delete in
    # the visual editor preserves the link from a Robot step to its
    # sidecar candidate group. The selector-missing path early-
    # returns above with the id baked into the comment, so by the
    # time we reach this point the line is always a real keyword.
    line = "    " + "    ".join(parts)
    if cmd.id:
        line += f"    # rbs:{cmd.id}"
    return line


def emit_robot(flow: RecordedFlow) -> str:
    """Serialise a RecordedFlow to `.robot` source.

    Web flows use Browser library syntax; desktop flows use RPA.Windows
    locator syntax. Selected by `flow.transport`.

    Output shape:

        *** Settings ***
        Library           Browser            # or RPA.Windows for desktop

        *** Test Cases ***
        <name or fallback>
            <cmd 1>
            <cmd 2>
            ...
    """
    test_name = flow.name or f"Recording {flow.session_id}"
    # Robot test names cannot contain a line break; collapse.
    test_name = test_name.replace("\n", " ").strip() or f"Recording {flow.session_id}"

    library = _library_for_transport(flow.transport)
    is_desktop = library == "RPA.Windows"

    lines: list[str] = [
        "*** Settings ***",
        f"Library           {library}",
        "",
    ]

    # Web flows reference `${HEADLESS}` in their bootstrap (`New Browser
    # chromium    headless=${HEADLESS}`) so the user can flip head /
    # headless without touching the test body. We MUST also DEFINE the
    # variable here, otherwise Robot Framework refuses to start with
    # "Variable '${HEADLESS}' not found." `false` is the right default
    # for recorded tests — they're authored by clicking through a real
    # page; running them headed by default is what the user expects.
    if not is_desktop:
        lines.extend([
            "*** Variables ***",
            "${HEADLESS}       false",
            "",
        ])

    lines.extend([
        "*** Test Cases ***",
        test_name,
    ])

    if not flow.commands:
        lines.append("    No Operation")
    elif is_desktop:
        for cmd in flow.commands:
            lines.append(_emit_desktop_command(cmd))
    else:
        # Web flows need an explicit Browser-library bootstrap before
        # any Click / Go To can run. We synthesise it from the FIRST
        # `Go To` we see (the captured initial-load) and drop that
        # original Go To since `New Page <url>` already navigates.
        first_goto_idx = next(
            (i for i, c in enumerate(flow.commands)
             if c.keyword == "Go To" and isinstance(c.args.get("url"), str)),
            None,
        )
        initial_url = (
            flow.commands[first_goto_idx].args["url"]
            if first_goto_idx is not None
            else "about:blank"
        )
        lines.append(f"    New Browser    chromium    headless=${{HEADLESS}}")
        lines.append(f"    New Context")
        # Default `wait_until=load` waits for every ad/tracker subresource
        # to settle, which on real-world pages (heise.de etc.) routinely
        # exceeds the Browser-library 10s timeout even when the page is
        # visually loaded and interactive. `domcontentloaded` is enough
        # for any subsequent Click / Type Text to find its target.
        lines.append(f"    New Page    {initial_url}    wait_until=domcontentloaded")
        for i, cmd in enumerate(flow.commands):
            if i == first_goto_idx:
                continue
            lines.append(_emit_command(cmd))

    return "\n".join(lines) + "\n"
