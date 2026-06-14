"""Regression tests for the report-parser QA-audit fixes (demo-readiness).

  - H1: nested suite names must be hierarchical (A.B.C), not flattened — the
        flat parser used a descendant iterator that lost the hierarchy, so
        same-named tests in different suites collided.
  - H2: a test's tags must NOT include keyword-level tags (the old `.//tag`
        descendant axis pulled in <tag> nested under <kw>).
"""

from __future__ import annotations

from pathlib import Path

from src.reports.parser import parse_output_xml


def _write(tmp_path: Path, xml: str) -> str:
    p = tmp_path / "output.xml"
    p.write_text(xml, encoding="utf-8")
    return str(p)


def test_nested_suite_names_are_hierarchical(tmp_path: Path) -> None:
    xml = """<robot>
      <suite name="A">
        <suite name="B">
          <suite name="C">
            <test name="Login"><status status="PASS"/></test>
          </suite>
          <test name="Mid"><status status="PASS"/></test>
        </suite>
        <test name="Top"><status status="PASS"/></test>
      </suite>
    </robot>"""
    report = parse_output_xml(_write(tmp_path, xml))
    names = {t.test_name: t.suite_name for t in report.test_results}
    assert names["Login"] == "A.B.C"
    assert names["Mid"] == "A.B"
    assert names["Top"] == "A"
    assert report.total_tests == 3
    assert report.suite_name == "A"


def test_same_named_tests_in_different_suites_dont_collide(tmp_path: Path) -> None:
    xml = """<robot>
      <suite name="Root">
        <suite name="Alpha"><test name="Login"><status status="PASS"/></test></suite>
        <suite name="Beta"><test name="Login"><status status="FAIL"/></test></suite>
      </suite>
    </robot>"""
    report = parse_output_xml(_write(tmp_path, xml))
    suites = sorted(t.suite_name for t in report.test_results)
    assert suites == ["Root.Alpha", "Root.Beta"]


def test_test_tags_exclude_keyword_tags(tmp_path: Path) -> None:
    xml = """<robot>
      <suite name="S">
        <test name="T">
          <kw name="Some Keyword"><tags><tag>kwtag</tag></tags></kw>
          <status status="PASS"/>
          <tags><tag>smoke</tag><tag>ui</tag></tags>
        </test>
      </suite>
    </robot>"""
    report = parse_output_xml(_write(tmp_path, xml))
    t = report.test_results[0]
    assert set(t.tags) == {"smoke", "ui"}
    assert "kwtag" not in t.tags


def test_pre_rf7_flat_tags_still_parsed(tmp_path: Path) -> None:
    xml = """<robot>
      <suite name="S">
        <test name="T">
          <status status="PASS"/>
          <tag>legacy</tag>
        </test>
      </suite>
    </robot>"""
    report = parse_output_xml(_write(tmp_path, xml))
    assert report.test_results[0].tags == ["legacy"]
