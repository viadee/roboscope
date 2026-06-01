"""Tests for the output.xml walker (DEBUG-2 helper)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from src.debug.output_xml_walker import find_first_failing_keyword


def _write(tmp_path: Path, name: str, body: str) -> str:
    p = tmp_path / name
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return str(p)


class TestFindFirstFailingKeyword:
    def test_extracts_first_failing_keyword(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path, "output.xml", """\
            <?xml version="1.0"?>
            <robot generated="2026-05-08">
              <suite source="/repo/tests/login.robot" name="Login">
                <test name="Login Works">
                  <kw name="Open Browser" source="/repo/tests/login.robot" line="5">
                    <status status="PASS"/>
                  </kw>
                  <kw name="Click Submit" source="/repo/tests/login.robot" line="12">
                    <status status="FAIL"/>
                  </kw>
                  <status status="FAIL">submit failed</status>
                </test>
              </suite>
            </robot>
            """,
        )
        loc = find_first_failing_keyword(path)
        assert loc is not None
        assert loc.test_name == "Login Works"
        assert loc.keyword_name == "Click Submit"
        assert loc.source == "/repo/tests/login.robot"
        assert loc.line == 12

    def test_picks_deepest_failure_in_nested_keywords(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path, "output.xml", """\
            <?xml version="1.0"?>
            <robot>
              <suite source="/repo/tests/checkout.robot" name="Checkout">
                <test name="Buy Item">
                  <kw name="Outer Wrap" source="/repo/tests/checkout.robot" line="3">
                    <kw name="Inner Click" source="/repo/tests/checkout.robot" line="42">
                      <status status="FAIL"/>
                    </kw>
                    <status status="FAIL"/>
                  </kw>
                  <status status="FAIL">inner failed</status>
                </test>
              </suite>
            </robot>
            """,
        )
        loc = find_first_failing_keyword(path)
        assert loc is not None
        assert loc.keyword_name == "Inner Click"
        assert loc.line == 42

    def test_returns_none_when_no_failure(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path, "output.xml", """\
            <?xml version="1.0"?>
            <robot>
              <suite source="/repo/tests/login.robot">
                <test name="Login">
                  <kw name="Log" source="/repo/tests/login.robot" line="3">
                    <status status="PASS"/>
                  </kw>
                  <status status="PASS"/>
                </test>
              </suite>
            </robot>
            """,
        )
        assert find_first_failing_keyword(path) is None

    def test_recurses_into_child_suites(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path, "output.xml", """\
            <?xml version="1.0"?>
            <robot>
              <suite name="Root">
                <suite source="/repo/tests/auth.robot" name="Auth">
                  <test name="Login">
                    <kw name="Click Login" source="/repo/tests/auth.robot" line="9">
                      <status status="FAIL"/>
                    </kw>
                    <status status="FAIL"/>
                  </test>
                </suite>
              </suite>
            </robot>
            """,
        )
        loc = find_first_failing_keyword(path)
        assert loc is not None
        assert loc.line == 9
        assert loc.source == "/repo/tests/auth.robot"

    def test_returns_none_when_failure_has_no_source(self, tmp_path: Path) -> None:
        # Failing setup with no concrete keyword line — caller should
        # fall back to test-header line.
        path = _write(
            tmp_path, "output.xml", """\
            <?xml version="1.0"?>
            <robot>
              <suite source="/repo/tests/odd.robot">
                <test name="Odd">
                  <kw name="Mystery">
                    <status status="FAIL"/>
                  </kw>
                  <status status="FAIL"/>
                </test>
              </suite>
            </robot>
            """,
        )
        assert find_first_failing_keyword(path) is None

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        assert find_first_failing_keyword(tmp_path / "nope.xml") is None

    def test_returns_none_for_malformed_xml(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "bad.xml", "not even xml")
        assert find_first_failing_keyword(path) is None
