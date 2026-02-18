"""Environment models."""

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base, TimestampMixin


class Environment(Base, TimestampMixin):
    """Execution environment configuration."""

    __tablename__ = "environments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    python_version: Mapped[str] = mapped_column(String(20), default="3.12")
    venv_path: Mapped[str | None] = mapped_column(String(500), default=None)
    docker_image: Mapped[str | None] = mapped_column(String(500), default=None)
    default_runner_type: Mapped[str] = mapped_column(String(20), default="subprocess")
    max_docker_containers: Mapped[int] = mapped_column(Integer, default=1)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class EnvironmentPackage(Base):
    """Installed package in an environment."""

    __tablename__ = "environment_packages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    environment_id: Mapped[int] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), index=True)
    package_name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str | None] = mapped_column(String(50), default=None)
    installed_version: Mapped[str | None] = mapped_column(String(50), default=None)


class EnvironmentVariable(Base):
    """Environment variable."""

    __tablename__ = "environment_variables"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    environment_id: Mapped[int] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(255))
    value: Mapped[str] = mapped_column(Text)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
