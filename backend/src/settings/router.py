"""Settings API endpoints (admin only)."""

import json
import logging
import subprocess

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.constants import Role
from src.auth.dependencies import require_role
from src.auth.models import User
from src.config import settings as app_settings
from src.database import get_db
from src.settings.schemas import SettingResponse, SettingsBulkUpdate
from src.settings.service import list_settings, update_settings

logger = logging.getLogger("mateox.settings")

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


def _get_docker_client():
    """Create a Docker client using the same fallback logic as DockerRunner."""
    import docker

    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception:
        base_url = None
        try:
            out = subprocess.check_output(
                ["docker", "context", "inspect"], text=True, timeout=5,
            )
            ctx = json.loads(out)
            if isinstance(ctx, list) and ctx:
                host = ctx[0].get("Endpoints", {}).get("docker", {}).get("Host", "")
                if host:
                    base_url = host
        except Exception:
            pass

        if base_url:
            return docker.DockerClient(base_url=base_url)
        raise


@router.get("/docker-status")
async def get_docker_status(
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Probe Docker daemon and return status info."""
    try:
        client = _get_docker_client()
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
