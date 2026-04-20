"""phase 4 sso and teams

Adds OIDC SSO, Team/IdP infrastructure, first-login tracking, and a persistent
rate-limit counter. Also seeds four new Phase-4 rows into `app_settings`
(NOT columns — `app_settings` is a key-value table).

Revision ID: b4d2e1a9c3f7
Revises: a3c7e1f82d4b
Create Date: 2026-04-15 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4d2e1a9c3f7"
down_revision: Union[str, None] = "a3c7e1f82d4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PHASE4_SETTING_KEYS = (
    "sso_emergency_bypass",
    "sso_emergency_bypass_expires_at",
    "deprovision_retention_days",
    "admin_contact_email",
)

_PHASE4_SETTINGS_ROWS = [
    {
        "key": "sso_emergency_bypass",
        "value": "false",
        "value_type": "bool",
        "category": "auth",
        "description": "Enable local-login fallback during SSO outage.",
    },
    {
        "key": "sso_emergency_bypass_expires_at",
        "value": "",
        "value_type": "string",
        "category": "auth",
        "description": "ISO-8601 auto-expiry for emergency bypass (empty = inactive).",
    },
    {
        "key": "deprovision_retention_days",
        "value": "90",
        "value_type": "int",
        "category": "auth",
        "description": "Days before deprovisioned-user cleanup.",
    },
    {
        "key": "admin_contact_email",
        "value": "admin@roboscope.local",
        "value_type": "string",
        "category": "auth",
        "description": "Displayed on SSO outage screen as admin contact.",
    },
]


def upgrade() -> None:
    # 1. identity_providers
    op.create_table(
        "identity_providers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("provider_type", sa.String(length=30), nullable=False),
        sa.Column("issuer_url", sa.String(length=500), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column(
            "scopes", sa.String(length=500), nullable=False,
            server_default="openid profile email",
        ),
        sa.Column(
            "group_claim_name", sa.String(length=100), nullable=False,
            server_default="groups",
        ),
        sa.Column(
            "is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("discovery_cache_json", sa.Text(), nullable=True),
        sa.Column("discovery_cached_at", sa.DateTime(), nullable=True),
        sa.Column("last_dry_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_dry_run_status", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_identity_providers_name", "identity_providers", ["name"], unique=True
    )

    # 2. teams
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_teams_name", "teams", ["name"], unique=True)
    op.create_index("ix_teams_external_id", "teams", ["external_id"])

    # 3. team_members (FK -> teams, users)
    op.create_table(
        "team_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "role", sa.String(length=20), nullable=False, server_default="viewer"
        ),
        sa.Column(
            "source", sa.String(length=20), nullable=False, server_default="manual"
        ),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"],
            name="fk_team_members_team_id_teams", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_team_members_user_id_users", ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "team_id", "user_id", name="uq_team_members_team_user"
        ),
    )
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"])
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"])

    # 4. idp_group_mappings (FK -> identity_providers, teams)
    op.create_table(
        "idp_group_mappings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("idp_id", sa.Integer(), nullable=False),
        sa.Column("group_claim_value", sa.String(length=255), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column(
            "role", sa.String(length=20), nullable=False, server_default="viewer"
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["idp_id"], ["identity_providers.id"],
            name="fk_idp_group_mappings_idp_id_identity_providers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"],
            name="fk_idp_group_mappings_team_id_teams", ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "idp_id", "group_claim_value", name="uq_idp_group_mappings_idp_group"
        ),
    )
    op.create_index(
        "ix_idp_group_mappings_idp_id", "idp_group_mappings", ["idp_id"]
    )
    op.create_index(
        "ix_idp_group_mappings_team_id", "idp_group_mappings", ["team_id"]
    )

    # 5. oidc_login_attempts
    op.create_table(
        "oidc_login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("state", sa.String(length=128), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("pkce_verifier", sa.String(length=128), nullable=False),
        sa.Column("idp_id", sa.Integer(), nullable=False),
        sa.Column(
            "return_to", sa.String(length=500), nullable=False, server_default="/"
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["idp_id"], ["identity_providers.id"],
            name="fk_oidc_login_attempts_idp_id_identity_providers",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_oidc_login_attempts_state", "oidc_login_attempts", ["state"], unique=True
    )
    op.create_index(
        "ix_oidc_login_attempts_expires_at",
        "oidc_login_attempts",
        ["expires_at"],
    )

    # 6. rate_limit_counters
    op.create_table(
        "rate_limit_counters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bucket_key", sa.String(length=255), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column(
            "count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.UniqueConstraint(
            "bucket_key", "window_start",
            name="uq_rate_limit_counters_bucket_window",
        ),
    )
    op.create_index(
        "ix_rate_limit_counters_window_start",
        "rate_limit_counters",
        ["window_start"],
    )

    # 7. repositories.team_id (nullable FK)
    with op.batch_alter_table("repositories") as batch_op:
        batch_op.add_column(
            sa.Column("team_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_repositories_team_id_teams",
            "teams",
            ["team_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_repositories_team_id", "repositories", ["team_id"])

    # 8. users.first_login_complete (NOT NULL, default FALSE) — backfill existing rows
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "first_login_complete",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    # 9. Seed Phase-4 rows into app_settings (key-value table).
    #    NOTE: app_settings is NOT columnar — architecture text was aspirational.
    #    Guard against duplicate-key violations: seed_default_settings() may have already
    #    inserted these rows on fresh installs (app started before alembic upgrade ran).
    settings_tbl = sa.table(
        "app_settings",
        sa.column("key", sa.String),
        sa.column("value", sa.Text),
        sa.column("value_type", sa.String),
        sa.column("category", sa.String),
        sa.column("description", sa.Text),
    )
    bind = op.get_bind()
    existing_keys = {
        row[0]
        for row in bind.execute(
            sa.select(sa.column("key"))
            .select_from(settings_tbl)
            .where(sa.column("key").in_(_PHASE4_SETTING_KEYS))
        ).fetchall()
    }
    rows_to_insert = [r for r in _PHASE4_SETTINGS_ROWS if r["key"] not in existing_keys]
    if rows_to_insert:
        op.bulk_insert(settings_tbl, rows_to_insert)


def downgrade() -> None:
    # Delete Phase-4 seeded settings rows.
    settings_tbl = sa.table("app_settings", sa.column("key", sa.String))
    op.execute(
        sa.delete(settings_tbl).where(sa.column("key").in_(_PHASE4_SETTING_KEYS))
    )

    # Drop users.first_login_complete
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("first_login_complete")

    # Drop repositories.team_id (+ FK + index — all inside batch for atomicity)
    with op.batch_alter_table("repositories") as batch_op:
        batch_op.drop_index("ix_repositories_team_id")
        batch_op.drop_constraint(
            "fk_repositories_team_id_teams", type_="foreignkey"
        )
        batch_op.drop_column("team_id")

    # Drop tables in reverse order (respect FKs).
    op.drop_index(
        "ix_rate_limit_counters_window_start", table_name="rate_limit_counters"
    )
    op.drop_table("rate_limit_counters")

    op.drop_index(
        "ix_oidc_login_attempts_expires_at", table_name="oidc_login_attempts"
    )
    op.drop_index(
        "ix_oidc_login_attempts_state", table_name="oidc_login_attempts"
    )
    op.drop_table("oidc_login_attempts")

    op.drop_index(
        "ix_idp_group_mappings_team_id", table_name="idp_group_mappings"
    )
    op.drop_index(
        "ix_idp_group_mappings_idp_id", table_name="idp_group_mappings"
    )
    op.drop_table("idp_group_mappings")

    op.drop_index("ix_team_members_user_id", table_name="team_members")
    op.drop_index("ix_team_members_team_id", table_name="team_members")
    op.drop_table("team_members")

    op.drop_index("ix_teams_external_id", table_name="teams")
    op.drop_index("ix_teams_name", table_name="teams")
    op.drop_table("teams")

    op.drop_index(
        "ix_identity_providers_name", table_name="identity_providers"
    )
    op.drop_table("identity_providers")
