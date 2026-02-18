"""Settings API endpoints (admin only)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.constants import Role
from src.auth.dependencies import require_role
from src.auth.models import User
from src.database import get_db
from src.settings.schemas import SettingResponse, SettingsBulkUpdate
from src.settings.service import list_settings, update_settings

router = APIRouter()


@router.get("", response_model=list[SettingResponse])
async def get_settings(
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """List all application settings."""
    return await list_settings(db, category)


@router.patch("", response_model=list[SettingResponse])
async def patch_settings(
    data: SettingsBulkUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Update multiple settings."""
    return await update_settings(db, data.settings)
