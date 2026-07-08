from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING
import json
from . import db


def _money_decimal(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


def rounded_up_cost_split(total_cost, split_count):
    split_count = int(split_count or 0)
    total = _money_decimal(total_cost)
    if split_count <= 0:
        return {
            'attended_count': 0,
            'cost_per_person': 0.0,
            'participant_shares': [],
            'total_cost': float(total),
            'rounded_total': 0.0,
            'rounding_adjustment': 0.0,
            'rounding_tolerance': 0.01,
        }
    share = (total / Decimal(split_count)).quantize(Decimal('0.01'), rounding=ROUND_CEILING)
    shares = [float(share)] * split_count
    rounded_total = (share * split_count).quantize(Decimal('0.01'))
    return {
        'attended_count': split_count,
        'cost_per_person': float(share),
        'participant_shares': shares,
        'total_cost': float(total),
        'rounded_total': float(rounded_total),
        'rounding_adjustment': float((total - rounded_total).quantize(Decimal('0.01'))),
        'rounding_tolerance': 0.01,
    }


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    whatsapp_number = db.Column(db.String(64), nullable=True)
    name = db.Column(db.String(128), nullable=True)
    role = db.Column(db.String(32), default='member')
    is_club_member = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'phone': self.phone,
            'email': self.email,
            'whatsapp_number': self.whatsapp_number,
            'name': self.name,
            'role': self.role,
            'is_club_member': self.is_club_member,
            'created_at': self.created_at.isoformat()
        }


class FamilyMember(db.Model):
    __tablename__ = 'family_members'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    relationship = db.Column(db.String(64), nullable=True)
    is_club_member = db.Column(db.Boolean, default=False)
    linked_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], backref='family_members', lazy=True)
    linked_user = db.relationship('User', foreign_keys=[linked_user_id], lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'relationship': self.relationship,
            'is_club_member': self.is_club_member,
            'linked_user_id': self.linked_user_id,
            'linked_user': self.linked_user.to_dict() if self.linked_user else None,
            'created_at': self.created_at.isoformat()
        }


class AdminAuditLog(db.Model):
    __tablename__ = 'admin_audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    occurred_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    admin_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    admin_name = db.Column(db.String(255), nullable=True)
    admin_email = db.Column(db.String(255), nullable=True)
    admin_phone = db.Column(db.String(64), nullable=True)
    event_type = db.Column(db.String(64), nullable=False)
    entity_type = db.Column(db.String(64), nullable=False)
    entity_id = db.Column(db.String(64), nullable=True)
    summary = db.Column(db.String(512), nullable=False)
    details = db.Column(db.Text, nullable=True)

    admin = db.relationship('User', lazy=True)

    def to_dict(self):
        try:
            details = json.loads(self.details or '{}')
        except Exception:
            details = {}
        return {
            'id': self.id,
            'occurred_at': self.occurred_at.isoformat() if self.occurred_at else None,
            'admin_user_id': self.admin_user_id,
            'admin_name': self.admin_name,
            'admin_email': self.admin_email,
            'admin_phone': self.admin_phone,
            'event_type': self.event_type,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'summary': self.summary,
            'details': details,
        }


class PlayAvailabilityVote(db.Model):
    __tablename__ = 'play_availability_votes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    play_date = db.Column(db.String(10), nullable=False)
    available = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(32), default='not_available')
    attendee_count = db.Column(db.Integer, default=0)
    attendee_details = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='availability_votes', lazy=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'play_date', name='uq_play_availability_user_date'),
    )

    def to_dict(self):
        try:
            attendee_details = json.loads(self.attendee_details or '[]')
        except Exception:
            attendee_details = []
        return {
            'id': self.id,
            'user_id': self.user_id,
            'play_date': self.play_date,
            'available': self.available,
            'status': self.status or ('available' if self.available else 'not_available'),
            'attendee_count': self.attendee_count,
            'attendee_details': attendee_details,
            'notes': self.notes,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Court(db.Model):
    __tablename__ = 'courts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    location = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    map_link = db.Column(db.String(1024), nullable=True)
    hourly_rate = db.Column(db.Float, default=25.0)
    half_hour_rate = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'description': self.description,
            'map_link': self.map_link,
            'hourly_rate': self.hourly_rate,
            'half_hour_rate': self.half_hour_rate if self.half_hour_rate is not None else round(float(self.hourly_rate or 0.0) / 2, 2),
            'is_active': self.is_active,
        }


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    court_id = db.Column(db.Integer, db.ForeignKey('courts.id'), nullable=False)
    booking_date = db.Column(db.String(10), nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    cost = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), default='confirmed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    court = db.relationship('Court', backref='bookings', lazy=True)

    def to_dict(self):
        attended = [participant for participant in self.participants if participant.status in {'attending', 'participated'}]
        split_count = len(attended)
        split = rounded_up_cost_split(self.cost, split_count)
        participant_cost_shares = {
            participant.id: split['participant_shares'][index]
            for index, participant in enumerate(attended)
        }
        return {
            'id': self.id,
            'court': self.court.to_dict() if self.court else None,
            'booking_date': self.booking_date,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'cost': self.cost,
            'notes': self.notes,
            'status': self.status,
            'participants': [participant.to_dict(participant_cost_shares.get(participant.id, 0.0)) for participant in self.participants],
            'cost_split': {
                'attended_count': split['attended_count'],
                'cost_per_person': split['cost_per_person'],
                'total_cost': split['total_cost'],
                'rounded_total': split['rounded_total'],
                'rounding_adjustment': split['rounding_adjustment'],
                'rounding_tolerance': split['rounding_tolerance'],
            },
            'invoice': self.invoice[0].to_dict() if self.invoice else None,
        }


