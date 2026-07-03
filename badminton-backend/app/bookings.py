from datetime import datetime, timedelta
import json

from flask import Blueprint, jsonify, request, current_app
import jwt

from . import db
from .models import Booking, BookingParticipant, Court, CourtFreezePeriod, FamilyMember, Invoice, MiscCost, PlayAvailabilityVote, User

bookings_bp = Blueprint('bookings', __name__)


def _get_current_user():
    auth_header = request.headers.get('Authorization', '')
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return None

    try:
        payload = jwt.decode(parts[1], current_app.config.get('JWT_SECRET'), algorithms=['HS256'])
    except Exception:
        return None

    user_id = payload.get('user_id')
    if not user_id:
        return None
    return User.query.get(user_id)


def _require_login():
    user = _get_current_user()
    if not user:
        return None, (jsonify({'error': 'missing_authorization'}), 401)
    return user, None


def _require_admin():
    user, error = _require_login()
    if error:
        return None, error
    if user.role != 'admin':
        return None, (jsonify({'error': 'admin_required'}), 403)
    return user, None


def _next_dates(count=7):
    today = datetime.utcnow().date()
    return [today + timedelta(days=index) for index in range(count)]


def _parse_iso_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except Exception:
        return None


def _date_is_frozen(date_value):
    return CourtFreezePeriod.query.filter(
        CourtFreezePeriod.is_active.is_(True),
        CourtFreezePeriod.start_date <= date_value,
        CourtFreezePeriod.end_date >= date_value,
    ).first()


def _next_playable_dates(count=7, start=None):
    current = start or datetime.utcnow().date()
    dates = []
    checked = 0
    while len(dates) < count and checked < 370:
        date_value = current.strftime('%Y-%m-%d')
        if not _date_is_frozen(date_value):
            dates.append(current)
        current += timedelta(days=1)
        checked += 1
    return dates


def _next_weekend_dates(count=4):
    today = datetime.utcnow().date()
    days_until_saturday = (5 - today.weekday()) % 7
    first_saturday = today + timedelta(days=days_until_saturday)
    dates = []
    current = first_saturday
    while len(dates) < count:
        dates.extend([current, current + timedelta(days=1)])
        current += timedelta(days=7)
    return dates[:count]


def _slot_overlaps(court_id, booking_date, start_time, end_time, exclude_booking_id=None):
    existing = Booking.query.filter_by(booking_date=booking_date, court_id=court_id).all()
    for booking in existing:
        if exclude_booking_id and booking.id == exclude_booking_id:
            continue
        if not (end_time <= booking.start_time or start_time >= booking.end_time):
            return True
    return False


def _valid_participant_status(status):
    return status in {'attending', 'not_attending', 'tentative'}


def _valid_availability_status(status):
    return status in {'available', 'tentative', 'not_available'}


def _month_bounds(month_value):
    try:
        start = datetime.strptime(month_value, '%Y-%m').date()
    except Exception:
        return None, None
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')


def _time_to_minutes(value):
    try:
        hours, minutes = [int(part) for part in (value or '').split(':')]
    except Exception:
        return None
    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
        return None
    return hours * 60 + minutes


def _booking_duration_minutes(start_time, end_time):
    start = _time_to_minutes(start_time)
    end = _time_to_minutes(end_time)
    if start is None or end is None or end <= start:
        return None
    return end - start


def _calculated_booking_cost(court, start_time, end_time):
    duration = _booking_duration_minutes(start_time, end_time)
    if duration is None:
        raise ValueError('end_time must be after start_time')
    hourly_rate = float(court.hourly_rate or 0.0)
    half_hour_rate = float(court.half_hour_rate if court.half_hour_rate is not None else hourly_rate / 2)
    hours, remainder = divmod(duration, 60)
    half_hours = (remainder + 29) // 30
    return round((hours * hourly_rate) + (half_hours * half_hour_rate), 2)


def _participant_keys_for_user(user):
    keys = {user.phone}
    for member in user.family_members:
        keys.add(f'family:{member.id}')
    return keys


def _monthly_invoice_summary(user, month_value):
    start_date, end_date = _month_bounds(month_value)
    if not start_date:
        return None

    participant_keys = _participant_keys_for_user(user)
    booking_items = []
    booking_total = 0.0
    bookings = (
        Booking.query
        .filter(Booking.booking_date >= start_date, Booking.booking_date < end_date)
        .order_by(Booking.booking_date.asc(), Booking.start_time.asc())
        .all()
    )
    for booking in bookings:
        attending = [participant for participant in booking.participants if participant.status == 'attending']
        matching = [participant for participant in attending if participant.phone in participant_keys]
        if not matching:
            continue
        split_count = max(1, len(attending) or 1)
        per_person = round(float(booking.cost or 0.0) / split_count, 2)
        amount = round(per_person * len(matching), 2)
        booking_total += amount
        booking_items.append({
            'booking_id': booking.id,
            'date': booking.booking_date,
            'court': booking.court.name if booking.court else None,
            'start_time': booking.start_time,
            'end_time': booking.end_time,
            'attendee_count': len(matching),
            'cost_per_person': per_person,
            'amount': amount,
            'invoice_status': booking.invoice[0].status if booking.invoice else 'not_generated',
        })

    misc_items = []
    misc_total = 0.0
    misc_costs = (
        MiscCost.query
        .filter(MiscCost.purchase_date >= start_date, MiscCost.purchase_date < end_date)
        .order_by(MiscCost.purchase_date.asc(), MiscCost.created_at.asc())
        .all()
    )
    for cost in misc_costs:
        split_count = max(1, int(cost.split_count or 1))
        amount = round(float(cost.amount or 0.0) / split_count, 2)
        misc_total += amount
        misc_items.append({
            'cost_id': cost.id,
            'title': cost.title,
            'purchase_date': cost.purchase_date,
            'status': cost.status,
            'split_count': split_count,
            'amount': amount,
        })

    total = round(booking_total + misc_total, 2)
    return {
        'user': user.to_dict(),
        'month': month_value,
        'booking_items': booking_items,
        'misc_items': misc_items,
        'booking_total': round(booking_total, 2),
        'misc_total': round(misc_total, 2),
        'total': total,
    }


def _availability_attendee_payload(user, attendees, default_status='available'):
    family_members = {
        member.id: member for member in FamilyMember.query.filter_by(user_id=user.id).all()
    }
    selected = []
    for attendee in attendees or []:
        status = attendee.get('status') or default_status
        if status == 'not_available':
            continue
        if not _valid_availability_status(status):
            raise ValueError('invalid_status')
        attendee_type = attendee.get('type')
        if attendee_type == 'self':
            selected.append({
                'type': 'self',
                'status': status,
                'name': user.name or user.email or user.phone,
                'phone': user.phone,
            })
            continue
        if attendee_type == 'family':
            member_id = attendee.get('family_member_id')
            member = family_members.get(member_id)
            if not member:
                raise ValueError('family_member_not_found')
            selected.append({
                'type': 'family',
                'status': status,
                'family_member_id': member.id,
                'name': member.name,
            })
    return selected


def _admin_user_payload(user):
    payload = user.to_dict()
    payload['family_members'] = [
        member.to_dict()
        for member in sorted(user.family_members, key=lambda item: item.created_at or datetime.min)
    ]
    return payload


