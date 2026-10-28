"""Unit tests for the deep output.xml parser, statistics and duration maths.

Written against the mutmut survivors of ``src/reports/parser.py`` (docs/TESTING.md):
every assertion below pins a default value, a fallback branch or a dict key that the
flat-parser tests never touched.
"""

from pathlib import Path

import pytest
from defusedxml import ElementTree as ET

from src.reports.parser import (
    ParsedReport,
    ParsedTestResult,
    _calc_duration,
    parse_output_xml,
    parse_output_xml_deep,
)

DEEP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<robot generated="20240101 12:00:00.000" generator="Robot 7.0">
  <suite name="Root" source="/tests/root" id="s1">
    <doc>  Root doc  </doc>
    <suite name="Child" source="/tests/child.robot" id="s1-s1">
      <test name="Login" id="s1-s1-t1">
        <doc> Logs in </doc>
        <tags><tag>smoke</tag><tag></tag><tag>auth</tag></tags>
        <kw name="Open Browser" library="SeleniumLibrary">
          <arg>https://x</arg><arg></arg><arg>chrome</arg>
          <msg timestamp="20240101 12:00:00.100" level="DEBUG"> opening </msg>
          <msg> plain </msg>
          <kw name="Inner" type="SETUP">
            <status status="PASS" start="20240101 12:00:00.000" end="20240101 12:00:00.250"/>
          </kw>
          <status status="PASS" start="20240101 12:00:00.000" end="20240101 12:00:01.500"/>
        </kw>
        <kw name="No Status"/>
        <status status="FAIL" start="20240101 12:00:00.000" end="20240101 12:00:02.000"> boom </status>
      </test>
      <test name="Bare">
        <status status="PASS" start="20240101 12:00:00.000" end="20240101 12:00:00.500"> ignored </status>
      </test>
      <test name="Statusless"/>
      <status status="FAIL" start="20240101 12:00:00.000" end="20240101 12:00:03.000"/>
    </suite>
    <status status="FAIL" start="20240101 12:00:00.000" end="20240101 12:00:04.000"/>
  </suite>
  <statistics>
    <total>
      <stat pass="1" fail="2" skip="3">All Tests</stat>
      <stat>Empty</stat>
    </total>
  </statistics>
