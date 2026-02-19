"""Database engine, session factory, and base model.

Uses synchronous SQLAlchemy to avoid the greenlet C-extension dependency,
which causes DLL-load issues on Windows machines without Visual C++ Runtime.
FastAPI runs sync route handlers in a thread pool automatically.
"""

import logging
from collections.abc import Generator
from datetime import datetime

from sqlalchemy import MetaData, create_engine, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

logger = logging.getLogger("roboscope.database")

from src.config import settings

# Naming convention for consistent constraint names across SQLite & PostgreSQL
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Engine configuration
engine_kwargs: dict = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}

if settings.is_sqlite:
    # FastAPI runs sync handlers in a thread pool; allow cross-thread SQLite access.
    engine_kwargs["connect_args"] = {"check_same_thread": False}

if settings.is_postgres:
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
    })

engine = create_engine(settings.sync_database_url, **engine_kwargs)

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base model with naming conventions."""

    metadata = MetaData(naming_convention=convention)


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session per request.

    FastAPI automatically runs sync dependencies in a thread pool.
    """
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def create_tables() -> None:
    """Create all tables (for development/testing)."""
    with engine.begin() as conn:
        Base.metadata.create_all(conn)
    _run_migrations()


def _run_migrations() -> None:
    """Run lightweight schema migrations for new columns on existing tables."""
    with engine.begin() as conn:
        if settings.is_sqlite:
            _migrate_sqlite(conn)
        else:
            _migrate_postgres(conn)


def _migrate_sqlite(conn) -> None:
    """SQLite migrations — add repo_type column and make git_url nullable."""
    result = conn.execute(text("PRAGMA table_info(repositories)"))
    columns = {row[1]: row for row in result.fetchall()}

    # Check if git_url still has NOT NULL constraint (notnull is index 3 in PRAGMA)
    git_url_notnull = columns.get("git_url", (0, 0, 0, 1))[3] == 1
    if "repo_type" not in columns or git_url_notnull:
        # Need to recreate the table to change NOT NULL on git_url and add repo_type
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS repositories_new ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  name VARCHAR(255) UNIQUE NOT NULL,"
            "  repo_type VARCHAR(20) DEFAULT 'git',"
            "  git_url VARCHAR(500),"
            "  default_branch VARCHAR(100) DEFAULT 'main',"
            "  local_path VARCHAR(500) NOT NULL,"
            "  last_synced_at DATETIME,"
            "  auto_sync BOOLEAN DEFAULT 1,"
            "  sync_interval_minutes INTEGER DEFAULT 15,"
            "  created_by INTEGER NOT NULL REFERENCES users(id),"
            "  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
            "  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        ))
        conn.execute(text(
            "INSERT OR IGNORE INTO repositories_new "
            "(id, name, repo_type, git_url, default_branch, local_path, "
            " last_synced_at, auto_sync, sync_interval_minutes, created_by, "
            " created_at, updated_at) "
            "SELECT id, name, 'git', git_url, default_branch, local_path, "
            " last_synced_at, auto_sync, sync_interval_minutes, created_by, "
            " created_at, updated_at "
            "FROM repositories"
        ))
        conn.execute(text("DROP TABLE repositories"))
        conn.execute(text("ALTER TABLE repositories_new RENAME TO repositories"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_repo_name ON repositories(name)"))
        logger.info("Migration: added repo_type column, made git_url nullable")
        # Re-read columns after possible recreation
        result = conn.execute(text("PRAGMA table_info(repositories)"))
        columns = {row[1]: row for row in result.fetchall()}

    # Add sync_status and sync_error columns if missing
    if "sync_status" not in columns:
        conn.execute(text("ALTER TABLE repositories ADD COLUMN sync_status VARCHAR(20) DEFAULT 'idle'"))
        logger.info("Migration: added sync_status column")
    if "sync_error" not in columns:
        conn.execute(text("ALTER TABLE repositories ADD COLUMN sync_error TEXT"))
        logger.info("Migration: added sync_error column")

    # Re-read columns after possible changes
    result = conn.execute(text("PRAGMA table_info(repositories)"))
    columns = {row[1]: row for row in result.fetchall()}

    if "environment_id" not in columns:
        conn.execute(text(
            "ALTER TABLE repositories ADD COLUMN environment_id INTEGER REFERENCES environments(id) ON DELETE SET NULL"
        ))
        logger.info("Migration: added environment_id column to repositories")

    # Migrate environments table: add default_runner_type and max_docker_containers
    result = conn.execute(text("PRAGMA table_info(environments)"))
    env_columns = {row[1] for row in result.fetchall()}
    if "default_runner_type" not in env_columns:
        conn.execute(text(
            "ALTER TABLE environments ADD COLUMN default_runner_type VARCHAR(20) DEFAULT 'subprocess'"
        ))
        logger.info("Migration: added default_runner_type column to environments")
    if "max_docker_containers" not in env_columns:
        conn.execute(text(
            "ALTER TABLE environments ADD COLUMN max_docker_containers INTEGER DEFAULT 1"
        ))
        logger.info("Migration: added max_docker_containers column to environments")


def _migrate_postgres(conn) -> None:
    """PostgreSQL migrations."""
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'repositories' AND column_name = 'repo_type'"
    ))
    if not result.fetchone():
        conn.execute(text(
            "ALTER TABLE repositories ADD COLUMN repo_type VARCHAR(20) DEFAULT 'git'"
        ))
        conn.execute(text(
            "ALTER TABLE repositories ALTER COLUMN git_url DROP NOT NULL"
        ))
        logger.info("Migration: added repo_type column, made git_url nullable")

    # Add environment_id column if missing
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'repositories' AND column_name = 'environment_id'"
    ))
    if not result.fetchone():
        conn.execute(text(
            "ALTER TABLE repositories ADD COLUMN environment_id INTEGER "
            "REFERENCES environments(id) ON DELETE SET NULL"
        ))
        logger.info("Migration: added environment_id column to repositories")

    # Add default_runner_type column to environments if missing
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'environments' AND column_name = 'default_runner_type'"
    ))
    if not result.fetchone():
        conn.execute(text(
            "ALTER TABLE environments ADD COLUMN default_runner_type VARCHAR(20) DEFAULT 'subprocess'"
        ))
        logger.info("Migration: added default_runner_type column to environments")

    # Add max_docker_containers column to environments if missing
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'environments' AND column_name = 'max_docker_containers'"
    ))
    if not result.fetchone():
        conn.execute(text(
            "ALTER TABLE environments ADD COLUMN max_docker_containers INTEGER DEFAULT 1"
        ))
        logger.info("Migration: added max_docker_containers column to environments")


def drop_tables() -> None:
    """Drop all tables (for testing)."""
    with engine.begin() as conn:
        Base.metadata.drop_all(conn)
