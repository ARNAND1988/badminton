"""add personal Tikkie and monthly payment method snapshots

Revision ID: 0020_add_monthly_payment_method
Revises: 0019_add_misc_cost_split_scope
"""
from alembic import op
import sqlalchemy as sa

revision = '0020_add_monthly_payment_method'
down_revision = '0019_add_misc_cost_split_scope'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('payment_settings', sa.Column('tikkie_payment_url', sa.String(length=1024)))
    op.add_column('payment_settings', sa.Column('tikkie_account_holder_name', sa.String(length=128)))
    op.add_column('monthly_invoice_statuses', sa.Column('payment_method', sa.String(length=32), nullable=False, server_default='BUSINESS_BANK'))
    op.add_column('payment_invoices', sa.Column('payment_method', sa.String(length=32), nullable=False, server_default='BUSINESS_BANK'))


def downgrade():
    op.drop_column('payment_invoices', 'payment_method')
    op.drop_column('monthly_invoice_statuses', 'payment_method')
    op.drop_column('payment_settings', 'tikkie_account_holder_name')
    op.drop_column('payment_settings', 'tikkie_payment_url')