</robot>
"""


def _write(tmp_path: Path, xml: str) -> str:
    p = tmp_path / "output.xml"
    p.write_text(xml, encoding="utf-8")
    return str(p)


@pytest.fixture
def deep(tmp_path):
    return parse_output_xml_deep(_write(tmp_path, DEEP_XML))


def test_dataclass_defaults_are_empty():
    assert ParsedTestResult() == ParsedTestResult("", "", "", 0.0, "", [], "", "")
    assert ParsedReport() == ParsedReport(0, 0, 0, 0, 0.0, [], "", "")


def test_top_level_shape(deep):
    assert set(deep) == {"suites", "statistics", "generated"}
    assert deep["generated"] == "20240101 12:00:00.000"
    assert len(deep["suites"]) == 1


def test_root_suite_fields(deep):
    root = deep["suites"][0]
    assert root["name"] == "Root"
    assert root["source"] == "/tests/root"
    assert root["status"] == "FAIL"
    assert root["start_time"] == "20240101 12:00:00.000"
    assert root["end_time"] == "20240101 12:00:04.000"
    assert root["duration"] == 4.0
    assert root["doc"] == "Root doc"
    assert root["tests"] == []
    assert [s["name"] for s in root["suites"]] == ["Child"]


def test_child_suite_and_test_fields(deep):
    child = deep["suites"][0]["suites"][0]
    assert child["duration"] == 3.0
    assert child["doc"] == ""
    assert child["suites"] == []
    login, bare, statusless = child["tests"]

    assert login["name"] == "Login"
    assert login["id"] == "s1-s1-t1"
    assert login["status"] == "FAIL"
    assert login["start_time"] == "20240101 12:00:00.000"
    assert login["end_time"] == "20240101 12:00:02.000"
    assert login["duration"] == 2.0
    assert login["doc"] == "Logs in"
    assert login["tags"] == ["smoke", "auth"]
    assert login["error_message"] == "boom"

    assert bare["id"] == ""
    assert bare["error_message"] == ""  # text only kept for FAIL
    assert bare["tags"] == []
    assert bare["keywords"] == []
    assert bare["duration"] == 0.5

    assert statusless["status"] == "FAIL"
    assert statusless["start_time"] == ""
    assert statusless["duration"] == 0.0


def test_keyword_fields(deep):
    login = deep["suites"][0]["suites"][0]["tests"][0]
    kw, no_status = login["keywords"]
    assert kw["name"] == "Open Browser"
    assert kw["type"] == "kw"
    assert kw["library"] == "SeleniumLibrary"
    assert kw["status"] == "PASS"
    assert kw["start_time"] == "20240101 12:00:00.000"
    assert kw["end_time"] == "20240101 12:00:01.500"
    assert kw["duration"] == 1.5
    assert kw["doc"] == ""
    assert kw["arguments"] == ["https://x", "chrome"]
    assert kw["messages"] == [
        {"timestamp": "20240101 12:00:00.100", "level": "DEBUG", "text": "opening"},
        {"timestamp": "", "level": "INFO", "text": "plain"},
    ]
    (inner,) = kw["keywords"]
    assert inner["type"] == "SETUP"
    assert inner["library"] == ""
    assert inner["duration"] == 0.25
    assert inner["keywords"] == []

    assert no_status["status"] == "UNKNOWN"
    assert no_status["duration"] == 0.0
    assert no_status["messages"] == []


def test_suite_without_status_is_unknown(tmp_path):
    xml = '<robot><suite name="S"><test name="T"/></suite></robot>'
    root = parse_output_xml_deep(_write(tmp_path, xml))["suites"][0]
    assert root["status"] == "UNKNOWN"
    assert root["start_time"] == root["end_time"] == ""
    assert root["duration"] == 0.0


def test_statistics_total(deep):
    stats = deep["statistics"]
    assert set(stats) == {"total", "tag", "suite"}
    assert stats["tag"] == [] and stats["suite"] == []
    assert stats["total"] == {
        "All Tests": {"pass": 1, "fail": 2, "skip": 3},
        "Empty": {"pass": 0, "fail": 0, "skip": 0},
    }


@pytest.mark.parametrize(
    "xml",
    [
        "<robot/>",
        "<robot><statistics/></robot>",
        "<robot><statistics><tag/></statistics></robot>",
    ],
)
def test_statistics_and_suites_degrade_to_empty(tmp_path, xml):
    deep = parse_output_xml_deep(_write(tmp_path, xml))
    assert deep["suites"] == []
    assert deep["generated"] == ""
    assert deep["statistics"] == {"total": {}, "tag": [], "suite": []}


def test_deep_missing_file_and_hostile_xml(tmp_path):
    with pytest.raises(FileNotFoundError, match="output.xml not found"):
        parse_output_xml_deep(str(tmp_path / "nope.xml"))
    hostile = '<!DOCTYPE r [<!ENTITY x "y">]><robot>&x;</robot>'
    with pytest.raises(ET.ParseError, match="rejected by defused parser"):
        parse_output_xml_deep(_write(tmp_path, hostile))
    with pytest.raises(ET.ParseError, match="rejected by defused parser"):
        parse_output_xml(_write(tmp_path, hostile))


def test_flat_parser_defaults_and_dedup(tmp_path):
    xml = """<robot>
      <suite name="S">
        <test name="A">
          <tag>x</tag><tag>x</tag><tag></tag>
          <status start="20240101 12:00:00.000" end="20240101 12:00:01.000"> msg </status>
        </test>
        <test name="B"><status status="PASS"> not an error </status></test>
      </suite>
    </robot>"""
    report = parse_output_xml(_write(tmp_path, xml))
    a, b = report.test_results
    assert a.status == "FAIL"  # missing status attribute defaults to FAIL
    assert a.error_message == "msg"
    assert a.tags == ["x"]
    assert a.duration_seconds == 1.0
    assert b.error_message == ""
    assert report.suite_name == "S"
    assert (report.total_tests, report.passed_tests, report.failed_tests) == (2, 1, 1)
    assert report.total_duration_seconds == 1.0


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("", "20240101 12:00:01.000", 0.0),
        ("20240101 12:00:01.000", "", 0.0),
        ("20240101 12:00:00.000", "20240101 12:00:01.250", 1.25),
        ("20240101 12:00:05.000", "20240101 12:00:01.000", 0.0),  # negative clamps
        ("2024-01-01T12:00:00", "2024-01-01T12:00:02.500", 2.5),  # ISO fallback
        ("2024-01-01T12:00:05", "2024-01-01T12:00:00", 0.0),
        ("20240101 12:00:00.000", "2024-01-01T12:00:01", 1.0),  # mixed: ISO fallback accepts both
        ("garbage", "garbage", 0.0),
    ],
)
def test_calc_duration(start, end, expected):
    assert _calc_duration(start, end) == expected