def _is_completed_booking(booking, today_value=None):
    today_value = today_value or datetime.utcnow().date().strftime('%Y-%m-%d')
    return booking.status == 'completed' or booking.booking_date < today_value


def _archive_cutoff_date():
    """Bookings before the current month are archived.

    From July 2026 onward this keeps this month's completed bookings in the
    active settlement list while moving bookings through June 2026 to archive.
    """
    today = datetime.utcnow().date()
    return today.replace(day=1).strftime('%Y-%m-%d')


def _booking_payload(booking, today_value=None):
    payload = booking.to_dict()
    if _is_completed_booking(booking, today_value):
        payload['status'] = 'completed'
    return payload


def _positive_int_arg(name, default, minimum=1, maximum=None):
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _ensure_upcoming_booking_data():
    """Keep the booking page populated after long-lived databases age out seeded rows."""
    today = datetime.utcnow().date()
    today_value = today.strftime('%Y-%m-%d')
    upcoming_exists = Booking.query.filter(
        Booking.booking_date >= today_value,
        Booking.status != 'completed'
    ).first()
    if upcoming_exists:
        return

    court_specs = [
        ('Court 1', 'Nieuwegein Sports Centre', 'Main indoor badminton court near reception', 25.0),
        ('Court 2', 'Nieuwegein Sports Centre', 'Second indoor court for doubles practice', 22.5),
        ('Training Court', 'Nieuwegein Sports Centre', 'Smaller court for warmups and junior sessions', 18.0),
    ]
    court_names = [spec[0] for spec in court_specs]
    courts_by_name = {
        court.name: court
        for court in Court.query.filter(Court.name.in_(court_names)).all()
    }
    for name, location, description, hourly_rate in court_specs:
        court = courts_by_name.get(name)
        if not court:
            court = Court(name=name)
            db.session.add(court)
            courts_by_name[name] = court
        court.location = court.location or location
        court.description = court.description or description
        court.hourly_rate = court.hourly_rate or hourly_rate
        court.half_hour_rate = court.half_hour_rate if court.half_hour_rate is not None else round(float(court.hourly_rate or hourly_rate) / 2, 2)
        court.is_active = True if court.is_active is None else court.is_active
    db.session.flush()

    booking_specs = [
        (
            'Court 1', today + timedelta(days=1), '19:00', '20:00',
            25.0, 'Evening doubles practice', ['+31611111111', '+31622222222']
        ),
        (
            'Court 2', today + timedelta(days=3), '10:00', '12:00',
            45.0, 'Weekend family session', ['+31611111111', '+31633333333']
        ),
        (
            'Training Court', today + timedelta(days=7), '18:30', '19:30',
            18.0, 'Junior warmup slot', []
        ),
    ]
    for (
        court_name, date_value, start_time, end_time, cost, notes, participants
    ) in booking_specs:
        court = courts_by_name.get(court_name)
        target_date = date_value.strftime('%Y-%m-%d')
        existing = Booking.query.filter_by(
            court_id=court.id,
            booking_date=target_date,
            start_time=start_time,
            end_time=end_time
        ).first()
        if existing:
            continue
        booking = Booking(
            court_id=court.id,
            booking_date=target_date,
            start_time=start_time,
            end_time=end_time,
            cost=cost,
            notes=notes,
            status='confirmed'
        )
        db.session.add(booking)
        db.session.flush()
        for phone in participants:
            _upsert_participant(booking, phone, status='tentative')
    db.session.commit()


def _ensure_historical_booking_data():
    """Backfill imported historical rental bookings for existing databases.

    The Kubernetes SQL init script only runs for fresh database volumes. Long-lived
    databases that predate that data still need the historical completed bookings
    when the Costs page asks for completed booking settlement history.
    """
    historical_court_specs = {
        'Gymzaal de Driemaster': 19.25,
        'Sportzaal De Sluis': 25.50,
        'Sportzaal Wijkersloot': 25.50,
        'Gymzaal de Triangel': 19.25,
    }
    courts_by_name = {
        court.name: court
        for court in Court.query.filter(Court.name.in_(historical_court_specs.keys())).all()
    }
    for name, hourly_rate in historical_court_specs.items():
        court = courts_by_name.get(name)
        if not court:
            court = Court(name=name)
            db.session.add(court)
            courts_by_name[name] = court
        court.location = court.location or name
        court.description = court.description or 'Historical booking location'
        court.hourly_rate = court.hourly_rate or hourly_rate
        court.half_hour_rate = court.half_hour_rate if court.half_hour_rate is not None else round(float(court.hourly_rate or hourly_rate) / 2, 2)
        court.is_active = True if court.is_active is None else court.is_active
    db.session.flush()

    historical_bookings = [
        ('2025-10-19', '17:00', '18:30', 'Gymzaal de Driemaster', 28.88, datetime(2025, 10, 12, 19, 19)),
        ('2025-10-26', '16:00', '18:00', 'Gymzaal de Driemaster', 38.50, datetime(2025, 10, 19, 18, 11)),
        ('2025-11-08', '18:00', '20:00', 'Sportzaal De Sluis', 51.00, datetime(2025, 11, 1, 19, 32)),
        ('2025-11-15', '17:30', '19:30', 'Sportzaal De Sluis', 51.00, datetime(2025, 11, 8, 19, 48)),
        ('2025-11-23', '16:00', '18:00', 'Sportzaal Wijkersloot', 51.00, datetime(2025, 11, 15, 20, 10)),
        ('2025-11-29', '17:00', '18:30', 'Sportzaal De Sluis', 38.25, datetime(2025, 11, 24, 20, 48)),
        ('2025-12-06', '17:00', '19:00', 'Sportzaal Wijkersloot', 51.00, datetime(2025, 11, 30, 22, 7)),
        ('2025-12-13', '18:00', '19:00', 'Gymzaal de Driemaster', 19.25, datetime(2025, 12, 12, 20, 50)),
        ('2026-01-03', '17:00', '18:00', 'Gymzaal de Driemaster', 19.25, datetime(2025, 12, 31, 17, 30)),
        ('2026-01-17', '17:00', '18:30', 'Sportzaal De Sluis', 38.25, datetime(2026, 1, 15, 9, 43)),
        ('2026-01-24', '16:00', '17:00', 'Sportzaal De Sluis', 25.50, datetime(2026, 1, 22, 16, 28)),
        ('2026-01-31', '17:30', '19:00', 'Sportzaal De Sluis', 38.25, datetime(2026, 1, 28, 8, 52)),
        ('2026-02-07', '17:30', '18:30', 'Sportzaal De Sluis', 25.50, datetime(2026, 2, 3, 16, 16)),
        ('2026-02-07', '19:00', '20:00', 'Sportzaal De Sluis', 25.50, datetime(2026, 2, 3, 16, 18)),
        ('2026-02-14', '18:00', '19:00', 'Sportzaal De Sluis', 25.50, datetime(2026, 2, 9, 21, 56)),
        ('2026-02-14', '19:30', '20:30', 'Sportzaal De Sluis', 25.50, datetime(2026, 2, 9, 21, 58)),
        ('2026-02-17', '21:00', '22:00', 'Gymzaal de Driemaster', 19.25, datetime(2026, 2, 15, 18, 54)),
        ('2026-02-21', '18:00', '19:00', 'Sportzaal De Sluis', 25.50, datetime(2026, 2, 18, 20, 54)),
        ('2026-02-21', '19:30', '20:30', 'Sportzaal De Sluis', 25.50, datetime(2026, 2, 18, 20, 55)),
        ('2026-02-27', '21:00', '22:00', 'Gymzaal de Driemaster', 19.25, datetime(2026, 2, 24, 16, 21)),
        ('2026-02-28', '17:30', '18:30', 'Sportzaal De Sluis', 25.50, datetime(2026, 2, 26, 15, 16)),
        ('2026-03-07', '20:00', '21:00', 'Gymzaal de Driemaster', 19.25, datetime(2026, 3, 3, 20, 15)),
        ('2026-03-15', '16:30', '18:00', 'Gymzaal de Triangel', 28.88, datetime(2026, 3, 10, 9, 4)),
        ('2026-03-21', '17:00', '18:00', 'Gymzaal de Driemaster', 19.25, datetime(2026, 3, 18, 17, 35)),
        ('2026-03-28', '17:30', '19:00', 'Sportzaal De Sluis', 38.25, datetime(2026, 3, 25, 13, 43)),
        ('2026-04-11', '18:00', '19:00', 'Gymzaal de Driemaster', 19.25, datetime(2026, 4, 9, 10, 15)),
        ('2026-04-18', '18:30', '19:30', 'Gymzaal de Driemaster', 19.25, datetime(2026, 4, 16, 21, 34)),
        ('2026-05-03', '18:00', '19:00', 'Gymzaal de Driemaster', 19.25, datetime(2026, 5, 2, 14, 23)),
        ('2026-05-04', '18:00', '19:00', 'Gymzaal de Driemaster', 19.25, datetime(2026, 5, 3, 23, 33)),
        ('2026-05-10', '18:30', '20:00', 'Sportzaal De Sluis', 38.25, datetime(2026, 5, 9, 19, 59)),
        ('2026-05-16', '18:30', '19:30', 'Gymzaal de Driemaster', 19.25, datetime(2026, 5, 16, 13, 34)),
        ('2026-06-07', '16:00', '18:00', 'Sportzaal Wijkersloot', 51.00, datetime(2026, 6, 4, 10, 9)),
        ('2026-06-13', '17:30', '19:00', 'Sportzaal De Sluis', 38.25, datetime(2026, 6, 9, 20, 17)),
        ('2026-06-19', '18:00', '19:00', 'Gymzaal de Driemaster', 19.25, datetime(2026, 6, 19, 17, 33)),
        ('2026-06-20', '17:00', '18:00', 'Gymzaal de Driemaster', 19.25, datetime(2026, 6, 17, 20, 34)),
        ('2026-06-20', '18:00', '19:00', 'Gymzaal de Driemaster', 19.25, datetime(2026, 6, 18, 19, 1)),
        ('2026-06-26', '20:00', '21:00', 'Gymzaal de Driemaster', 19.25, datetime(2026, 6, 26, 9, 23)),
        ('2026-06-28', '17:00', '18:00', 'Gymzaal de Driemaster', 19.25, datetime(2026, 6, 27, 21, 0)),
    ]

    for booking_date, start_time, end_time, court_name, cost, created_at in historical_bookings:
        court = courts_by_name[court_name]
        booking = Booking.query.filter_by(
            court_id=court.id,
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_time,
        ).first()
        if not booking:
            booking = Booking(
                court_id=court.id,
                booking_date=booking_date,
                start_time=start_time,
                end_time=end_time,
                notes='Historical booking imported from invoiced rental data',
                created_at=created_at,
            )
            db.session.add(booking)
            db.session.flush()
        booking.cost = cost
        booking.status = 'completed'
        if booking.invoice:
            invoice = booking.invoice[0]
        else:
            invoice = Invoice(booking_id=booking.id)
            db.session.add(invoice)
        invoice.total_amount = cost
        invoice.split_count = 1
        invoice.status = 'settled'
    db.session.commit()


