"""Shared test fixtures for the mateoX backend."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.auth.constants import Role
from src.auth.service import create_access_token, hash_password
from src.database import Base, get_db
from src.main import app

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    """Create a test database engine (in-memory SQLite).

    check_same_thread=False is required because FastAPI runs sync route
    handlers in a thread pool, while the test session is created in the
    main thread.
    """
    engine = create_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(engine):
    """Provide a transactional database session that rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session: Session):
    """Provide a test client with overridden DB dependency."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session: Session):
    """Create an admin user and return it."""
    from src.auth.models import User

    user = User(
        email="admin@test.com",
        username="admin",
        hashed_password=hash_password("admin123"),
        role=Role.ADMIN,
    )
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user


@pytest.fixture
def runner_user(db_session: Session):
    """Create a runner user and return it."""
    from src.auth.models import User

    user = User(
        email="runner@test.com",
        username="runner",
        hashed_password=hash_password("runner123"),
        role=Role.RUNNER,
    )
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user


@pytest.fixture
def viewer_user(db_session: Session):
    """Create a viewer user and return it."""
    from src.auth.models import User

    user = User(
        email="viewer@test.com",
        username="viewer",
        hashed_password=hash_password("viewer123"),
        role=Role.VIEWER,
    )
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user


def auth_header(user) -> dict:
    """Create an authorization header for a user."""
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}
