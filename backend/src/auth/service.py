"""Authentication service: user creation, verification, JWT handling."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.constants import ERR_TOKEN_EXPIRED, ERR_TOKEN_INVALID, Role
from src.auth.models import User
from src.auth.schemas import RegisterRequest, TokenResponse, UserResponse
from src.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


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
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """Create a JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        raise ValueError(ERR_TOKEN_INVALID) from e


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Find a user by email."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Find a user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[User]:
    """List all users with pagination."""
    result = await db.execute(select(User).offset(skip).limit(limit))
    return list(result.scalars().all())


async def create_user(db: AsyncSession, data: RegisterRequest) -> User:
    """Create a new user."""
    user = User(
        email=data.email,
        username=data.username,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """Authenticate a user by email and password."""
    user = await get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()
    return user


async def update_user(db: AsyncSession, user: User, **kwargs) -> User:
    """Update user fields."""
    for key, value in kwargs.items():
        if value is not None and hasattr(user, key):
            setattr(user, key, value)
    await db.flush()
    await db.refresh(user)
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


async def ensure_admin_exists(db: AsyncSession) -> None:
    """Create a default admin user if no users exist."""
    result = await db.execute(select(User).limit(1))
    if result.scalar_one_or_none() is None:
        admin = User(
            email="admin@mateox.local",
            username="admin",
            hashed_password=hash_password("admin123"),
            role=Role.ADMIN,
        )
        db.add(admin)
        await db.flush()