def _upsert_participant(booking, phone, name=None, status='tentative', is_adhoc=False):
    normalized_phone = (phone or '').strip()
    if not normalized_phone:
        raise ValueError('phone required')
    if not _valid_participant_status(status):
        raise ValueError('invalid_status')

    participant = BookingParticipant.query.filter_by(
        booking_id=booking.id,
        phone=normalized_phone
    ).first()
    if not participant:
        participant = BookingParticipant(booking_id=booking.id, phone=normalized_phone)
        db.session.add(participant)

    participant.name = (name or participant.name or '').strip() or None
    participant.status = status
    participant.is_adhoc = bool(is_adhoc)
    return participant


@bookings_bp.route('/bookings/availability', methods=['GET'])
def availability():
    date_value = request.args.get('date')
    if not date_value:
        return jsonify({'error': 'date required'}), 400

    courts = Court.query.filter_by(is_active=True).all()
    slots = []
    for court in courts:
        existing = Booking.query.filter_by(booking_date=date_value, court_id=court.id).all()
        booked_ranges = [(b.start_time, b.end_time) for b in existing]
        slots.append({
            'court_id': court.id,
            'court_name': court.name,
            'hourly_rate': court.hourly_rate,
            'booked': booked_ranges,
            'available': True,
        })
    return jsonify({'date': date_value, 'slots': slots})


@bookings_bp.route('/family-members', methods=['GET'])
def list_family_members():
    user, error = _require_login()
    if error:
        return error

    members = FamilyMember.query.filter_by(user_id=user.id).order_by(FamilyMember.created_at.asc()).all()
    return jsonify({'members': [member.to_dict() for member in members]})


@bookings_bp.route('/family-members', methods=['POST'])
def create_family_member():
    user, error = _require_login()
    if error:
        return error

    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400

    member = FamilyMember(
        user_id=user.id,
        name=name,
    )
    db.session.add(member)
    db.session.commit()
    return jsonify(member.to_dict())


@bookings_bp.route('/family-members/<int:member_id>', methods=['DELETE'])
def delete_family_member(member_id):
    user, error = _require_login()
    if error:
        return error

    member = FamilyMember.query.filter_by(id=member_id, user_id=user.id).first_or_404()
    db.session.delete(member)
    db.session.commit()
    return jsonify({'status': 'deleted'})


