"""V14.4: DELETE /reports/{id} (+ /all regression via the shared helper)."""

import pytest

from src.auth.constants import Role
from src.auth.models import User
from src.auth.service import hash_password
from src.config import settings
from src.execution.models import ExecutionRun
from src.reports.models import Report, TestResult
from tests.conftest import auth_header
from tests.reports.test_router import _make_test_result, _setup_report


@pytest.fixture
def reports_root(tmp_path, monkeypatch):
    root = tmp_path / "reports"
    root.mkdir()
    monkeypatch.setattr(settings, "REPORTS_DIR", str(root))
    return root


@pytest.fixture
def editor_user(db_session):
    user = User(email="editor@test.com", username="editor",
                hashed_password=hash_password("editor123"), role=Role.EDITOR)
    db_session.add(user)
    db_session.flush()
    return user


def _out(dirpath):
    dirpath.mkdir(parents=True)
    (dirpath / "output.xml").write_text("<robot/>")
    return str(dirpath / "output.xml")


def test_delete_removes_rows_and_dir_keeps_run(client, db_session, admin_user, reports_root):
    run_dir = reports_root / "run_1_abc"
    report = _setup_report(db_session, admin_user, output_xml_path=_out(run_dir))
    db_session.add(_make_test_result(report.id))
    db_session.flush()
    rid, run_id = report.id, report.execution_run_id

    r = client.delete(f"/api/v1/reports/{rid}", headers=auth_header(admin_user))
    assert r.status_code == 204
    assert not run_dir.exists()
    assert reports_root.exists()
    db_session.expire_all()
    assert db_session.get(Report, rid) is None
    assert db_session.query(TestResult).filter_by(report_id=rid).count() == 0
    assert db_session.get(ExecutionRun, run_id) is not None
    # the run's report link degrades to None, not a 500
    r = client.get(f"/api/v1/runs/{run_id}/report", headers=auth_header(admin_user))
    assert r.status_code == 200
    assert r.json() == {"report_id": None}


def test_dir_outside_root_not_removed(client, db_session, admin_user, reports_root, tmp_path):
    outside = tmp_path / "elsewhere"
    report = _setup_report(db_session, admin_user, output_xml_path=_out(outside))
    r = client.delete(f"/api/v1/reports/{report.id}", headers=auth_header(admin_user))
    assert r.status_code == 204
    assert outside.exists()


def test_root_itself_never_removed(client, db_session, admin_user, reports_root):
    report = _setup_report(db_session, admin_user, output_xml_path=str(reports_root / "output.xml"))
    r = client.delete(f"/api/v1/reports/{report.id}", headers=auth_header(admin_user))
    assert r.status_code == 204
    assert reports_root.exists()


def test_archive_nested_output_removes_archive_dir_only(
    client, db_session, admin_user, reports_root
):
    archive = reports_root / "archives" / "suite_abc123"
    xml = _out(archive / "nested")
    report = Report(execution_run_id=None, archive_name="suite", output_xml_path=xml)
    db_session.add(report)
    db_session.flush()
    r = client.delete(f"/api/v1/reports/{report.id}", headers=auth_header(admin_user))
    assert r.status_code == 204
    assert not archive.exists()
    assert (reports_root / "archives").exists()


def test_404(client, admin_user):
    r = client.delete("/api/v1/reports/99999", headers=auth_header(admin_user))
    assert r.status_code == 404


def test_viewer_403(client, db_session, admin_user, viewer_user, reports_root):
    report = _setup_report(db_session, admin_user)
    r = client.delete(f"/api/v1/reports/{report.id}", headers=auth_header(viewer_user))
    assert r.status_code == 403


def test_uploaded_report_editor_ok_runner_403(
    client, db_session, editor_user, runner_user, reports_root
):
    report = Report(execution_run_id=None, archive_name="x", output_xml_path="/nope/output.xml")
    db_session.add(report)
    db_session.flush()
    url = f"/api/v1/reports/{report.id}"
    assert client.delete(url, headers=auth_header(runner_user)).status_code == 403
    assert client.delete(url, headers=auth_header(editor_user)).status_code == 204


def test_delete_all_still_works(client, db_session, admin_user, reports_root):
    run_dir = reports_root / "run_2_def"
    report = _setup_report(db_session, admin_user, output_xml_path=_out(run_dir))
    db_session.add(_make_test_result(report.id))
    db_session.flush()
    r = client.delete("/api/v1/reports/all", headers=auth_header(admin_user))
    assert r.status_code == 200
    assert r.json() == {"deleted": 1, "dirs_cleaned": 1}
    assert not run_dir.exists()
    db_session.expire_all()
    assert db_session.query(Report).count() == 0
