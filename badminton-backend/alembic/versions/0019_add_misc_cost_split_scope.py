"""add misc cost split scope

Revision ID: 0019_add_misc_cost_split_scope
Revises: 0017_add_payment_invoices
Create Date: 2026-07-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = '0019_add_misc_cost_split_scope'
down_revision = '0017_add_payment_invoices'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('misc_costs', sa.Column('split_scope', sa.String(length=32), server_default='manual'))


def downgrade():
    op.drop_column('misc_costs', 'split_scope')