@bookings_bp.route('/play-availability', methods=['GET'])
def list_play_availability():
    user = _get_current_user()

    start_date = request.args.get('start_date')
    days = min(max(int(request.args.get('days', 7) or 7), 1), 14)
    if start_date:
        start = _parse_iso_date(start_date)
        if not start:
            return jsonify({'error': 'invalid_start_date'}), 400
        dates = _next_playable_dates(days, start=start)
    else:
        dates = _next_playable_dates(days)

    date_values = [date_value.strftime('%Y-%m-%d') for date_value in dates]
    votes = PlayAvailabilityVote.query.filter(
        PlayAvailabilityVote.play_date.in_(date_values)
    ).all()
    user_votes = {vote.play_date: vote for vote in votes if user and vote.user_id == user.id}

    totals = {}
    for vote in votes:
        if vote.play_date not in totals:
            totals[vote.play_date] = {
                'available_families': 0,
                'tentative_families': 0,
                'attendee_count': 0,
                'available_count': 0,
                'tentative_count': 0,
                'available_attendees': [],
                'tentative_attendees': [],
            }
        vote_payload = vote.to_dict()
        vote_attendees = vote_payload.get('attendee_details') or []
        available_attendees = [
            attendee for attendee in vote_attendees
            if attendee.get('status', 'available') == 'available'
        ]
        tentative_attendees = [
            attendee for attendee in vote_attendees
            if attendee.get('status') == 'tentative'
        ]
        vote_status = vote.status or ('available' if vote.available else 'not_available')
        if available_attendees:
            totals[vote.play_date]['available_families'] += 1
            totals[vote.play_date]['attendee_count'] += len(available_attendees)
            totals[vote.play_date]['available_count'] += len(available_attendees)
            totals[vote.play_date]['available_attendees'].extend(available_attendees)
        elif vote_status == 'available':
            totals[vote.play_date]['available_families'] += 1
            totals[vote.play_date]['attendee_count'] += vote.attendee_count or 0
            totals[vote.play_date]['available_count'] += vote.attendee_count or 0
        if tentative_attendees:
            totals[vote.play_date]['tentative_families'] += 1
            totals[vote.play_date]['tentative_count'] += len(tentative_attendees)
            totals[vote.play_date]['tentative_attendees'].extend(tentative_attendees)
        elif vote_status == 'tentative':
            totals[vote.play_date]['tentative_families'] += 1
            totals[vote.play_date]['tentative_count'] += vote.attendee_count or 0

    days_payload = []
    for date_value in date_values:
        vote = user_votes.get(date_value)
        days_payload.append({
            'date': date_value,
            'weekday': datetime.strptime(date_value, '%Y-%m-%d').strftime('%A'),
            'vote': vote.to_dict() if vote else None,
            'totals': totals.get(date_value, {
                'available_families': 0,
                'tentative_families': 0,
                'attendee_count': 0,
                'available_count': 0,
                'tentative_count': 0,
                'available_attendees': [],
                'tentative_attendees': [],
            }),
        })

    return jsonify({'days': days_payload})


@bookings_bp.route('/play-availability', methods=['POST'])
def save_play_availability():
    user, error = _require_login()
    if error:
        return error

    data = request.get_json() or {}
    play_date = data.get('play_date')
    if not play_date:
        return jsonify({'error': 'play_date required'}), 400

    status = data.get('status')
    if not status:
        status = 'available' if bool(data.get('available', False)) else 'not_available'
    if not _valid_availability_status(status):
        return jsonify({'error': 'invalid_status'}), 400

    try:
        attendee_details = _availability_attendee_payload(user, data.get('attendees') or [], default_status=status)
    except ValueError as exc:
        status_code = 404 if str(exc) == 'family_member_not_found' else 400
        return jsonify({'error': str(exc)}), status_code

    available_count = len([
        attendee for attendee in attendee_details
        if attendee.get('status', 'available') == 'available'
    ])
    tentative_count = len([
        attendee for attendee in attendee_details
        if attendee.get('status') == 'tentative'
    ])

    if attendee_details:
        status = 'available' if available_count else 'tentative' if tentative_count else 'not_available'

    if not attendee_details and status == 'available':
        attendee_count = int(data.get('attendee_count', 0) or 0)
        if attendee_count < 0:
            return jsonify({'error': 'attendee_count must be zero or greater'}), 400
    else:
        attendee_count = available_count

    vote = PlayAvailabilityVote.query.filter_by(user_id=user.id, play_date=play_date).first()
    if not vote:
        vote = PlayAvailabilityVote(user_id=user.id, play_date=play_date)
        db.session.add(vote)

    vote.status = status
    vote.available = available_count > 0 or (status == 'available' and not attendee_details)
    vote.attendee_count = attendee_count if vote.available else 0
    vote.attendee_details = json.dumps(attendee_details) if attendee_details else None
    vote.notes = (data.get('notes') or '').strip() or None
    db.session.commit()

    return jsonify(vote.to_dict())


@bookings_bp.route('/bookings', methods=['POST'])
def create_booking():
    user, error = _require_admin()
    if error:
        return error

    data = request.get_json() or {}
    court_id = data.get('court_id')
    booking_date = data.get('booking_date')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    manual_cost = bool(data.get('manual_cost', False))
    cost = data.get('cost')
    notes = data.get('notes', '')
    participants = data.get('participants', []) or []
    recurring = bool(data.get('recurring', False))
    recurring_interval_weeks = int(data.get('recurring_interval_weeks', 1) or 1)
    recurring_count = int(data.get('recurring_count', 1) or 1)
    recurring_end_date = data.get('recurring_end_date') or data.get('end_date')

    if not all([court_id, booking_date, start_time, end_time]):
        return jsonify({'error': 'court_id, booking_date, start_time and end_time are required'}), 400

    court = Court.query.get(court_id)
    if not court:
        return jsonify({'error': 'court_not_found'}), 404
    try:
        calculated_cost = _calculated_booking_cost(court, start_time, end_time)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    booking_cost = float(cost or 0.0) if manual_cost and cost is not None else calculated_cost

    def _create_single_booking(target_date):
        if _slot_overlaps(court_id, target_date, start_time, end_time):
            raise ValueError('slot_unavailable')

        booking = Booking(
            court_id=court_id,
            booking_date=target_date,
            start_time=start_time,
            end_time=end_time,
            cost=booking_cost,
            notes=notes,
            status='confirmed'
        )
        db.session.add(booking)
        db.session.flush()

        for participant_phone in participants:
            if participant_phone:
                _upsert_participant(booking, participant_phone, status='tentative')

        return booking

    created_bookings = []
    try:
        if recurring:
            current_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
            stop_date = _parse_iso_date(recurring_end_date) if recurring_end_date else None
            if recurring_end_date and not stop_date:
                return jsonify({'error': 'recurring_end_date must use YYYY-MM-DD'}), 400
            if stop_date and stop_date < current_date:
                return jsonify({'error': 'recurring_end_date must be on or after booking_date'}), 400
            if stop_date:
                while current_date <= stop_date:
                    booking = _create_single_booking(current_date.strftime('%Y-%m-%d'))
                    created_bookings.append(booking)
                    current_date += timedelta(weeks=recurring_interval_weeks)
            else:
                for index in range(recurring_count):
                    booking = _create_single_booking(current_date.strftime('%Y-%m-%d'))
                    created_bookings.append(booking)
                    current_date += timedelta(weeks=recurring_interval_weeks)
            if not created_bookings:
                return jsonify({'error': 'no_bookings_generated'}), 400
        else:
            booking = _create_single_booking(booking_date)
            created_bookings.append(booking)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 409

    db.session.commit()
    for booking in created_bookings:
        _send_whatsapp_event('booking_created', _booking_notification_context(booking))
    return jsonify(created_bookings[-1].to_dict())


@bookings_bp.route('/bookings/<int:booking_id>', methods=['PUT'])
def update_booking(booking_id):
    user, error = _require_admin()
    if error:
        return error

    booking = Booking.query.get_or_404(booking_id)
    data = request.get_json() or {}

    court_id = data.get('court_id', booking.court_id)
    booking_date = data.get('booking_date', booking.booking_date)
    start_time = data.get('start_time', booking.start_time)
    end_time = data.get('end_time', booking.end_time)

    if not all([court_id, booking_date, start_time, end_time]):
        return jsonify({'error': 'court_id, booking_date, start_time and end_time are required'}), 400

    court = Court.query.get(court_id)
    if not court:
        return jsonify({'error': 'court_not_found'}), 404

    if _slot_overlaps(court_id, booking_date, start_time, end_time, exclude_booking_id=booking.id):
        return jsonify({'error': 'slot_unavailable'}), 409

    try:
        calculated_cost = _calculated_booking_cost(court, start_time, end_time)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    booking.court_id = court_id
    booking.booking_date = booking_date
    booking.start_time = start_time
    booking.end_time = end_time
    booking.cost = float(data.get('cost', booking.cost) or 0.0) if data.get('manual_cost') else calculated_cost
    booking.notes = data.get('notes', booking.notes)
    booking.status = data.get('status', booking.status or 'confirmed')
    db.session.commit()

    return jsonify(booking.to_dict())


