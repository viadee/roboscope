"""Database engine, session factory, and base model."""

import logging
from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import MetaData, func, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

logger = logging.getLogger("mateox.database")

from src.config import settings

# Naming convention for consistent constraint names across SQLite & PostgreSQL
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Engine configuration varies by database type
engine_kwargs: dict = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}

if settings.is_postgres:
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
    })

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
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


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables() -> None:
    """Create all tables (for development/testing)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _run_migrations()


async def _run_migrations() -> None:
    """Run lightweight schema migrations for new columns on existing tables."""
    async with engine.begin() as conn:
        if settings.is_sqlite:
            await _migrate_sqlite(conn)
        else:
            await _migrate_postgres(conn)


async def _migrate_sqlite(conn) -> None:
    """SQLite migrations — add repo_type column and make git_url nullable."""
    result = await conn.execute(text("PRAGMA table_info(repositories)"))
    columns = {row[1]: row for row in result.fetchall()}

    # Check if git_url still has NOT NULL constraint (notnull is index 3 in PRAGMA)
    git_url_notnull = columns.get("git_url", (0, 0, 0, 1))[3] == 1
    if "repo_type" not in columns or git_url_notnull:
        # Need to recreate the table to change NOT NULL on git_url and add repo_type
        await conn.execute(text(
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
        await conn.execute(text(
            "INSERT OR IGNORE INTO repositories_new "
            "(id, name, repo_type, git_url, default_branch, local_path, "
            " last_synced_at, auto_sync, sync_interval_minutes, created_by, "
            " created_at, updated_at) "
            "SELECT id, name, 'git', git_url, default_branch, local_path, "
            " last_synced_at, auto_sync, sync_interval_minutes, created_by, "
            " created_at, updated_at "
            "FROM repositories"
        ))
        await conn.execute(text("DROP TABLE repositories"))
        await conn.execute(text("ALTER TABLE repositories_new RENAME TO repositories"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_repo_name ON repositories(name)"))
        logger.info("Migration: added repo_type column, made git_url nullable")
        # Re-read columns after possible recreation
        result = await conn.execute(text("PRAGMA table_info(repositories)"))
        columns = {row[1]: row for row in result.fetchall()}

    # Add sync_status and sync_error columns if missing
    if "sync_status" not in columns:
        await conn.execute(text("ALTER TABLE repositories ADD COLUMN sync_status VARCHAR(20) DEFAULT 'idle'"))
        logger.info("Migration: added sync_status column")
    if "sync_error" not in columns:
        await conn.execute(text("ALTER TABLE repositories ADD COLUMN sync_error TEXT"))
        logger.info("Migration: added sync_error column")

    # Re-read columns after possible changes
    result = await conn.execute(text("PRAGMA table_info(repositories)"))
    columns = {row[1]: row for row in result.fetchall()}

    if "environment_id" not in columns:
        await conn.execute(text(
            "ALTER TABLE repositories ADD COLUMN environment_id INTEGER REFERENCES environments(id) ON DELETE SET NULL"
        ))
        logger.info("Migration: added environment_id column to repositories")

    # Migrate environments table: add default_runner_type and max_docker_containers
    result = await conn.execute(text("PRAGMA table_info(environments)"))
    env_columns = {row[1] for row in result.fetchall()}
    if "default_runner_type" not in env_columns:
        await conn.execute(text(
            "ALTER TABLE environments ADD COLUMN default_runner_type VARCHAR(20) DEFAULT 'subprocess'"
        ))
        logger.info("Migration: added default_runner_type column to environments")
    if "max_docker_containers" not in env_columns:
        await conn.execute(text(
            "ALTER TABLE environments ADD COLUMN max_docker_containers INTEGER DEFAULT 1"
        ))
        logger.info("Migration: added max_docker_containers column to environments")


async def _migrate_postgres(conn) -> None:
    """PostgreSQL migrations."""
    result = await conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'repositories' AND column_name = 'repo_type'"
    ))
    if not result.fetchone():
        await conn.execute(text(
            "ALTER TABLE repositories ADD COLUMN repo_type VARCHAR(20) DEFAULT 'git'"
        ))
        await conn.execute(text(
            "ALTER TABLE repositories ALTER COLUMN git_url DROP NOT NULL"
        ))
        logger.info("Migration: added repo_type column, made git_url nullable")

    # Add environment_id column if missing
    result = await conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'repositories' AND column_name = 'environment_id'"
    ))
    if not result.fetchone():
        await conn.execute(text(
            "ALTER TABLE repositories ADD COLUMN environment_id INTEGER "
            "REFERENCES environments(id) ON DELETE SET NULL"
        ))
        logger.info("Migration: added environment_id column to repositories")

    # Add default_runner_type column to environments if missing
    result = await conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'environments' AND column_name = 'default_runner_type'"
    ))
    if not result.fetchone():
        await conn.execute(text(
            "ALTER TABLE environments ADD COLUMN default_runner_type VARCHAR(20) DEFAULT 'subprocess'"
        ))
        logger.info("Migration: added default_runner_type column to environments")

    # Add max_docker_containers column to environments if missing
    result = await conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'environments' AND column_name = 'max_docker_containers'"
    ))
    if not result.fetchone():
        await conn.execute(text(
            "ALTER TABLE environments ADD COLUMN max_docker_containers INTEGER DEFAULT 1"
        ))
        logger.info("Migration: added max_docker_containers column to environments")


async def drop_tables() -> None:
    """Drop all tables (for testing)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
