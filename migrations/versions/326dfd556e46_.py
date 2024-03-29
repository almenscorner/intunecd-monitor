"""empty message

Revision ID: 326dfd556e46
Revises: 3a8c28fde990
Create Date: 2023-10-06 15:41:22.551351

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '326dfd556e46'
down_revision = '3a8c28fde990'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('intunecd_tenants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('create_documentation', sa.String(), nullable=True))

    with op.batch_alter_table('summary_average_diffs', schema=None) as batch_op:
        batch_op.alter_column('average_diffs',
               existing_type=sa.INTEGER(),
               type_=sa.Float(),
               existing_nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('summary_average_diffs', schema=None) as batch_op:
        batch_op.alter_column('average_diffs',
               existing_type=sa.Float(),
               type_=sa.INTEGER(),
               existing_nullable=True)

    with op.batch_alter_table('intunecd_tenants', schema=None) as batch_op:
        batch_op.drop_column('create_documentation')

    # ### end Alembic commands ###
