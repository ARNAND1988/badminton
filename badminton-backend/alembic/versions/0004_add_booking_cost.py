from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('bookings', sa.Column('cost', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('bookings', 'cost')
