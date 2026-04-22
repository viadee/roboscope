"""Story W.6 — POST /recordings/save persists a RecordedFlow to the repo."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.audit.models import AuditLog
from src.auth.models import User
from src.auth.service import hash_password
from src.repos.models import Repository
from tests.conftest import auth_header


ENDPOINT = "/api/v1/recordings/save"


@pytest.fixture
def repo_with_tmpdir(db_session: Session, admin_user: User, tmp_path: Path) -> Repository:
    r = Repository(
        name="rec-save",
        git_url="https://github.com/x/y.git",
        default_branch="main",
        local_path=str(tmp_path),
        created_by=admin_user.id,
    )
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    return r


def _mk_flow(transport: str = "web_playwright") -> dict:
    return {
        "schema_version": 1,
        "transport": transport,
        "session_id": "s-1",
        "name": "Login happy path",
        "commands": [
            {
                "index": 0,
                "keyword": "Go To",
                "args": {"url": "https://example.com"},
                "selector_candidates": [],
                "active_candidate_index": 0,
            },
            {
                "index": 1,
                "keyword": "Click",
                "args": {},
                "selector_candidates": [
                    {
                        "strategy": "testid",
                        "value": '[data-testid="submit"]',
                        "quality_score": 95,
                        "verified_unique": True,
                    }
                ],
                "active_candidate_index": 0,
            },
        ],
    }


class TestSaveHappyPath:
    def test_saves_file_and_audits(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        repo_with_tmpdir: Repository,
    ) -> None:
        resp = client.post(
            ENDPOINT,
            json={
                "flow": _mk_flow(),
                "repo_id": repo_with_tmpdir.id,
                "path": "flows/login_happy",
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["saved_path"] == "flows/login_happy.robot"
        assert body["bytes_written"] > 0

        on_disk = Path(repo_with_tmpdir.local_path) / body["saved_path"]
        content = on_disk.read_text()
        assert "*** Test Cases ***" in content
        assert "Go To    https://example.com" in content
        assert 'Click    [data-testid="submit"]' in content

        audits = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "recording.flow.saved")
            .all()
        )
        assert len(audits) == 1
        detail = json.loads(audits[0].detail)
        assert detail["command_count"] == 2
        assert detail["path"] == "flows/login_happy.robot"

    def test_auto_suffixes_dot_robot(
        self,
        client: TestClient,
        admin_user: User,
        repo_with_tmpdir: Repository,
    ) -> None:
        resp = client.post(
            ENDPOINT,
            json={"flow": _mk_flow(), "repo_id": repo_with_tmpdir.id, "path": "foo/bar"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201
        assert resp.json()["saved_path"].endswith(".robot")


class TestPermissions:
    def test_viewer_forbidden(
        self,
        client: TestClient,
        db_session: Session,
        repo_with_tmpdir: Repository,
    ) -> None:
        viewer = User(
            email="v-save@test.com", username="v-save",
            hashed_password=hash_password("pw"), role="viewer",
        )
        db_session.add(viewer)
        db_session.commit()
        db_session.refresh(viewer)

        resp = client.post(
            ENDPOINT,
            json={"flow": _mk_flow(), "repo_id": repo_with_tmpdir.id, "path": "a.robot"},
            headers=auth_header(viewer),
        )
        assert resp.status_code == 403


class TestPathSafety:
    def test_absolute_path_rejected(
        self,
        client: TestClient,
        admin_user: User,
        repo_with_tmpdir: Repository,
    ) -> None:
        resp = client.post(
            ENDPOINT,
            json={
                "flow": _mk_flow(),
                "repo_id": repo_with_tmpdir.id,
                "path": "/etc/passwd",
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400

    def test_traversal_segment_rejected(
        self,
        client: TestClient,
        admin_user: User,
        repo_with_tmpdir: Repository,
    ) -> None:
        resp = client.post(
            ENDPOINT,
            json={
                "flow": _mk_flow(),
                "repo_id": repo_with_tmpdir.id,
                "path": "flows/../../../escape.robot",
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400

    def test_empty_path_rejected(
        self,
        client: TestClient,
        admin_user: User,
        repo_with_tmpdir: Repository,
    ) -> None:
        resp = client.post(
            ENDPOINT,
            json={"flow": _mk_flow(), "repo_id": repo_with_tmpdir.id, "path": "  "},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400


class TestFlowValidation:
    def test_unknown_schema_version_rejected(
        self,
        client: TestClient,
        admin_user: User,
        repo_with_tmpdir: Repository,
    ) -> None:
        flow = _mk_flow()
        flow["schema_version"] = 99
        resp = client.post(
            ENDPOINT,
            json={"flow": flow, "repo_id": repo_with_tmpdir.id, "path": "bad.robot"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400

    def test_missing_schema_version_rejected(
        self,
        client: TestClient,
        admin_user: User,
        repo_with_tmpdir: Repository,
    ) -> None:
        flow = _mk_flow()
        del flow["schema_version"]
        resp = client.post(
            ENDPOINT,
            json={"flow": flow, "repo_id": repo_with_tmpdir.id, "path": "bad.robot"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400


class TestRepoNotFound:
    def test_unknown_repo_404(
        self, client: TestClient, admin_user: User
    ) -> None:
        resp = client.post(
            ENDPOINT,
            json={"flow": _mk_flow(), "repo_id": 99999, "path": "a.robot"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404
