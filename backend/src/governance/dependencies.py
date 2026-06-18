"""FastAPI dependencies enforcing deployment governance (Epic GOV).

`require_feature` is a generic flag gate; `require_package_op` composes the
packageManagement flag gate (absolute — even ADMIN is blocked when off) with
the configurable per-op role floor (GOV-4). The flag check runs first: a
locked deployment 403s before any role consideration.

Blocked attempts are written to the audit log here, because the audit
MIDDLEWARE deliberately skips responses with status >= 400 — a 403 raised from
a dependency would otherwise leave no trace (FR-6).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.audit.service import log_audit
from src.auth.constants import ROLE_HIERARCHY, Role
from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.governance.flags import resolve_flag, resolve_package_op_role


def _audit_block(db: Session, request: Request, user: User, detail: str) -> None:
    """Record a governance-blocked mutation, then commit so it survives the
    403 (the request's session is otherwise rolled back / never committed)."""
    log_audit(
        db,
        user_id=user.id,
        username=user.email,
        action="blocked",
        resource_type="environment_package",
        detail=detail,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()


def require_feature(flag: str):
    """Dependency: 403 when `flag` is disabled for this deployment."""

    def dep(db: Session = Depends(get_db)) -> None:
        if not resolve_flag(db, flag).value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"feature_disabled:{flag}",
            )

    return dep


def require_package_op(op: str):
    """Dependency: gate a package operation behind the packageManagement flag
    (absolute) then the configurable role floor (GOV-4)."""

    def dep(
        request: Request,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not resolve_flag(db, "packageManagement").value:
            _audit_block(db, request, current_user, f"feature_disabled:packageManagement:{op}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="feature_disabled:packageManagement",
            )
        floor = resolve_package_op_role(db, op)
        user_level = ROLE_HIERARCHY.get(Role(current_user.role), -1)
        if user_level < ROLE_HIERARCHY.get(floor, 999):
            _audit_block(db, request, current_user, f"insufficient_role:{op}:{current_user.role}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="insufficient_role",
            )
        return current_user

    return dep
