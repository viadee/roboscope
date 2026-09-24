"""V14.3: GET /reports/{id}/export?format=csv|json."""

import csv
import io

from tests.conftest import auth_header
from tests.reports.test_router import _make_test_result, _setup_report


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
