"""add unique constraint on environment_packages(environment_id, package_name)

Removes duplicate rows (keeping the highest-id record per pair) and then
adds a unique constraint so the MultipleResultsFound 500 error cannot recur.

Revision ID: f1a2b3c4d5e6
Revises: d5e8b2c1f7a3
Create Date: 2026-06-12 08:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "d5e8b2c1f7a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Delete duplicate rows, keeping only the row with the highest id for each
    # (environment_id, package_name) pair.  Works on both SQLite and PostgreSQL.
    conn.execute(
        sa.text(
            """
            DELETE FROM environment_packages
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM environment_packages
                GROUP BY environment_id, package_name
            )
            """
        )
    )

    with op.batch_alter_table("environment_packages") as batch_op:
        batch_op.create_unique_constraint(
            "uq_env_pkg", ["environment_id", "package_name"]
        )


def downgrade() -> None:
    with op.batch_alter_table("environment_packages") as batch_op:
        batch_op.drop_constraint("uq_env_pkg", type_="unique")
