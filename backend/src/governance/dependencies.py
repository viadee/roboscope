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


def _role_at_least(user: User, floor: Role) -> bool:
    try:
        rank = ROLE_HIERARCHY.get(Role(user.role), -1)
    except ValueError:
        rank = -1  # unknown/legacy role string → fail closed (deny), never 500
    return rank >= ROLE_HIERARCHY.get(floor, 999)


def _modifier_key(m: object) -> str:
    """A modifier reference is either a registry key (curated) or a free class
    path (user-code). Accept `{key|name, args}` dicts or a bare string."""
    if isinstance(m, dict):
        return str(m.get("key") or m.get("name") or "").strip()
    return str(m or "").strip()


def gate_advanced_execution(
    db: Session,
    request: Request,
    user: User,
    advanced_config: dict | None,
    repo_root: str | None = None,
) -> None:
    """Gate + validate advanced execution config (EXEC.3 + EXEC.10).

    No-op when ``advanced_config`` carries nothing. Otherwise enforces, in order
    (403 authorization fail-fast BEFORE 422 input rejection):

    1. ``executionAdvancedArgs`` flag + EDITOR floor (the advanced section).
    2. **Modifiers** route by registry membership: a curated key (Tier A/B) needs
       only the above; a non-registered class path is **user-code** (Tier C) and
       needs ADMIN + ``executionPreRunModifierUserCode`` + consent.
    3. ``python_paths`` → ADMIN + ``executionPythonPath``; ``variable_files`` →
       ADMIN + ``executionVariableFile``.
    4. Freeform args validated against the deny-list (422); ``python_paths`` /
       ``variable_files`` confined to ``repo_root`` (422 on escape).

    Every block writes its own audit row + commits BEFORE raising (the audit
    middleware skips >=400). A permitted advanced run is audited with the resolved
    argv + lever payload.
    """
    from src.execution.modifiers import get_modifier, is_curated_key
    from src.execution.resolver import _confine_to_repo

    if not advanced_config:
        return

    def _block(audit_detail: str, http_detail: str, code: int = status.HTTP_403_FORBIDDEN) -> None:
        _audit_block(db, request, user, audit_detail, "execution_run")
        raise HTTPException(status_code=code, detail=http_detail)

    def _as_list(field: str) -> list:
        v = advanced_config.get(field)
        if v is None:
            return []
        if not isinstance(v, list):
            _block(
                f"malformed:{field}",
                f"{field} must be a list",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return v

    args = _as_list("args")
    prerun = _as_list("prerun_modifiers")
    prerebot = _as_list("prerebot_modifiers")
    python_paths = _as_list("python_paths")
    variable_files = _as_list("variable_files")
    if not any((args, prerun, prerebot, python_paths, variable_files)):
        return

    # 1. Advanced-section flag + EDITOR floor.
    if not resolve_flag(db, "executionAdvancedArgs").value:
        _block("feature_disabled:executionAdvancedArgs", "feature_disabled:executionAdvancedArgs")
    if not _role_at_least(user, Role.EDITOR):
        _block(f"insufficient_role:executionAdvancedArgs:{user.role}", "insufficient_role")

    # 2. Modifiers: anything not a curated registry key is Tier-C user-code.
    usercode_mods = [
        k for m in (*prerun, *prerebot) if (k := _modifier_key(m)) and not is_curated_key(k)
    ]
    if usercode_mods:
        if not resolve_flag(db, "executionPreRunModifierUserCode").value:
            _block(
                "feature_disabled:executionPreRunModifierUserCode",
                "feature_disabled:executionPreRunModifierUserCode",
            )
        if not _role_at_least(user, Role.ADMIN):
            _block(f"insufficient_role:preRunModifierUserCode:{user.role}", "insufficient_role")

    # 3. Repo-confined code-loading levers — each its own ADMIN-only flag.
    if python_paths:
        if not resolve_flag(db, "executionPythonPath").value:
            _block("feature_disabled:executionPythonPath", "feature_disabled:executionPythonPath")
        if not _role_at_least(user, Role.ADMIN):
            _block(f"insufficient_role:executionPythonPath:{user.role}", "insufficient_role")
    if variable_files:
        if not resolve_flag(db, "executionVariableFile").value:
            _block("feature_disabled:executionVariableFile", "feature_disabled:executionVariableFile")  # noqa: E501
        if not _role_at_least(user, Role.ADMIN):
            _block(f"insufficient_role:executionVariableFile:{user.role}", "insufficient_role")

    # 4. Input rejection (422) AFTER the 403 gates.
    # 4a. Code-loading levers require explicit consent server-side (not just UI).
    if (python_paths or variable_files) and advanced_config.get("code_load_consent") is not True:
        _block(
            "consent_required",
            "code-loading consent required",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # 4b. Validate modifier entries: well-formed, a curated key must match the
    # list's kind, and an arg may not contain ':' (RF's modifier-spec separator).
    for entries, kind in ((prerun, "prerun"), (prerebot, "prerebot")):
        for m in entries:
            if not isinstance(m, (dict, str)):
                _block(
                    "malformed:modifier",
                    "modifier entries must be objects or strings",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            key = _modifier_key(m)
            if not key:
                continue
            margs = (m.get("args") or []) if isinstance(m, dict) else []
            if not isinstance(margs, list):
                _block(
                    "malformed:modifier_args",
                    "modifier args must be a list",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            if any(":" in str(a) for a in margs):
                _block(
                    "modifier_arg_colon",
                    "modifier arguments cannot contain ':'",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            entry = get_modifier(key)
            if entry is not None and entry.kind != kind:
                _block(
                    f"modifier_kind_mismatch:{key}",
                    f"'{key}' is not a {kind} modifier",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

    try:
        resolved_args = list(validate_advanced_args(args))
    except AdvancedArgError as e:
        _block(f"advanced_arg_rejected:{e}", str(e), status.HTTP_422_UNPROCESSABLE_ENTITY)

    confined_pp: list[str] = []
    confined_vf: list[str] = []
    try:
        confined_pp = [
            _confine_to_repo(str(p).strip(), repo_root) for p in python_paths if str(p).strip()
        ]
        confined_vf = [
            _confine_to_repo(str(p).strip(), repo_root) for p in variable_files if str(p).strip()
        ]
    except AdvancedArgError as e:
        _block(f"path_rejected:{e}", str(e), status.HTTP_422_UNPROCESSABLE_ENTITY)

    # Permitted advanced run — structured audit of the resolved argv + levers.
    zones_used = []
    if resolved_args:
        zones_used.append("z3")
    if prerun:
        zones_used.append("prerun_modifier")
    if prerebot:
        zones_used.append("prerebot_modifier")
    if python_paths:
        zones_used.append("pythonpath")
    if variable_files:
        zones_used.append("variablefile")
    if usercode_mods:
        zones_used.append("usercode_modifier")

    def _resolved_mods(entries: list) -> list[dict]:
        # Audit the actual class path + tier that will run, not just the key.
        out: list[dict] = []
        for m in entries:
            key = _modifier_key(m)
            if not key:
                continue
            e = get_modifier(key)
            out.append(
                {
                    "key": key,
                    "tier": e.tier if e else "usercode",
                    "class_path": e.class_path if e else key,
                }
            )
        return out

    detail = json.dumps(
        {
            "resolved_argv": resolved_args,
            "prerun_modifiers": _resolved_mods(prerun),
            "prerebot_modifiers": _resolved_mods(prerebot),
            "python_paths": confined_pp,
            "variable_files": confined_vf,
            "usercode_modifiers": usercode_mods,
            "code_load_consent": bool(advanced_config.get("code_load_consent")),
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
