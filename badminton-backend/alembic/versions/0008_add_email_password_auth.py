"""add email password auth fields

Revision ID: 0008_email_password_auth
Revises: 0007_misc_cost_purchase_date
Create Date: 2026-07-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0008_email_password_auth'
down_revision = '0007_add_misc_cost_purchase_date'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('password_hash', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('whatsapp_number', sa.String(length=64), nullable=True))


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('whatsapp_number')
        batch_op.drop_column('password_hash')
