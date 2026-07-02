"""add play availability status

Revision ID: 0010_add_play_availability_status
Revises: 0009_add_club_member_flags
Create Date: 2026-07-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0010_add_play_availability_status'
down_revision = '0009_add_club_member_flags'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('play_availability_votes') as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=32), nullable=True, server_default='not_available'))

    op.execute("UPDATE play_availability_votes SET status = CASE WHEN available THEN 'available' ELSE 'not_available' END")


def downgrade():
    with op.batch_alter_table('play_availability_votes') as batch_op:
        batch_op.drop_column('status')
