"""Story SH-4 — /runs/{id}/heal-report/{idx}/apply endpoint tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.service import hash_password
from src.execution.models import ExecutionRun, RunStatus
from src.repos.models import Repository
from tests.conftest import auth_header


APPLY = "/api/v1/runs/{}/heal-report/{}/apply"


def _viewer(db_session: Session) -> User:
    u = User(
        email="sh4-viewer@test.com", username="sh4-viewer",
        hashed_password=hash_password("pw"), role="viewer",
    )
    db_session.add(u)
    db_session.flush()
    db_session.refresh(u)
    return u


def _write_audit_and_output(
    output_dir: Path,
    *,
    records: list[dict],
    test_outcomes: dict[str, str],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "heal_audit.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records), encoding="utf-8",
    )
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<robot>", "<suite>"]
    for name, status in test_outcomes.items():
        parts.append(f'<test name="{name}"><status status="{status}"/></test>')
    parts.append("</suite></robot>")
    (output_dir / "output.xml").write_text("\n".join(parts), encoding="utf-8")


@pytest.fixture
def repo_with_robot(
    db_session: Session, admin_user: User, tmp_path: Path
) -> tuple[Repository, Path]:
    """A repo with a single .robot file containing a healable line."""
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    robot_path = tmp_path / "tests" / "login.robot"
    robot_path.write_text(
        "*** Settings ***\n"
        "Library    Browser\n\n"
        "*** Test Cases ***\n"
        "Happy Test\n"
        "    Open Browser    http://x\n"
        "    Click    id=submit\n"
        "    Close Browser\n",
        encoding="utf-8",
    )
    repo = Repository(
        name="sh4-repo",
        git_url="https://github.com/x/y.git",
        default_branch="main",
        local_path=str(tmp_path),
        created_by=admin_user.id,
    )
    db_session.add(repo)
    db_session.flush()
    db_session.refresh(repo)
    return repo, robot_path


def _mk_run(
    db_session: Session, repo: Repository, owner: User, output_dir: Path,
    *, target_path: str = "tests/login.robot",
):
    run = ExecutionRun(
        repository_id=repo.id,
        target_path=target_path,
        branch="main",
        status=RunStatus.PASSED,
        output_dir=str(output_dir),
        triggered_by=owner.id,
    )
    db_session.add(run)
    db_session.flush()
    db_session.refresh(run)
    return run


class TestApplyHappyPath:
    def test_confirmed_heal_writes_new_selector(
        self, client, db_session, admin_user, repo_with_robot, tmp_path
    ) -> None:
        repo, robot_path = repo_with_robot
        out = tmp_path / "out"
        _write_audit_and_output(
            out,
            records=[{
                "timestamp": "2026-04-24T10:00:00Z",
                "test_name": "Happy Test",
                "keyword": "Click",
                "original_selector": "id=submit",
                "healed_selector": "[data-testid=submit]",
                "confidence": 0.95,
                "source": "sidecar",
            }],
            test_outcomes={"Happy Test": "PASS"},
        )
        run = _mk_run(db_session, repo, admin_user, out)

        resp = client.post(APPLY.format(run.id, 0), headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["applied"] is True
        assert body["file_path"] == "tests/login.robot"

        # File now carries the healed selector on that line.
        content = robot_path.read_text(encoding="utf-8")
        assert "    Click    [data-testid=submit]" in content
        assert "    Click    id=submit" not in content

    def test_idempotent_reapply_returns_applied_false(
        self, client, db_session, admin_user, repo_with_robot, tmp_path
    ) -> None:
        repo, robot_path = repo_with_robot
        out = tmp_path / "out"
        _write_audit_and_output(
            out,
            records=[{
                "timestamp": "2026-04-24T10:00:00Z",
                "test_name": "Happy Test",
                "keyword": "Click",
                "original_selector": "id=submit",
                "healed_selector": "[data-testid=submit]",
                "confidence": 0.95,
                "source": "sidecar",
            }],
            test_outcomes={"Happy Test": "PASS"},
        )
        run = _mk_run(db_session, repo, admin_user, out)
        # First apply: writes.
        resp1 = client.post(APPLY.format(run.id, 0), headers=auth_header(admin_user))
        assert resp1.status_code == 200
        assert resp1.json()["applied"] is True
        # Second apply: already patched, idempotent.
        resp2 = client.post(APPLY.format(run.id, 0), headers=auth_header(admin_user))
        assert resp2.status_code == 200
        body = resp2.json()
        assert body["applied"] is False
        assert body["reason"] == "already_patched"


class TestSafetyGates:
    def test_suspect_heal_rejected(
        self, client, db_session, admin_user, repo_with_robot, tmp_path
    ) -> None:
        repo, _ = repo_with_robot
        out = tmp_path / "out"
        _write_audit_and_output(
            out,
            records=[{
                "timestamp": "x",
                "test_name": "Happy Test",
                "keyword": "Click",
                "original_selector": "id=submit",
                "healed_selector": "text=Submit",
                "confidence": 0.7,
                "source": "transposition",
            }],
            test_outcomes={"Happy Test": "FAIL"},  # FAIL → suspect
        )
        run = _mk_run(db_session, repo, admin_user, out)
        resp = client.post(APPLY.format(run.id, 0), headers=auth_header(admin_user))
        assert resp.status_code == 400
        assert "suspect" in resp.json()["detail"].lower()

    def test_index_out_of_bounds(
        self, client, db_session, admin_user, repo_with_robot, tmp_path
    ) -> None:
        repo, _ = repo_with_robot
        out = tmp_path / "out"
        _write_audit_and_output(
            out, records=[], test_outcomes={},
        )
        run = _mk_run(db_session, repo, admin_user, out)
        resp = client.post(APPLY.format(run.id, 99), headers=auth_header(admin_user))
        assert resp.status_code == 404

    def test_viewer_forbidden(
        self, client, db_session, admin_user, repo_with_robot, tmp_path
    ) -> None:
        repo, _ = repo_with_robot
        viewer = _viewer(db_session)
        out = tmp_path / "out"
        _write_audit_and_output(
            out,
            records=[{
                "timestamp": "x",
                "test_name": "Happy Test",
                "keyword": "Click",
                "original_selector": "id=submit",
                "healed_selector": "[data-testid=submit]",
                "confidence": 0.95,
                "source": "sidecar",
            }],
            test_outcomes={"Happy Test": "PASS"},
        )
        run = _mk_run(db_session, repo, admin_user, out)
        resp = client.post(APPLY.format(run.id, 0), headers=auth_header(viewer))
        assert resp.status_code == 403

    def test_ambiguous_line_not_written(
        self, client, db_session, admin_user, tmp_path
    ) -> None:
        # A .robot with two matching lines → the patcher must refuse.
        (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
        robot_path = tmp_path / "tests" / "dup.robot"
        robot_path.write_text(
            "*** Test Cases ***\nT1\n"
            "    Click    id=submit\n"
            "T2\n"
            "    Click    id=submit\n",
            encoding="utf-8",
        )
        repo = Repository(
            name="sh4-dup", git_url="https://github.com/x/y.git",
            default_branch="main", local_path=str(tmp_path),
            created_by=admin_user.id,
        )
        import sqlalchemy as sa
        from sqlalchemy.orm import Session as _Session
        db_session.add(repo)
        db_session.flush()
        db_session.refresh(repo)

        out = tmp_path / "out"
        _write_audit_and_output(
            out,
            records=[{
                "timestamp": "x",
                "test_name": "T1",
                "keyword": "Click",
                "original_selector": "id=submit",
                "healed_selector": "[data-testid=submit]",
                "confidence": 0.95,
                "source": "sidecar",
            }],
            test_outcomes={"T1": "PASS"},
        )
        run = _mk_run(
            db_session, repo, admin_user, out,
            target_path="tests/dup.robot",
        )
        resp = client.post(APPLY.format(run.id, 0), headers=auth_header(admin_user))
        assert resp.status_code == 409
        # File must not have changed.
        after = robot_path.read_text(encoding="utf-8")
        assert after.count("id=submit") == 2
        assert "[data-testid=submit]" not in after


# ─── RECORDER-IDMAP — heal patch must preserve `# rbs:<id>` comment ──


class TestHealPatchPreservesRbsComment:
    """A fresh recording emits each step line with a trailing
    `    # rbs:<id>` comment. The heal-patch endpoint used to ignore
    that comment when matching (so it couldn't find the line) AND
    drop it when rewriting (so the FlowEditor's id-based matcher
    silently regressed to positional). Both bugs fixed together."""

    def test_finds_line_with_trailing_rbs_comment(
        self, client, db_session, admin_user, tmp_path
    ):
        # Realistic shape of a recorder-emitted line.
        robot_path = tmp_path / "tests" / "rec.robot"
        robot_path.parent.mkdir(parents=True)
        robot_path.write_text(
            "*** Test Cases ***\n"
            "T1\n"
            "    Click    id=submit    # rbs:abc123def456\n",
            encoding="utf-8",
        )
        repo = Repository(
            name="rbs-find", git_url="https://github.com/x/y.git",
            default_branch="main", local_path=str(tmp_path),
            created_by=admin_user.id,
        )
        db_session.add(repo)
        db_session.flush()
        db_session.refresh(repo)

        out = tmp_path / "out"
        _write_audit_and_output(
            out,
            records=[{
                "timestamp": "x",
                "test_name": "T1",
                "keyword": "Click",
                "original_selector": "id=submit",
                "healed_selector": "[data-testid=submit]",
                "confidence": 0.95,
                "source": "sidecar",
                "command_id": "abc123def456",
            }],
            test_outcomes={"T1": "PASS"},
        )
        run = _mk_run(
            db_session, repo, admin_user, out, target_path="tests/rec.robot",
        )
        resp = client.post(APPLY.format(run.id, 0), headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["applied"] is True
        # Line was rewritten WITH the rbs comment preserved.
        after = robot_path.read_text(encoding="utf-8")
        assert "[data-testid=submit]" in after
        assert "# rbs:abc123def456" in after
        # Original selector replaced.
        assert "id=submit    # rbs" not in after

    def test_healed_selector_starting_with_hash_is_escaped(
        self, client, db_session, admin_user, tmp_path
    ):
        """RECORDER-RF-ESCAPE — if the heal swaps to a CSS-ID
        candidate like `#login-form`, the rewriter must add the
        `\\` escape so RF doesn't treat the new line as a comment."""
        robot_path = tmp_path / "tests" / "rec.robot"
        robot_path.parent.mkdir(parents=True)
        robot_path.write_text(
            "*** Test Cases ***\n"
            "T1\n"
            "    Click    text=Submit    # rbs:idz1\n",
            encoding="utf-8",
        )
        repo = Repository(
            name="rbs-esc", git_url="https://github.com/x/y.git",
            default_branch="main", local_path=str(tmp_path),
            created_by=admin_user.id,
        )
        db_session.add(repo)
        db_session.flush()
        db_session.refresh(repo)

        out = tmp_path / "out"
        _write_audit_and_output(
            out,
            records=[{
                "timestamp": "x",
                "test_name": "T1",
                "keyword": "Click",
                "original_selector": "text=Submit",
                "healed_selector": "#login-form",  # raw CSS-ID — must get escaped
                "confidence": 0.95,
                "source": "sidecar",
            }],
            test_outcomes={"T1": "PASS"},
        )
        run = _mk_run(
            db_session, repo, admin_user, out, target_path="tests/rec.robot",
        )
        resp = client.post(APPLY.format(run.id, 0), headers=auth_header(admin_user))
        assert resp.status_code == 200
        after = robot_path.read_text(encoding="utf-8")
        # Backslash-escape applied + rbs comment preserved.
        assert "\\#login-form" in after
        assert "# rbs:idz1" in after
