"""add payment settings and payment invoices

Revision ID: 0017_add_payment_invoices
Revises: 0016_link_family_members_to_users, 0016_add_whatsapp_test_recipient_number
Create Date: 2026-07-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '0017_add_payment_invoices'
down_revision = ('0016_link_family_members_to_users', '0016_add_whatsapp_test_recipient_number')
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('payment_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_holder_name', sa.String(length=128)),
        sa.Column('bank_name', sa.String(length=128)),
        sa.Column('iban', sa.String(length=64)),
        sa.Column('bic', sa.String(length=32)),
        sa.Column('description_prefix', sa.String(length=255)),
        sa.Column('default_due_days', sa.Integer()),
        sa.Column('qr_enabled', sa.Boolean()),
        sa.Column('test_mode', sa.Boolean()),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id')),
    )
    op.create_table('payment_invoices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('month', sa.String(length=7)),
        sa.Column('invoice_number', sa.String(length=32), nullable=False, unique=True),
        sa.Column('payment_status', sa.String(length=32)),
        sa.Column('payment_reference', sa.String(length=64), nullable=False, unique=True),
        sa.Column('amount_due', sa.Float()),
        sa.Column('due_date', sa.String(length=10)),
        sa.Column('paid_at', sa.DateTime()),
        sa.Column('paid_amount', sa.Float()),
        sa.Column('payment_note', sa.Text()),
        sa.Column('qr_payload', sa.Text()),
        sa.Column('qr_code_data_url', sa.Text()),
        sa.Column('is_test_invoice', sa.Boolean()),
        sa.Column('bank_account_holder', sa.String(length=128)),
        sa.Column('bank_name', sa.String(length=128)),
        sa.Column('iban', sa.String(length=64)),
        sa.Column('bic', sa.String(length=32)),
        sa.Column('booking_items_json', sa.Text()),
        sa.Column('misc_items_json', sa.Text()),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id')),
    )
    op.create_table('payment_audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('payment_invoices.id'), nullable=False),
        sa.Column('old_status', sa.String(length=32)),
        sa.Column('new_status', sa.String(length=32), nullable=False),
        sa.Column('amount', sa.Float()),
        sa.Column('note', sa.Text()),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime()),
    )


def downgrade():
    op.drop_table('payment_audit_logs')
    op.drop_table('payment_invoices')
    op.drop_table('payment_settings')
