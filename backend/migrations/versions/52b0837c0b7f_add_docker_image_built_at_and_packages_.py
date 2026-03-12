"""add docker_image_built_at and packages_changed_at to environments

Revision ID: 52b0837c0b7f
Revises: 001_add_registry_urls
Create Date: 2026-03-12 18:29:53.073916
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52b0837c0b7f'
down_revision: Union[str, None] = '001_add_registry_urls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('environments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('docker_image_built_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('packages_changed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('environments', schema=None) as batch_op:
        batch_op.drop_column('packages_changed_at')
        batch_op.drop_column('docker_image_built_at')
