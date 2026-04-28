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

    if cmd.keyword in _DESKTOP_TARGETED_KEYWORDS:
        active = (
            cmd.selector_candidates[cmd.active_candidate_index]
            if cmd.selector_candidates
            else None
        )
        if active is None:
            parts.append("# WARNING: no selector captured")
        else:
            parts.append(_render_desktop_selector(active))

    ordered = ("text", "value", "key")
    for key in ordered:
        if key in cmd.args:
            parts.append(_render_arg(cmd.args[key]))
    for key, val in cmd.args.items():
        if key not in ordered:
            parts.append(_render_arg(val))

    return "    " + "    ".join(parts)


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
        "*** Test Cases ***",
        test_name,
    ]

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
        lines.append(f"    New Page    {initial_url}")
        for i, cmd in enumerate(flow.commands):
            if i == first_goto_idx:
                continue
            lines.append(_emit_command(cmd))

    return "\n".join(lines) + "\n"