class BookingParticipant(db.Model):
    __tablename__ = 'booking_participants'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    phone = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(128), nullable=True)
    status = db.Column(db.String(32), default='tentative')
    is_adhoc = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    booking = db.relationship('Booking', backref='participants', lazy=True)

    def to_dict(self, cost_share=0.0):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'phone': self.phone,
            'name': self.name,
            'status': self.status,
            'is_adhoc': self.is_adhoc,
            'cost_share': cost_share if self.status in {'attending', 'participated'} else 0.0,
        }


class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False, unique=True)
    total_amount = db.Column(db.Float, default=0.0)
    split_count = db.Column(db.Integer, default=1)
    status = db.Column(db.String(32), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    booking = db.relationship('Booking', backref='invoice', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'total_amount': self.total_amount,
            'split_count': self.split_count,
            'status': self.status,
        }



class PaymentSettings(db.Model):
    __tablename__ = 'payment_settings'
    id = db.Column(db.Integer, primary_key=True)
    account_holder_name = db.Column(db.String(128), nullable=True)
    bank_name = db.Column(db.String(128), nullable=True)
    iban = db.Column(db.String(64), nullable=True)
    bic = db.Column(db.String(32), nullable=True)
    description_prefix = db.Column(db.String(255), default='Nieuwegein Badminton Invoice')
    default_due_days = db.Column(db.Integer, default=14)
    qr_enabled = db.Column(db.Boolean, default=True)
    test_mode = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    updater = db.relationship('User', lazy=True)

    def effective_account_holder_name(self):
        return self.account_holder_name or ('Nieuwegein Badminton Test' if self.test_mode else '')

    def effective_bank_name(self):
        return self.bank_name or ('Test Bank' if self.test_mode else '')

    def effective_iban(self):
        return self.iban or ('NL02ABNA0123456789' if self.test_mode else '')

    def effective_bic(self):
        return self.bic or ('ABNANL2A' if self.test_mode else '')

    def to_dict(self, include_effective=False):
        payload = {
            'id': self.id,
            'account_holder_name': self.account_holder_name,
            'bank_name': self.bank_name,
            'iban': self.iban,
            'bic': self.bic,
            'description_prefix': self.description_prefix,
            'default_due_days': self.default_due_days,
            'qr_enabled': self.qr_enabled,
            'test_mode': self.test_mode,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'updated_by': self.updated_by,
        }
        if include_effective:
            payload.update({
                'effective_account_holder_name': self.effective_account_holder_name(),
                'effective_bank_name': self.effective_bank_name(),
                'effective_iban': self.effective_iban(),
                'effective_bic': self.effective_bic(),
            })
        return payload


class PaymentInvoice(db.Model):
    __tablename__ = 'payment_invoices'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    month = db.Column(db.String(7), nullable=True)
    invoice_number = db.Column(db.String(32), unique=True, nullable=False)
    payment_status = db.Column(db.String(32), default='UNPAID')
    payment_reference = db.Column(db.String(64), unique=True, nullable=False)
    amount_due = db.Column(db.Float, default=0.0)
    due_date = db.Column(db.String(10), nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    paid_amount = db.Column(db.Float, default=0.0)
    payment_note = db.Column(db.Text, nullable=True)
    qr_payload = db.Column(db.Text, nullable=True)
    qr_code_data_url = db.Column(db.Text, nullable=True)
    is_test_invoice = db.Column(db.Boolean, default=False)
    bank_account_holder = db.Column(db.String(128), nullable=True)
    bank_name = db.Column(db.String(128), nullable=True)
    iban = db.Column(db.String(64), nullable=True)
    bic = db.Column(db.String(32), nullable=True)
    booking_items_json = db.Column(db.Text, nullable=True)
    misc_items_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    user = db.relationship('User', foreign_keys=[user_id], lazy=True)
    updater = db.relationship('User', foreign_keys=[updated_by], lazy=True)

    def to_dict(self, include_qr=True):
        def loads(value):
            try:
                return json.loads(value or '[]')
            except Exception:
                return []
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user': self.user.to_dict() if self.user else None,
            'month': self.month,
            'invoice_number': self.invoice_number,
            'payment_status': self.payment_status,
            'payment_reference': self.payment_reference,
            'amount_due': round(float(self.amount_due or 0.0), 2),
            'due_date': self.due_date,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'paid_amount': round(float(self.paid_amount or 0.0), 2),
            'payment_note': self.payment_note,
            'qr_payload': self.qr_payload,
            'qr_code_data_url': self.qr_code_data_url if include_qr else None,
            'is_test_invoice': self.is_test_invoice,
            'account_holder_name': self.bank_account_holder,
            'bank_name': self.bank_name,
            'iban': self.iban,
            'bic': self.bic,
            'booking_items': loads(self.booking_items_json),
            'misc_items': loads(self.misc_items_json),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'updated_by': self.updated_by,
        }


class MonthlyInvoiceStatus(db.Model):
    __tablename__ = 'monthly_invoice_statuses'
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(7), unique=True, nullable=False)
    status = db.Column(db.String(32), default='OPEN', nullable=False)
    ready_at = db.Column(db.DateTime, nullable=True)
    settled_at = db.Column(db.DateTime, nullable=True)
    note = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    updater = db.relationship('User', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'month': self.month,
            'status': self.status,
            'ready_at': self.ready_at.isoformat() if self.ready_at else None,
            'settled_at': self.settled_at.isoformat() if self.settled_at else None,
            'note': self.note,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'updated_by': self.updated_by,
        }


