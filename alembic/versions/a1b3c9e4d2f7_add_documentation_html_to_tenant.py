"""add documentation_html to tenant

Revision ID: a1b3c9e4d2f7
Revises: c7a2e1f09b4d
Create Date: 2026-03-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b3c9e4d2f7'
down_revision: Union[str, Sequence[str], None] = 'c7a2e1f09b4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('intunecd_tenants', sa.Column('documentation_html', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('intunecd_tenants', 'documentation_html')
