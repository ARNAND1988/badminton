"""add monthly Tikkie payment details

Revision ID: 0021_add_monthly_tikkie_links
Revises: 0020_add_monthly_payment_method
"""

from alembic import op
import sqlalchemy as sa


revision = '0021_add_monthly_tikkie_links'
down_revision = '0020_add_monthly_payment_method'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('monthly_invoice_statuses', sa.Column('tikkie_payment_url', sa.String(length=1024), nullable=True))
    op.add_column('monthly_invoice_statuses', sa.Column('tikkie_account_holder_name', sa.String(length=128), nullable=True))


def downgrade():
    op.drop_column('monthly_invoice_statuses', 'tikkie_account_holder_name')
    op.drop_column('monthly_invoice_statuses', 'tikkie_payment_url')
