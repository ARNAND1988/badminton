"""Add verified WhatsApp member links, rate limits and inbound deduplication."""

from alembic import op
import sqlalchemy as sa


revision = '0026_whatsapp_member_links'
down_revision = '0025_whatsapp_all_linked'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'whatsapp_member_links',
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('identity', sa.String(128), unique=True),
        sa.Column('code_digest', sa.String(64), unique=True),
        sa.Column('code_expires_at', sa.DateTime),
    )
    op.create_table(
        'whatsapp_inbound_events',
        sa.Column('event_digest', sa.String(64), primary_key=True),
    )
    op.create_table(
        'whatsapp_link_rate_limits',
        sa.Column('key', sa.String(64), primary_key=True),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('attempts', sa.Integer, nullable=False),
    )


def downgrade():
    op.drop_table('whatsapp_link_rate_limits')
    op.drop_table('whatsapp_inbound_events')
    op.drop_table('whatsapp_member_links')
