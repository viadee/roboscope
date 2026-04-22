"""Story W.6 — Robot Framework emitter for Recorder v2 flows.

Pure function: `emit_robot(flow)` → .robot file contents (str). No file I/O,
no DB. The save endpoint composes this with file writing + audit.

Keyword mapping is the 15-keyword set frozen in architecture doc AR-6
(`Browser` library family groups). Future keywords can be added to
_KEYWORD_EMITTERS without breaking existing flows.
"""

from __future__ import annotations

from src.recording.selector_schema import (
    RecordedCommand,
    RecordedFlow,
    SelectorCandidate,
)


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


def _render_selector(cand: SelectorCandidate) -> str:
    """Return the on-disk representation of a selector for a Robot line.

    Browser library selectors are plain strings (it accepts css, xpath,
    text, role, and id= prefixes). We emit `strategy=value` only where
    Browser requires an explicit prefix; otherwise use the raw value.
    """
    value = cand.value
    if cand.strategy == "xpath":
        return f"xpath={value}"
    if cand.strategy == "text":
        return value if value.startswith("text=") else f"text={value}"
    # testid / css / aria / pw_locator / desktop strategies keep their value
    # verbatim — Browser library + test-author both read them clearly.
    return value


def _render_arg(value: object) -> str:
    """Render a keyword argument for a Robot line."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "${TRUE}" if value else "${FALSE}"
    if value is None:
        return "${None}"
    return str(value)


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
            # Fail loud — a targeted keyword without a selector is a bug.
            parts.append("# WARNING: no selector captured")
        else:
            parts.append(_render_selector(active))

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

    return "    " + "    ".join(parts)


def emit_robot(flow: RecordedFlow) -> str:
    """Serialise a RecordedFlow to `.robot` source.

    Output shape:

        *** Settings ***
        Library           Browser

        *** Test Cases ***
        <name or fallback>
            <cmd 1>
            <cmd 2>
            ...
    """
    test_name = flow.name or f"Recording {flow.session_id}"
    # Robot test names cannot contain a line break; collapse.
    test_name = test_name.replace("\n", " ").strip() or f"Recording {flow.session_id}"

    lines: list[str] = [
        "*** Settings ***",
        "Library           Browser",
        "",
        "*** Test Cases ***",
        test_name,
    ]

    if not flow.commands:
        lines.append("    No Operation")
    else:
        for cmd in flow.commands:
            lines.append(_emit_command(cmd))

    return "\n".join(lines) + "\n"
