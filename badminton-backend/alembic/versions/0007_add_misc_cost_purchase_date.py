from alembic import op
import sqlalchemy as sa


revision = '0007_add_misc_cost_purchase_date'
down_revision = '0006_add_attendance_and_misc_costs'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('misc_costs', sa.Column('purchase_date', sa.String(length=10), nullable=True))


def downgrade():
    op.drop_column('misc_costs', 'purchase_date')
