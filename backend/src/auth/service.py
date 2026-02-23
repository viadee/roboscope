"""Authentication service: user creation, verification, JWT handling."""

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
    return user


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


def ensure_admin_exists(db: Session) -> None:
    """Create a default admin user if no users exist."""
    result = db.execute(select(User).limit(1))
    if result.scalar_one_or_none() is None:
        admin = User(
            email="admin@roboscope.local",
            username="admin",
            hashed_password=hash_password("admin123"),
            role=Role.ADMIN,
        )
        db.add(admin)
        db.flush()
