from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('courts', sa.Column('location', sa.String(length=255), nullable=True))
    op.add_column('courts', sa.Column('description', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('courts', 'description')
    op.drop_column('courts', 'location')
