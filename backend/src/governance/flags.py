"""Feature-flag registry + resolver (Epic GOV).

Resolves deployment-level feature toggles with precedence

    ENV var  >  app_settings (DB)  >  built-in default (ON)

so an operator can disable a whole feature area (v1: package management)
independent of user roles. The ENV override is the hard lock for managed /
remote installs where the admin team owns the host, not the app — it wins over
any in-app admin toggle and marks the flag ``locked`` (the UI renders it
non-editable). See _bmad-output/planning-artifacts/gov-architecture.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.settings.service import get_setting_value

# Flag registry: key -> default value. Default is ON so upgrades never silently
# remove a feature. Adding a flag here (+ a seed row in settings) is all it
# takes to govern a new area.
FEATURE_FLAGS: dict[str, bool] = {
    "packageManagement": True,
    # EXEC.2: advanced execution levers. These MUST be registered explicitly
    # with default False — `resolve_flag` falls back to `.get(key, True)`, so an
    # UNregistered key would default ON. Security requires these OFF by default,
    # the deliberate exception to the registry's "default-ON" convention.
    "executionAdvancedArgs": False,
    "executionPreRunModifierUserCode": False,
    "executionDataDriver": False,
    # EXEC.10: repo-confined code-loading levers, ADMIN-only, default OFF.
    "executionPythonPath": False,
    "executionVariableFile": False,
    # EXEC.11: runtime user-code listeners (curated listeners need no flag),
    # ADMIN-only, default OFF.
    "executionCustomListenerUserCode": False,
}

SETTINGS_CATEGORY = "features"
_ENV_PREFIX = "ROBOSCOPE_FEATURE_"
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}

# Package operations gated by the configurable role floor (GOV-4). Consulted
# only when the packageManagement area is ON.
PACKAGE_OPS = ("install", "uninstall", "upgrade", "docker_build", "rfbrowser_init")
PACKAGE_OP_ROLE_DEFAULT = Role.EDITOR  # matches pre-GOV behavior


@dataclass(frozen=True)
class ResolvedFlag:
    """A flag's resolved value plus whether it was locked by an ENV override."""

    value: bool
    locked: bool


def settings_key(flag: str) -> str:
    """The `app_settings.key` for a feature flag (category `features`)."""
    return f"{SETTINGS_CATEGORY}.{flag}"


def env_key(flag: str) -> str:
    """ROBOSCOPE_FEATURE_<UPPER_SNAKE>, e.g. packageManagement -> ...PACKAGE_MANAGEMENT."""
    snake = "".join(f"_{c}" if c.isupper() else c for c in flag).upper().strip("_")
    return _ENV_PREFIX + snake


def _parse_bool(raw: str | None) -> bool | None:
    if raw is None:
        return None
    v = raw.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    return None


def resolve_flag(db: Session, key: str) -> ResolvedFlag:
    """Resolve one flag: ENV (locked) > DB > registry default (ON)."""
    default = FEATURE_FLAGS.get(key, True)
    env = _parse_bool(os.environ.get(env_key(key)))
    if env is not None:
        return ResolvedFlag(value=env, locked=True)
    db_value = _parse_bool(get_setting_value(db, settings_key(key)))
    return ResolvedFlag(value=db_value if db_value is not None else default, locked=False)


def resolve_all(db: Session) -> dict[str, ResolvedFlag]:
    """Resolve every registered flag."""
    return {key: resolve_flag(db, key) for key in FEATURE_FLAGS}


def resolve_package_op_role(db: Session, op: str) -> Role:
    """Configurable minimum role for a package operation (default EDITOR)."""
    raw = get_setting_value(db, f"{SETTINGS_CATEGORY}.packageManagement.role.{op}")
    try:
        return Role(raw) if raw else PACKAGE_OP_ROLE_DEFAULT
    except ValueError:
        return PACKAGE_OP_ROLE_DEFAULT
