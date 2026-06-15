"""add environment_keyword_cache table (Flow Editor — libdoc-per-environment)

Revision ID: d5e8b2c1f7a3
Revises: c0f1a9d2e4b8
Create Date: 2026-06-14 14:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d5e8b2c1f7a3"
down_revision: Union[str, None] = "c0f1a9d2e4b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "environment_keyword_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "environment_id",
            sa.Integer(),
            sa.ForeignKey("environments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="ready"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("keywords_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "environment_id", name="uq_environment_keyword_cache_env"
        ),
    )
    op.create_index(
        "ix_environment_keyword_cache_environment_id",
        "environment_keyword_cache",
        ["environment_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_environment_keyword_cache_environment_id",
        table_name="environment_keyword_cache",
    )
    op.drop_table("environment_keyword_cache")
