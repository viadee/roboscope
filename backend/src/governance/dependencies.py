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

import json

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.audit.service import log_audit
from src.auth.constants import ROLE_HIERARCHY, Role
from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.execution.resolver import AdvancedArgError, validate_advanced_args
from src.governance.flags import resolve_flag, resolve_package_op_role


def _audit_block(
    db: Session,
    request: Request,
    user: User,
    detail: str,
    resource_type: str = "environment_package",
) -> None:
    """Record a governance-blocked mutation, then commit so it survives the
    403 (the request's session is otherwise rolled back / never committed)."""
    log_audit(
        db,
        user_id=user.id,
        username=user.email,
        action="blocked",
        resource_type=resource_type,
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


def gate_advanced_execution(
    db: Session,
    request: Request,
    user: User,
    advanced_config: dict | None,
) -> None:
    """Gate + validate advanced execution config (EXEC.3).

    No-op when ``advanced_config`` carries no args/modifiers. Otherwise enforces,
    in order: the ``executionAdvancedArgs`` feature flag (403 if off), an EDITOR
    role floor (403), the three-zone deny-list on freeform args (422), and — for
    user-authored ``prerun_modifiers`` — the ADMIN-only
    ``executionPreRunModifierUserCode`` flag (403). Every block writes its own
    audit row + commits BEFORE raising (the audit middleware skips >=400). A
    permitted advanced run is also audited (resolved args recorded).
    """
    if not advanced_config:
        return
    args = list(advanced_config.get("args") or [])
    modifiers = list(advanced_config.get("prerun_modifiers") or [])
    if not args and not modifiers:
        return

    if not resolve_flag(db, "executionAdvancedArgs").value:
        _audit_block(db, request, user, "feature_disabled:executionAdvancedArgs", "execution_run")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="feature_disabled:executionAdvancedArgs",
        )

    if ROLE_HIERARCHY.get(Role(user.role), -1) < ROLE_HIERARCHY.get(Role.EDITOR, 999):
        _audit_block(
            db,
            request,
            user,
            f"insufficient_role:executionAdvancedArgs:{user.role}",
            "execution_run",
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_role")

    if modifiers:
        if not resolve_flag(db, "executionPreRunModifierUserCode").value:
            _audit_block(
                db,
                request,
                user,
                "feature_disabled:executionPreRunModifierUserCode",
                "execution_run",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="feature_disabled:executionPreRunModifierUserCode",
            )
        if ROLE_HIERARCHY.get(Role(user.role), -1) < ROLE_HIERARCHY.get(Role.ADMIN, 999):
            _audit_block(
                db,
                request,
                user,
                f"insufficient_role:preRunModifierUserCode:{user.role}",
                "execution_run",
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_role")

    try:
        resolved_args = list(validate_advanced_args(args))
    except AdvancedArgError as e:
        _audit_block(db, request, user, f"advanced_arg_rejected:{e}", "execution_run")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e

    # Permitted advanced run — record the RESOLVED args AND the modifiers in the
    # structured shape the architecture mandates (resolved_argv / zones_used /
    # blocked), so the audit reflects what actually runs (modifier runs were
    # previously invisible in the audit content).
    zones_used = []
    if resolved_args:
        zones_used.append("z3")
    if modifiers:
        zones_used.append("modifier")
    detail = json.dumps(
        {
            "resolved_argv": resolved_args,
            "prerun_modifiers": modifiers,
            "zones_used": zones_used,
            "blocked": False,
        },
        ensure_ascii=False,
        default=str,
    )
    log_audit(
        db,
        user_id=user.id,
        username=user.email,
        action="advanced_run",
        resource_type="execution_run",
        detail=detail,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()


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
