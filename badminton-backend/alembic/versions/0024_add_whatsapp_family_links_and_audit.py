"""add WhatsApp family links, preferences, and availability audit

Revision ID: 0024_whatsapp_family_links
Revises: 0023_add_public_availability_voter_token
"""
from alembic import op
import sqlalchemy as sa


revision = '0024_whatsapp_family_links'
down_revision = '0023_add_public_availability_voter_token'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'whatsapp_account_links',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, unique=True),
        sa.Column('whatsapp_number', sa.String(64), nullable=False, unique=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('notifications_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        'whatsapp_notification_preferences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_owner_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, unique=True),
        sa.Column('delivery_mode', sa.String(16), nullable=False, server_default='PRIMARY_ONLY'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("delivery_mode IN ('PRIMARY_ONLY', 'ALL_LINKED')", name='ck_whatsapp_delivery_mode'),
    )
    op.create_table(
        'whatsapp_availability_audits',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_owner_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('play_date', sa.String(10), nullable=False),
        sa.Column('previous_attendee_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('attendee_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_whatsapp_availability_family_date', 'whatsapp_availability_audits', ['family_owner_user_id', 'play_date'])


def downgrade():
    op.drop_index('ix_whatsapp_availability_family_date', table_name='whatsapp_availability_audits')
    op.drop_table('whatsapp_availability_audits')
    op.drop_table('whatsapp_notification_preferences')
    op.drop_table('whatsapp_account_links')
