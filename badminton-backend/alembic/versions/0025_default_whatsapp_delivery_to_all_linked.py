"""default WhatsApp family delivery to all linked numbers

Revision ID: 0025_whatsapp_all_linked
Revises: 0024_whatsapp_family_links
"""
from alembic import op
import sqlalchemy as sa


revision = '0025_whatsapp_all_linked'
down_revision = '0024_whatsapp_family_links'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE whatsapp_notification_preferences SET delivery_mode = 'ALL_LINKED' WHERE delivery_mode = 'PRIMARY_ONLY'")
    op.alter_column('whatsapp_notification_preferences', 'delivery_mode', server_default='ALL_LINKED', existing_type=sa.String(16), nullable=False)


def downgrade():
    op.execute("UPDATE whatsapp_notification_preferences SET delivery_mode = 'PRIMARY_ONLY' WHERE delivery_mode = 'ALL_LINKED'")
    op.alter_column('whatsapp_notification_preferences', 'delivery_mode', server_default='PRIMARY_ONLY', existing_type=sa.String(16), nullable=False)
