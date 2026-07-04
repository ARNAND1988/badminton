"""add admin audit logs

Revision ID: 0015_add_admin_audit_logs
Revises: 0014_add_whatsapp_notification_settings
Create Date: 2026-07-04
"""
from alembic import op
import sqlalchemy as sa

revision = '0015_add_admin_audit_logs'
down_revision = '0014_add_whatsapp_notification_settings'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'admin_audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('admin_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('admin_name', sa.String(length=255), nullable=True),
        sa.Column('admin_email', sa.String(length=255), nullable=True),
        sa.Column('admin_phone', sa.String(length=64), nullable=True),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=True),
        sa.Column('summary', sa.String(length=512), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
    )
    op.create_index('ix_admin_audit_logs_occurred_at', 'admin_audit_logs', ['occurred_at'])
    op.create_index('ix_admin_audit_logs_entity', 'admin_audit_logs', ['entity_type', 'entity_id'])


def downgrade():
    op.drop_index('ix_admin_audit_logs_entity', table_name='admin_audit_logs')
    op.drop_index('ix_admin_audit_logs_occurred_at', table_name='admin_audit_logs')
    op.drop_table('admin_audit_logs')
