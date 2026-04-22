"""CRUD endpoints for Identity Provider configuration."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import require_role
from src.auth.handoff_generator import generate_markdown, generate_pdf
from src.auth.oidc_discovery import probe_idp_discovery
from src.auth.idp_service import (
    create_identity_provider,
    delete_identity_provider,
    get_identity_provider,
    get_identity_provider_by_name,
    list_identity_providers,
    update_identity_provider,
)
from src.auth.models import User
from src.auth.schemas import (
    DiscoveryCacheRefreshResponse,
    DryRunProbeResponse,
    IdentityProviderCreate,
    IdentityProviderResponse,
    IdentityProviderUpdate,
)
from src.database import get_db

router = APIRouter()


@router.get("", response_model=list[IdentityProviderResponse])
def list_idps(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    return list_identity_providers(db)


@router.post(
    "", response_model=IdentityProviderResponse, status_code=status.HTTP_201_CREATED
)
def create_idp(
    data: IdentityProviderCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    if get_identity_provider_by_name(db, data.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Identity provider with name '{data.name}' already exists",
        )
    idp = create_identity_provider(db, data)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Identity provider with name '{data.name}' already exists",
        )
    return idp


@router.post("/discovery-cache/refresh", response_model=DiscoveryCacheRefreshResponse)
def trigger_discovery_cache_refresh(
    _: User = Depends(require_role(Role.ADMIN)),
) -> DiscoveryCacheRefreshResponse:
    from src.auth.discovery_refresh import refresh_discovery_cache

    result = refresh_discovery_cache(force_all=True)
    return DiscoveryCacheRefreshResponse(**result)


@router.get("/{idp_id}", response_model=IdentityProviderResponse)
def get_idp(
    idp_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    idp = get_identity_provider(db, idp_id)
    if not idp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Identity provider not found",
        )
    return idp


@router.patch("/{idp_id}", response_model=IdentityProviderResponse)
def update_idp(
    idp_id: int,
    data: IdentityProviderUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    idp = get_identity_provider(db, idp_id)
    if not idp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Identity provider not found",
        )
    if data.name is not None and data.name != idp.name:
        existing = get_identity_provider_by_name(db, data.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Identity provider with name '{data.name}' already exists",
            )
    updated = update_identity_provider(db, idp, data)
    db.commit()
    return updated


@router.delete("/{idp_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_idp(
    idp_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    idp = get_identity_provider(db, idp_id)
    if not idp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Identity provider not found",
        )
    delete_identity_provider(db, idp)
    db.commit()


@router.get("/{idp_id}/handoff")
def handoff_artifact(
    idp_id: int,
    request: Request,
    format: Literal["pdf", "md"] = Query("pdf"),
    lang: Literal["en", "de", "fr", "es"] = Query("en"),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> StreamingResponse:
    idp = get_identity_provider(db, idp_id)
    if not idp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Identity provider not found",
        )
    base_url = str(request.base_url)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in idp.name)
    if format == "pdf":
        content = generate_pdf(idp, base_url, lang)
        media_type = "application/pdf"
        filename = f"idp-handoff-{safe_name}-{lang}.pdf"
    else:
        content = generate_markdown(idp, base_url, lang).encode("utf-8")
        media_type = "text/markdown; charset=utf-8"
        filename = f"idp-handoff-{safe_name}-{lang}.md"
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{idp_id}/dry-run", response_model=DryRunProbeResponse)
def dry_run_idp(
    idp_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    idp = get_identity_provider(db, idp_id)
    if not idp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Identity provider not found",
        )
    result = probe_idp_discovery(db, idp)
    db.commit()
    return result


@router.get("/{idp_id}/available-groups", response_model=list[str])
def available_groups_for_idp(
    idp_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> list[str]:
    """Return the distinct sorted union of mapped + login-observed group names
    for the given IdP (Story 3-4).
    """
    from src.teams.service import list_available_groups_for_idp

    idp = get_identity_provider(db, idp_id)
    if not idp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Identity provider not found",
        )
    return list_available_groups_for_idp(db, idp_id)
