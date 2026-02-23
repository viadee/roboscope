"""Application settings service."""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.settings.models import AppSetting
from src.settings.schemas import SettingUpdate

# Default settings to seed on first start
DEFAULT_SETTINGS = [
    {"key": "default_runner", "value": "subprocess", "value_type": "string", "category": "execution", "description": "Default runner type (subprocess or docker)"},
    {"key": "max_parallel_runs", "value": "4", "value_type": "int", "category": "execution", "description": "Maximum parallel test runs"},
    {"key": "default_timeout", "value": "3600", "value_type": "int", "category": "execution", "description": "Default timeout in seconds"},
    {"key": "git_sync_interval", "value": "15", "value_type": "int", "category": "git", "description": "Git auto-sync interval in minutes"},
    {"key": "report_retention_days", "value": "90", "value_type": "int", "category": "retention", "description": "Days to keep reports"},
    {"key": "log_retention_days", "value": "30", "value_type": "int", "category": "retention", "description": "Days to keep logs"},
    {"key": "log_level", "value": "INFO", "value_type": "string", "category": "general", "description": "Application log level"},
    {"key": "enable_notifications", "value": "true", "value_type": "bool", "category": "general", "description": "Enable WebSocket notifications"},
    {"key": "docker_default_image", "value": "python:3.12-slim", "value_type": "string", "category": "docker", "description": "Default Docker image for test execution"},
    {"key": "docker_memory_limit", "value": "2g", "value_type": "string", "category": "docker", "description": "Docker container memory limit"},
    {"key": "rf_mcp_auto_start", "value": "false", "value_type": "bool", "category": "ai", "description": "Auto-start rf-mcp server on app startup"},
    {"key": "rf_mcp_environment_id", "value": "", "value_type": "string", "category": "ai", "description": "Environment ID for rf-mcp server"},
    {"key": "rf_mcp_port", "value": "9090", "value_type": "int", "category": "ai", "description": "Port for rf-mcp server"},
]


def list_settings(db: Session, category: str | None = None) -> list[AppSetting]:
    """List all application settings."""
    query = select(AppSetting).order_by(AppSetting.category, AppSetting.key)
    if category:
        query = query.where(AppSetting.category == category)
    result = db.execute(query)
    return list(result.scalars().all())


def get_setting(db: Session, key: str) -> AppSetting | None:
    """Get a single setting by key."""
    result = db.execute(select(AppSetting).where(AppSetting.key == key))
    return result.scalar_one_or_none()


def get_setting_value(db: Session, key: str, default: str = "") -> str:
    """Get the value of a setting."""
    setting = get_setting(db, key)
    return setting.value if setting else default


def update_settings(db: Session, updates: list[SettingUpdate]) -> list[AppSetting]:
    """Update multiple settings at once."""
    updated: list[AppSetting] = []
    for update in updates:
        setting = get_setting(db, update.key)
        if setting:
            setting.value = update.value
            updated.append(setting)
    db.flush()
    return updated


def seed_default_settings(db: Session) -> None:
    """Create default settings if they don't exist."""
    for default in DEFAULT_SETTINGS:
        existing = get_setting(db, default["key"])
        if existing is None:
            setting = AppSetting(**default)
            db.add(setting)
    db.flush()
