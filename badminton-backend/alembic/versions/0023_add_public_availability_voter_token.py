"""add public availability voter token

Revision ID: 0023_add_public_availability_voter_token
Revises: 0022_add_adhoc_payment_invoice_identity
Create Date: 2026-09-09 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0023_add_public_availability_voter_token'
down_revision = '0022_add_adhoc_payment_invoice_identity'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('play_availability_votes') as batch_op:
        batch_op.add_column(sa.Column('public_voter_token', sa.String(length=64), nullable=True))
        batch_op.create_index('ix_play_availability_votes_public_voter_token', ['public_voter_token'], unique=False)
        batch_op.create_unique_constraint(
            'uq_play_availability_public_voter_date',
            ['public_voter_token', 'play_date'],
        )


def downgrade():
    with op.batch_alter_table('play_availability_votes') as batch_op:
        batch_op.drop_constraint('uq_play_availability_public_voter_date', type_='unique')
        batch_op.drop_index('ix_play_availability_votes_public_voter_token')
        batch_op.drop_column('public_voter_token')