class PaymentAuditLog(db.Model):
    __tablename__ = 'payment_audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('payment_invoices.id'), nullable=False)
    old_status = db.Column(db.String(32), nullable=True)
    new_status = db.Column(db.String(32), nullable=False)
    amount = db.Column(db.Float, nullable=True)
    note = db.Column(db.Text, nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    invoice = db.relationship('PaymentInvoice', backref='audit_logs', lazy=True)
    updater = db.relationship('User', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'invoice_id': self.invoice_id,
            'old_status': self.old_status,
            'new_status': self.new_status,
            'amount': self.amount,
            'note': self.note,
            'updated_by': self.updated_by,
            'updated_by_name': self.updater.name if self.updater else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class MiscCost(db.Model):
    __tablename__ = 'misc_costs'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    amount = db.Column(db.Float, default=0.0)
    paid_by = db.Column(db.String(128), nullable=True)
    purchase_date = db.Column(db.String(10), nullable=True)
    split_count = db.Column(db.Integer, default=1)
    status = db.Column(db.String(32), default='open')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        split_count = max(1, int(self.split_count or 1))
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'amount': self.amount,
            'paid_by': self.paid_by,
            'purchase_date': self.purchase_date,
            'split_count': split_count,
            'cost_per_person': round(float(self.amount or 0.0) / split_count, 2),
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class CourtFreezePeriod(db.Model):
    __tablename__ = 'court_freeze_periods'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    start_date = db.Column(db.String(10), nullable=False)
    end_date = db.Column(db.String(10), nullable=False)
    reason = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'reason': self.reason,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class WhatsAppNotificationSetting(db.Model):
    __tablename__ = 'whatsapp_notification_settings'
    id = db.Column(db.Integer, primary_key=True)
    event_key = db.Column(db.String(64), unique=True, nullable=False)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    template = db.Column(db.Text, nullable=False)
    is_enabled = db.Column(db.Boolean, default=False)
    send_to_group = db.Column(db.Boolean, default=True)
    group_id = db.Column(db.String(255), nullable=True)
    test_recipient_number = db.Column(db.String(64), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'event_key': self.event_key,
            'title': self.title,
            'description': self.description,
            'template': self.template,
            'is_enabled': self.is_enabled,
            'send_to_group': self.send_to_group,
            'group_id': self.group_id,
            'test_recipient_number': self.test_recipient_number,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class WhatsAppNotificationLog(db.Model):
    __tablename__ = 'whatsapp_notification_logs'
    id = db.Column(db.Integer, primary_key=True)
    setting_id = db.Column(db.Integer, db.ForeignKey('whatsapp_notification_settings.id'), nullable=True)
    event_key = db.Column(db.String(64), nullable=False)
    recipient = db.Column(db.String(255), nullable=True)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), default='queued')
    response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    setting = db.relationship('WhatsAppNotificationSetting', backref='logs', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'setting_id': self.setting_id,
            'event_key': self.event_key,
            'recipient': self.recipient,
            'message': self.message,
            'status': self.status,
            'response': self.response,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
