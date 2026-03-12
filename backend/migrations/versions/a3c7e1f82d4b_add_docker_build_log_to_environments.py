"""add docker_build_log to environments

Revision ID: a3c7e1f82d4b
Revises: 9bf996e4380f
Create Date: 2026-03-12 20:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c7e1f82d4b'
down_revision: Union[str, None] = '9bf996e4380f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('environments', sa.Column('docker_build_log', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('environments', 'docker_build_log')
