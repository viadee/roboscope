"""Story 3-6: table-driven tests for `effective_role()`."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.models import User
from src.auth.permissions import (
    effective_role,
    project_member_role,
    team_role_for_repo,
)
from src.auth.service import hash_password
from src.repos.models import ProjectMember, Repository
from src.teams.models import Team, TeamMember


# ---------- Fixtures --------------------------------------------------------


def _mk_user(db: Session, *, role: str = "viewer", email: str = "u@test.com") -> User:
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


def _mk_team(db: Session, name: str = "T") -> Team:
    t = Team(name=name)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _mk_repo(
    db: Session, user: User, team: Team | None = None, name: str = "r"
) -> Repository:
    r = Repository(
        name=name,
        git_url="https://github.com/x/y.git",
        default_branch="main",
        local_path=f"/tmp/{name}",
        created_by=user.id,
        team_id=team.id if team else None,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _add_team_member(
    db: Session, team: Team, user: User, role: str
) -> TeamMember:
    tm = TeamMember(team_id=team.id, user_id=user.id, role=role, source="manual")
    db.add(tm)
    db.commit()
    return tm


def _add_project_member(
    db: Session, repo: Repository, user: User, role: str
) -> ProjectMember:
    pm = ProjectMember(user_id=user.id, repository_id=repo.id, role=role)
    db.add(pm)
    db.commit()
    return pm


# ---------- Table-driven -----------------------------------------------------


@pytest.mark.parametrize(
    "global_role, team_role, project_role, expected",
    [
        # No team, no project — global wins (pre-Phase-4 regression guard).
        ("viewer", None, None, Role.VIEWER),
        ("runner", None, None, Role.RUNNER),
        ("editor", None, None, Role.EDITOR),
        ("admin", None, None, Role.ADMIN),
        # Team dominates global when higher.
        ("viewer", "editor", None, Role.EDITOR),
        ("viewer", "admin", None, Role.ADMIN),
        # Project dominates global when higher.
        ("viewer", None, "runner", Role.RUNNER),
        ("viewer", None, "editor", Role.EDITOR),
        # Global dominates when team/project are lower.
        ("admin", "viewer", "viewer", Role.ADMIN),
        ("editor", "runner", "viewer", Role.EDITOR),
        # All three contribute — MAX wins.
        ("viewer", "runner", "editor", Role.EDITOR),
        ("viewer", "editor", "runner", Role.EDITOR),
        ("runner", "editor", "viewer", Role.EDITOR),
        ("viewer", "admin", "editor", Role.ADMIN),
        # Spec example: global viewer + team editor + project runner → editor.
        ("viewer", "editor", "runner", Role.EDITOR),
    ],
)
def test_effective_role_table(
    db_session: Session,
    global_role: str,
    team_role: str | None,
    project_role: str | None,
    expected: Role,
) -> None:
    user = _mk_user(db_session, role=global_role, email=f"u-{global_role}-{team_role}-{project_role}@t.com")
    team = _mk_team(db_session, name=f"T-{global_role}-{team_role}-{project_role}")
    repo = _mk_repo(db_session, user, team=team if team_role else None, name=f"r-{global_role}-{team_role}-{project_role}")
    if team_role is not None:
        _add_team_member(db_session, team, user, team_role)
    if project_role is not None:
        _add_project_member(db_session, repo, user, project_role)

    assert effective_role(db_session, user, repo) == expected


# ---------- Individual edge cases ------------------------------------------


class TestEffectiveRoleEdgeCases:
    def test_repo_with_null_team_id_reduces_to_global_plus_project(
        self, db_session: Session
    ) -> None:
        user = _mk_user(db_session, role="viewer", email="no-team@test.com")
        repo = _mk_repo(db_session, user, team=None, name="no-team-repo")
        _add_project_member(db_session, repo, user, "editor")
        assert effective_role(db_session, user, repo) == Role.EDITOR

    def test_user_not_member_of_team_ignores_team_role(
        self, db_session: Session
    ) -> None:
        owner = _mk_user(db_session, role="admin", email="owner@test.com")
        team = _mk_team(db_session, name="Exclusive")
        # Team member: the owner.
        _add_team_member(db_session, team, owner, "admin")

        # Outsider has no membership.
        outsider = _mk_user(db_session, role="viewer", email="outsider@test.com")
        repo = _mk_repo(db_session, owner, team=team, name="team-repo")

        # outsider gets only their global role (viewer) — team role must be None.
        assert team_role_for_repo(db_session, outsider, repo) is None
        assert effective_role(db_session, outsider, repo) == Role.VIEWER

    def test_project_member_alone_takes_effect(
        self, db_session: Session
    ) -> None:
        user = _mk_user(db_session, role="viewer", email="pm-only@test.com")
        repo = _mk_repo(db_session, user, team=None, name="pm-only-repo")
        _add_project_member(db_session, repo, user, "runner")
        assert project_member_role(db_session, user, repo) == Role.RUNNER
        assert effective_role(db_session, user, repo) == Role.RUNNER

    def test_unknown_role_strings_are_ignored(
        self, db_session: Session
    ) -> None:
        user = _mk_user(db_session, role="viewer", email="bad-role@test.com")
        team = _mk_team(db_session, name="BadRoleTeam")
        repo = _mk_repo(db_session, user, team=team, name="bad-role-repo")
        # Insert a TeamMember row with a nonsense role — defense against manual DB edits.
        bad = TeamMember(
            team_id=team.id, user_id=user.id, role="sovereign", source="manual"
        )
        db_session.add(bad)
        db_session.commit()

        assert team_role_for_repo(db_session, user, repo) is None
        assert effective_role(db_session, user, repo) == Role.VIEWER
