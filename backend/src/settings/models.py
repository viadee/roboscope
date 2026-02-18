"""Application settings models."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class AppSetting(Base):
    """Key-value application settings stored in DB."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    value_type: Mapped[str] = mapped_column(String(20), default="string")  # string, int, bool, json
    category: Mapped[str] = mapped_column(String(50), default="general")
    description: Mapped[str | None] = mapped_column(Text, default=None)
