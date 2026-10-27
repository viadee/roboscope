"""V14.3: GET /reports/{id}/export?format=csv|json."""

import csv
import io

import pytest

from tests.conftest import auth_header
from tests.reports.test_router import _make_test_result, _setup_report

pytestmark = pytest.mark.slow  # real subprocess / git in tmp_path — out of the fast dev loop


def _seed(db_session, admin_user):
    report = _setup_report(db_session, admin_user)
    db_session.add(_make_test_result(report.id, test_name="Plain", tags="smoke,ui"))
    db_session.add(_make_test_result(
        report.id, test_name='=HYPERLINK("x")', status="FAIL",
        error_message='line one, "quoted"\nline two',
    ))
    db_session.add(_make_test_result(report.id, test_name="@SUM(A1)", error_message="-1+2"))
    db_session.flush()
    return report


def test_csv_export(client, db_session, admin_user):
    report = _seed(db_session, admin_user)
    r = client.get(
        f"/api/v1/reports/{report.id}/export?format=csv", headers=auth_header(admin_user)
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert f"report_{report.id}_results.csv" in r.headers["content-disposition"]

    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == [
        "suite_name", "test_name", "long_name", "status", "duration_seconds",
        "tags", "start_time", "end_time", "error_message",
    ]
    assert len(rows) == 4
    fail = next(row for row in rows[1:] if row[3] == "FAIL")
    # multi-line error with comma + quotes round-trips intact
    assert fail[8] == 'line one, "quoted"\nline two'
    # formula-looking cells are neutralised
    assert fail[1] == "'=HYPERLINK(\"x\")"
    assert {"'@SUM(A1)", "Plain"} <= {row[1] for row in rows[1:]}
    assert "'-1+2" in {row[8] for row in rows[1:]}


def test_json_export(client, db_session, admin_user):
    report = _seed(db_session, admin_user)
    r = client.get(
        f"/api/v1/reports/{report.id}/export?format=json", headers=auth_header(admin_user)
    )
    assert r.status_code == 200
    assert f"report_{report.id}_results.json" in r.headers["content-disposition"]
    data = r.json()
    assert len(data) == 3
    assert {"id", "report_id", "test_name", "long_name", "status", "error_message"} <= set(data[0])
    # JSON is not a spreadsheet: values stay raw
    assert '=HYPERLINK("x")' in {d["test_name"] for d in data}


def test_bad_format_422(client, db_session, admin_user):
    report = _seed(db_session, admin_user)
    r = client.get(
        f"/api/v1/reports/{report.id}/export?format=xlsx", headers=auth_header(admin_user)
    )
    assert r.status_code == 422


def test_missing_report_404(client, admin_user):
    r = client.get("/api/v1/reports/99999/export?format=csv", headers=auth_header(admin_user))
    assert r.status_code == 404


def test_requires_auth(client, db_session, admin_user):
    report = _seed(db_session, admin_user)
    assert client.get(f"/api/v1/reports/{report.id}/export?format=csv").status_code in (401, 403)


def test_csv_safe_tab_cr_and_non_strings():
    from src.reports.router import _csv_safe

    assert _csv_safe("\t=1") == "'\t=1"
    assert _csv_safe("\r=1") == "'\r=1"
    assert _csv_safe("ok") == "ok"
    assert _csv_safe(-1.5) == -1.5
    assert _csv_safe(None) is None


# --- V15.1: JUnit/xUnit export via rebot ---------------------------------

import subprocess  # noqa: E402
import sys  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402

_SUITE = """*** Test Cases ***
Passes
    Log    ok

Fails
    Fail    boom
"""


@pytest.fixture
def junit_report(tmp_path, db_session, admin_user):
    suite = tmp_path / "demo.robot"
    suite.write_text(_SUITE)
    out = tmp_path / "output.xml"
    subprocess.run(
        [sys.executable, "-m", "robot", "--output", str(out), "--log", "NONE",
         "--report", "NONE", str(suite)],
        capture_output=True, check=False, timeout=120,
    )
    assert out.is_file()
    return _setup_report(db_session, admin_user, output_xml_path=str(out))


def _junit(client, report_id, user):
    return client.get(
        f"/api/v1/reports/{report_id}/export?format=junit", headers=auth_header(user)
    )


def test_junit_export(client, junit_report, admin_user):
    r = _junit(client, junit_report.id, admin_user)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/xml")
    assert (
        f'filename="report_{junit_report.id}_xunit.xml"' in r.headers["content-disposition"]
    )
    root = ET.fromstring(r.content)
    assert root.tag == "testsuite"
    assert root.get("tests") == "2"
    assert root.get("failures") == "1"


def test_junit_missing_file_404(client, junit_report, admin_user, tmp_path):
    (tmp_path / "output.xml").unlink()
    r = _junit(client, junit_report.id, admin_user)
    assert r.status_code == 404
    assert r.json()["detail"] == "output.xml not found"


def test_junit_corrupt_output_422(client, junit_report, admin_user, tmp_path):
    (tmp_path / "output.xml").write_text("not xml at all")
    r = _junit(client, junit_report.id, admin_user)
    assert r.status_code == 422
    assert r.json()["detail"]


def test_junit_timeout_422(client, junit_report, admin_user):
    with patch(
        "src.reports.service.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="rebot", timeout=120),
    ):
        r = _junit(client, junit_report.id, admin_user)
    assert r.status_code == 422
    assert r.json()["detail"] == "conversion timed out"


def test_junit_missing_report_404(client, admin_user):
    assert _junit(client, 99999, admin_user).status_code == 404
