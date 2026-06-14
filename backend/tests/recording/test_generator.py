"""Tests for Robot Framework file generation from recorded events."""

import json

from src.recording.generator import generate_robot_file


class TestGenerateRobotFile:
    """Tests for generate_robot_file()."""

    def test_empty_events(self):
        result = generate_robot_file("[]", "Browser")
        assert "*** Settings ***" in result
        assert "No events were recorded" in result

    def test_none_events(self):
        result = generate_robot_file(None, "Browser")
        assert "No events were recorded" in result

    def test_navigate_browser(self):
        events = json.dumps([
            {"event_type": "navigate", "url": "https://example.com"},
        ])
        result = generate_robot_file(events, "Browser")
        assert "New Browser" in result
        # Story RECORDER-NAV-1 — Run 32 hit a 10s `page.goto` timeout
        # on heise.de because the default `wait_until=load` waits for
        # every ad/tracker subresource. The browser was visible (DOM
        # was loaded), but `load` never fired in time.
        # Fix: emit `wait_until=domcontentloaded` on every recorded
        # `New Page`. This regression guard keeps the option pinned —
        # if anyone drops it, real-world recordings start timing out
        # again.
        assert "New Page    https://example.com    wait_until=domcontentloaded" in result

    def test_navigate_selenium(self):
        events = json.dumps([
            {"event_type": "navigate", "url": "https://example.com"},
        ])
        result = generate_robot_file(events, "SeleniumLibrary")
        assert "Open Browser    https://example.com" in result

    def test_click_browser(self):
        events = json.dumps([
            {"event_type": "click", "selector": "//button[@id='submit']"},
        ])
        result = generate_robot_file(events, "Browser")
        assert "Click    //button[@id='submit']" in result

    def test_click_selenium(self):
        events = json.dumps([
            {"event_type": "click", "selector": "//button[@id='submit']"},
        ])
        result = generate_robot_file(events, "SeleniumLibrary")
        assert "Click Element    //button[@id='submit']" in result

    def test_input_browser(self):
        events = json.dumps([
            {"event_type": "input", "selector": "//input[@id='user']", "value": "admin"},
        ])
        result = generate_robot_file(events, "Browser")
        assert "Fill Text    //input[@id='user']    admin" in result

    def test_input_selenium(self):
        events = json.dumps([
            {"event_type": "input", "selector": "//input[@id='user']", "value": "admin"},
        ])
        result = generate_robot_file(events, "SeleniumLibrary")
        assert "Input Text    //input[@id='user']    admin" in result

    def test_password_masked(self):
        events = json.dumps([
            {"event_type": "password", "selector": "//input[@id='pass']", "value": "secret"},
        ])
        result = generate_robot_file(events, "Browser")
        # L1: reference a ${PASSWORD} variable (defined as a placeholder),
        # not a literal "***" that types asterisks and breaks login.
        assert "Fill Secret    //input[@id='pass']    ${PASSWORD}" in result
        assert "${PASSWORD}    CHANGE_ME" in result
        assert "secret" not in result

    def test_select_browser(self):
        events = json.dumps([
            {"event_type": "select", "selector": "//select[@id='role']", "value": "admin"},
        ])
        result = generate_robot_file(events, "Browser")
        assert "Select Options By    //select[@id='role']    value    admin" in result

    def test_select_selenium(self):
        events = json.dumps([
            {"event_type": "select", "selector": "//select[@id='role']", "value": "admin"},
        ])
        result = generate_robot_file(events, "SeleniumLibrary")
        assert "Select From List By Value    //select[@id='role']    admin" in result

    def test_full_recording_sequence(self):
        events = json.dumps([
            {"event_type": "navigate", "url": "https://example.com/login"},
            {"event_type": "input", "selector": "//input[@id='user']", "value": "admin"},
            {"event_type": "password", "selector": "//input[@id='pass']", "value": "pw"},
            {"event_type": "click", "selector": "//button[@type='submit']"},
        ])
        result = generate_robot_file(
            events, "Browser", target_url="https://example.com/login"
        )
        assert "*** Settings ***" in result
        assert "Library           Browser" in result
        assert "*** Variables ***" in result
        assert "*** Test Cases ***" in result
        assert "Recorded Test" in result
        lines = result.split("\n")
        # Find test step lines
        steps = [l for l in lines if l.startswith("    ")]
        assert len(steps) >= 4

    def test_custom_test_name(self):
        events = json.dumps([
            {"event_type": "click", "selector": "//button"},
        ])
        result = generate_robot_file(events, "Browser", test_name="Login Flow")
        assert "Login Flow" in result

    def test_settings_section_has_library(self):
        events = json.dumps([
            {"event_type": "click", "selector": "//button"},
        ])
        result = generate_robot_file(events, "SeleniumLibrary")
        assert "Library           SeleniumLibrary" in result
        assert "Close Browser" in result


class TestPasswordVariable:
    """L1: a recorded password field must reference ${PASSWORD} (with a
    defined placeholder), not a literal '***' that would type asterisks and
    break the login — and must never emit the real captured secret."""

    def test_password_uses_variable_not_literal(self):
        events = json.dumps([
            {"event_type": "password", "selector": "#pw", "value": "hunter2"},
        ])
        out = generate_robot_file(events, "Browser")
        assert "${PASSWORD}" in out
        assert "${PASSWORD}    CHANGE_ME" in out  # placeholder defined
        assert "hunter2" not in out               # real secret never emitted

    def test_no_password_no_password_var(self):
        events = json.dumps([
            {"event_type": "input", "selector": "#u", "value": "alice"},
        ])
        out = generate_robot_file(events, "Browser")
        assert "${PASSWORD}" not in out
