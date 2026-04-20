"""CRUD endpoints for Identity Provider configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import require_role
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
