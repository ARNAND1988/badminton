"""add club member flags

Revision ID: 0009_add_club_member_flags
Revises: 0008_email_password_auth
Create Date: 2026-07-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0009_add_club_member_flags'
down_revision = '0008_email_password_auth'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('is_club_member', sa.Boolean(), nullable=True, server_default=sa.false()))

    with op.batch_alter_table('family_members') as batch_op:
        batch_op.add_column(sa.Column('is_club_member', sa.Boolean(), nullable=True, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('family_members') as batch_op:
        batch_op.drop_column('is_club_member')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('is_club_member')
