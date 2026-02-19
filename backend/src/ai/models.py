"""AI module database models."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base, TimestampMixin


class AiProvider(Base, TimestampMixin):
    """LLM provider configuration."""

    __tablename__ = "ai_providers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    provider_type: Mapped[str] = mapped_column(String(50))  # openai, anthropic, openrouter, ollama
    api_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str] = mapped_column(String(100))
    temperature: Mapped[float] = mapped_column(Float, default=0.3)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class AiJob(Base, TimestampMixin):
    """Tracks async AI generation/reverse jobs."""

    __tablename__ = "ai_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(20))  # generate, reverse
    status: Mapped[str] = mapped_column(String(20), default="pending")
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("ai_providers.id"))
    spec_path: Mapped[str] = mapped_column(String(500))
    target_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    triggered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