@bookings_bp.route('/bookings/<int:booking_id>', methods=['DELETE'])
def delete_booking(booking_id):
    user, error = _require_admin()
    if error:
        return error

    booking = Booking.query.get_or_404(booking_id)
    _send_whatsapp_event('booking_cancelled', _booking_notification_context(booking))
    Invoice.query.filter_by(booking_id=booking.id).delete()
    BookingParticipant.query.filter_by(booking_id=booking.id).delete()
    db.session.delete(booking)
    db.session.commit()
    return jsonify({'status': 'deleted', 'id': booking_id})


@bookings_bp.route('/bookings', methods=['GET'])
def list_bookings():
    _ensure_upcoming_booking_data()
    status_filter = (request.args.get('status') or '').strip().lower()
    today_value = datetime.utcnow().date().strftime('%Y-%m-%d')
    page = _positive_int_arg('page', 1)
    per_page = _positive_int_arg('per_page', 25, maximum=100)

    if status_filter in {'completed', 'archive'}:
        user, error = _require_login()
        if error:
            return error
        _ensure_historical_booking_data()
        completed_filter = db.or_(Booking.status == 'completed', Booking.booking_date < today_value)
        if status_filter == 'archive':
            query = Booking.query.filter(
                completed_filter,
                Booking.booking_date < _archive_cutoff_date()
            ).order_by(Booking.booking_date.desc(), Booking.start_time.desc())
        else:
            query = Booking.query.filter(
                completed_filter,
                Booking.booking_date >= _archive_cutoff_date()
            ).order_by(Booking.booking_date.desc(), Booking.start_time.desc())
    elif status_filter == 'upcoming':
        query = Booking.query.filter(
            Booking.booking_date >= today_value,
            Booking.status != 'completed'
        ).order_by(Booking.booking_date.asc(), Booking.start_time.asc())
    else:
        query = Booking.query.order_by(Booking.booking_date.asc(), Booking.start_time.asc())

    total = query.count()
    bookings = query.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'bookings': [_booking_payload(b, today_value) for b in bookings],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page if total else 0,
        }
    })


@bookings_bp.route('/bookings/<int:booking_id>/rsvp', methods=['POST'])
def save_booking_rsvp(booking_id):
    user, error = _require_login()
    if error:
        return error

    booking = Booking.query.get_or_404(booking_id)
    data = request.get_json() or {}
    status = data.get('status', 'tentative')
    if not _valid_participant_status(status):
        return jsonify({'error': 'invalid_status'}), 400

    participant = _upsert_participant(
        booking,
        user.phone,
        name=user.name,
        status=status,
        is_adhoc=False
    )
    db.session.commit()
    return jsonify(participant.to_dict())


@bookings_bp.route('/bookings/<int:booking_id>/family-attendance', methods=['POST'])
def save_booking_family_attendance(booking_id):
    user, error = _require_login()
    if error:
        return error

    booking = Booking.query.get_or_404(booking_id)
    data = request.get_json() or {}
    attendees = data.get('attendees', []) or []
    family_members = {
        member.id: member for member in FamilyMember.query.filter_by(user_id=user.id).all()
    }

    saved = []
    for attendee in attendees:
        attendee_type = attendee.get('type')
        status = attendee.get('status', 'not_attending')
        if not _valid_participant_status(status):
            return jsonify({'error': 'invalid_status'}), 400

        if attendee_type == 'self':
            saved.append(_upsert_participant(
                booking,
                user.phone,
                name=user.name,
                status=status,
                is_adhoc=False
            ))
            continue

        if attendee_type == 'family':
            member_id = attendee.get('family_member_id')
            member = family_members.get(member_id)
            if not member:
                return jsonify({'error': 'family_member_not_found'}), 404
            saved.append(_upsert_participant(
                booking,
                f'family:{member.id}',
                name=member.name,
                status=status,
                is_adhoc=False
            ))

    db.session.commit()
    return jsonify({'participants': [participant.to_dict() for participant in saved]})


@bookings_bp.route('/bookings/<int:booking_id>/participants', methods=['POST'])
def add_booking_participant(booking_id):
    user, error = _require_admin()
    if error:
        return error

    booking = Booking.query.get_or_404(booking_id)
    data = request.get_json() or {}
    try:
        participant = _upsert_participant(
            booking,
            data.get('phone'),
            name=data.get('name'),
            status=data.get('status', 'attending'),
            is_adhoc=data.get('is_adhoc', True)
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    db.session.commit()
    return jsonify(participant.to_dict())


@bookings_bp.route('/bookings/<int:booking_id>/participants/<int:participant_id>', methods=['PUT'])
def update_booking_participant(booking_id, participant_id):
    user, error = _require_admin()
    if error:
        return error

    Booking.query.get_or_404(booking_id)
    participant = BookingParticipant.query.filter_by(id=participant_id, booking_id=booking_id).first_or_404()
    data = request.get_json() or {}
    status = data.get('status', participant.status)
    if not _valid_participant_status(status):
        return jsonify({'error': 'invalid_status'}), 400

    participant.name = (data.get('name', participant.name) or '').strip() or None
    participant.phone = (data.get('phone', participant.phone) or '').strip()
    participant.status = status
    if 'is_adhoc' in data:
        participant.is_adhoc = bool(data.get('is_adhoc'))
    db.session.commit()
    return jsonify(participant.to_dict())


@bookings_bp.route('/bookings/<int:booking_id>/participants/<int:participant_id>', methods=['DELETE'])
def delete_booking_participant(booking_id, participant_id):
    user, error = _require_admin()
    if error:
        return error

    participant = BookingParticipant.query.filter_by(id=participant_id, booking_id=booking_id).first_or_404()
    db.session.delete(participant)
    db.session.commit()
    return jsonify({'status': 'deleted'})


@bookings_bp.route('/bookings/<int:booking_id>/invoice', methods=['POST'])
def generate_invoice(booking_id):
    user, error = _require_admin()
    if error:
        return error

    booking = Booking.query.get_or_404(booking_id)
    invoice = Invoice.query.filter_by(booking_id=booking_id).first()
    if not invoice:
        invoice = Invoice(booking_id=booking.id)
        db.session.add(invoice)

    court = booking.court
    total_amount = float(booking.cost or court.hourly_rate if court else 0.0)
    attended_count = len([participant for participant in booking.participants if participant.status == 'attending'])
    invoice.total_amount = total_amount
    invoice.split_count = max(1, attended_count or 1)
    invoice.status = invoice.status if invoice.status == 'settled' else 'generated'
    db.session.commit()
    return jsonify(invoice.to_dict())


@bookings_bp.route('/bookings/<int:booking_id>/settle', methods=['POST'])
def settle_booking_cost(booking_id):
    user, error = _require_admin()
    if error:
        return error

    booking = Booking.query.get_or_404(booking_id)
    attended_count = len([participant for participant in booking.participants if participant.status == 'attending'])
    invoice = Invoice.query.filter_by(booking_id=booking.id).first()
    if not invoice:
        invoice = Invoice(booking_id=booking.id)
        db.session.add(invoice)
    invoice.total_amount = float(booking.cost or 0.0)
    invoice.split_count = max(1, attended_count or 1)
    invoice.status = 'settled'
    db.session.commit()
    return jsonify(invoice.to_dict())


@bookings_bp.route('/misc-costs', methods=['GET'])
def list_misc_costs():
    user, error = _require_login()
    if error:
        return error

    costs = MiscCost.query.order_by(MiscCost.created_at.desc()).all()
    return jsonify({'costs': [cost.to_dict() for cost in costs]})


@bookings_bp.route('/misc-costs', methods=['POST'])
def create_misc_cost():
    user, error = _require_admin()
    if error:
        return error

    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'title required'}), 400

    cost = MiscCost(
        title=title,
        description=(data.get('description') or '').strip() or None,
        amount=float(data.get('amount', 0) or 0.0),
        paid_by=(data.get('paid_by') or '').strip() or None,
        purchase_date=(data.get('purchase_date') or '').strip() or None,
        split_count=max(1, int(data.get('split_count', 1) or 1)),
        status=data.get('status', 'open') or 'open',
    )
    db.session.add(cost)
    db.session.commit()
    return jsonify(cost.to_dict())


