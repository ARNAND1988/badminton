"""link family members to registered users

Revision ID: 0016_link_family_members_to_users
Revises: 0015_add_admin_audit_logs
Create Date: 2026-07-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '0016_link_family_members_to_users'
down_revision = '0015_add_admin_audit_logs'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('family_members') as batch_op:
        batch_op.add_column(sa.Column('linked_user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_family_members_linked_user_id_users', 'users', ['linked_user_id'], ['id'])


def downgrade():
    with op.batch_alter_table('family_members') as batch_op:
        batch_op.drop_constraint('fk_family_members_linked_user_id_users', type_='foreignkey')
        batch_op.drop_column('linked_user_id')
