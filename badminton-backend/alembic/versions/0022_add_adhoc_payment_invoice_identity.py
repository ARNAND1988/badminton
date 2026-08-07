"""add ad hoc payment invoice identity

Revision ID: 0022_adhoc_invoice_identity
Revises: 0021_add_monthly_tikkie_links
"""
from alembic import op
import sqlalchemy as sa


revision = '0022_adhoc_invoice_identity'
down_revision = '0021_add_monthly_tikkie_links'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('payment_invoices', sa.Column('subject_key', sa.String(length=255), nullable=True))
    op.add_column('payment_invoices', sa.Column('billing_name', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('payment_invoices', 'billing_name')
    op.drop_column('payment_invoices', 'subject_key')
