from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('booking_participants', sa.Column('name', sa.String(length=128), nullable=True))
    op.add_column('booking_participants', sa.Column('status', sa.String(length=32), nullable=True, server_default='tentative'))
    op.add_column('booking_participants', sa.Column('is_adhoc', sa.Boolean(), nullable=True, server_default=sa.false()))
    op.create_table(
        'misc_costs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('paid_by', sa.String(length=128), nullable=True),
        sa.Column('split_count', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('misc_costs')
    op.drop_column('booking_participants', 'is_adhoc')
    op.drop_column('booking_participants', 'status')
    op.drop_column('booking_participants', 'name')
