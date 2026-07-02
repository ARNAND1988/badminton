"""allow detached play availability votes

Revision ID: 0012_allow_detached_play_availability_votes
Revises: 0011_add_play_availability_attendee_details
Create Date: 2026-07-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0012_allow_detached_play_availability_votes'
down_revision = '0011_add_play_availability_attendee_details'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('play_availability_votes') as batch_op:
        batch_op.alter_column(
            'user_id',
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade():
    with op.batch_alter_table('play_availability_votes') as batch_op:
        batch_op.alter_column(
            'user_id',
            existing_type=sa.Integer(),
            nullable=False,
        )
