"""Authentication service: user creation, verification, JWT handling."""

import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt as pyjwt
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.constants import ERR_TOKEN_EXPIRED, ERR_TOKEN_INVALID, Role
from src.auth.models import User
from src.auth.schemas import RegisterRequest, TokenResponse, UserResponse
from src.config import settings

logger = logging.getLogger("roboscope.auth")


def hash_password(password: str) -> str:
    """Hash a plaintext password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: int, role: str) -> str:
    """Create a JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """Create a JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except InvalidTokenError as e:
        raise ValueError(ERR_TOKEN_INVALID) from e


def get_user_by_email(db: Session, email: str) -> User | None:
    """Find a user by email."""
    result = db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Find a user by ID."""
    result = db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    """List all users with pagination."""
    result = db.execute(select(User).offset(skip).limit(limit))
    return list(result.scalars().all())


def create_user(db: Session, data: RegisterRequest) -> User:
    """Create a new user."""
    user = User(
        email=data.email,
        username=data.username,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Authenticate a user by email and password."""
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    db.flush()
    # Story SECURITY-1 — surface in the server log every time a
    # password-change-required user authenticates so the operator can
    # see the unfinished rotation in their log stream.
    if user.password_change_required:
        logger.warning(
            "Login by user=%s with password_change_required=True — "
            "operator must complete the rotation.",
            user.email,
        )
    return user


def change_password(
    db: Session, user: User, current_password: str, new_password: str,
) -> None:
    """Verify current password, set new one, clear the
    `password_change_required` flag. Story SECURITY-1.

    Raises:
      `ValueError("wrong_current")` — current password mismatch (caller maps to 401).
      `ValueError("too_short")`     — new password < 8 chars (422).
      `ValueError("same_as_current")` — new password equals current (422).
    """
    if not verify_password(current_password, user.hashed_password):
        raise ValueError("wrong_current")
    if len(new_password) < 8:
        raise ValueError("too_short")
    if current_password == new_password:
        raise ValueError("same_as_current")
    user.hashed_password = hash_password(new_password)
    user.password_change_required = False
    db.flush()


def update_user(db: Session, user: User, **kwargs) -> User:
    """Update user fields."""
    for key, value in kwargs.items():
        if value is not None and hasattr(user, key):
            setattr(user, key, value)
    db.flush()
    db.refresh(user)
    return user


def create_token_response(user: User) -> TokenResponse:
    """Create a full token response for a user."""
    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


DEFAULT_ADMIN_EMAIL = "admin@roboscope.local"
DEFAULT_ADMIN_PASSWORD = "admin123"


def ensure_admin_exists(db: Session) -> None:
    """Create a default admin user if no users exist.

    Story SECURITY-1: the seed admin starts with
    `password_change_required=True` so the frontend forces a rotation
    before any other action.

    Pessimistic upgrade for existing deployments: if an admin row
    already exists *and* still verifies against the well-known default
    password, flip the flag on so legacy installations also pick up
    the forced-rotation modal on next login.
    """
    result = db.execute(select(User).limit(1))
    first_user = result.scalar_one_or_none()
    if first_user is None:
        admin = User(
            email=DEFAULT_ADMIN_EMAIL,
            username="admin",
            hashed_password=hash_password(DEFAULT_ADMIN_PASSWORD),
            role=Role.ADMIN,
            password_change_required=True,
        )
        db.add(admin)
        db.flush()
        return

    # Legacy upgrade: any user (most often the original seed admin)
    # whose password still matches the well-known default gets the
    # flag flipped on. Constant-time bcrypt verify, runs once per
    # startup at most.
    candidates = db.execute(
        select(User).where(User.password_change_required.is_(False))
    ).scalars().all()
    flipped = 0
    for user in candidates:
        if user.hashed_password and verify_password(
            DEFAULT_ADMIN_PASSWORD, user.hashed_password,
        ):
            user.password_change_required = True
            flipped += 1
    if flipped:
        db.flush()
