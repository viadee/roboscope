"""Authentication dependencies for FastAPI dependency injection."""

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.auth.constants import (
    ERR_INACTIVE_USER,
    ERR_INSUFFICIENT_PERMISSIONS,
    ERR_TOKEN_INVALID,
    ROLE_HIERARCHY,
    Role,
)
from src.auth.models import User
from src.auth.service import decode_token, get_user_by_id
from src.database import get_db

security = HTTPBearer()

# Prefix for API tokens (e.g., rbs_abc123...)
_API_TOKEN_PREFIX = "rbs_"


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the current user from JWT or API token.

    Supports two auth flows:
    - JWT access token (default): Bearer <jwt>
    - API token: Bearer rbs_<hex> — long-lived token for CI/CD
    """
    token_str = credentials.credentials

    # API token flow: token starts with rbs_ prefix
    if token_str.startswith(_API_TOKEN_PREFIX):
        return _authenticate_api_token(token_str, db)

    # JWT flow (default)
    try:
        payload = decode_token(token_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERR_TOKEN_INVALID,
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERR_TOKEN_INVALID,
        )

    user_id = int(payload["sub"])
    user = get_user_by_id(db, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERR_TOKEN_INVALID,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERR_INACTIVE_USER,
        )

    return user


def _authenticate_api_token(token_str: str, db: Session) -> User:
    """Authenticate a request using an API token (rbs_... prefix)."""
    from src.webhooks.service import get_token_by_hash, verify_token, update_token_last_used

    token_hash = verify_token(token_str)
    api_token = get_token_by_hash(db, token_hash)

    if api_token is None or not api_token.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API token",
        )

    # Check expiry
    if api_token.expires_at and api_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API token has expired",
        )

    # Look up the token owner
    user = get_user_by_id(db, api_token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token owner account is inactive or deleted",
        )

    # Update last-used timestamp
    update_token_last_used(db, api_token)

    # Override user role with token's scoped role (may be more restrictive)
    # We create a transient copy with the token's role for this request
    token_role_level = ROLE_HIERARCHY.get(Role(api_token.role), 0)
    user_role_level = ROLE_HIERARCHY.get(Role(user.role), 0)
    effective_role = api_token.role if token_role_level <= user_role_level else user.role

    # Store effective role on request-scoped user object
    # (We mutate in-place since Session won't commit this change — expire_on_commit=False)
    user.role = effective_role
    # Story 3-15: mark the request as API-token-authenticated so
    # require_effective_role skips team/project grants for CI/CD tokens.
    # Team semantics are per-user UI concept; tokens must stay capped at
    # the token's scoped role to avoid accidental CI elevation.
    user._auth_via_api_token = True  # type: ignore[attr-defined]
    return user


def require_role(min_role: Role):
    """Dependency factory that requires a minimum role level."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_level = ROLE_HIERARCHY.get(Role(current_user.role), -1)
        required_level = ROLE_HIERARCHY.get(min_role, 999)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ERR_INSUFFICIENT_PERMISSIONS,
            )
        return current_user

    return role_checker


def require_effective_role(min_role: Role):
    """Dependency factory that gates on `effective_role(user, repo) >= min_role`.

    Reads the `repo_id` path parameter from the route (int or int-coercible),
    resolves the repository, computes the additive effective role (global +
    team + project), and returns the user if it meets or exceeds the threshold.

    - 401 is handled upstream by `get_current_user` (no token / bad token).
    - 404 if `repo_id` is missing, non-int, or no such repository.
    - 403 if the effective role is below `min_role`.
    """

    def check(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        from src.auth.permissions import effective_role
        from src.repos.models import Repository

        raw_repo_id = request.path_params.get("repo_id")
        try:
            repo_id = int(raw_repo_id)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )

        repo = db.get(Repository, repo_id)
        if repo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )

        # Story 3-15: API tokens stay capped at their scoped role — no
        # team/project elevation. This preserves the existing rbs_… token
        # contract for CI/CD pipelines.
        if getattr(current_user, "_auth_via_api_token", False):
            user_level = ROLE_HIERARCHY.get(Role(current_user.role), -1)
            if user_level < ROLE_HIERARCHY.get(min_role, 999):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=ERR_INSUFFICIENT_PERMISSIONS,
                )
            return current_user

        er = effective_role(db, current_user, repo)
        if ROLE_HIERARCHY.get(er, -1) < ROLE_HIERARCHY.get(min_role, 999):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ERR_INSUFFICIENT_PERMISSIONS,
            )
        return current_user

    return check


def require_effective_role_for_run(min_role: Role):
    """Dependency factory gating on the user's effective role on the repo
    that a given run belongs to.

    Reads `run_id` from the path, resolves `ExecutionRun.repository_id`,
    then reuses the same effective-role computation as
    `require_effective_role`. Story 3-8 migration entry point.
    """

    def check(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        from src.auth.permissions import effective_role
        from src.execution.models import ExecutionRun
        from src.repos.models import Repository

        raw_run_id = request.path_params.get("run_id")
        try:
            run_id = int(raw_run_id)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found",
            )

        run = db.get(ExecutionRun, run_id)
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found",
            )

        repo = db.get(Repository, run.repository_id)
        if repo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )

        if getattr(current_user, "_auth_via_api_token", False):
            user_level = ROLE_HIERARCHY.get(Role(current_user.role), -1)
            if user_level < ROLE_HIERARCHY.get(min_role, 999):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=ERR_INSUFFICIENT_PERMISSIONS,
                )
            return current_user

        er = effective_role(db, current_user, repo)
        if ROLE_HIERARCHY.get(er, -1) < ROLE_HIERARCHY.get(min_role, 999):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ERR_INSUFFICIENT_PERMISSIONS,
            )
        return current_user

    return check


def require_effective_role_for_report(min_role: Role):
    """Dependency factory gating on the user's effective role on the repo
    that a given report's run belongs to.

    Reads `report_id` from the path, joins report → run → repo, then
    reuses the effective-role computation. Story 3-9 migration entry.
    """

    def check(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        from src.auth.permissions import effective_role
        from src.execution.models import ExecutionRun
        from src.reports.models import Report
        from src.repos.models import Repository

        raw_report_id = request.path_params.get("report_id")
        try:
            report_id = int(raw_report_id)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found",
            )

        report = db.get(Report, report_id)
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found",
            )

        if report.execution_run_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report is not linked to a run",
            )

        run = db.get(ExecutionRun, report.execution_run_id)
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found",
            )

        repo = db.get(Repository, run.repository_id)
        if repo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )

        if getattr(current_user, "_auth_via_api_token", False):
            user_level = ROLE_HIERARCHY.get(Role(current_user.role), -1)
            if user_level < ROLE_HIERARCHY.get(min_role, 999):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=ERR_INSUFFICIENT_PERMISSIONS,
                )
            return current_user

        er = effective_role(db, current_user, repo)
        if ROLE_HIERARCHY.get(er, -1) < ROLE_HIERARCHY.get(min_role, 999):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ERR_INSUFFICIENT_PERMISSIONS,
            )
        return current_user

    return check
