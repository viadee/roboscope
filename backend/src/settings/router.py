"""Settings API endpoints (admin only)."""

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import require_role
from src.auth.models import User
from src.config import settings as app_settings
from src.database import get_db
from src.settings.schemas import SettingResponse, SettingsBulkUpdate
from src.settings.service import get_setting, list_settings, update_settings

logger = logging.getLogger("roboscope.settings")

router = APIRouter()


@router.get("", response_model=list[SettingResponse])
def get_settings(
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """List all application settings."""
    return list_settings(db, category)


@router.patch("", response_model=list[SettingResponse])
def patch_settings(
    data: SettingsBulkUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Update multiple settings."""
    return update_settings(db, data.settings)


@router.get("/docker-status")
def get_docker_status(
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Probe Docker daemon and return status info."""
    # Story REFACTOR-1 — shared bootstrap helper.
    from src.docker_client import get_docker_client
    try:
        client = get_docker_client()
        version_info = client.version()

        containers = client.containers.list()

        images_raw = client.images.list()
        images_raw.sort(key=lambda img: img.attrs.get("Size", 0), reverse=True)
        images = []
        for img in images_raw[:20]:
            tags = img.tags
            if not tags:
                short_id = img.id.replace("sha256:", "")[:12]
                repo = short_id
                tag = "<none>"
            else:
                parts = tags[0].split(":", 1)
                repo = parts[0]
                tag = parts[1] if len(parts) > 1 else "latest"
            images.append({
                "repository": repo,
                "tag": tag,
                "size": img.attrs.get("Size", 0),
                "created": img.attrs.get("Created", ""),
            })

        return {
            "connected": True,
            "version": version_info.get("Version", ""),
            "api_version": version_info.get("ApiVersion", ""),
            "os": version_info.get("Os", ""),
            "arch": version_info.get("Arch", ""),
            "default_image": app_settings.DOCKER_DEFAULT_IMAGE,
            "running_containers": len(containers),
            "images": images,
        }
    except Exception as e:
        logger.warning("Docker status check failed: %s", e)
        return {
            "connected": False,
            "error": str(e),
            "default_image": app_settings.DOCKER_DEFAULT_IMAGE,
        }


# --- Story 5-1: SSO Emergency Bypass API ---

_SSO_EMERGENCY_BYPASS_MAX_HOURS = int(
    os.environ.get("SSO_EMERGENCY_BYPASS_MAX_HOURS", "24")
)


class SsoEmergencyBypassActivate(BaseModel):
    hours: int = Field(..., gt=0, description="How many hours the bypass stays active.")


class SsoEmergencyBypassStatus(BaseModel):
    active: bool
    expires_at: str | None = None
    max_hours: int


@router.get("/sso-emergency-bypass", response_model=SsoEmergencyBypassStatus)
def get_emergency_bypass_status(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
) -> SsoEmergencyBypassStatus:
    """Read current emergency-bypass status (ADMIN)."""
    flag = get_setting(db, "sso_emergency_bypass")
    exp = get_setting(db, "sso_emergency_bypass_expires_at")
    active = flag is not None and flag.value.lower() == "true"
    return SsoEmergencyBypassStatus(
        active=active,
        expires_at=exp.value if exp and exp.value else None,
        max_hours=_SSO_EMERGENCY_BYPASS_MAX_HOURS,
    )


@router.post("/sso-emergency-bypass", response_model=SsoEmergencyBypassStatus)
def activate_emergency_bypass(
    data: SsoEmergencyBypassActivate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
) -> SsoEmergencyBypassStatus:
    """Activate the installation-wide SSO emergency bypass for `hours` hours.

    Story 5-1. Rejects durations above SSO_EMERGENCY_BYPASS_MAX_HOURS (default 24).
    Emits `sso.emergency_bypass.activated` with actor id + duration.
    """
    from src.audit.event_types import AuditEventType
    from src.audit.service import log_event
    from src.settings.models import AppSetting

    if data.hours > _SSO_EMERGENCY_BYPASS_MAX_HOURS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bypass duration exceeds maximum of {_SSO_EMERGENCY_BYPASS_MAX_HOURS} hours",
        )

    flag = get_setting(db, "sso_emergency_bypass")
    exp = get_setting(db, "sso_emergency_bypass_expires_at")
    if flag is None:
        flag = AppSetting(
            key="sso_emergency_bypass", value="false", value_type="bool",
            category="auth", description="Enable local-login fallback during SSO outage.",
        )
        db.add(flag)
    if exp is None:
        exp = AppSetting(
            key="sso_emergency_bypass_expires_at", value="", value_type="string",
            category="auth", description="ISO-8601 auto-expiry for emergency bypass (empty = inactive).",
        )
        db.add(exp)

    expires_at = datetime.now(timezone.utc) + timedelta(hours=data.hours)
    flag.value = "true"
    exp.value = expires_at.isoformat()
    db.flush()

    log_event(
        db,
        AuditEventType.SSO_EMERGENCY_BYPASS_ACTIVATED,
        user_id=current_user.id,
        detail={
            "actor_id": current_user.id,
            "duration_hours": data.hours,
            "expires_at": expires_at.isoformat(),
        },
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return SsoEmergencyBypassStatus(
        active=True,
        expires_at=exp.value,
        max_hours=_SSO_EMERGENCY_BYPASS_MAX_HOURS,
    )


@router.delete("/sso-emergency-bypass", response_model=SsoEmergencyBypassStatus)
def deactivate_emergency_bypass(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
) -> SsoEmergencyBypassStatus:
    """Manually deactivate the bypass (ADMIN)."""
    from src.audit.event_types import AuditEventType
    from src.audit.service import log_event

    flag = get_setting(db, "sso_emergency_bypass")
    exp = get_setting(db, "sso_emergency_bypass_expires_at")
    was_active = flag is not None and flag.value.lower() == "true"

    if flag is not None:
        flag.value = "false"
    if exp is not None:
        exp.value = ""
    db.flush()

    if was_active:
        log_event(
            db,
            AuditEventType.SSO_EMERGENCY_BYPASS_DEACTIVATED,
            user_id=current_user.id,
            detail={"actor_id": current_user.id, "reason": "manual"},
            ip_address=request.client.host if request.client else None,
        )
    db.commit()
    return SsoEmergencyBypassStatus(
        active=False,
        expires_at=None,
        max_hours=_SSO_EMERGENCY_BYPASS_MAX_HOURS,
    )
