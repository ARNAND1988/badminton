"""add whatsapp notification settings

Revision ID: 0014_add_whatsapp_notification_settings
Revises: 0013_add_court_map_link
Create Date: 2026-07-03
"""
from alembic import op
import sqlalchemy as sa

revision = '0014_add_whatsapp_notification_settings'
down_revision = '0013_add_court_map_link'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'whatsapp_notification_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_key', sa.String(length=64), nullable=False, unique=True),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template', sa.Text(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=True),
        sa.Column('send_to_group', sa.Boolean(), nullable=True),
        sa.Column('group_id', sa.String(length=255), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_table(
        'whatsapp_notification_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('setting_id', sa.Integer(), sa.ForeignKey('whatsapp_notification_settings.id'), nullable=True),
        sa.Column('event_key', sa.String(length=64), nullable=False),
        sa.Column('recipient', sa.String(length=255), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('response', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('whatsapp_notification_logs')
    op.drop_table('whatsapp_notification_settings')
