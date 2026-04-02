"""replace vault_name with encrypted_pat

Revision ID: c7a2e1f09b4d
Revises: b5fabaedf83a
Create Date: 2026-03-20 08:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7a2e1f09b4d'
down_revision: Union[str, Sequence[str], None] = 'b5fabaedf83a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('intunecd_tenants', sa.Column('encrypted_pat', sa.String(), nullable=True))
    op.drop_column('intunecd_tenants', 'vault_name')


def downgrade() -> None:
    op.add_column('intunecd_tenants', sa.Column('vault_name', sa.String(), nullable=True))
    op.drop_column('intunecd_tenants', 'encrypted_pat')
