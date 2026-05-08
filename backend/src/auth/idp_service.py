"""Service functions for Identity Provider CRUD operations."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import IdentityProvider
from src.auth.schemas import IdentityProviderCreate, IdentityProviderUpdate
from src.encryption import decrypt_value, is_encrypted

logger = logging.getLogger("roboscope.auth.idp")


def list_identity_providers(db: Session) -> list[IdentityProvider]:
    stmt = select(IdentityProvider).order_by(IdentityProvider.name)
    return list(db.execute(stmt).scalars().all())


def get_identity_provider(db: Session, idp_id: int) -> IdentityProvider | None:
    return db.execute(
        select(IdentityProvider).where(IdentityProvider.id == idp_id)
    ).scalar_one_or_none()


def get_identity_provider_by_name(db: Session, name: str) -> IdentityProvider | None:
    return db.execute(
        select(IdentityProvider).where(IdentityProvider.name == name)
    ).scalar_one_or_none()


def create_identity_provider(
    db: Session, data: IdentityProviderCreate
) -> IdentityProvider:
    from src.encryption import encrypt_value

    idp = IdentityProvider(
        name=data.name,
        provider_type=data.provider_type,
        issuer_url=data.issuer_url,
        client_id=data.client_id,
        client_secret_encrypted=encrypt_value(data.client_secret).encode(),
        scopes=data.scopes,
        group_claim_name=data.group_claim_name,
    )
    db.add(idp)
    db.flush()
    db.refresh(idp)
    return idp


def update_identity_provider(
    db: Session, idp: IdentityProvider, data: IdentityProviderUpdate
) -> IdentityProvider:
    from src.encryption import encrypt_value

    updates = data.model_dump(exclude_unset=True)
    if "client_secret" in updates:
        secret = updates.pop("client_secret")
        if secret is not None:
            idp.client_secret_encrypted = encrypt_value(secret).encode()
    for key, value in updates.items():
        setattr(idp, key, value)
    db.flush()
    db.refresh(idp)
    return idp


def delete_identity_provider(db: Session, idp: IdentityProvider) -> None:
    db.delete(idp)
    db.flush()


def get_decrypted_client_secret(idp: IdentityProvider) -> str:
    """Return the IdP client_secret as plaintext. For outbound OIDC use only.

    Uses `is_encrypted()`-first preflight matching `src/environments/service.py`
    Phase-2 pattern: when the stored value is not a Fernet token under the
    current SECRET_KEY, fall back to treating it as legacy plaintext and log
    a warning (with IdP id, never the value) so operators can detect legacy
    or post-rotation rows.

    Never log the returned value.
    """
    stored_bytes = idp.client_secret_encrypted
    if not stored_bytes:
        raise ValueError(
            f"IdP {idp.id} has no client_secret_encrypted value"
        )
    try:
        stored = stored_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"IdP {idp.id} client_secret_encrypted is not valid UTF-8"
        ) from exc
    if is_encrypted(stored):
        return decrypt_value(stored)
    # Legacy plaintext (pre-encryption rows or post SECRET_KEY rotation).
    # Log a warning so operators can detect this state; never log the value.
    logger.warning(
        "IdP %s: client_secret using legacy-plaintext fallback "
        "(pre-encryption row or SECRET_KEY rotation)",
        idp.id,
    )
    return stored
