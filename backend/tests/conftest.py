"""Shared test fixtures for the RoboScope backend."""

import os
import tempfile

# Must precede `src.config` import: Settings reads the environment once.
# SECRET_KEY: the app lifespan refuses to boot without one (CI sets it,
# local runs forgot — 800+ setup errors). DATABASE_URL: the lifespan runs
# create_tables()+seeds against the app's own engine; a per-xdist-worker
# file stops workers racing on ./roboscope.db ("table users already exists").
os.environ.setdefault("SECRET_KEY", "pytest-secret-key")
# The xdist controller imports this conftest too (initial conftest for
# `testpaths`) and workers inherit its environ, so a marker tells a worker
# that DATABASE_URL came from here and must be re-derived per worker.
_worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
if "DATABASE_URL" not in os.environ or os.environ.get("_ROBOSCOPE_PYTEST_DB"):
    _app_db = f"{tempfile.gettempdir()}/roboscope-pytest-{_worker}.db"
    if os.path.exists(_app_db):
        os.remove(_app_db)
    os.environ["_ROBOSCOPE_PYTEST_DB"] = "1"
    os.environ["DATABASE_URL"] = f"sqlite:///{_app_db}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from src.auth.constants import Role  # noqa: E402
from src.auth.service import create_access_token, hash_password  # noqa: E402
from src.database import Base, get_db  # noqa: E402
from src.main import app  # noqa: E402

TEST_DATABASE_URL = "sqlite:///:memory:"

# Test tiers (see docs/TESTING.md). Derived from what a test touches, so
# nobody has to remember a decorator:
#   unit — no DB, no app, no real subprocess (fast, mutation-tested)
#   db   — uses db_session / client (FastAPI TestClient + in-memory SQLite)
#   slow / integration — explicit marks: real subprocess / venv / browser
_DB_FIXTURES = {"db_session", "client", "engine", "admin_user", "runner_user", "viewer_user"}


def pytest_collection_modifyitems(items):
    for item in items:
        if item.get_closest_marker("slow") or item.get_closest_marker("integration"):
            continue
        fixtures = set(getattr(item, "fixturenames", ()))
        item.add_marker("db" if fixtures & _DB_FIXTURES else "unit")


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
    """Provide a transactional database session that rolls back after each test.

    Uses the SQLAlchemy SAVEPOINT pattern: the outer connection-level
    transaction wraps the whole test, and a nested SAVEPOINT is re-issued
    after every session.commit() so commit-heavy handlers (SSO callback,
    rate-limit counters) don't leak partial state between tests.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def end_savepoint(session, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    if transaction.is_active:
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


@pytest.fixture(autouse=True)
def _reset_process_level_caches():
    """Clear in-process caches that would otherwise leak between tests.

    - SSO 429-audit dedup dict (sso_router module-level state).
    - slowapi rate-limit counters: every TestClient request comes from the
      same "testclient" address, so per-endpoint limits (e.g. 20/minute on
      recording create) accumulate ACROSS tests. Invisible while the suite
      was slow; a fast suite trips them with order-dependent 429s.

    Extend this fixture if more per-process caches are added.
    """
    try:
        from src.auth.sso_router import _clear_audit_dedup_state
        _clear_audit_dedup_state()
    except Exception:
        pass
    try:
        from src.rate_limit import limiter
        limiter.reset()
    except Exception:
        pass
    yield
