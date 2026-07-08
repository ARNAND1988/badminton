"""add whatsapp notification test recipient number

Revision ID: 0016_add_whatsapp_test_recipient_number
Revises: 0015_add_admin_audit_logs
Create Date: 2026-07-08
"""
from alembic import op
import sqlalchemy as sa

revision = '0016_add_whatsapp_test_recipient_number'
down_revision = '0015_add_admin_audit_logs'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('whatsapp_notification_settings') as batch_op:
        batch_op.add_column(sa.Column('test_recipient_number', sa.String(length=64), nullable=True))


def downgrade():
    with op.batch_alter_table('whatsapp_notification_settings') as batch_op:
        batch_op.drop_column('test_recipient_number')
