"""Stories 3-7..3-11: smoke tests proving effective-role migration works end-to-end.

For each migrated endpoint, assert that a VIEWER-global user who is an
editor via Team on the repo is permitted — proving the elevation flows
through `require_effective_role` (or its run/report variants).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.service import hash_password
from src.execution.models import ExecutionRun, RunStatus
from src.repos.models import Repository
from src.teams.models import Team, TeamMember
from tests.conftest import auth_header


def _mk_user(db: Session, *, role: str, email: str) -> User:
    u = User(
        email=email,
        username=email.split("@")[0],
        hashed_password=hash_password("pw"),
        role=role,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _setup_viewer_with_team_editor(
    db: Session, email: str, owner: User
) -> tuple[User, Repository]:
    """Create a viewer user who is editor on a team-assigned repo."""
    viewer = _mk_user(db, role="viewer", email=email)
    team = Team(name=f"Team-{email}")
    db.add(team)
    db.commit()
    db.refresh(team)
    tm = TeamMember(team_id=team.id, user_id=viewer.id, role="editor", source="manual")
    db.add(tm)
    db.commit()

    repo = Repository(
        name=f"er-{email}",
        git_url="https://github.com/x/y.git",
        default_branch="main",
        local_path=f"/tmp/er-{email}",
        created_by=owner.id,
        team_id=team.id,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return viewer, repo


class TestReposEndpointElevation:
    def test_team_editor_can_patch_repo(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        viewer, repo = _setup_viewer_with_team_editor(
            db_session, "ep-repo-patch@t.com", admin_user
        )
        resp = client.patch(
            f"/api/v1/repos/{repo.id}",
            json={"default_branch": "develop"},
            headers=auth_header(viewer),
        )
        assert resp.status_code == 200

    def test_team_editor_can_add_project_member(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        viewer, repo = _setup_viewer_with_team_editor(
            db_session, "ep-member@t.com", admin_user
        )
        # Add a second user who will become the member.
        newbie = _mk_user(db_session, role="viewer", email="newbie@t.com")
        resp = client.post(
            f"/api/v1/repos/{repo.id}/members",
            json={"user_id": newbie.id, "role": "viewer"},
            headers=auth_header(viewer),
        )
        assert resp.status_code == 201


class TestRunsEndpointElevation:
    def test_team_runner_can_cancel_run(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        viewer, repo = _setup_viewer_with_team_editor(
            db_session, "ep-run-cancel@t.com", admin_user
        )
        # Create a pending run on that repo.
        run = ExecutionRun(
            repository_id=repo.id,
            triggered_by=admin_user.id,
            status=RunStatus.PENDING,
            run_type="single",
            runner_type="subprocess",
            branch="main",
            target_path="tests/",
        )
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)

        resp = client.post(
            f"/api/v1/runs/{run.id}/cancel",
            headers=auth_header(viewer),
        )
        # 200 if cancellable, 400 if already finished — either way,
        # NOT 403 (the gate opened).
        assert resp.status_code != 403
        assert resp.status_code != 401

    def test_non_member_gets_403(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        outsider = _mk_user(db_session, role="viewer", email="ep-outsider@t.com")
        _viewer, repo = _setup_viewer_with_team_editor(
            db_session, "ep-run-403@t.com", admin_user
        )
        run = ExecutionRun(
            repository_id=repo.id,
            triggered_by=admin_user.id,
            status=RunStatus.PENDING,
            run_type="single",
            runner_type="subprocess",
            branch="main",
            target_path="tests/",
        )
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)

        resp = client.post(
            f"/api/v1/runs/{run.id}/cancel",
            headers=auth_header(outsider),
        )
        assert resp.status_code == 403


class TestPreRegression:
    """Make sure non-Phase-4 behavior (repos with team_id=NULL + global admin)
    still flows through unchanged — the migration must be additive."""

    def test_admin_still_can_patch_repo_without_team(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        repo = Repository(
            name="pre-reg-repo",
            git_url="https://github.com/x/y.git",
            default_branch="main",
            local_path="/tmp/pre-reg",
            created_by=admin_user.id,
            team_id=None,
        )
        db_session.add(repo)
        db_session.commit()
        db_session.refresh(repo)

        resp = client.patch(
            f"/api/v1/repos/{repo.id}",
            json={"default_branch": "develop"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
