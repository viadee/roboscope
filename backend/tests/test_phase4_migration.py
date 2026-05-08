"""Phase-4 Alembic migration round-trip test.

Verifies that `b4d2e1a9c3f7_phase4_sso_and_teams.py`:
  1. Creates all 6 new tables + columns on `upgrade()`
  2. Seeds the 4 Phase-4 rows in `app_settings`
  3. Cleanly reverts on `downgrade()` without orphaning existing data

The baseline schema is built via `Base.metadata.create_all()` with Phase-4 tables
temporarily removed — this simulates the pre-Phase-4 state. We then stamp Alembic
to the pre-Phase-4 revision and exercise upgrade/downgrade.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
import sqlalchemy as sa
from sqlalchemy import create_engine, inspect, text

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PRE_PHASE4_REV = "a3c7e1f82d4b"
PHASE4_REV = "b4d2e1a9c3f7"

PHASE4_TABLES = (
    "identity_providers",
    "teams",
    "team_members",
    "idp_group_mappings",
    "oidc_login_attempts",
    "rate_limit_counters",
)

PHASE4_SETTING_KEYS = (
    "sso_emergency_bypass",
    "sso_emergency_bypass_expires_at",
    "deprovision_retention_days",
    "admin_contact_email",
)


def _build_alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    return cfg


@pytest.fixture
def fresh_db():
    """Yield a SQLite file URL and cleanup on exit."""
    tmpdir = tempfile.mkdtemp(prefix="roboscope_mig_")
    db_path = Path(tmpdir) / "test.db"
    url = f"sqlite:///{db_path}"
    old_env = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        yield url
    finally:
        if old_env is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_env
        if db_path.exists():
            db_path.unlink()
        Path(tmpdir).rmdir()


def _build_pre_phase4_baseline(url: str) -> None:
    """Build a pre-Phase-4 schema by copying only non-Phase-4 tables into a fresh MetaData.

    Avoids SQLite's inability to DROP a column that participates in an FK constraint.
    """
    from sqlalchemy import MetaData, Table, UniqueConstraint

    from src.database import Base
    import src.auth.models  # noqa: F401
    import src.repos.models  # noqa: F401
    import src.execution.models  # noqa: F401
    import src.environments.models  # noqa: F401
    import src.reports.models  # noqa: F401
    import src.stats.models  # noqa: F401
    import src.settings.models  # noqa: F401
    import src.teams.models  # noqa: F401
    import src.rate_limit  # noqa: F401

    phase4_table_names = set(PHASE4_TABLES)
    baseline_md = MetaData(naming_convention=Base.metadata.naming_convention)

    for t in Base.metadata.sorted_tables:
        if t.name in phase4_table_names:
            continue
        new_cols = []
        for col in t.columns:
            if t.name == "repositories" and col.name == "team_id":
                continue
            if t.name == "users" and col.name == "first_login_complete":
                continue
            new_cols.append(col.copy())
        new_constraints = []
        for ck in t.constraints:
            if isinstance(ck, UniqueConstraint):
                new_constraints.append(
                    UniqueConstraint(*[c.name for c in ck.columns], name=ck.name)
                )
        Table(t.name, baseline_md, *new_cols, *new_constraints)

    engine = create_engine(url, connect_args={"check_same_thread": False})
    baseline_md.create_all(engine)
    engine.dispose()


def test_phase4_migration_roundtrip(fresh_db):
    url = fresh_db
    _build_pre_phase4_baseline(url)

    cfg = _build_alembic_cfg(url)

    # Stamp to pre-Phase-4 head so alembic thinks the chain is at a3c7e1f82d4b.
    command.stamp(cfg, PRE_PHASE4_REV)

    engine = create_engine(url, connect_args={"check_same_thread": False})

    # --- UPGRADE ---
    command.upgrade(cfg, PHASE4_REV)

    insp = inspect(engine)
    existing = set(insp.get_table_names())
    for t in PHASE4_TABLES:
        assert t in existing, f"expected table {t} after upgrade"

    repo_cols = {c["name"] for c in insp.get_columns("repositories")}
    assert "team_id" in repo_cols

    user_cols = {c["name"] for c in insp.get_columns("users")}
    assert "first_login_complete" in user_cols

    # Seeded settings rows.
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT key, value, value_type, category FROM app_settings "
                 "WHERE category = 'auth' ORDER BY key")
        ).fetchall()
    keys = [r[0] for r in rows]
    for k in PHASE4_SETTING_KEYS:
        assert k in keys, f"expected seeded setting key {k}"
    by_key = {r[0]: r for r in rows}
    assert by_key["sso_emergency_bypass"][1] == "false"
    assert by_key["sso_emergency_bypass"][2] == "bool"
    assert by_key["deprovision_retention_days"][1] == "90"
    assert by_key["deprovision_retention_days"][2] == "int"
    assert by_key["admin_contact_email"][1] == "admin@roboscope.local"

    # --- DOWNGRADE ---
    command.downgrade(cfg, PRE_PHASE4_REV)

    insp = inspect(engine)
    existing = set(insp.get_table_names())
    for t in PHASE4_TABLES:
        assert t not in existing, f"expected table {t} to be dropped after downgrade"

    repo_cols = {c["name"] for c in insp.get_columns("repositories")}
    assert "team_id" not in repo_cols, "team_id should be removed after downgrade"

    user_cols = {c["name"] for c in insp.get_columns("users")}
    assert "first_login_complete" not in user_cols

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT key FROM app_settings WHERE key IN :keys").bindparams(
                sa.bindparam("keys", expanding=True)
            ),
            {"keys": list(PHASE4_SETTING_KEYS)},
        ).fetchall()
    assert rows == [], "Phase-4 seeded settings should be removed after downgrade"

    # --- UPGRADE AGAIN (idempotent round-trip) ---
    command.upgrade(cfg, PHASE4_REV)
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    for t in PHASE4_TABLES:
        assert t in existing

    engine.dispose()
