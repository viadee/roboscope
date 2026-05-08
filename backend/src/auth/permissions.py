"""Effective-role resolution (Story 3-6).

`effective_role(db, user, repo)` is the single source of truth for
"what role does this user have on this repo?". It composes three
contributors additively:

  max(
      user.role,                          # global (User.role)
      team_role_for_repo(user, repo),     # inherited from Team membership
      project_member_role(user, repo),    # explicit per-repo grant
  )

Purely additive — no deny semantics. Missing contributors count as
VIEWER (lowest). This matches the brownfield expectation that pre-
Phase-4 behavior (global + project) is a strict subset of the new
resolution.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.constants import ROLE_HIERARCHY, Role
from src.auth.models import User
from src.repos.models import ProjectMember, Repository
from src.teams.models import TeamMember


def _to_role(raw: str | None) -> Role | None:
    """Coerce a stored role string to the `Role` enum; return None for unknowns."""
    if raw is None:
        return None
    try:
        return Role(raw)
    except ValueError:
        return None


def team_role_for_repo(
    db: Session, user: User, repo: Repository
) -> Role | None:
    """Return the user's team-level role on the repo, or None.

    A single JOIN on `team_members` scoped to the repo's team.
    """
    if repo.team_id is None:
        return None
    row = db.execute(
        select(TeamMember.role).where(
            TeamMember.team_id == repo.team_id,
            TeamMember.user_id == user.id,
        )
    ).scalar_one_or_none()
    return _to_role(row)


def project_member_role(
    db: Session, user: User, repo: Repository
) -> Role | None:
    """Return the explicit per-repo `ProjectMember.role`, or None."""
    row = db.execute(
        select(ProjectMember.role).where(
            ProjectMember.repository_id == repo.id,
            ProjectMember.user_id == user.id,
        )
    ).scalar_one_or_none()
    return _to_role(row)


def effective_role(db: Session, user: User, repo: Repository) -> Role:
    """Additive max of (global, team, project) role contributors."""
    contributors: list[Role] = []
    global_role = _to_role(user.role)
    if global_role is not None:
        contributors.append(global_role)

    team_role = team_role_for_repo(db, user, repo)
    if team_role is not None:
        contributors.append(team_role)

    project_role = project_member_role(db, user, repo)
    if project_role is not None:
        contributors.append(project_role)

    if not contributors:
        # No known role — default VIEWER preserves the "no deny" invariant.
        return Role.VIEWER

    return max(contributors, key=lambda r: ROLE_HIERARCHY[r])
