"""add court map link

Revision ID: 0013_add_court_map_link
Revises: 0012_allow_detached_play_availability_votes
Create Date: 2026-07-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0013_add_court_map_link'
down_revision = '0012_allow_detached_play_availability_votes'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('courts', sa.Column('map_link', sa.String(length=1024), nullable=True))


def downgrade():
    op.drop_column('courts', 'map_link')