@bookings_bp.route('/misc-costs/<int:cost_id>', methods=['PUT'])
def update_misc_cost(cost_id):
    user, error = _require_admin()
    if error:
        return error

    cost = MiscCost.query.get_or_404(cost_id)
    data = request.get_json() or {}
    title = (data.get('title', cost.title) or '').strip()
    if not title:
        return jsonify({'error': 'title required'}), 400

    cost.title = title
    cost.description = (data.get('description', cost.description) or '').strip() or None
    cost.amount = float(data.get('amount', cost.amount) or 0.0)
    cost.paid_by = (data.get('paid_by', cost.paid_by) or '').strip() or None
    cost.purchase_date = (data.get('purchase_date', cost.purchase_date) or '').strip() or None
    cost.split_count = max(1, int(data.get('split_count', cost.split_count) or 1))
    cost.status = data.get('status', cost.status) or 'open'
    db.session.commit()
    return jsonify(cost.to_dict())


@bookings_bp.route('/misc-costs/<int:cost_id>', methods=['DELETE'])
def delete_misc_cost(cost_id):
    user, error = _require_admin()
    if error:
        return error

    cost = MiscCost.query.get_or_404(cost_id)
    db.session.delete(cost)
    db.session.commit()
    return jsonify({'status': 'deleted'})


@bookings_bp.route('/invoices/monthly', methods=['GET'])
def current_user_monthly_invoice():
    user, error = _require_login()
    if error:
        return error

    month_value = request.args.get('month') or datetime.utcnow().strftime('%Y-%m')
    summary = _monthly_invoice_summary(user, month_value)
    if not summary:
        return jsonify({'error': 'month must use YYYY-MM'}), 400
    return jsonify(summary)


@bookings_bp.route('/admin/invoices/monthly', methods=['GET'])
def admin_monthly_invoices():
    user, error = _require_admin()
    if error:
        return error

    month_value = request.args.get('month') or datetime.utcnow().strftime('%Y-%m')
    start_date, _ = _month_bounds(month_value)
    if not start_date:
        return jsonify({'error': 'month must use YYYY-MM'}), 400
    users = User.query.order_by(User.name.asc(), User.email.asc(), User.phone.asc()).all()
    summaries = [_monthly_invoice_summary(item, month_value) for item in users]
    return jsonify({'month': month_value, 'invoices': summaries})


@bookings_bp.route('/admin/users', methods=['GET'])
def admin_users():
    user, error = _require_admin()
    if error:
        return error

    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({'users': [_admin_user_payload(item) for item in users]})


@bookings_bp.route('/admin/users', methods=['POST'])
def create_admin_user():
    admin, error = _require_admin()
    if error:
        return error

    data = request.get_json() or {}
    phone = (data.get('phone') or '').strip()
    if not phone:
        return jsonify({'error': 'phone required'}), 400
    user = User.query.filter_by(phone=phone).first()
    if not user:
        role = data.get('role', 'member')
        if role not in {'member', 'admin'}:
            return jsonify({'error': 'invalid_role'}), 400
        user = User(
            phone=phone,
            email=data.get('email'),
            name=data.get('name'),
            whatsapp_number=data.get('whatsapp_number'),
            role=role,
            is_club_member=bool(data.get('is_club_member', False))
        )
        db.session.add(user)
        db.session.commit()
    return jsonify(_admin_user_payload(user))


@bookings_bp.route('/admin/users/<int:user_id>', methods=['PUT'])
def update_admin_user(user_id):
    admin, error = _require_admin()
    if error:
        return error

    target_user = User.query.get_or_404(user_id)
    data = request.get_json() or {}

    if 'email' in data:
        email = (data.get('email') or '').strip().lower() or None
        if email:
            existing = User.query.filter(User.email == email, User.id != target_user.id).first()
            if existing:
                return jsonify({'error': 'email_already_registered'}), 409
        target_user.email = email

    if 'phone' in data:
        phone = (data.get('phone') or '').strip()
        if not phone:
            return jsonify({'error': 'phone required'}), 400
        existing = User.query.filter(User.phone == phone, User.id != target_user.id).first()
        if existing:
            return jsonify({'error': 'phone_already_registered'}), 409
        target_user.phone = phone

    if 'name' in data:
        target_user.name = (data.get('name') or '').strip() or None
    if 'whatsapp_number' in data:
        target_user.whatsapp_number = (data.get('whatsapp_number') or '').strip() or None
    if 'is_club_member' in data:
        target_user.is_club_member = bool(data.get('is_club_member'))
    if 'role' in data:
        role = data.get('role')
        if role not in {'member', 'admin'}:
            return jsonify({'error': 'invalid_role'}), 400
        target_user.role = role

    db.session.commit()
    return jsonify(_admin_user_payload(target_user))


@bookings_bp.route('/admin/users/<int:user_id>', methods=['DELETE'])
def delete_admin_user(user_id):
    user, error = _require_admin()
    if error:
        return error

    target_user = User.query.get_or_404(user_id)

    FamilyMember.query.filter_by(user_id=target_user.id).delete()
    PlayAvailabilityVote.query.filter_by(user_id=target_user.id).update(
        {PlayAvailabilityVote.user_id: None},
        synchronize_session=False
    )
    db.session.delete(target_user)
    db.session.commit()

    return jsonify({'status': 'deleted'})


@bookings_bp.route('/admin/family-members/<int:member_id>', methods=['PUT'])
def update_admin_family_member(member_id):
    user, error = _require_admin()
    if error:
        return error

    member = FamilyMember.query.get_or_404(member_id)
    data = request.get_json() or {}
    if 'name' in data:
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': 'name required'}), 400
        member.name = name
    if 'relationship' in data:
        member.relationship = (data.get('relationship') or '').strip() or None
    if 'is_club_member' in data:
        member.is_club_member = bool(data.get('is_club_member'))

    db.session.commit()
    return jsonify(member.to_dict())


