"""Application configuration using Pydantic Settings."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global application settings, loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    PROJECT_NAME: str = "mateoX"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    # Default: SQLite. Set to PostgreSQL URL for production.
    # SQLite:     sqlite+aiosqlite:///./mateox.db
    # PostgreSQL: postgresql+asyncpg://user:pass@localhost:5432/mateox
    DATABASE_URL: str = "sqlite+aiosqlite:///./mateox.db"

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return "postgresql" in self.DATABASE_URL

    @property
    def sync_database_url(self) -> str:
        """Convert async URL to sync URL for Alembic migrations."""
        return (
            self.DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://")
            .replace("postgresql+asyncpg://", "postgresql://")
        )

    # JWT Authentication
    SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Task execution uses an in-process ThreadPoolExecutor (no external deps).
    # Redis/Celery settings are kept for optional future use.
    REDIS_URL: str = "redis://localhost:6379/0"

    # Execution
    RUNNER_TYPE: Literal["subprocess", "docker", "auto"] = "auto"
    WORKSPACE_DIR: str = str(Path.home() / ".mateox" / "workspace")
    REPORTS_DIR: str = str(Path.home() / ".mateox" / "reports")
    VENVS_DIR: str = str(Path.home() / ".mateox" / "venvs")
    DEFAULT_TIMEOUT_SECONDS: int = 3600
    MAX_PARALLEL_RUNS: int = 4

    # Docker
    DOCKER_AVAILABLE: bool = False
    DOCKER_DEFAULT_IMAGE: str = "python:3.12-slim"
    DOCKER_NETWORK: str = "mateox-network"

    # Git
    GIT_SYNC_INTERVAL_MINUTES: int = 15

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Logging
    LOG_LEVEL: str = "INFO"

    # Retention
    REPORT_RETENTION_DAYS: int = 90
    LOG_RETENTION_DAYS: int = 30


settings = Settings()
