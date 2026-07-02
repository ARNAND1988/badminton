from datetime import datetime
import json
from . import db


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='family_members', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'relationship': self.relationship,
            'is_club_member': self.is_club_member,
            'created_at': self.created_at.isoformat()
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
    hourly_rate = db.Column(db.Float, default=25.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'description': self.description,
            'hourly_rate': self.hourly_rate,
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
        attended = [participant for participant in self.participants if participant.status == 'attending']
        split_count = len(attended)
        cost_per_person = round(float(self.cost or 0.0) / split_count, 2) if split_count else 0.0
        return {
            'id': self.id,
            'court': self.court.to_dict() if self.court else None,
            'booking_date': self.booking_date,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'cost': self.cost,
            'notes': self.notes,
            'status': self.status,
            'participants': [participant.to_dict(cost_per_person) for participant in self.participants],
            'cost_split': {
                'attended_count': split_count,
                'cost_per_person': cost_per_person,
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
            'cost_share': cost_share if self.status == 'attending' else 0.0,
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
