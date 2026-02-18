"""Shared test fixtures for the mateoX backend."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.auth.constants import Role
from src.auth.service import create_access_token, hash_password
from src.database import Base, get_db
from src.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create a test database engine (in-memory SQLite)."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine):
    """Provide a transactional database session that rolls back after each test."""
    async_session = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with async_session() as session:
        # Start a savepoint so we can rollback
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    """Provide an HTTPX async test client with overridden DB dependency."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession):
    """Create an admin user and return it."""
    from src.auth.models import User

    user = User(
        email="admin@test.com",
        username="admin",
        hashed_password=hash_password("admin123"),
        role=Role.ADMIN,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def runner_user(db_session: AsyncSession):
    """Create a runner user and return it."""
    from src.auth.models import User

    user = User(
        email="runner@test.com",
        username="runner",
        hashed_password=hash_password("runner123"),
        role=Role.RUNNER,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def viewer_user(db_session: AsyncSession):
    """Create a viewer user and return it."""
    from src.auth.models import User

    user = User(
        email="viewer@test.com",
        username="viewer",
        hashed_password=hash_password("viewer123"),
        role=Role.VIEWER,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


def auth_header(user) -> dict:
    """Create an authorization header for a user."""
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}
