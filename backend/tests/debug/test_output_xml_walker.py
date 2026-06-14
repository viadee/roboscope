"""H3 regression: find_first_failing_keyword must descend into RF 7.x control
structures (FOR/IF/TRY/WHILE), not just <kw>. Otherwise a failure nested in a
loop/conditional is invisible and the debugger breakpoint lands at the wrong
line (the test header fallback)."""

from __future__ import annotations

from pathlib import Path

from src.debug.output_xml_walker import find_first_failing_keyword


def _write(tmp_path: Path, xml: str) -> Path:
    p = tmp_path / "output.xml"
    p.write_text(xml, encoding="utf-8")
    return p


def test_plain_keyword_failure_still_found(tmp_path: Path) -> None:
    xml = """<robot><suite name="S" source="/repo/s.robot">
      <test name="T">
        <kw name="Click" source="/repo/s.robot" line="10"><status status="FAIL"/></kw>
        <status status="FAIL"/>
      </test></suite></robot>"""
    loc = find_first_failing_keyword(_write(tmp_path, xml))
    assert loc is not None and loc.line == 10 and loc.keyword_name == "Click"


def test_failure_inside_for_loop_is_found(tmp_path: Path) -> None:
    xml = """<robot><suite name="S" source="/repo/s.robot">
      <test name="T">
        <for flavor="IN">
          <iter>
            <kw name="Inner KW" source="/repo/s.robot" line="42"><status status="FAIL"/></kw>
            <status status="FAIL"/>
          </iter>
          <status status="FAIL"/>
        </for>
        <status status="FAIL"/>
      </test></suite></robot>"""
    loc = find_first_failing_keyword(_write(tmp_path, xml))
    assert loc is not None
    assert loc.line == 42
    assert loc.keyword_name == "Inner KW"


def test_failure_inside_if_branch_is_found(tmp_path: Path) -> None:
    xml = """<robot><suite name="S" source="/repo/s.robot">
      <test name="T">
        <if>
          <branch type="IF" condition="True">
            <kw name="Then KW" source="/repo/s.robot" line="7"><status status="FAIL"/></kw>
            <status status="FAIL"/>
          </branch>
          <status status="FAIL"/>
        </if>
        <status status="FAIL"/>
      </test></suite></robot>"""
    loc = find_first_failing_keyword(_write(tmp_path, xml))
    assert loc is not None and loc.line == 7 and loc.keyword_name == "Then KW"


def test_no_failure_returns_none(tmp_path: Path) -> None:
    xml = """<robot><suite name="S" source="/repo/s.robot">
      <test name="T"><kw name="OK" source="/repo/s.robot" line="3"><status status="PASS"/></kw>
      <status status="PASS"/></test></suite></robot>"""
    assert find_first_failing_keyword(_write(tmp_path, xml)) is None
