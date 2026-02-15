"""initial create users table

Revision ID: 0001_initial
Revises: 
Create Date: 2026-02-15 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('phone', sa.String(length=64), nullable=False, unique=True),
        sa.Column('name', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('users')
