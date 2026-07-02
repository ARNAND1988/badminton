"""add play availability attendee details

Revision ID: 0011_add_play_availability_attendee_details
Revises: 0010_add_play_availability_status
Create Date: 2026-07-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0011_add_play_availability_attendee_details'
down_revision = '0010_add_play_availability_status'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('play_availability_votes') as batch_op:
        batch_op.add_column(sa.Column('attendee_details', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('play_availability_votes') as batch_op:
        batch_op.drop_column('attendee_details')
