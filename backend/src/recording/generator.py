"""Generate Robot Framework .robot files from recorded events."""

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("roboscope.recording.generator")

# Mapping from event types to Browser library keywords
BROWSER_KEYWORD_MAP = {
    "click": "Click",
    "input": "Fill Text",
    "password": "Fill Secret",
    "select": "Select Options By",
    "navigate": "Go To",
    "checkbox": "Check Checkbox",
    "radio": "Click",
    "file": "Upload File By Selector",
}

# Mapping from event types to SeleniumLibrary keywords
SELENIUM_KEYWORD_MAP = {
    "click": "Click Element",
    "input": "Input Text",
    "password": "Input Password",
    "select": "Select From List By Value",
    "navigate": "Go To",
    "checkbox": "Select Checkbox",
    "radio": "Click Element",
    "file": "Choose File",
}


def generate_robot_file(
    events_json: str,
    target_library: str = "Browser",
    test_name: str | None = None,
    target_url: str | None = None,
) -> str:
    """Generate a .robot file from recorded events.

    Args:
        events_json: JSON string containing array of recorded events.
        target_library: "Browser" or "SeleniumLibrary".
        test_name: Name for the test case. Auto-generated if not provided.
        target_url: Base URL for documentation.

    Returns:
        Complete .robot file content as string.
    """
    events = json.loads(events_json) if events_json else []
    if not events:
        return _empty_robot(target_library, test_name)

    keyword_map = (
        BROWSER_KEYWORD_MAP if target_library == "Browser" else SELENIUM_KEYWORD_MAP
    )

    if not test_name:
        test_name = f"Recorded Test {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

    lines = []

    # Settings section
    lines.append("*** Settings ***")
    if target_url:
        lines.append(f"Documentation     Recorded test for {target_url}")
    lines.append(f"Library           {target_library}")
    lines.append(f"Test Teardown     Close Browser")
    lines.append("")

    # Variables section
    lines.append("*** Variables ***")
    lines.append("${BROWSER}    chromium")
    # L1: if the recording typed into a password field, reference a
    # ${PASSWORD} variable instead of a literal "***" (which would type three
    # asterisks and make the login fail). Define a clearly-placeholder value
    # the user replaces; without the definition RF errors "variable not found".
    if any(e.get("event_type") == "password" for e in events):
        lines.append("${PASSWORD}    CHANGE_ME")
    lines.append("")

    # Test Cases section
    lines.append("*** Test Cases ***")
    lines.append(test_name)

    for event in events:
        event_type = event.get("event_type", "click")
        selector = event.get("selector", "")
        value = event.get("value", "")
        url = event.get("url", "")

        keyword = keyword_map.get(event_type, keyword_map.get("click", "Click"))

        if event_type == "navigate":
            if target_library == "Browser":
                lines.append(f"    New Browser    ${{BROWSER}}    headless=false")
                # Default `wait_until=load` waits for every ad/tracker
                # subresource to settle, which on real-world pages
                # (heise.de etc.) routinely exceeds the Browser-library
                # 10s timeout even when the page is visually loaded and
                # interactive. `domcontentloaded` is enough for any
                # subsequent Click / Type Text to find its target.
                lines.append(f"    New Page    {url}    wait_until=domcontentloaded")
            else:
                lines.append(f"    Open Browser    {url}    ${{BROWSER}}")
        elif event_type in ("input", "password"):
            display_value = "${PASSWORD}" if event_type == "password" else value
            lines.append(f"    {keyword}    {selector}    {display_value}")
        elif event_type == "select":
            if target_library == "Browser":
                lines.append(f"    {keyword}    {selector}    value    {value}")
            else:
                lines.append(f"    {keyword}    {selector}    {value}")
        elif event_type in ("click", "checkbox", "radio"):
            lines.append(f"    {keyword}    {selector}")
        else:
            # Fallback: use click keyword with selector
            if selector:
                lines.append(f"    {keyword}    {selector}")

    lines.append("")
    return "\n".join(lines)


def _empty_robot(target_library: str, test_name: str | None = None) -> str:
    """Generate a minimal .robot file with no test steps."""
    name = test_name or "Empty Recorded Test"
    return (
        f"*** Settings ***\n"
        f"Library           {target_library}\n"
        f"\n"
        f"*** Test Cases ***\n"
        f"{name}\n"
        f"    Log    No events were recorded\n"
    )
