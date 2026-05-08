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
        # RECORDER-1C: the first Go To becomes the initial-URL input to
        # the New Browser/New Context/New Page bootstrap.
        assert "New Page    https://example.com" in content
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


# ─── RECORDER-IDMAP — id round-trip through /save ─────────────────────


class TestIdMapRoundTrip:
    """End-to-end pin for the position-independent command id chain.

    The user's report: "wenn mehrere selektoren aufgenommen wurden
    passen diese nicht zu den korrekten befehlen". Phase 1 +
    Phase 2 tests covered emit and FE-matcher in isolation; this
    test runs the actual /save endpoint and asserts the wire
    contract — that the same id ends up on BOTH the `.robot` line
    AND the `.rbs.json` command, so the FlowEditor can later
    re-link by identity instead of position.
    """

    def _mk_flow_with_ids(self) -> dict:
        return {
            "schema_version": 1,
            "transport": "web_playwright",
            "session_id": "id-test",
            "name": "ID Round Trip",
            "commands": [
                {
                    "id": "cmd-go-to",
                    "index": 0,
                    "keyword": "Go To",
                    "args": {"url": "https://example.com"},
                    "selector_candidates": [],
                    "active_candidate_index": 0,
                },
                {
                    "id": "cmd-click-1",
                    "index": 1,
                    "keyword": "Click",
                    "args": {},
                    "selector_candidates": [
                        {
                            "strategy": "testid",
                            "value": '[data-testid="login"]',
                            "quality_score": 95,
                            "verified_unique": True,
                        }
                    ],
                    "active_candidate_index": 0,
                },
                {
                    "id": "cmd-click-2",
                    "index": 2,
                    "keyword": "Click",
                    "args": {},
                    "selector_candidates": [
                        {
                            "strategy": "css",
                            "value": "#submit",
                            "quality_score": 60,
                            "verified_unique": True,
                        }
                    ],
                    "active_candidate_index": 0,
                },
            ],
        }

    def test_robot_lines_carry_id_comments(
        self, client, admin_user, repo_with_tmpdir
    ):
        resp = client.post(
            ENDPOINT,
            json={
                "flow": self._mk_flow_with_ids(),
                "repo_id": repo_with_tmpdir.id,
                "path": "flows/idmap",
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201

        robot_path = Path(repo_with_tmpdir.local_path) / "flows" / "idmap.robot"
        content = robot_path.read_text()

        # First Go To gets folded into the New Page bootstrap (per
        # RECORDER-1C); its id doesn't surface as a # rbs comment.
        # The two Click rows DO carry their ids.
        assert "# rbs:cmd-click-1" in content
        assert "# rbs:cmd-click-2" in content
        # The login-click line specifically carries cmd-click-1.
        click_1_line = next(
            ln for ln in content.splitlines()
            if '[data-testid="login"]' in ln
        )
        assert click_1_line.rstrip().endswith("# rbs:cmd-click-1")
        # And the submit-click line carries cmd-click-2 — AND its
        # CSS-ID gets the leading-`#` escape (RECORDER-RF-ESCAPE).
        click_2_line = next(
            ln for ln in content.splitlines() if "#submit" in ln
        )
        assert "\\#submit" in click_2_line
        assert click_2_line.rstrip().endswith("# rbs:cmd-click-2")

    def test_sidecar_preserves_explicit_ids(
        self, client, admin_user, repo_with_tmpdir
    ):
        """The sidecar `.rbs.json` must carry the same ids as the
        `.robot` lines, otherwise the FlowEditor's ID-based matcher
        has nothing to look up."""
        resp = client.post(
            ENDPOINT,
            json={
                "flow": self._mk_flow_with_ids(),
                "repo_id": repo_with_tmpdir.id,
                "path": "flows/idmap_sidecar",
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201

        sidecar_path = Path(repo_with_tmpdir.local_path) / "flows" / "idmap_sidecar.rbs.json"
        sidecar = json.loads(sidecar_path.read_text())
        ids = [c["id"] for c in sidecar["commands"]]
        assert ids == ["cmd-go-to", "cmd-click-1", "cmd-click-2"]

    def test_robot_and_sidecar_ids_correspond(
        self, client, admin_user, repo_with_tmpdir
    ):
        """The ACTUAL contract: every `# rbs:<id>` in the .robot must
        match a command id in the .rbs.json. This is what the
        FlowEditor's matcher relies on; if the wire format ever
        drifts, this test fires."""
        import re
        resp = client.post(
            ENDPOINT,
            json={
                "flow": self._mk_flow_with_ids(),
                "repo_id": repo_with_tmpdir.id,
                "path": "flows/idmap_correspond",
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201

        base = Path(repo_with_tmpdir.local_path) / "flows" / "idmap_correspond"
        robot_text = (base.with_suffix(".robot")).read_text()
        sidecar = json.loads((base.with_suffix(".rbs.json")).read_text())

        ids_in_robot = set(re.findall(r"# rbs:([A-Za-z0-9-]+)", robot_text))
        ids_in_sidecar = {c["id"] for c in sidecar["commands"]}

        # Every id that surfaces in the .robot must exist in the
        # sidecar. (Sidecar may carry MORE ids — Go To etc. don't
        # always emit a `# rbs:` line.)
        assert ids_in_robot, "Expected at least one # rbs:<id> in the .robot"
        assert ids_in_robot.issubset(ids_in_sidecar)

    def test_default_factory_fires_when_id_omitted(
        self, client, admin_user, repo_with_tmpdir
    ):
        """A frontend that posts a flow without ids on commands
        (legacy / hand-built sidecar) gets ids minted by Pydantic's
        default factory. The sidecar always carries valid ids;
        absence of `# rbs:` in the .robot is what signals "legacy"
        to the FlowEditor matcher."""
        flow = self._mk_flow_with_ids()
        for cmd in flow["commands"]:
            del cmd["id"]
        resp = client.post(
            ENDPOINT,
            json={
                "flow": flow,
                "repo_id": repo_with_tmpdir.id,
                "path": "flows/idmap_default",
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201

        sidecar_path = Path(repo_with_tmpdir.local_path) / "flows" / "idmap_default.rbs.json"
        sidecar = json.loads(sidecar_path.read_text())
        for cmd in sidecar["commands"]:
            # 12-char hex from `_new_command_id`.
            assert len(cmd["id"]) == 12
            assert all(c in "0123456789abcdef" for c in cmd["id"])