@bookings_bp.route('/admin/family-members', methods=['POST'])
def create_admin_family_member():
    user, error = _require_admin()
    if error:
        return error

    data = request.get_json() or {}
    user_id = data.get('user_id')
    owner = User.query.get_or_404(user_id)
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400

    member = FamilyMember(
        user_id=owner.id,
        name=name,
        relationship=(data.get('relationship') or '').strip() or None,
        is_club_member=bool(data.get('is_club_member', False))
    )
    db.session.add(member)
    db.session.commit()
    return jsonify(member.to_dict())


@bookings_bp.route('/admin/family-members/<int:member_id>', methods=['DELETE'])
def delete_admin_family_member(member_id):
    user, error = _require_admin()
    if error:
        return error

    member = FamilyMember.query.get_or_404(member_id)
    db.session.delete(member)
    db.session.commit()
    return jsonify({'status': 'deleted'})


@bookings_bp.route('/admin/courts', methods=['POST'])
def create_court():
    user, error = _require_admin()
    if error:
        return error

    data = request.get_json() or {}
    name = data.get('name')
    if not name:
        return jsonify({'error': 'name required'}), 400
    court = Court(
        name=name,
        location=data.get('location', ''),
        description=data.get('description', ''),
        map_link=(data.get('map_link') or '').strip() or None,
        hourly_rate=data.get('hourly_rate', 25.0),
        half_hour_rate=data.get('half_hour_rate'),
        is_active=data.get('is_active', True)
    )
    db.session.add(court)
    db.session.commit()
    return jsonify(court.to_dict())


@bookings_bp.route('/admin/courts', methods=['GET'])
def list_courts():
    user, error = _require_admin()
    if error:
        return error

    courts = Court.query.order_by(Court.name.asc()).all()
    return jsonify({'courts': [court.to_dict() for court in courts]})


