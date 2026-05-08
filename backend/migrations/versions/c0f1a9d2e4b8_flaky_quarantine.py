"""add flaky_quarantine table (story FLAKY-1)

Revision ID: c0f1a9d2e4b8
Revises: b4d2e1a9c3f7
Create Date: 2026-04-24 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c0f1a9d2e4b8"
down_revision: Union[str, None] = "b4d2e1a9c3f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flaky_quarantine",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "repository_id",
            sa.Integer(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("suite_name", sa.String(500), nullable=False),
        sa.Column("test_name", sa.String(500), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "quarantined_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "quarantined_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "repository_id",
            "suite_name",
            "test_name",
            name="uq_flaky_quarantine_repo_suite_test",
        ),
    )
    op.create_index(
        "ix_flaky_quarantine_repository_id",
        "flaky_quarantine",
        ["repository_id"],
    )
    op.create_index(
        "ix_flaky_quarantine_suite_name",
        "flaky_quarantine",
        ["suite_name"],
    )
    op.create_index(
        "ix_flaky_quarantine_test_name",
        "flaky_quarantine",
        ["test_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_flaky_quarantine_test_name", table_name="flaky_quarantine")
    op.drop_index("ix_flaky_quarantine_suite_name", table_name="flaky_quarantine")
    op.drop_index("ix_flaky_quarantine_repository_id", table_name="flaky_quarantine")
    op.drop_table("flaky_quarantine")
