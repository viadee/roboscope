"""Story 3-15: API tokens MUST stay capped at their scoped role.

Team-membership elevation from Epic 3 must NOT apply to rbs_… tokens.
Locks in the security invariant that CI/CD tokens cannot be accidentally
elevated via a team grant on the owner's account.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.service import hash_password
from src.repos.models import Repository
from src.teams.models import Team, TeamMember
from src.webhooks.service import create_api_token


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


def _mk_team_with_member(
    db: Session, user: User, role: str = "editor"
) -> Team:
    team = Team(name=f"T-{user.id}")
    db.add(team)
    db.commit()
    db.refresh(team)
    tm = TeamMember(team_id=team.id, user_id=user.id, role=role, source="manual")
    db.add(tm)
    db.commit()
    return team


def _mk_repo(db: Session, owner: User, team: Team | None = None) -> Repository:
    r = Repository(
        name=f"tokcap-{owner.id}-{team.id if team else 'null'}",
        git_url="https://github.com/x/y.git",
        default_branch="main",
        local_path=f"/tmp/tokcap-{owner.id}",
        created_by=owner.id,
        team_id=team.id if team else None,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


class TestApiTokenRoleCapRegression:
    def test_viewer_token_on_team_editor_repo_stays_viewer(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        """VIEWER-global + team-EDITOR + token=VIEWER → still capped at VIEWER.

        Pre-Phase-4 expectation: the token grants exactly what it says.
        Phase-4 Teams must not elevate the token.
        """
        alice = _mk_user(db_session, role="viewer", email="alice-token@test.com")
        team = _mk_team_with_member(db_session, alice, role="editor")
        repo = _mk_repo(db_session, admin_user, team=team)

        _token_row, raw = create_api_token(
            db_session, name="alice-ci", role="viewer", user_id=alice.id
        )
        db_session.commit()

        headers = {"Authorization": f"Bearer {raw}"}
        resp = client.patch(
            f"/api/v1/repos/{repo.id}",
            json={"default_branch": "develop"},
            headers=headers,
        )
        assert resp.status_code == 403

    def test_viewer_token_is_blocked_on_team_runner_run_cancel(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        """Same invariant for the run helper: team-grant must not elevate
        a VIEWER token to cancel a run."""
        from src.execution.models import ExecutionRun, RunStatus

        alice = _mk_user(db_session, role="viewer", email="alice-run@test.com")
        team = _mk_team_with_member(db_session, alice, role="runner")
        repo = _mk_repo(db_session, admin_user, team=team)
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

        _token, raw = create_api_token(
            db_session, name="alice-ci-run", role="viewer", user_id=alice.id
        )
        db_session.commit()

        headers = {"Authorization": f"Bearer {raw}"}
        resp = client.post(
            f"/api/v1/runs/{run.id}/cancel", headers=headers
        )
        assert resp.status_code == 403

    def test_runner_token_on_editor_team_grant_does_not_elevate_to_editor(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        """Runner-global + team-EDITOR + token=RUNNER → token is still RUNNER,
        not EDITOR. The EDITOR-gated PATCH /repos/{id} must 403."""
        alice = _mk_user(db_session, role="runner", email="alice-runner@test.com")
        team = _mk_team_with_member(db_session, alice, role="editor")
        repo = _mk_repo(db_session, admin_user, team=team)

        _token, raw = create_api_token(
            db_session, name="alice-ci-runner", role="runner", user_id=alice.id
        )
        db_session.commit()

        headers = {"Authorization": f"Bearer {raw}"}
        resp = client.patch(
            f"/api/v1/repos/{repo.id}",
            json={"default_branch": "develop"},
            headers=headers,
        )
        assert resp.status_code == 403

    def test_editor_token_with_editor_user_can_patch(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        """Positive control: the token's own scoped role IS honored.
        No team membership involved, no elevation required.
        """
        bob = _mk_user(db_session, role="editor", email="bob@test.com")
        repo = _mk_repo(db_session, admin_user)

        # Grant bob project-membership so the vanilla require_effective_role
        # path would also grant EDITOR — proving that WITHOUT a team grant,
        # the token's own EDITOR role is enough.
        _token, raw = create_api_token(
            db_session, name="bob-ci", role="editor", user_id=bob.id
        )
        db_session.commit()

        # Bob is the repo creator — but team_id is None, so effective_role is
        # just bob.role = editor. Token.role = editor. Patch allowed.
        from src.repos.models import ProjectMember

        pm = ProjectMember(user_id=bob.id, repository_id=repo.id, role="editor")
        db_session.add(pm)
        db_session.commit()

        headers = {"Authorization": f"Bearer {raw}"}
        resp = client.patch(
            f"/api/v1/repos/{repo.id}",
            json={"default_branch": "develop"},
            headers=headers,
        )
        assert resp.status_code == 200

    def test_admin_token_on_viewer_owner_is_capped(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ) -> None:
        """Token.role = admin but user.role = viewer → cap to viewer.

        This is the pre-Phase-4 cap invariant (independent of teams),
        kept as a regression guard.
        """
        alice = _mk_user(db_session, role="viewer", email="alice-caponly@test.com")
        repo = _mk_repo(db_session, admin_user)

        # Owner is global VIEWER but token was minted as admin — the cap
        # in _authenticate_api_token downgrades to viewer.
        _token, raw = create_api_token(
            db_session, name="alice-admin-token", role="admin", user_id=alice.id
        )
        db_session.commit()

        headers = {"Authorization": f"Bearer {raw}"}
        resp = client.patch(
            f"/api/v1/repos/{repo.id}",
            json={"default_branch": "develop"},
            headers=headers,
        )
        assert resp.status_code == 403
