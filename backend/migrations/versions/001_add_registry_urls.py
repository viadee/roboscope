"""Add index_url and extra_index_url to environments.

Revision ID: 001_add_registry_urls
Revises:
Create Date: 2026-03-09
"""

from alembic import op
import sqlalchemy as sa

revision = "001_add_registry_urls"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("environments") as batch_op:
        batch_op.add_column(sa.Column("index_url", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("extra_index_url", sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("environments") as batch_op:
        batch_op.drop_column("extra_index_url")
        batch_op.drop_column("index_url")
