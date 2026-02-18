"""Authentication dependencies for FastAPI dependency injection."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

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


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from the JWT token."""
    try:
        payload = decode_token(credentials.credentials)
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
    user = await get_user_by_id(db, user_id)

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


def require_role(min_role: Role):
    """Dependency factory that requires a minimum role level."""

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_level = ROLE_HIERARCHY.get(Role(current_user.role), -1)
        required_level = ROLE_HIERARCHY.get(min_role, 999)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ERR_INSUFFICIENT_PERMISSIONS,
            )
        return current_user

    return role_checker
