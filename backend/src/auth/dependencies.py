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
            status_code=status.HTTP_403_FORBIDDEN,
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
