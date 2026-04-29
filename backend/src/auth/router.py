"""Authentication API endpoints."""

import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.auth.constants import ERR_INVALID_CREDENTIALS, ERR_TOKEN_INVALID, Role

# Simple in-memory rate limiter for login endpoint.
# Tracks timestamps of failed attempts per IP. Allows MAX_ATTEMPTS in WINDOW_SECONDS.
_MAX_ATTEMPTS = 10
_WINDOW_SECONDS = 300  # 5 minutes
_login_attempts: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(request: Request) -> None:
    """Raise 429 if too many login attempts from this IP."""
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    # Prune old entries
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _WINDOW_SECONDS]
    if len(_login_attempts[ip]) >= _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )


def _record_failed_attempt(request: Request) -> None:
    """Record a failed login attempt for rate limiting."""
    ip = request.client.host if request.client else "unknown"
    _login_attempts[ip].append(time.monotonic())
from src.auth.dependencies import get_current_user, require_role
from src.auth.models import User
from src.auth.schemas import (
    ChangePasswordRequest,
    FirstLoginCompleteRequest,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    TeamSummary,
    TokenResponse,
    UserResponse,
    UserUpdate,
)
from sqlalchemy import select
from src.auth.service import (
    authenticate_user,
    create_token_response,
    create_user,
    decode_token,
    get_user_by_email,
    get_user_by_id,
    get_users,
    hash_password,
    update_user,
)
from src.database import get_db

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate user and return JWT tokens."""
    _check_rate_limit(request)
    user = authenticate_user(db, data.email, data.password)
    if user is None:
        _record_failed_attempt(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERR_INVALID_CREDENTIALS,
        )
    return create_token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    data: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Refresh access token using refresh token."""
    try:
        payload = decode_token(data.refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERR_TOKEN_INVALID,
        ) from None

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERR_TOKEN_INVALID,
        )

    user = get_user_by_id(db, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERR_TOKEN_INVALID,
        )

    return create_token_response(user)


@router.get("/me", response_model=MeResponse)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current authenticated user with Phase 4 session extensions.

    Story 4-1: returns the user's Teams, default team, effective role per
    repo (repos where user has team or project grant), and the
    first_login_complete flag — additive to pre-Phase-4 UserResponse.
    """
    from src.auth.permissions import effective_role
    from src.repos.models import ProjectMember, Repository
    from src.teams.models import Team, TeamMember

    team_ids: list[int] = [
        row[0]
        for row in db.execute(
            select(TeamMember.team_id).where(TeamMember.user_id == current_user.id)
        ).all()
    ]
    teams: list[Team] = (
        list(db.execute(select(Team).where(Team.id.in_(team_ids))).scalars().all())
        if team_ids
        else []
    )
    teams.sort(key=lambda t: t.id)

    repo_candidates: set[int] = set()
    if team_ids:
        for rid in db.execute(
            select(Repository.id).where(Repository.team_id.in_(team_ids))
        ).scalars().all():
            repo_candidates.add(rid)
    for rid in db.execute(
        select(ProjectMember.repository_id).where(
            ProjectMember.user_id == current_user.id
        )
    ).scalars().all():
        repo_candidates.add(rid)

    roles_by_repo: dict[int, Role] = {}
    for rid in repo_candidates:
        repo = db.get(Repository, rid)
        if repo is None:
            continue
        roles_by_repo[rid] = effective_role(db, current_user, repo)

    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        role=Role(current_user.role),
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
        teams=[TeamSummary(id=t.id, name=t.name) for t in teams],
        default_team_id=teams[0].id if teams else None,
        effective_roles_by_repo=roles_by_repo,
        first_login_complete=bool(current_user.first_login_complete),
        password_change_required=bool(current_user.password_change_required),
    )


@router.patch("/me/first-login-complete", response_model=MeResponse)
def patch_first_login_complete(
    data: FirstLoginCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark the first-login tutorial as dismissed (Story 4-1)."""
    current_user.first_login_complete = data.value
    db.commit()
    db.refresh(current_user)
    return get_me(current_user=current_user, db=db)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password_endpoint(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Story SECURITY-1: rotate the current user's password.

    Used by the forced password-change modal when
    `password_change_required=True` on the user row, but also a regular
    self-service endpoint for any authenticated user. Always clears
    the flag on success.
    """
    from src.auth.service import change_password

    try:
        change_password(
            db, current_user, data.current_password, data.new_password,
        )
    except ValueError as e:
        reason = str(e)
        if reason == "wrong_current":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect",
            ) from e
        if reason == "too_short":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="New password must be at least 8 characters",
            ) from e
        if reason == "same_as_current":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="New password must differ from the current one",
            ) from e
        raise
    db.commit()


# --- User Management (Admin only) ---


@router.get("/users", response_model=list[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """List all users (admin only)."""
    return get_users(db, skip=skip, limit=limit)


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    data: RegisterRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Create a new user (admin only)."""
    existing = get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    user = create_user(db, data)
    return user


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Get user details (admin only)."""
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _cascade_revoke_on_deactivate(
    db: Session, target: User, actor_id: int, ip: str | None
) -> int:
    """Story 5-3: revoke every active ApiToken owned by `target` and emit
    `user.deactivated` audit event with the cascade count. Returns the
    number of tokens revoked.
    """
    from src.audit.event_types import AuditEventType
    from src.audit.service import log_event
    from src.webhooks.models import ApiToken

    tokens = (
        db.query(ApiToken)
        .filter(ApiToken.user_id == target.id, ApiToken.is_active.is_(True))
        .all()
    )
    for t in tokens:
        t.is_active = False
    db.flush()

    from src.auth.pii_hash import hash_email
    log_event(
        db,
        AuditEventType.USER_DEACTIVATED,
        user_id=actor_id,
        resource_id=target.id,
        detail={
            "email_hash": hash_email(target.email),
            "revoked_api_tokens": len(tokens),
            "revoked_token_ids": [t.id for t in tokens],
        },
        ip_address=ip,
    )
    return len(tokens)


@router.patch("/users/{user_id}", response_model=UserResponse)
def patch_user(
    user_id: int,
    data: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Update user fields (admin only).

    Story 5-3: flipping is_active from True to False cascade-revokes all
    of the user's ApiTokens and emits `user.deactivated` with the
    revocation count.
    """
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = data.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))

    will_deactivate = (
        "is_active" in update_data
        and update_data["is_active"] is False
        and user.is_active is True
    )

    updated = update_user(db, user, **update_data)

    if will_deactivate:
        ip = request.client.host if request.client else None
        _cascade_revoke_on_deactivate(db, updated, current_user.id, ip)
        db.commit()

    return updated


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Deactivate a user (admin only).

    Soft-delete that also cascade-revokes the user's ApiTokens (Story 5-3).
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself",
        )
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    was_active = user.is_active
    update_user(db, user, is_active=False)

    if was_active:
        ip = request.client.host if request.client else None
        _cascade_revoke_on_deactivate(db, user, current_user.id, ip)
        db.commit()
