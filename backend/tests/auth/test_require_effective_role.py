"""Story 3-6: integration tests for `require_effective_role` dependency."""

from __future__ import annotations

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import require_effective_role
from src.auth.models import User
from src.auth.service import hash_password
from src.repos.models import ProjectMember, Repository
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


def _mk_repo(
    db: Session, owner: User, team: Team | None = None
) -> Repository:
    r = Repository(
        name=f"rer-{owner.id}-{team.id if team else 'null'}",
        git_url="https://github.com/x/y.git",
        default_branch="main",
        local_path=f"/tmp/rer-{owner.id}",
        created_by=owner.id,
        team_id=team.id if team else None,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


# We mount a tiny test router on the real app via pytest monkey-patching the
# main API router. Simpler: register a dedicated endpoint in the real router
# module via conftest/fixture wouldn't be clean. Instead, we use the
# already-registered endpoints (e.g., `/repos/{id}`) and assert 403 when the
# new dependency gates them. But we don't migrate existing endpoints in this
# story, so let's mount a test app in-fixture.

@pytest.fixture
def app_with_guarded_route(client: TestClient):
    """Attach a one-off endpoint that uses `require_effective_role(EDITOR)`.

    Returns a fresh TestClient that shares DB with the main one by
    monkey-patching the real app's router.
    """
    from src.main import app as real_app

    router = APIRouter()

    @router.get("/test/repos/{repo_id}/editor-gated")
    def editor_gated(
        repo_id: int,
        _current: User = Depends(require_effective_role(Role.EDITOR)),
    ) -> dict:
        return {"ok": True, "repo_id": repo_id}

    real_app.include_router(router, prefix="/api/v1")
    yield
    # Cleanup: drop the test routes from the app (by path).
    real_app.router.routes = [
        r for r in real_app.router.routes
        if getattr(r, "path", "") != "/api/v1/test/repos/{repo_id}/editor-gated"
    ]


class TestRequireEffectiveRoleDependency:
    def test_returns_200_when_effective_role_meets_threshold(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        app_with_guarded_route,
    ) -> None:
        repo = _mk_repo(db_session, admin_user)
        resp = client.get(
            f"/api/v1/test/repos/{repo.id}/editor-gated",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_returns_403_when_below_threshold(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        app_with_guarded_route,
    ) -> None:
        viewer = _mk_user(db_session, role="viewer", email="ev@test.com")
        repo = _mk_repo(db_session, admin_user)
        resp = client.get(
            f"/api/v1/test/repos/{repo.id}/editor-gated",
            headers=auth_header(viewer),
        )
        assert resp.status_code == 403

    def test_team_membership_lifts_viewer_to_editor(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        app_with_guarded_route,
    ) -> None:
        viewer = _mk_user(db_session, role="viewer", email="team-lift@test.com")
        team = Team(name="LiftTeam")
        db_session.add(team)
        db_session.commit()
        db_session.refresh(team)
        tm = TeamMember(team_id=team.id, user_id=viewer.id, role="editor", source="manual")
        db_session.add(tm)
        db_session.commit()
        repo = _mk_repo(db_session, admin_user, team=team)
        resp = client.get(
            f"/api/v1/test/repos/{repo.id}/editor-gated",
            headers=auth_header(viewer),
        )
        assert resp.status_code == 200

    def test_project_membership_lifts_viewer_to_editor(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        app_with_guarded_route,
    ) -> None:
        viewer = _mk_user(db_session, role="viewer", email="pm-lift@test.com")
        repo = _mk_repo(db_session, admin_user)
        pm = ProjectMember(user_id=viewer.id, repository_id=repo.id, role="editor")
        db_session.add(pm)
        db_session.commit()
        resp = client.get(
            f"/api/v1/test/repos/{repo.id}/editor-gated",
            headers=auth_header(viewer),
        )
        assert resp.status_code == 200

    def test_404_when_repo_missing(
        self,
        client: TestClient,
        admin_user: User,
        app_with_guarded_route,
    ) -> None:
        resp = client.get(
            "/api/v1/test/repos/99999/editor-gated",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

    def test_401_when_unauthenticated(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        app_with_guarded_route,
    ) -> None:
        repo = _mk_repo(db_session, admin_user)
        resp = client.get(f"/api/v1/test/repos/{repo.id}/editor-gated")
        assert resp.status_code == 401
