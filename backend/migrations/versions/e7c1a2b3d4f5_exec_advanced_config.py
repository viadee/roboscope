"""EXEC.2: advanced_config on execution_runs + advanced_config/variables on schedules

Adds nullable JSON-string columns for advanced robot execution config and
brings the Schedule table to parity with ExecutionRun (it previously carried
neither variables nor advanced config). All columns are nullable with no
server default, so existing rows load unchanged.

Revision ID: e7c1a2b3d4f5
Revises: f1a2b3c4d5e6
Create Date: 2026-06-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e7c1a2b3d4f5'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('execution_runs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('advanced_config', sa.Text(), nullable=True))

    with op.batch_alter_table('schedules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('variables', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('advanced_config', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('schedules', schema=None) as batch_op:
        batch_op.drop_column('advanced_config')
        batch_op.drop_column('variables')

    with op.batch_alter_table('execution_runs', schema=None) as batch_op:
        batch_op.drop_column('advanced_config')