@bookings_bp.route('/admin/courts/<int:court_id>', methods=['PUT'])
def update_court(court_id):
    user, error = _require_admin()
    if error:
        return error

    court = Court.query.get_or_404(court_id)
    data = request.get_json() or {}
    name = (data.get('name') or court.name or '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400

    court.name = name
    court.location = (data.get('location') or '').strip()
    court.description = (data.get('description') or '').strip()
    court.map_link = (data.get('map_link') or '').strip() or None
    court.hourly_rate = float(data.get('hourly_rate', court.hourly_rate) or 0.0)
    half_hour_rate = data.get('half_hour_rate', court.half_hour_rate)
    court.half_hour_rate = float(half_hour_rate) if half_hour_rate not in (None, '') else None
    if 'is_active' in data:
        court.is_active = bool(data.get('is_active'))
    db.session.commit()
    return jsonify(court.to_dict())


@bookings_bp.route('/admin/courts/<int:court_id>', methods=['DELETE'])
def delete_court(court_id):
    user, error = _require_admin()
    if error:
        return error

    court = Court.query.get_or_404(court_id)
    court.is_active = False
    db.session.commit()
    return jsonify(court.to_dict())


def _apply_freeze_period_data(period, data):
    title = (data.get('title') or '').strip()
    start_date = (data.get('start_date') or '').strip()
    end_date = (data.get('end_date') or '').strip()
    if not title:
        return jsonify({'error': 'title required'}), 400
    start = _parse_iso_date(start_date)
    end = _parse_iso_date(end_date)
    if not start or not end:
        return jsonify({'error': 'start_date and end_date must use YYYY-MM-DD'}), 400
    if end < start:
        return jsonify({'error': 'end_date must be on or after start_date'}), 400
    period.title = title
    period.start_date = start_date
    period.end_date = end_date
    period.reason = (data.get('reason') or '').strip() or None
    if 'is_active' in data:
        period.is_active = bool(data.get('is_active'))
    return None


@bookings_bp.route('/admin/freeze-periods', methods=['GET'])
def list_freeze_periods():
    user, error = _require_admin()
    if error:
        return error
    periods = CourtFreezePeriod.query.order_by(CourtFreezePeriod.start_date.asc(), CourtFreezePeriod.created_at.asc()).all()
    return jsonify({'periods': [period.to_dict() for period in periods]})


@bookings_bp.route('/admin/freeze-periods', methods=['POST'])
def create_freeze_period():
    user, error = _require_admin()
    if error:
        return error
    period = CourtFreezePeriod(is_active=True)
    validation_error = _apply_freeze_period_data(period, request.get_json() or {})
    if validation_error:
        return validation_error
    db.session.add(period)
    db.session.commit()
    return jsonify(period.to_dict()), 201


@bookings_bp.route('/admin/freeze-periods/<int:period_id>', methods=['PUT'])
def update_freeze_period(period_id):
    user, error = _require_admin()
    if error:
        return error
    period = CourtFreezePeriod.query.get_or_404(period_id)
    validation_error = _apply_freeze_period_data(period, request.get_json() or {})
    if validation_error:
        return validation_error
    db.session.commit()
    return jsonify(period.to_dict())


@bookings_bp.route('/admin/freeze-periods/<int:period_id>', methods=['DELETE'])
def delete_freeze_period(period_id):
    user, error = _require_admin()
    if error:
        return error
    period = CourtFreezePeriod.query.get_or_404(period_id)
    db.session.delete(period)
    db.session.commit()
    return jsonify({'status': 'deleted', 'id': period_id})

WHATSAPP_NOTIFICATION_DEFAULTS = [
    {
        'event_key': 'booking_created',
        'title': 'New booking created',
        'description': 'Notify the WhatsApp group when an admin creates a court booking.',
        'template': '🏸 New badminton booking\nCourt: {{court}}\nDate: {{date}}\nTime: {{start_time}}-{{end_time}}\nNotes: {{notes}}',
    },
    {
        'event_key': 'booking_cancelled',
        'title': 'Booking cancelled',
        'description': 'Notify the WhatsApp group when an admin deletes or cancels a court booking.',
        'template': '❌ Badminton booking cancelled\nCourt: {{court}}\nDate: {{date}}\nTime: {{start_time}}-{{end_time}}\nNotes: {{notes}}',
        'is_enabled': True,
    },
    {
        'event_key': 'booking_reminder',
        'title': 'Booking reminder',
        'description': 'Reminder text admins can send before a session.',
        'template': '⏰ Reminder: badminton at {{start_time}} today on {{court}}. Please update your attendance in the app.',
    },
    {
        'event_key': 'availability_summary',
        'title': 'Availability summary',
        'description': 'Share current availability totals for a play date.',
        'template': '📋 Availability for {{date}}\nAvailable: {{available_count}}\nTentative: {{tentative_count}}\nOpen the app to update your status.',
    },
    {
        'event_key': 'cost_settled',
        'title': 'Cost settled',
        'description': 'Tell the group when a court or shared cost has been settled.',
        'template': '💶 Cost update: {{title}} is {{status}}. Amount: €{{amount}}.',
    },
]


def _ensure_whatsapp_notification_settings():
    from .models import WhatsAppNotificationSetting
    existing = {item.event_key: item for item in WhatsAppNotificationSetting.query.all()}
    changed = False
    for spec in WHATSAPP_NOTIFICATION_DEFAULTS:
        if spec['event_key'] in existing:
            continue
        setting_data = {key: value for key, value in spec.items() if key != 'is_enabled'}
        db.session.add(WhatsAppNotificationSetting(**setting_data, is_enabled=spec.get('is_enabled', False), send_to_group=True))
        changed = True
    if changed:
        db.session.commit()


def _render_template(template, context):
    rendered = template or ''
    for key, value in (context or {}).items():
        rendered = rendered.replace('{{' + key + '}}', str(value if value is not None else ''))
    return rendered


def _fallback_whatsapp_group_id(exclude_event_key=None):
    from .models import WhatsAppNotificationSetting
    query = WhatsAppNotificationSetting.query.filter(WhatsAppNotificationSetting.group_id.isnot(None))
    if exclude_event_key:
        query = query.filter(WhatsAppNotificationSetting.event_key != exclude_event_key)
    setting = query.order_by(WhatsAppNotificationSetting.updated_at.desc()).first()
    return setting.group_id if setting else None


def _send_whatsapp_bot_message(message, recipient=None):
    import os
    import requests
    bot_url = os.environ.get('WHATSAPP_BOT_URL')
    if not bot_url:
        return 'skipped', 'WHATSAPP_BOT_URL is not configured'
    headers = {}
    bot_token = os.environ.get('WHATSAPP_BOT_TOKEN')
    if bot_token:
        headers['X-Bot-Token'] = bot_token
    try:
        response = requests.post(
            f"{bot_url.rstrip('/')}/send",
            json={'message': message, 'recipient': recipient},
            headers=headers,
            timeout=5,
        )
        return ('sent' if response.ok else 'failed'), response.text[:1000]
    except Exception as exc:
        return 'failed', str(exc)


def _send_whatsapp_event(event_key, context):
    from .models import WhatsAppNotificationLog, WhatsAppNotificationSetting
    _ensure_whatsapp_notification_settings()
    setting = WhatsAppNotificationSetting.query.filter_by(event_key=event_key).first()
    if not setting or not setting.is_enabled:
        return None

    message = _render_template(setting.template, context)
    recipient = (setting.group_id or '').strip() or _fallback_whatsapp_group_id(event_key)
    status, response_text = _send_whatsapp_bot_message(message, recipient)
    log = WhatsAppNotificationLog(
        setting_id=setting.id,
        event_key=setting.event_key,
        recipient=recipient,
        message=message,
        status=status,
        response=response_text,
    )
    db.session.add(log)
    db.session.commit()
    return log


def _booking_notification_context(booking):
    court = booking.court or Court.query.get(booking.court_id)
    court_name = court.name if court else 'Court'
    return {
        'booking_id': booking.id,
        'court': court_name,
        'court_name': court_name,
        'court.name': court_name,
        'court_location': court.location if court else '',
        'court.location': court.location if court else '',
        'date': booking.booking_date,
        'booking_date': booking.booking_date,
        'start_time': booking.start_time,
        'end_time': booking.end_time,
        'cost': booking.cost or 0,
        'notes': booking.notes or 'No notes',
    }


def _list_whatsapp_bot_groups():
    import os
    import requests
    bot_url = os.environ.get('WHATSAPP_BOT_URL')
    if not bot_url:
        return None, (jsonify({'error': 'whatsapp_bot_not_configured'}), 503)
    headers = {}
    bot_token = os.environ.get('WHATSAPP_BOT_TOKEN')
    if bot_token:
        headers['X-Bot-Token'] = bot_token
    try:
        response = requests.get(f"{bot_url.rstrip('/')}/groups", headers=headers, timeout=8)
    except Exception as exc:
        return None, (jsonify({'error': 'whatsapp_bot_unreachable', 'message': str(exc)}), 503)
    if response.status_code == 503:
        return None, (jsonify({'error': 'whatsapp_not_ready', 'message': 'Scan the WhatsApp QR code before listing groups.'}), 503)
    if not response.ok:
        return None, (jsonify({'error': 'whatsapp_bot_error', 'message': response.text[:1000]}), response.status_code)
    return response.json(), None


@bookings_bp.route('/admin/whatsapp-notifications', methods=['GET'])
def list_whatsapp_notifications():
    user, error = _require_admin()
    if error:
        return error
    from .models import WhatsAppNotificationLog, WhatsAppNotificationSetting
    _ensure_whatsapp_notification_settings()
    settings = WhatsAppNotificationSetting.query.order_by(WhatsAppNotificationSetting.title.asc()).all()
    logs = WhatsAppNotificationLog.query.order_by(WhatsAppNotificationLog.created_at.desc()).limit(10).all()
    return jsonify({'settings': [item.to_dict() for item in settings], 'logs': [item.to_dict() for item in logs]})


@bookings_bp.route('/admin/whatsapp-groups', methods=['GET'])
def list_whatsapp_groups():
    user, error = _require_admin()
    if error:
        return error
    data, bot_error = _list_whatsapp_bot_groups()
    if bot_error:
        return bot_error
    return jsonify(data)


@bookings_bp.route('/admin/whatsapp-notifications/<int:setting_id>', methods=['PUT'])
def update_whatsapp_notification(setting_id):
    user, error = _require_admin()
    if error:
        return error
    from .models import WhatsAppNotificationSetting
    setting = WhatsAppNotificationSetting.query.get_or_404(setting_id)
    data = request.get_json() or {}
    if 'title' in data:
        setting.title = (data.get('title') or '').strip() or setting.title
    if 'description' in data:
        setting.description = (data.get('description') or '').strip() or None
    if 'template' in data:
        template = (data.get('template') or '').strip()
        if not template:
            return jsonify({'error': 'template required'}), 400
        setting.template = template
    if 'is_enabled' in data:
        setting.is_enabled = bool(data.get('is_enabled'))
    if 'send_to_group' in data:
        setting.send_to_group = bool(data.get('send_to_group'))
    if 'group_id' in data:
        setting.group_id = (data.get('group_id') or '').strip() or None
    db.session.commit()
    return jsonify(setting.to_dict())


@bookings_bp.route('/admin/whatsapp-notifications/<int:setting_id>/test', methods=['POST'])
def test_whatsapp_notification(setting_id):
    user, error = _require_admin()
    if error:
        return error
    from .models import WhatsAppNotificationLog, WhatsAppNotificationSetting
    setting = WhatsAppNotificationSetting.query.get_or_404(setting_id)
    data = request.get_json() or {}
    sample_context = {
        'court': data.get('court', data.get('court_name', 'Court 1')),
        'court_name': data.get('court_name', data.get('court', 'Court 1')),
        'court.name': data.get('court_name', data.get('court', 'Court 1')),
        'court_location': data.get('court_location', ''),
        'court.location': data.get('court_location', ''),
        'date': data.get('date', datetime.utcnow().date().strftime('%Y-%m-%d')),
        'start_time': data.get('start_time', '19:00'),
        'end_time': data.get('end_time', '20:00'),
        'notes': data.get('notes', 'Friendly doubles session'),
        'available_count': data.get('available_count', 8),
        'tentative_count': data.get('tentative_count', 2),
        'title': data.get('title', setting.title),
        'status': data.get('status', 'settled'),
        'amount': data.get('amount', '25.00'),
    }
    message = _render_template(setting.template, sample_context)
    recipient = (data.get('recipient') or setting.group_id or '').strip() or None
    status, response_text = _send_whatsapp_bot_message(message, recipient)
    log = WhatsAppNotificationLog(setting_id=setting.id, event_key=setting.event_key, recipient=recipient, message=message, status=status, response=response_text)
    db.session.add(log)
    db.session.commit()
    return jsonify({'message': message, 'log': log.to_dict()})
