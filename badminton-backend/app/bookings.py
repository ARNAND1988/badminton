from datetime import datetime, timedelta
import json
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request, current_app
import jwt
from passlib.hash import pbkdf2_sha256

from . import db
from .models import AdminAuditLog, Booking, BookingParticipant, Court, CourtFreezePeriod, FamilyMember, Invoice, MiscCost, MonthlyInvoiceStatus, PlayAvailabilityVote, User, rounded_up_cost_split

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
    if (user.role or '').lower() not in {'admin', 'super_admin'}:
        return None, (jsonify({'error': 'admin_required'}), 403)
    return user, None



def _public_user_label(user):
    return user.name or user.email or user.phone or f'User {user.id}'


def _snapshot_fields(obj, fields):
    return {field: getattr(obj, field, None) for field in fields}


def _changed_fields(before, after):
    return {key: {'from': before.get(key), 'to': after.get(key)} for key in before if before.get(key) != after.get(key)}


def _normalize_password(value):
    password = value or ''
    if password and len(password) < 6:
        raise ValueError('password_too_short')
    return password


def _record_admin_audit(user, event_type, entity_type, entity_id=None, summary='', details=None):
    log = AdminAuditLog(
        admin_user_id=user.id if user else None,
        admin_name=user.name if user else None,
        admin_email=user.email if user else None,
        admin_phone=user.phone if user else None,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        summary=summary[:512] if summary else f'{event_type} {entity_type}',
        details=json.dumps(details or {}, sort_keys=True),
    )
    db.session.add(log)
    return log

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
    return status in {'attending', 'participated', 'not_attending', 'tentative'}


def _is_cost_split_status(status):
    return status in {'attending', 'participated'}


def _participant_status_for_booking(booking, status):
    if booking and booking.status == 'completed' and status == 'attending':
        return 'participated'
    return status


def _sync_participation_for_booking_status(booking):
    if booking.status != 'completed':
        return
    for participant in booking.participants:
        participant.status = _participant_status_for_booking(booking, participant.status)


def _normalize_person_name(value):
    normalized = ''.join(ch for ch in (value or '').lower() if ch.isalnum() or ch.isspace())
    return ' '.join(normalized.split())


def _names_match(left, right):
    left = _normalize_person_name(left)
    right = _normalize_person_name(right)
    if not left or not right:
        return False
    if left == right:
        return True
    left_parts = left.split()
    right_parts = right.split()
    return bool(left_parts and right_parts and left_parts[0] == right_parts[0] and (left.startswith(right + ' ') or right.startswith(left + ' ')))




def _sync_booking_invoice(booking):
    invoice = Invoice.query.filter_by(booking_id=booking.id).first()
    if not invoice:
        return None
    attended_count = len([participant for participant in booking.participants if _is_cost_split_status(participant.status)])
    invoice.total_amount = float(booking.cost or 0.0)
    invoice.split_count = max(1, attended_count or 1)
    return invoice

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


def _family_group_users(user):
    if not user or not user.id:
        return [user] if user else []
    group_ids = {user.id}
    changed = True
    family_links = FamilyMember.query.filter(FamilyMember.linked_user_id.isnot(None)).all()
    while changed:
        changed = False
        for link in family_links:
            if not link.user_id or not link.linked_user_id:
                continue
            if link.user_id in group_ids or link.linked_user_id in group_ids:
                before = len(group_ids)
                group_ids.update([link.user_id, link.linked_user_id])
                changed = changed or len(group_ids) != before
    return User.query.filter(User.id.in_(group_ids)).order_by(User.id.asc()).all()


def _family_owner_for_user(user):
    group = _family_group_users(user)
    return group[0] if group else user


def _billable_member_count_for_owner(owner, split_scope='manual'):
    scope = split_scope or 'manual'
    if scope == 'manual':
        return 1

    count = 0
    counted_user_ids = set()
    family_users = _family_group_users(owner)
    for group_user in family_users:
        if group_user.id not in counted_user_ids and (scope == 'all_members' or bool(group_user.is_club_member)):
            count += 1
            counted_user_ids.add(group_user.id)

        for member in group_user.family_members:
            linked_user = member.linked_user
            if linked_user:
                if linked_user.id in counted_user_ids:
                    continue
                if scope == 'all_members' or bool(linked_user.is_club_member) or bool(member.is_club_member):
                    count += 1
                    counted_user_ids.add(linked_user.id)
                continue

            if scope == 'all_members' or bool(member.is_club_member):
                count += 1

    return count


def _misc_cost_dynamic_split_count(split_scope='all_members'):
    owners = User.query.order_by(User.id.asc()).all()
    seen_owner_ids = set()
    count = 0
    for item in owners:
        owner = _family_owner_for_user(item)
        if owner.id in seen_owner_ids:
            continue
        seen_owner_ids.add(owner.id)
        count += _billable_member_count_for_owner(owner, split_scope)
    return max(1, count)


def _misc_cost_split_count(cost):
    if (cost.status or 'open') == 'settled' or (cost.split_scope or 'manual') == 'manual':
        return max(1, int(cost.split_count or 1))
    return _misc_cost_dynamic_split_count(cost.split_scope)


def _sync_open_misc_cost_splits():
    for cost in MiscCost.query.filter(MiscCost.status != 'settled').all():
        cost.split_count = _misc_cost_split_count(cost)


def _participant_keys_for_user(user):
    keys = set()
    for group_user in _family_group_users(user):
        if group_user.phone:
            keys.add(group_user.phone)
        for member in group_user.family_members:
            keys.add(f'family:{member.id}')
            if member.linked_user and member.linked_user.phone:
                keys.add(member.linked_user.phone)
    return keys


MONTHLY_INVOICE_STATUSES = {'OPEN', 'READY_FOR_PAYMENT', 'SETTLED'}
TEST_PAYMENT_INVOICE_AMOUNT = 1.00


def _family_display_name(user):
    names = []
    for value in [user.name or user.email or user.phone, *[member.name for member in sorted(user.family_members, key=lambda item: item.created_at or datetime.min)]]:
        value = (value or '').strip()
        if value and not any(_names_match(value, existing) for existing in names):
            names.append(value)
    return ' & '.join(names) if names else user.email or user.phone or 'Family'


def _append_unique_family_name(names, value):
    value = (value or '').strip()
    if value and not any(_names_match(value, existing) for existing in names):
        names.append(value)


def _monthly_invoice_status(month_value, create=False):
    status = MonthlyInvoiceStatus.query.filter_by(month=month_value).first()
    if not status and create:
        status = MonthlyInvoiceStatus(month=month_value, status='OPEN')
        db.session.add(status)
        db.session.flush()
    return status


def _monthly_invoice_summary(user, month_value):
    start_date, end_date = _month_bounds(month_value)
    if not start_date:
        return None

    _mark_past_bookings_completed()

    requested_user = user
    user = _family_owner_for_user(user)
    participant_keys = _participant_keys_for_user(user)
    family_title = _family_display_name(user)
    participant_labels = {}
    for group_user in _family_group_users(user):
        participant_labels[group_user.phone] = group_user.name or group_user.email or group_user.phone
        for member in group_user.family_members:
            participant_labels[f'family:{member.id}'] = member.name
            if member.linked_user and member.linked_user.phone:
                participant_labels[member.linked_user.phone] = member.name or member.linked_user.name or member.linked_user.email or member.linked_user.phone
    booking_items = []
    booking_total = 0.0
    bookings = (
        Booking.query
        .filter(
            Booking.booking_date >= start_date,
            Booking.booking_date < end_date,
            Booking.status.in_(COMPLETED_BOOKING_STATUSES),
        )
        .order_by(Booking.booking_date.asc(), Booking.start_time.asc())
        .all()
    )
    for booking in bookings:
        attending = [participant for participant in booking.participants if _is_cost_split_status(participant.status)]
        matching = [participant for participant in attending if participant.phone in participant_keys]
        if not matching:
            known_names = [label for label in participant_labels.values() if label]
            matching = [
                participant for participant in attending
                if any(_names_match(participant.name or participant.phone, label) for label in known_names)
            ]
        if not matching:
            continue
        split_count = max(1, len(attending) or 1)
        split = rounded_up_cost_split(booking.cost, split_count)
        per_person = split['cost_per_person']
        matching_ids = set()
        matching_amount = 0.0
        matching_participants = []
        known_names = [label for label in participant_labels.values() if label]
        for index, participant in enumerate(attending):
            if participant not in matching:
                continue
            participant_label = participant.name or participant.phone or 'Player'
            matched_key = participant.phone if participant.phone in participant_keys else None
            if not matched_key:
                for label in known_names:
                    if _names_match(participant_label, label):
                        matched_key = f'name:{_normalize_person_name(label)}'
                        break
            matched_key = matched_key or f'participant:{participant.id}'
            if matched_key in matching_ids:
                continue
            matching_ids.add(matched_key)
            matching_amount = round(matching_amount + split['participant_shares'][index], 2)
            matching_participants.append(participant)
        amount = matching_amount
        booking_total += amount
        booking_items.append({
            'booking_id': booking.id,
            'title': family_title,
            'date': booking.booking_date,
            'court': booking.court.name if booking.court else None,
            'start_time': booking.start_time,
            'end_time': booking.end_time,
            'attendee_count': len(matching_participants),
            'total_people_played': split_count,
            'total_cost': round(float(booking.cost or 0.0), 2),
            'cost_per_person': per_person,
            'participants': [participant_labels.get(participant.phone, participant.name or participant.phone or 'Player') for participant in matching_participants],
            'family_members': [participant_labels.get(participant.phone, participant.name or participant.phone or 'Player') for participant in matching_participants],
            'amount': amount,
            'booking_status': booking.status,
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
        split_count = _misc_cost_split_count(cost)
        billable_members = _billable_member_count_for_owner(user, cost.split_scope)
        if billable_members <= 0:
            continue
        amount = round((float(cost.amount or 0.0) / split_count) * billable_members, 2)
        misc_total += amount
        misc_items.append({
            'cost_id': cost.id,
            'title': cost.title,
            'purchase_date': cost.purchase_date,
            'status': cost.status,
            'split_count': split_count,
            'split_scope': cost.split_scope or 'manual',
            'billable_members': billable_members,
            'amount_total': round(float(cost.amount or 0.0), 2),
            'amount': amount,
        })

    total = round(booking_total + misc_total, 2)
    paid_count = len([item for item in booking_items if item.get('invoice_status') == 'settled' and item.get('booking_status') == 'settled'])
    paid_amount = round(sum(float(item.get('amount') or 0.0) for item in booking_items if item.get('invoice_status') == 'settled' and item.get('booking_status') == 'settled'), 2)
    return {
        'user': requested_user.to_dict(),
        'family_owner': user.to_dict(),
        'family_title': family_title,
        'month': month_value,
        'month_status': (_monthly_invoice_status(month_value) or MonthlyInvoiceStatus(month=month_value, status='OPEN')).to_dict(),
        'booking_items': booking_items,
        'misc_items': misc_items,
        'booking_total': round(booking_total, 2),
        'misc_total': round(misc_total, 2),
        'total': total,
        'paid_amount': paid_amount,
        'balance_amount': round(total - paid_amount, 2),
        'paid_count': paid_count,
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
                'linked_user_id': member.linked_user_id,
                'phone': member.linked_user.phone if member.linked_user else None,
            })
    return selected


def _availability_person_key(attendee, fallback_user_id=None):
    linked_user_id = attendee.get('linked_user_id')
    if linked_user_id:
        return f'user:{linked_user_id}'
    if attendee.get('type') == 'self' and fallback_user_id:
        return f'user:{fallback_user_id}'
    family_member_id = attendee.get('family_member_id')
    if family_member_id:
        member = FamilyMember.query.get(family_member_id)
        if member and member.linked_user_id:
            return f'user:{member.linked_user_id}'
        return f'family:{family_member_id}'
    phone = (attendee.get('phone') or '').strip()
    if phone:
        return f'phone:{phone}'
    name = (attendee.get('name') or '').strip().lower()
    return f'name:{name}' if name else None


def _availability_merge_attendee(attendees_by_key, attendee, status, fallback_user_id=None):
    key = _availability_person_key(attendee, fallback_user_id=fallback_user_id)
    if not key:
        key = f'ad-hoc:{len(attendees_by_key)}:{attendee.get("name") or "Member"}'
    payload = {**attendee, 'status': status}
    existing = attendees_by_key.get(key)
    if not existing or (existing.get('status') != 'available' and status == 'available'):
        attendees_by_key[key] = payload


def _sync_linked_family_owner_votes(user, play_date, attendee_details, notes):
    linked_members = FamilyMember.query.filter_by(linked_user_id=user.id).all()
    if not linked_members:
        return
    own_attendee = next((attendee for attendee in attendee_details if attendee.get('type') == 'self'), None)
    own_status = own_attendee.get('status') if own_attendee else 'not_available'
    for member in linked_members:
        owner_vote = PlayAvailabilityVote.query.filter_by(user_id=member.user_id, play_date=play_date).first()
        if not owner_vote:
            owner_vote = PlayAvailabilityVote(user_id=member.user_id, play_date=play_date)
            db.session.add(owner_vote)
        try:
            owner_attendees = json.loads(owner_vote.attendee_details or '[]')
        except Exception:
            owner_attendees = []
        owner_attendees = [
            attendee for attendee in owner_attendees
            if not (attendee.get('type') == 'family' and attendee.get('family_member_id') == member.id)
        ]
        if own_status != 'not_available':
            owner_attendees.append({
                'type': 'family',
                'status': own_status,
                'family_member_id': member.id,
                'name': member.name,
                'linked_user_id': user.id,
                'phone': user.phone,
            })
        available_count = len([attendee for attendee in owner_attendees if attendee.get('status', 'available') == 'available'])
        tentative_count = len([attendee for attendee in owner_attendees if attendee.get('status') == 'tentative'])
        owner_vote.status = 'available' if available_count else 'tentative' if tentative_count else 'not_available'
        owner_vote.available = available_count > 0
        owner_vote.attendee_count = available_count
        owner_vote.attendee_details = json.dumps(owner_attendees) if owner_attendees else None
        owner_vote.notes = notes


def _linked_family_member_vote_payload(user, vote):
    if not user or not vote:
        return None
    vote_payload = vote.to_dict()
    for attendee in vote_payload.get('attendee_details') or []:
        if attendee.get('type') == 'family' and attendee.get('linked_user_id') == user.id:
            return {
                'id': vote.id,
                'user_id': user.id,
                'play_date': vote.play_date,
                'available': attendee.get('status', 'available') == 'available',
                'status': attendee.get('status', 'available'),
                'attendee_count': 1 if attendee.get('status', 'available') == 'available' else 0,
                'attendee_details': [{
                    'type': 'self',
                    'status': attendee.get('status', 'available'),
                    'name': attendee.get('name'),
                    'phone': attendee.get('phone'),
                }],
                'notes': vote.notes,
                'updated_at': vote_payload.get('updated_at'),
            }
    return None

def _admin_user_payload(user):
    payload = user.to_dict()
    payload['family_members'] = [
        member.to_dict()
        for member in sorted(user.family_members, key=lambda item: item.created_at or datetime.min)
    ]
    return payload


def _current_booking_cutoff_values(now=None):
    now = now or datetime.utcnow()
    return now.date().strftime('%Y-%m-%d'), now.strftime('%H:%M')


def _booking_has_ended(booking_date, end_time=None, today_value=None, current_time=None):
    today_value, current_time = (today_value, current_time) if today_value and current_time else _current_booking_cutoff_values()
    if not booking_date:
        return False
    if booking_date < today_value:
        return True
    return booking_date == today_value and bool(end_time) and end_time <= current_time


BOOKING_STATUSES = {'confirmed', 'completed', 'settled', 'cancelled'}
AMSTERDAM_TZ = ZoneInfo('Europe/Amsterdam')
COMPLETED_BOOKING_STATUSES = {'completed', 'settled'}
TERMINAL_BOOKING_STATUSES = {'settled', 'cancelled'}


def _normalize_booking_status(status, fallback='confirmed'):
    status = (status or fallback or 'confirmed').strip().lower()
    if status == 'created':
        status = 'confirmed'
    if status not in BOOKING_STATUSES:
        raise ValueError('invalid_status')
    return status


def _booking_status_for_date(booking_date, status='confirmed', today_value=None, end_time=None, current_time=None):
    status = _normalize_booking_status(status)
    if status in TERMINAL_BOOKING_STATUSES:
        return status
    return 'completed' if _booking_has_ended(booking_date, end_time, today_value, current_time) else status


def _is_completed_booking(booking, today_value=None, current_time=None):
    if booking.status == 'cancelled':
        return False
    if not today_value or not current_time:
        today_value, current_time = _current_booking_cutoff_values()
    return booking.status in COMPLETED_BOOKING_STATUSES or _booking_has_ended(booking.booking_date, booking.end_time, today_value, current_time)


def _mark_past_bookings_completed(today_value=None, current_time=None):
    if not today_value or not current_time:
        today_value, current_time = _current_booking_cutoff_values()
    completed_bookings = Booking.query.filter(
        db.or_(
            Booking.booking_date < today_value,
            db.and_(Booking.booking_date == today_value, Booking.end_time <= current_time),
        ),
        ~Booking.status.in_(COMPLETED_BOOKING_STATUSES | {'cancelled'})
    ).all()
    for booking in completed_bookings:
        booking.status = 'completed'
        _sync_participation_for_booking_status(booking)
        _sync_booking_invoice(booking)
    if completed_bookings:
        db.session.commit()
    return len(completed_bookings)


def _archive_cutoff_date(today=None):
    """Return the July 1 start date for the active cost year.

    The club cost year runs from July through June. Data before the active
    July 1 boundary is archive-only, so uploaded data through June 2026 is
    archived starting July 2026 and each following July starts a new active
    year.
    """
    today = today or datetime.utcnow().date()
    fiscal_year = today.year if today.month >= 7 else today.year - 1
    return datetime(fiscal_year, 7, 1).date().strftime('%Y-%m-%d')


def _is_archived_record(date_value):
    return bool(date_value) and date_value < _archive_cutoff_date()


def _archived_booking_response(booking):
    if _is_archived_record(booking.booking_date):
        return jsonify({'error': 'booking_archived'}), 409
    return None


def _booking_payload(booking, today_value=None, current_time=None):
    payload = booking.to_dict()
    if _is_completed_booking(booking, today_value, current_time):
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


def _participant_related_keys(phone):
    normalized_phone = (phone or '').strip()
    keys = {normalized_phone} if normalized_phone else set()
    if normalized_phone.startswith('family:'):
        try:
            member_id = int(normalized_phone.split(':', 1)[1])
        except (TypeError, ValueError):
            member_id = None
        member = FamilyMember.query.get(member_id) if member_id else None
        if member:
            keys.add(f'family:{member.id}')
            if member.linked_user and member.linked_user.phone:
                keys.add(member.linked_user.phone)
            for reciprocal in FamilyMember.query.filter_by(linked_user_id=member.linked_user_id).all() if member.linked_user_id else []:
                keys.add(f'family:{reciprocal.id}')
    else:
        linked_user = User.query.filter_by(phone=normalized_phone).first()
        if linked_user:
            for member in FamilyMember.query.filter_by(linked_user_id=linked_user.id).all():
                keys.add(f'family:{member.id}')
    return {key for key in keys if key}


def _canonical_participant_phone(phone):
    normalized_phone = (phone or '').strip()
    if not normalized_phone.startswith('family:'):
        return normalized_phone
    try:
        member_id = int(normalized_phone.split(':', 1)[1])
    except (TypeError, ValueError):
        return normalized_phone
    member = FamilyMember.query.get(member_id)
    if member and member.linked_user and member.linked_user.phone:
        return member.linked_user.phone
    return normalized_phone


def _upsert_participant(booking, phone, name=None, status='tentative', is_adhoc=False):
    normalized_phone = (phone or '').strip()
    if not normalized_phone:
        raise ValueError('phone required')
    if not _valid_participant_status(status):
        raise ValueError('invalid_status')

    related_keys = _participant_related_keys(normalized_phone)
    canonical_phone = _canonical_participant_phone(normalized_phone)
    related_keys.add(canonical_phone)
    matches = BookingParticipant.query.filter(
        BookingParticipant.booking_id == booking.id,
        BookingParticipant.phone.in_(related_keys),
    ).order_by(BookingParticipant.created_at.asc(), BookingParticipant.id.asc()).all()
    participant = matches[0] if matches else None
    if not participant:
        participant = BookingParticipant(booking_id=booking.id, phone=canonical_phone)
        db.session.add(participant)
    else:
        participant.phone = canonical_phone
        for duplicate in matches[1:]:
            db.session.delete(duplicate)

    participant.name = (name or participant.name or '').strip() or None
    participant.status = _participant_status_for_booking(booking, status)
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
    db.session.flush()
    _record_admin_audit(user, 'create', 'family_member', member.id, f'Created family member {member.name}', {'family_member': member.to_dict()})
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
    today = datetime.utcnow().date()
    if start_date:
        start = _parse_iso_date(start_date)
        if not start:
            return jsonify({'error': 'invalid_start_date'}), 400
        if start < today:
            start = today
        dates = _next_playable_dates(days, start=start)
    else:
        dates = _next_playable_dates(days, start=today)

    date_values = [date_value.strftime('%Y-%m-%d') for date_value in dates]
    votes = PlayAvailabilityVote.query.filter(
        PlayAvailabilityVote.play_date.in_(date_values)
    ).all()
    current_family_user_ids = {user.id} if user else set()
    if user:
        owner = _family_owner_for_user(user)
        current_family_user_ids.add(owner.id)
        current_family_user_ids.update(member.linked_user_id for member in owner.family_members if member.linked_user_id)
    user_votes = {}
    if user:
        for vote in votes:
            if vote.user_id in current_family_user_ids and vote.play_date not in user_votes:
                user_votes[vote.play_date] = vote
        own_votes = PlayAvailabilityVote.query.filter(
            PlayAvailabilityVote.user_id == user.id,
            PlayAvailabilityVote.play_date.in_(date_values),
        ).all()
        for vote in own_votes:
            user_votes[vote.play_date] = vote

    attendees_by_date = {}
    family_statuses_by_date = {}
    for vote in votes:
        attendees_by_date.setdefault(vote.play_date, {})
        family_statuses_by_date.setdefault(vote.play_date, {})
        vote_payload = vote.to_dict()
        vote_attendees = vote_payload.get('attendee_details') or []
        vote_status = vote.status or ('available' if vote.available else 'not_available')
        for attendee in vote_attendees:
            attendee_status = attendee.get('status', 'available')
            if attendee_status in {'available', 'tentative'}:
                _availability_merge_attendee(attendees_by_date[vote.play_date], attendee, attendee_status, fallback_user_id=vote.user_id)
                family_statuses_by_date[vote.play_date][vote.user_id or vote.id] = attendee_status
        if not vote_attendees and vote_status in {'available', 'tentative'}:
            fallback_name = vote.user.name or vote.user.email or vote.user.phone if vote.user else None
            fallback_count = max(1, int(vote.attendee_count or 1)) if vote_status == 'available' else 1
            for index in range(fallback_count):
                fallback_attendee = {
                    'type': 'self' if index == 0 else 'guest',
                    'name': fallback_name or 'Member' if index == 0 else f'{fallback_name or "Member"} guest {index + 1}',
                    'status': vote_status,
                }
                _availability_merge_attendee(
                    attendees_by_date[vote.play_date],
                    fallback_attendee,
                    vote_status,
                    fallback_user_id=vote.user_id if index == 0 else None,
                )
            family_statuses_by_date[vote.play_date][vote.user_id or vote.id] = vote_status

    totals = {}
    for date_value, attendees_by_key in attendees_by_date.items():
        attendees = list(attendees_by_key.values())
        available_attendees = [attendee for attendee in attendees if attendee.get('status') == 'available']
        tentative_attendees = [attendee for attendee in attendees if attendee.get('status') == 'tentative']
        family_statuses = family_statuses_by_date.get(date_value, {}).values()
        totals[date_value] = {
            'available_families': len([status for status in family_statuses if status == 'available']),
            'tentative_families': len([status for status in family_statuses if status == 'tentative']),
            'attendee_count': len(available_attendees),
            'available_count': len(available_attendees),
            'tentative_count': len(tentative_attendees),
            'available_attendees': available_attendees,
            'tentative_attendees': tentative_attendees,
        }

    days_payload = []
    for date_value in date_values:
        vote = user_votes.get(date_value)
        vote_payload = vote.to_dict() if vote else None
        if user and vote and vote.user_id != user.id:
            vote_payload = _linked_family_member_vote_payload(user, vote) or vote_payload
        days_payload.append({
            'date': date_value,
            'weekday': datetime.strptime(date_value, '%Y-%m-%d').strftime('%A'),
            'vote': vote_payload,
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
    for attendee in attendee_details:
        linked_user_id = attendee.get('linked_user_id')
        if not linked_user_id:
            continue
        linked_vote = PlayAvailabilityVote.query.filter_by(user_id=linked_user_id, play_date=play_date).first()
        if not linked_vote:
            linked_vote = PlayAvailabilityVote(user_id=linked_user_id, play_date=play_date)
            db.session.add(linked_vote)
        linked_vote.status = attendee.get('status') or status
        linked_vote.available = linked_vote.status == 'available'
        linked_vote.attendee_count = 1 if linked_vote.available else 0
        linked_vote.attendee_details = json.dumps([{'type': 'self', 'status': linked_vote.status, 'name': attendee.get('name'), 'phone': attendee.get('phone')}])
        linked_vote.notes = vote.notes
    _sync_linked_family_owner_votes(user, play_date, attendee_details, vote.notes)
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
    if not court or court.is_active is False:
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
            status=_booking_status_for_date(target_date, 'confirmed', end_time=end_time)
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

    for booking in created_bookings:
        _record_admin_audit(user, 'create', 'booking', booking.id, f'Created booking for {booking.court.name if booking.court else booking.court_id} on {booking.booking_date}', {'booking': booking.to_dict()})
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
    archived_error = _archived_booking_response(booking)
    if archived_error:
        return archived_error
    data = request.get_json() or {}
    before = _snapshot_fields(booking, ['court_id', 'booking_date', 'start_time', 'end_time', 'cost', 'notes', 'status'])

    court_id = data.get('court_id', booking.court_id)
    booking_date = data.get('booking_date', booking.booking_date)
    start_time = data.get('start_time', booking.start_time)
    end_time = data.get('end_time', booking.end_time)

    if not all([court_id, booking_date, start_time, end_time]):
        return jsonify({'error': 'court_id, booking_date, start_time and end_time are required'}), 400

    court = Court.query.get(court_id)
    if not court or court.is_active is False:
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
    try:
        requested_status = _normalize_booking_status(data.get('status', booking.status or 'confirmed'))
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    booking.status = _booking_status_for_date(booking.booking_date, requested_status, end_time=booking.end_time)
    _sync_participation_for_booking_status(booking)
    if booking.status == 'settled':
        invoice = Invoice.query.filter_by(booking_id=booking.id).first()
        if not invoice:
            invoice = Invoice(booking_id=booking.id)
            db.session.add(invoice)
        invoice.status = 'settled'
    _sync_booking_invoice(booking)
    after = _snapshot_fields(booking, ['court_id', 'booking_date', 'start_time', 'end_time', 'cost', 'notes', 'status'])
    changes = _changed_fields(before, after)
    if changes:
        _record_admin_audit(user, 'update', 'booking', booking.id, f'Updated booking {booking.id}', {'changes': changes})
    db.session.commit()

    return jsonify(booking.to_dict())


@bookings_bp.route('/bookings/<int:booking_id>', methods=['DELETE'])
def delete_booking(booking_id):
    user, error = _require_admin()
    if error:
        return error

    booking = Booking.query.get_or_404(booking_id)
    archived_error = _archived_booking_response(booking)
    if archived_error:
        return archived_error
    booking_snapshot = booking.to_dict()
    _send_whatsapp_event('booking_cancelled', _booking_notification_context(booking))
    _record_admin_audit(user, 'delete', 'booking', booking.id, f'Deleted booking {booking.id}', {'booking': booking_snapshot})
    Invoice.query.filter_by(booking_id=booking.id).delete()
    BookingParticipant.query.filter_by(booking_id=booking.id).delete()
    db.session.delete(booking)
    db.session.commit()
    return jsonify({'status': 'deleted', 'id': booking_id})


@bookings_bp.route('/bookings', methods=['GET'])
def list_bookings():
    _send_due_booking_reminders()
    today_value, current_time = _current_booking_cutoff_values()
    _mark_past_bookings_completed(today_value, current_time)
    status_filter = (request.args.get('status') or '').strip().lower()
    page = _positive_int_arg('page', 1)
    per_page = _positive_int_arg('per_page', 25, maximum=100)

    if status_filter in {'completed', 'archive'}:
        user, error = _require_login()
        if error:
            return error
        _ensure_historical_booking_data()
        completed_filter = db.or_(
            Booking.status.in_(COMPLETED_BOOKING_STATUSES),
            Booking.booking_date < today_value,
            db.and_(Booking.booking_date == today_value, Booking.end_time <= current_time),
        )
        if status_filter == 'archive':
            query = Booking.query.filter(
                completed_filter,
                Booking.status != 'cancelled',
                Booking.booking_date < _archive_cutoff_date()
            ).order_by(Booking.booking_date.desc(), Booking.start_time.desc())
        else:
            query = Booking.query.filter(
                completed_filter,
                Booking.status != 'cancelled',
                Booking.booking_date >= _archive_cutoff_date()
            )
            month_value = (request.args.get('month') or '').strip()
            if month_value:
                month_start, month_end = _month_bounds(month_value)
                if not month_start:
                    return jsonify({'error': 'month must use YYYY-MM'}), 400
                query = query.filter(Booking.booking_date >= month_start, Booking.booking_date < month_end)
            query = query.order_by(Booking.booking_date.desc(), Booking.start_time.desc())
    elif status_filter == 'upcoming':
        query = Booking.query.filter(
            ~Booking.status.in_(COMPLETED_BOOKING_STATUSES | {'cancelled'}),
            db.or_(
                Booking.booking_date > today_value,
                db.and_(Booking.booking_date == today_value, Booking.end_time > current_time),
            )
        ).order_by(Booking.booking_date.asc(), Booking.start_time.asc())
    else:
        query = Booking.query.order_by(Booking.booking_date.asc(), Booking.start_time.asc())

    total = query.count()
    bookings = query.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'bookings': [_booking_payload(b, today_value, current_time) for b in bookings],
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
    archived_error = _archived_booking_response(booking)
    if archived_error:
        return archived_error
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
    _sync_booking_invoice(booking)
    db.session.commit()
    return jsonify(participant.to_dict())


@bookings_bp.route('/bookings/<int:booking_id>/family-attendance', methods=['POST'])
def save_booking_family_attendance(booking_id):
    user, error = _require_login()
    if error:
        return error

    booking = Booking.query.get_or_404(booking_id)
    archived_error = _archived_booking_response(booking)
    if archived_error:
        return archived_error
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
            participant_phone = member.linked_user.phone if member.linked_user and member.linked_user.phone else f'family:{member.id}'
            saved.append(_upsert_participant(
                booking,
                participant_phone,
                name=member.name,
                status=status,
                is_adhoc=False
            ))

    _sync_booking_invoice(booking)
    db.session.commit()
    return jsonify({'participants': [participant.to_dict() for participant in saved]})


@bookings_bp.route('/bookings/<int:booking_id>/participants', methods=['POST'])
def add_booking_participant(booking_id):
    user, error = _require_admin()
    if error:
        return error

    booking = Booking.query.get_or_404(booking_id)
    archived_error = _archived_booking_response(booking)
    if archived_error:
        return archived_error
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

    _sync_booking_invoice(booking)
    db.session.commit()
    return jsonify(participant.to_dict())


@bookings_bp.route('/bookings/<int:booking_id>/participants/<int:participant_id>', methods=['PUT'])
def update_booking_participant(booking_id, participant_id):
    user, error = _require_admin()
    if error:
        return error

    booking = Booking.query.get_or_404(booking_id)
    archived_error = _archived_booking_response(booking)
    if archived_error:
        return archived_error
    participant = BookingParticipant.query.filter_by(id=participant_id, booking_id=booking_id).first_or_404()
    data = request.get_json() or {}
    status = data.get('status', participant.status)
    if not _valid_participant_status(status):
        return jsonify({'error': 'invalid_status'}), 400

    participant.name = (data.get('name', participant.name) or '').strip() or None
    participant.phone = (data.get('phone', participant.phone) or '').strip()
    participant.status = _participant_status_for_booking(booking, status)
    if 'is_adhoc' in data:
        participant.is_adhoc = bool(data.get('is_adhoc'))
    _sync_booking_invoice(booking)
    db.session.commit()
    return jsonify(participant.to_dict())


@bookings_bp.route('/bookings/<int:booking_id>/participants/<int:participant_id>', methods=['DELETE'])
def delete_booking_participant(booking_id, participant_id):
    user, error = _require_admin()
    if error:
        return error

    booking = Booking.query.get_or_404(booking_id)
    archived_error = _archived_booking_response(booking)
    if archived_error:
        return archived_error
    participant = BookingParticipant.query.filter_by(id=participant_id, booking_id=booking_id).first_or_404()
    db.session.delete(participant)
    db.session.flush()
    _sync_booking_invoice(booking)
    db.session.commit()
    return jsonify({'status': 'deleted'})


@bookings_bp.route('/bookings/<int:booking_id>/invoice', methods=['POST'])
def generate_invoice(booking_id):
    user, error = _require_admin()
    if error:
        return error

    booking = Booking.query.get_or_404(booking_id)
    archived_error = _archived_booking_response(booking)
    if archived_error:
        return archived_error
    invoice = Invoice.query.filter_by(booking_id=booking_id).first()
    if not invoice:
        invoice = Invoice(booking_id=booking.id)
        db.session.add(invoice)

    court = booking.court
    total_amount = float(booking.cost or court.hourly_rate if court else 0.0)
    attended_count = len([participant for participant in booking.participants if _is_cost_split_status(participant.status)])
    invoice.total_amount = total_amount
    invoice.split_count = max(1, attended_count or 1)
    invoice.status = invoice.status if invoice.status == 'settled' else 'generated'
    _record_admin_audit(user, 'create', 'invoice', invoice.booking_id, f'Generated invoice for booking {booking.id}', {'invoice': invoice.to_dict()})
    db.session.commit()
    return jsonify(invoice.to_dict())


@bookings_bp.route('/bookings/<int:booking_id>/settle', methods=['POST'])
def settle_booking_cost(booking_id):
    user, error = _require_admin()
    if error:
        return error

    booking = Booking.query.get_or_404(booking_id)
    archived_error = _archived_booking_response(booking)
    if archived_error:
        return archived_error
    attended_count = len([participant for participant in booking.participants if _is_cost_split_status(participant.status)])
    invoice = Invoice.query.filter_by(booking_id=booking.id).first()
    if not invoice:
        invoice = Invoice(booking_id=booking.id)
        db.session.add(invoice)
    invoice.total_amount = float(booking.cost or 0.0)
    invoice.split_count = max(1, attended_count or 1)
    invoice.status = 'settled'
    booking.status = 'settled'
    _record_admin_audit(user, 'settle', 'booking', booking.id, f'Settled booking cost for booking {booking.id}', {'invoice': invoice.to_dict()})
    db.session.commit()
    return jsonify(invoice.to_dict())


@bookings_bp.route('/misc-costs', methods=['GET'])
def list_misc_costs():
    user, error = _require_login()
    if error:
        return error

    status_filter = (request.args.get('status') or 'active').strip().lower()
    query = MiscCost.query
    if status_filter == 'archive':
        query = query.filter(MiscCost.purchase_date < _archive_cutoff_date())
    elif status_filter != 'all':
        query = query.filter(db.or_(MiscCost.purchase_date.is_(None), MiscCost.purchase_date >= _archive_cutoff_date()))
    _sync_open_misc_cost_splits()
    costs = query.order_by(MiscCost.purchase_date.desc(), MiscCost.created_at.desc()).all()
    return jsonify({'costs': [cost.to_dict() for cost in costs], 'archive_cutoff_date': _archive_cutoff_date()})


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
        split_scope=data.get('split_scope', 'manual') if data.get('split_scope') in {'manual', 'all_members', 'club_members'} else 'manual',
        status=data.get('status', 'open') or 'open',
    )
    if cost.status != 'settled':
        cost.split_count = _misc_cost_split_count(cost)
    db.session.add(cost)
    db.session.flush()
    _record_admin_audit(user, 'create', 'misc_cost', cost.id, f'Created shared cost {cost.title}', {'cost': cost.to_dict()})
    db.session.commit()
    return jsonify(cost.to_dict())


@bookings_bp.route('/misc-costs/<int:cost_id>', methods=['PUT'])
def update_misc_cost(cost_id):
    user, error = _require_admin()
    if error:
        return error

    cost = MiscCost.query.get_or_404(cost_id)
    before = _snapshot_fields(cost, ['title', 'description', 'amount', 'paid_by', 'purchase_date', 'split_count', 'split_scope', 'status'])
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
    if data.get('split_scope') in {'manual', 'all_members', 'club_members'}:
        cost.split_scope = data.get('split_scope')
    cost.status = data.get('status', cost.status) or 'open'
    if cost.status != 'settled':
        cost.split_count = _misc_cost_split_count(cost)
    after = _snapshot_fields(cost, ['title', 'description', 'amount', 'paid_by', 'purchase_date', 'split_count', 'split_scope', 'status'])
    changes = _changed_fields(before, after)
    if changes:
        _record_admin_audit(user, 'update', 'misc_cost', cost.id, f'Updated shared cost {cost.title}', {'changes': changes})
    db.session.commit()
    return jsonify(cost.to_dict())


@bookings_bp.route('/misc-costs/<int:cost_id>', methods=['DELETE'])
def delete_misc_cost(cost_id):
    user, error = _require_admin()
    if error:
        return error

    cost = MiscCost.query.get_or_404(cost_id)
    cost_snapshot = cost.to_dict()
    _record_admin_audit(user, 'delete', 'misc_cost', cost.id, f'Deleted shared cost {cost.title}', {'cost': cost_snapshot})
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
    start_date, end_date = _month_bounds(month_value)
    if not start_date:
        return jsonify({'error': 'month must use YYYY-MM'}), 400
    month_status = _monthly_invoice_status(month_value)
    expose_payment_details = bool(month_status and month_status.status in {'READY_FOR_PAYMENT', 'SETTLED'})

    users = User.query.order_by(User.name.asc(), User.email.asc(), User.phone.asc()).all()
    subjects = []
    by_key = {}
    user_by_id = {item.id: item for item in users}
    parent = {item.id: item.id for item in users}

    def find(user_id):
        while parent[user_id] != user_id:
            parent[user_id] = parent[parent[user_id]]
            user_id = parent[user_id]
        return user_id

    def union(left_id, right_id):
        left_root = find(left_id)
        right_root = find(right_id)
        if left_root == right_root:
            return
        winner = min(left_root, right_root)
        loser = max(left_root, right_root)
        parent[loser] = winner

    all_family_members = FamilyMember.query.all()
    for family_member in all_family_members:
        if family_member.user_id in parent and family_member.linked_user_id in parent:
            union(family_member.user_id, family_member.linked_user_id)

    owner_by_user_id = {}
    owner_aliases = {}
    for item in users:
        owner = user_by_id.get(find(item.id), item)
        owner_by_user_id[item.id] = owner
        owner_aliases.setdefault(owner.id, set()).update(filter(None, [owner.name, owner.email, owner.phone]))
        for member in item.family_members:
            owner_aliases[owner.id].update(
                alias
                for alias in [member.name, member.linked_user.name if member.linked_user else None, member.linked_user.email if member.linked_user else None, member.linked_user.phone if member.linked_user else None]
                if alias
            )
    for item in users:
        if owner_by_user_id[item.id].id != item.id:
            continue
        for candidate in users:
            if candidate.id == item.id or owner_by_user_id[candidate.id].id != candidate.id:
                continue
            candidate_aliases = [candidate.name, candidate.email, candidate.phone]
            matching_alias = any(
                _names_match(candidate_alias, owner_alias)
                for candidate_alias in candidate_aliases
                if candidate_alias
                for owner_alias in owner_aliases.get(item.id, set())
            )
            if matching_alias:
                owner_by_user_id[candidate.id] = item
                owner_aliases[item.id].update(filter(None, candidate_aliases))

    def add_subject(subject_id, display_name, user_obj=None, participant_keys=None, aliases=None):
        subject = {
            'id': subject_id,
            'display_name': display_name,
            'user': user_obj.to_dict() if user_obj else {
                'id': subject_id,
                'phone': subject_id,
                'email': None,
                'whatsapp_number': None,
                'name': display_name,
                'role': 'member',
                'is_club_member': False,
                'created_at': None,
            },
            'participant_keys': set(participant_keys or []),
            'aliases': [alias for alias in (aliases or []) if alias],
            'booking_items': [],
            'misc_items': [],
            'booking_total': 0.0,
            'misc_total': 0.0,
            'total': 0.0,
            'paid_amount': 0.0,
            'balance_amount': 0.0,
            'paid_count': 0,
            'family_title': display_name,
            'payment_invoice': None,
        }
        subjects.append(subject)
        for key in subject['participant_keys']:
            by_key[key] = subject
        return subject

    for item in users:
        owner = owner_by_user_id.get(item.id, item)
        if owner.id != item.id:
            continue
        family_names = []
        group_user_ids = {group_user.id for group_user in users if owner_by_user_id.get(group_user.id, group_user).id == item.id}
        incoming_names_by_user_id = {}
        for family_member in all_family_members:
            if family_member.user_id in group_user_ids and family_member.linked_user_id in group_user_ids and family_member.name:
                incoming_names_by_user_id.setdefault(family_member.linked_user_id, []).append(family_member.name)

        def preferred_account_name(account):
            account_name = account.name or account.email or account.phone
            for alias in incoming_names_by_user_id.get(account.id, []):
                normalized_account = _normalize_person_name(account_name)
                normalized_alias = _normalize_person_name(alias)
                if _names_match(alias, account_name):
                    return account_name if len(normalized_account) <= len(normalized_alias) else alias
                if len(normalized_account) <= 3:
                    return alias
            return account_name

        for group_user in users:
            if group_user.id not in group_user_ids:
                continue
            _append_unique_family_name(family_names, preferred_account_name(group_user))
        for group_user in users:
            if group_user.id not in group_user_ids:
                continue
            for family_member in sorted(group_user.family_members, key=lambda fm: fm.created_at or datetime.min):
                if family_member.linked_user_id:
                    continue
                if any(_names_match(family_member.name, preferred_account_name(account)) for account in users if account.id in group_user_ids):
                    continue
                _append_unique_family_name(family_names, family_member.name)
        display_name = ' & '.join(family_names) if family_names else _family_display_name(item)
        keys = [item.phone]
        aliases = [item.name, item.email, item.phone]
        add_subject(f'user:{item.id}', display_name, item, keys, aliases)
        subject = subjects[-1]
        for family_member in sorted(item.family_members, key=lambda fm: fm.created_at or datetime.min):
            subject['participant_keys'].add(f'family:{family_member.id}')
            subject['aliases'].append(family_member.name)
            by_key[f'family:{family_member.id}'] = subject
            if family_member.linked_user and family_member.linked_user.phone:
                subject['participant_keys'].add(family_member.linked_user.phone)
                subject['aliases'].extend([family_member.linked_user.name, family_member.linked_user.email, family_member.linked_user.phone])
                by_key[family_member.linked_user.phone] = subject
        for candidate in users:
            if candidate.id != item.id and owner_by_user_id.get(candidate.id, candidate).id == item.id:
                subject['participant_keys'].add(candidate.phone)
                subject['aliases'].extend([candidate.name, candidate.email, candidate.phone])
                by_key[candidate.phone] = subject

    def subject_for_participant(participant):
        if participant.phone in by_key:
            return by_key[participant.phone]
        label = participant.name or participant.phone or 'Player'
        for subject in subjects:
            if any(_names_match(label, alias) for alias in subject['aliases']):
                return subject
        key = f'adhoc:{_normalize_person_name(label) or participant.id}'
        subject = by_key.get(key)
        if not subject:
            subject = add_subject(key, label, None, [key], [label])
        return subject

    _mark_past_bookings_completed()
    bookings = (
        Booking.query
        .filter(
            Booking.booking_date >= start_date,
            Booking.booking_date < end_date,
            Booking.status.in_(COMPLETED_BOOKING_STATUSES),
        )
        .order_by(Booking.booking_date.asc(), Booking.start_time.asc())
        .all()
    )
    seen_booking_subjects = set()
    for booking in bookings:
        attending = [participant for participant in booking.participants if _is_cost_split_status(participant.status)]
        split_count = max(1, len(attending) or 1)
        split = rounded_up_cost_split(booking.cost, split_count)
        per_person = split['cost_per_person']
        for index, participant in enumerate(attending):
            participant_amount = split['participant_shares'][index]
            subject = subject_for_participant(participant)
            item_key = (booking.id, subject['id'])
            existing_item = next((item for item in subject['booking_items'] if item['booking_id'] == booking.id), None)
            if item_key in seen_booking_subjects and existing_item:
                subject['booking_total'] = round(subject['booking_total'] + participant_amount, 2)
                existing_item['attendee_count'] += 1
                existing_item['amount'] = round(float(existing_item['amount'] or 0.0) + participant_amount, 2)
                participant_label = participant.name or participant.phone or subject['display_name']
                if participant_label not in existing_item['participants']:
                    existing_item['participants'].append(participant_label)
                if participant_label not in existing_item['family_members']:
                    existing_item['family_members'].append(participant_label)
                continue
            seen_booking_subjects.add(item_key)
            subject['booking_total'] = round(subject['booking_total'] + participant_amount, 2)
            subject['booking_items'].append({
                'booking_id': booking.id,
                'title': subject['family_title'],
                'date': booking.booking_date,
                'court': booking.court.name if booking.court else None,
                'start_time': booking.start_time,
                'end_time': booking.end_time,
                'attendee_count': 1,
                'total_people_played': split_count,
                'total_cost': round(float(booking.cost or 0.0), 2),
                'cost_per_person': per_person,
                'participants': [participant.name or participant.phone or subject['display_name']],
                'family_members': [participant.name or participant.phone or subject['display_name']],
                'amount': participant_amount,
                'booking_status': booking.status,
                'invoice_status': booking.invoice[0].status if booking.invoice else 'not_generated',
            })

    # Shared misc costs remain split across registered users only.
    user_summaries = {}
    for item in users:
        owner = owner_by_user_id.get(item.id, item)
        if owner.id in user_summaries:
            continue
        user_summaries[owner.id] = _monthly_invoice_summary(owner, month_value)
    for subject in subjects:
        user_id = subject['user'].get('id') if isinstance(subject['user'].get('id'), int) else None
        if user_id in user_summaries:
            summary = user_summaries[user_id]
            subject['misc_items'] = summary['misc_items']
            subject['misc_total'] = summary['misc_total']
        if user_id and expose_payment_details:
            payment_invoice = PaymentInvoice.query.filter_by(user_id=user_id, month=month_value, is_test_invoice=False).first()
            if payment_invoice:
                subject['payment_invoice'] = payment_invoice.to_dict(include_qr=False)
        subject['total'] = round(subject['booking_total'] + subject['misc_total'], 2)
        subject['booking_total'] = round(subject['booking_total'], 2)
        subject['paid_count'] = len([item for item in subject['booking_items'] if item.get('invoice_status') == 'settled' and item.get('booking_status') == 'settled'])
        subject['paid_amount'] = round(sum(float(item.get('amount') or 0.0) for item in subject['booking_items'] if item.get('invoice_status') == 'settled' and item.get('booking_status') == 'settled'), 2)
        if subject['payment_invoice']:
            invoice_status = subject['payment_invoice'].get('payment_status')
            invoice_paid_amount = float(subject['payment_invoice'].get('paid_amount') or 0.0)
            if invoice_status == 'PAID':
                subject['paid_amount'] = subject['total']
            elif invoice_paid_amount > 0:
                subject['paid_amount'] = min(subject['total'], round(invoice_paid_amount, 2))
        subject['balance_amount'] = round(subject['total'] - subject['paid_amount'], 2)

    visible = [
        subject
        for subject in subjects
        if subject['booking_items'] or subject['misc_items'] or subject['payment_invoice'] or float(subject['total'] or 0.0) > 0
    ]
    for subject in visible:
        subject.pop('participant_keys', None)
        subject.pop('aliases', None)
        subject.pop('display_name', None)
    return jsonify({
        'month': month_value,
        'month_status': (month_status or MonthlyInvoiceStatus(month=month_value, status='OPEN')).to_dict(),
        'invoices': visible,
        'totals': {
            'booking_total': round(sum(item['booking_total'] for item in visible), 2),
            'misc_total': round(sum(item['misc_total'] for item in visible), 2),
            'total': round(sum(item['total'] for item in visible), 2),
        }
    })

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
        if role not in {'member', 'admin', 'super_admin'}:
            return jsonify({'error': 'invalid_role'}), 400
        if role == 'super_admin' and (admin.role or '').lower() != 'super_admin':
            return jsonify({'error': 'super_admin_required_for_role_changes'}), 403
        try:
            password = _normalize_password(data.get('password'))
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        user = User(
            phone=phone,
            email=(data.get('email') or '').strip().lower() or None,
            name=(data.get('name') or '').strip() or None,
            whatsapp_number=(data.get('whatsapp_number') or '').strip() or None,
            password_hash=pbkdf2_sha256.hash(password) if password else None,
            role=role,
            is_club_member=bool(data.get('is_club_member', False))
        )
        db.session.add(user)
        db.session.flush()
        _record_admin_audit(admin, 'create', 'user', user.id, f'Created user {_public_user_label(user)}', {'user': _admin_user_payload(user)})
        db.session.commit()
    return jsonify(_admin_user_payload(user))


@bookings_bp.route('/admin/users/<int:user_id>', methods=['PUT'])
def update_admin_user(user_id):
    admin, error = _require_admin()
    if error:
        return error

    target_user = User.query.get_or_404(user_id)
    before = _snapshot_fields(target_user, ['email', 'phone', 'name', 'whatsapp_number', 'role', 'is_club_member'])
    data = request.get_json() or {}
    password_changed = False

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
        if role not in {'member', 'admin', 'super_admin'}:
            return jsonify({'error': 'invalid_role'}), 400
        if role == 'super_admin' and (admin.role or '').lower() != 'super_admin':
            return jsonify({'error': 'super_admin_required_for_role_changes'}), 403
        if target_user.role == 'super_admin' and role != 'super_admin' and (admin.role or '').lower() != 'super_admin':
            return jsonify({'error': 'super_admin_required_for_role_changes'}), 403
        target_user.role = role
    if 'password' in data and data.get('password'):
        try:
            password = _normalize_password(data.get('password'))
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        target_user.password_hash = pbkdf2_sha256.hash(password)
        password_changed = True

    after = _snapshot_fields(target_user, ['email', 'phone', 'name', 'whatsapp_number', 'role', 'is_club_member'])
    changes = _changed_fields(before, after)
    if password_changed:
        changes['password'] = {'from': 'unchanged', 'to': 'reset'}
    if changes:
        _record_admin_audit(admin, 'update', 'user', target_user.id, f'Updated user {_public_user_label(target_user)}', {'changes': changes})
    db.session.commit()
    return jsonify(_admin_user_payload(target_user))


@bookings_bp.route('/admin/users/<int:user_id>', methods=['DELETE'])
def delete_admin_user(user_id):
    user, error = _require_admin()
    if error:
        return error

    target_user = User.query.get_or_404(user_id)
    user_snapshot = _admin_user_payload(target_user)

    _record_admin_audit(user, 'delete', 'user', target_user.id, f'Deleted user {_public_user_label(target_user)}', {'user': user_snapshot})
    FamilyMember.query.filter_by(user_id=target_user.id).delete()
    FamilyMember.query.filter_by(linked_user_id=target_user.id).update(
        {FamilyMember.linked_user_id: None},
        synchronize_session=False
    )
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
    before = _snapshot_fields(member, ['name', 'relationship', 'is_club_member', 'linked_user_id'])
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
    if 'linked_user_id' in data:
        linked_user_id = data.get('linked_user_id')
        if linked_user_id in ('', None):
            member.linked_user_id = None
        else:
            linked_user = User.query.get(linked_user_id)
            if not linked_user:
                return jsonify({'error': 'linked_user_not_found'}), 404
            if linked_user.id == member.user_id:
                return jsonify({'error': 'cannot_link_owner_as_family_member'}), 400
            member.linked_user_id = linked_user.id

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

    linked_user_id = data.get('linked_user_id') or None
    if linked_user_id:
        linked_user = User.query.get(linked_user_id)
        if not linked_user:
            return jsonify({'error': 'linked_user_not_found'}), 404
        if linked_user.id == owner.id:
            return jsonify({'error': 'cannot_link_owner_as_family_member'}), 400
        linked_user_id = linked_user.id

    member = FamilyMember(
        user_id=owner.id,
        name=name,
        relationship=(data.get('relationship') or '').strip() or None,
        is_club_member=bool(data.get('is_club_member', False)),
        linked_user_id=linked_user_id
    )
    db.session.add(member)
    db.session.flush()
    _record_admin_audit(user, 'create', 'family_member', member.id, f'Created family member {member.name}', {'family_member': member.to_dict(), 'owner_id': owner.id})
    db.session.commit()
    return jsonify(member.to_dict())


@bookings_bp.route('/admin/family-members/<int:member_id>', methods=['DELETE'])
def delete_admin_family_member(member_id):
    user, error = _require_admin()
    if error:
        return error

    member = FamilyMember.query.get_or_404(member_id)
    member_snapshot = member.to_dict()
    _record_admin_audit(user, 'delete', 'family_member', member.id, f'Deleted family member {member.name}', {'family_member': member_snapshot})
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
    db.session.flush()
    _record_admin_audit(user, 'create', 'court', court.id, f'Created court {court.name}', {'court': court.to_dict()})
    db.session.commit()
    return jsonify(court.to_dict())


@bookings_bp.route('/admin/courts', methods=['GET'])
def list_courts():
    user, error = _require_admin()
    if error:
        return error

    include_inactive = (request.args.get('include_inactive') or '1').lower() not in {'0', 'false', 'no'}
    query = Court.query
    if not include_inactive:
        query = query.filter_by(is_active=True)
    courts = query.order_by(Court.name.asc()).all()
    return jsonify({'courts': [court.to_dict() for court in courts]})


@bookings_bp.route('/admin/courts/<int:court_id>', methods=['PUT'])
def update_court(court_id):
    user, error = _require_admin()
    if error:
        return error

    court = Court.query.get_or_404(court_id)
    before = _snapshot_fields(court, ['name', 'location', 'description', 'map_link', 'hourly_rate', 'half_hour_rate', 'is_active'])
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
    after = _snapshot_fields(court, ['name', 'location', 'description', 'map_link', 'hourly_rate', 'half_hour_rate', 'is_active'])
    changes = _changed_fields(before, after)
    if changes:
        _record_admin_audit(user, 'update', 'court', court.id, f'Updated court {court.name}', {'changes': changes})
    db.session.commit()
    return jsonify(court.to_dict())


@bookings_bp.route('/admin/courts/<int:court_id>', methods=['DELETE'])
def delete_court(court_id):
    user, error = _require_admin()
    if error:
        return error

    court = Court.query.get_or_404(court_id)
    before = court.to_dict()
    court.is_active = False
    _record_admin_audit(user, 'delete', 'court', court.id, f'Deleted court {court.name}', {'court': before})
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
    db.session.flush()
    _record_admin_audit(user, 'create', 'freeze_period', period.id, f'Created freeze period {period.title}', {'freeze_period': period.to_dict()})
    db.session.commit()
    return jsonify(period.to_dict()), 201


@bookings_bp.route('/admin/freeze-periods/<int:period_id>', methods=['PUT'])
def update_freeze_period(period_id):
    user, error = _require_admin()
    if error:
        return error
    period = CourtFreezePeriod.query.get_or_404(period_id)
    before = _snapshot_fields(period, ['title', 'start_date', 'end_date', 'reason', 'is_active'])
    validation_error = _apply_freeze_period_data(period, request.get_json() or {})
    if validation_error:
        return validation_error
    after = _snapshot_fields(period, ['title', 'start_date', 'end_date', 'reason', 'is_active'])
    changes = _changed_fields(before, after)
    if changes:
        _record_admin_audit(user, 'update', 'freeze_period', period.id, f'Updated freeze period {period.title}', {'changes': changes})
    db.session.commit()
    return jsonify(period.to_dict())


@bookings_bp.route('/admin/freeze-periods/<int:period_id>', methods=['DELETE'])
def delete_freeze_period(period_id):
    user, error = _require_admin()
    if error:
        return error
    period = CourtFreezePeriod.query.get_or_404(period_id)
    period_snapshot = period.to_dict()
    _record_admin_audit(user, 'delete', 'freeze_period', period.id, f'Deleted freeze period {period.title}', {'freeze_period': period_snapshot})
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
        'description': 'Automatically remind the WhatsApp group one hour before a booking starts today.',
        'template': '⏰ Reminder: badminton starts at {{start_time}} today on {{court}}. Please update your attendance in the app.',
    },
    {
        'event_key': 'availability_summary',
        'title': 'Availability overview',
        'description': 'Share a holistic availability overview for the next few playable days.',
        'template': '{{overview}}',
        'is_enabled': True,
    },
    {
        'event_key': 'monthly_invoice_ready',
        'title': 'Monthly invoices ready',
        'description': 'Notify the WhatsApp group once the monthly invoice run is ready for payment.',
        'template': '💶 Monthly badminton invoices for {{month}} are ready. {{note}} Open: {{app_url}}',
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
            setting = existing[spec['event_key']]
            if spec['event_key'] == 'availability_summary' and '{{overview}}' not in (setting.template or ''):
                setting.title = spec['title']
                setting.description = spec['description']
                setting.template = spec['template']
                changed = True
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


def _normalize_whatsapp_test_recipient(recipient):
    recipient = (recipient or '').strip()
    if not recipient:
        return None
    if '@' in recipient:
        return recipient
    digits = ''.join(ch for ch in recipient if ch.isdigit())
    if not digits:
        return recipient
    return f'{digits}@c.us'


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


def _whatsapp_setting(event_key):
    from .models import WhatsAppNotificationSetting
    _ensure_whatsapp_notification_settings()
    return WhatsAppNotificationSetting.query.filter_by(event_key=event_key).first()


def _whatsapp_known_test_recipients():
    from .models import WhatsAppNotificationSetting
    _ensure_whatsapp_notification_settings()
    recipients = []
    seen = set()
    settings = WhatsAppNotificationSetting.query.filter(WhatsAppNotificationSetting.test_recipient_number.isnot(None)).order_by(WhatsAppNotificationSetting.title.asc()).all()
    for setting in settings:
        value = (setting.test_recipient_number or '').strip()
        normalized = _normalize_whatsapp_test_recipient(value)
        if not value or normalized in seen:
            continue
        seen.add(normalized)
        recipients.append({'label': f'{setting.title}: {value}', 'value': value, 'normalized': normalized})
    return recipients


def _log_whatsapp_message(setting, message, recipient, response_suffix=None):
    from .models import WhatsAppNotificationLog
    status, response_text = _send_whatsapp_bot_message(message, recipient)
    log = WhatsAppNotificationLog(
        setting_id=setting.id if setting else None,
        event_key=setting.event_key if setting else 'custom_notification',
        recipient=recipient,
        message=message,
        status=status,
        response=f'{response_text}\n{response_suffix}' if response_suffix else response_text,
    )
    db.session.add(log)
    db.session.commit()
    return log


def _send_whatsapp_event(event_key, context, dedupe_key=None, message_override=None, recipient_override=None, force=False):
    setting = _whatsapp_setting(event_key)
    if not setting or (not force and (not setting.is_enabled or not setting.send_to_group)):
        return None
    if dedupe_key and not force:
        from .models import WhatsAppNotificationLog
        existing_log = WhatsAppNotificationLog.query.filter(
            WhatsAppNotificationLog.event_key == event_key,
            WhatsAppNotificationLog.response.contains(dedupe_key)
        ).first()
        if existing_log:
            return None

    message = message_override if message_override is not None else _render_template(setting.template, context)
    recipient = recipient_override if recipient_override is not None else (setting.group_id or '').strip() or _fallback_whatsapp_group_id(event_key)
    return _log_whatsapp_message(setting, message, recipient, response_suffix=dedupe_key if dedupe_key else None)



def _amsterdam_now(now=None):
    if now is None:
        return datetime.now(AMSTERDAM_TZ)
    if now.tzinfo is None:
        return now.replace(tzinfo=AMSTERDAM_TZ)
    return now.astimezone(AMSTERDAM_TZ)


def _send_due_booking_reminders(now=None):
    amsterdam_now = _amsterdam_now(now)
    today_value = amsterdam_now.date().strftime('%Y-%m-%d')
    bookings = Booking.query.filter(
        Booking.booking_date == today_value,
        Booking.status.in_({'confirmed'})
    ).order_by(Booking.start_time.asc()).all()
    sent_logs = []
    for booking in bookings:
        start_minutes = _time_to_minutes(booking.start_time)
        if start_minutes is None:
            continue
        start_at = datetime.combine(amsterdam_now.date(), datetime.min.time(), tzinfo=AMSTERDAM_TZ) + timedelta(minutes=start_minutes)
        seconds_until_start = (start_at - amsterdam_now).total_seconds()
        if 0 < seconds_until_start <= 3600:
            dedupe_key = f'booking_reminder:{booking.id}:{booking.booking_date}:{booking.start_time}:Europe/Amsterdam'
            log = _send_whatsapp_event('booking_reminder', _booking_notification_context(booking), dedupe_key=dedupe_key)
            if log:
                sent_logs.append(log)
    return sent_logs


def _availability_summary_context(days_payload):
    included_days = []
    lines = ['🏸 Availability overview (next few playable days)']
    for day in days_payload:
        totals = day.get('totals') or {}
        available = [item.get('name') or 'Member' for item in totals.get('available_attendees') or []]
        tentative = [item.get('name') or 'Member' for item in totals.get('tentative_attendees') or []]
        if not available and not tentative:
            continue
        included_days.append(day)
        lines.append(f"\n{day.get('weekday')} {day.get('date')}")
        lines.append(f"✅ Available ({len(available)}): {', '.join(available) if available else 'None'}")
        lines.append(f"🤔 Tentative ({len(tentative)}): {', '.join(tentative) if tentative else 'None'}")
    if not included_days:
        lines.append('\nNo available or tentative votes yet for the next few playable days.')
    lines.append('\nOpen the app to update your status.')
    overview = '\n'.join(lines)
    return {
        'overview': overview,
        'days_overview': overview,
        'date_range': f"{days_payload[0]['date']} to {days_payload[-1]['date']}" if days_payload else '',
        'days_count': len(included_days),
        'available_count': sum((day.get('totals') or {}).get('available_count', 0) for day in days_payload),
        'tentative_count': sum((day.get('totals') or {}).get('tentative_count', 0) for day in days_payload),
    }


def _availability_days_payload(days=7, start=None):
    start = start or _amsterdam_now().date()
    dates = _next_playable_dates(days, start=start)
    date_values = [date_value.strftime('%Y-%m-%d') for date_value in dates]
    votes = PlayAvailabilityVote.query.filter(PlayAvailabilityVote.play_date.in_(date_values)).all()
    totals = {}
    attendees_by_date = {}
    for vote in votes:
        totals.setdefault(vote.play_date, {
            'available_count': 0,
            'tentative_count': 0,
            'available_attendees': [],
            'tentative_attendees': [],
        })
        attendees_by_date.setdefault(vote.play_date, {})
        vote_payload = vote.to_dict()
        attendees = vote_payload.get('attendee_details') or []
        status = vote.status or ('available' if vote.available else 'not_available')
        fallback_name = vote.user.name or vote.user.email or vote.user.phone if vote.user else 'Member'
        if not attendees and status in {'available', 'tentative'}:
            attendees = [{'type': 'self', 'name': fallback_name, 'status': status, 'phone': vote.user.phone if vote.user else None}]
        for attendee in attendees:
            attendee_status = attendee.get('status', status)
            if attendee_status in {'available', 'tentative'}:
                _availability_merge_attendee(attendees_by_date[vote.play_date], attendee, attendee_status, fallback_user_id=vote.user_id)
    for date_value, attendees_by_key in attendees_by_date.items():
        available_attendees = [attendee for attendee in attendees_by_key.values() if attendee.get('status') == 'available']
        tentative_attendees = [attendee for attendee in attendees_by_key.values() if attendee.get('status') == 'tentative']
        totals[date_value] = {
            'available_count': len(available_attendees),
            'tentative_count': len(tentative_attendees),
            'available_attendees': available_attendees,
            'tentative_attendees': tentative_attendees,
        }
    return [{
        'date': date_value,
        'weekday': datetime.strptime(date_value, '%Y-%m-%d').strftime('%A'),
        'totals': totals.get(date_value, {'available_count': 0, 'tentative_count': 0, 'available_attendees': [], 'tentative_attendees': []}),
    } for date_value in date_values]

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



@bookings_bp.route('/admin/booking-reminders/run', methods=['POST'])
def run_booking_reminders():
    user, error = _require_admin()
    if error:
        return error
    logs = _send_due_booking_reminders()
    return jsonify({'sent': len(logs), 'logs': [log.to_dict() for log in logs]})


def _availability_summary_preview(days=7):
    days = min(max(int(days or 7), 1), 14)
    days_payload = _availability_days_payload(days=days)
    context = _availability_summary_context(days_payload)
    setting = _whatsapp_setting('availability_summary')
    message = _render_template(setting.template if setting else '{{overview}}', context)
    recipient = (setting.group_id or '').strip() or _fallback_whatsapp_group_id('availability_summary') if setting else None
    return setting, context, message, recipient, days


@bookings_bp.route('/admin/availability-summary/preview', methods=['POST'])
def preview_availability_summary():
    _, error = _require_admin()
    if error:
        return error
    data = request.get_json() or {}
    setting, context, message, recipient, days = _availability_summary_preview(data.get('days', 7))
    return jsonify({
        'message': message,
        'context': context,
        'recipient': recipient,
        'setting': setting.to_dict() if setting else None,
        'test_recipients': _whatsapp_known_test_recipients(),
        'days': days,
    })


@bookings_bp.route('/admin/availability-summary/send', methods=['POST'])
def send_availability_summary():
    user, error = _require_admin()
    if error:
        return error
    data = request.get_json() or {}
    setting, context, message, recipient, days = _availability_summary_preview(data.get('days', 7))
    message = (data.get('message') or message).strip()
    if not message:
        return jsonify({'error': 'message required'}), 400
    send_test = bool(data.get('test'))
    recipient_override = None
    if send_test:
        recipient_override = _normalize_whatsapp_test_recipient(data.get('recipient'))
        if not recipient_override:
            return jsonify({'error': 'test recipient required'}), 400
    log = _send_whatsapp_event('availability_summary', context, message_override=message, recipient_override=recipient_override, force=send_test)
    if log:
        summary = 'Sent availability overview test notification' if send_test else 'Sent availability overview notification'
        _record_admin_audit(user, 'send', 'whatsapp_notification', log.id, summary, {'days': days, 'status': log.status, 'test': send_test, 'recipient': log.recipient})
    return jsonify({'sent': 1 if log else 0, 'message': message, 'status': log.status if log else 'skipped', 'log': log.to_dict() if log else None})


@bookings_bp.route('/admin/audit-logs', methods=['GET'])
def list_admin_audit_logs():
    user, error = _require_admin()
    if error:
        return error

    page = _positive_int_arg('page', 1)
    per_page = _positive_int_arg('per_page', 50, maximum=100)
    query = AdminAuditLog.query.order_by(AdminAuditLog.occurred_at.desc(), AdminAuditLog.id.desc())
    total = query.count()
    logs = query.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'logs': [log.to_dict() for log in logs],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page if total else 0,
        }
    })

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
    before = _snapshot_fields(setting, ['title', 'description', 'template', 'is_enabled', 'send_to_group', 'group_id', 'test_recipient_number'])
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
    if 'test_recipient_number' in data:
        setting.test_recipient_number = (data.get('test_recipient_number') or '').strip() or None
    after = _snapshot_fields(setting, ['title', 'description', 'template', 'is_enabled', 'send_to_group', 'group_id', 'test_recipient_number'])
    changes = _changed_fields(before, after)
    if changes:
        _record_admin_audit(user, 'update', 'whatsapp_notification', setting.id, f'Updated WhatsApp notification {setting.title}', {'changes': changes})
    db.session.commit()
    return jsonify(setting.to_dict())


def _whatsapp_sample_context(setting, data=None):
    data = data or {}
    return {
        'court': data.get('court', data.get('court_name', 'Sample court')),
        'court_name': data.get('court_name', data.get('court', 'Sample court')),
        'court.name': data.get('court_name', data.get('court', 'Sample court')),
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


@bookings_bp.route('/admin/whatsapp-notifications/<int:setting_id>/preview', methods=['POST'])
def preview_whatsapp_notification(setting_id):
    _, error = _require_admin()
    if error:
        return error
    from .models import WhatsAppNotificationSetting
    setting = WhatsAppNotificationSetting.query.get_or_404(setting_id)
    data = request.get_json() or {}
    message = data.get('message') or _render_template(setting.template, _whatsapp_sample_context(setting, data))
    recipient = (setting.group_id or '').strip() or _fallback_whatsapp_group_id(setting.event_key)
    return jsonify({'message': message, 'recipient': recipient, 'setting': setting.to_dict(), 'test_recipients': _whatsapp_known_test_recipients()})


@bookings_bp.route('/admin/whatsapp-notifications/<int:setting_id>/send', methods=['POST'])
def send_whatsapp_notification(setting_id):
    user, error = _require_admin()
    if error:
        return error
    from .models import WhatsAppNotificationSetting
    setting = WhatsAppNotificationSetting.query.get_or_404(setting_id)
    data = request.get_json() or {}
    message = (data.get('message') or _render_template(setting.template, _whatsapp_sample_context(setting, data))).strip()
    if not message:
        return jsonify({'error': 'message required'}), 400
    if data.get('test'):
        recipient = _normalize_whatsapp_test_recipient(data.get('recipient') or setting.test_recipient_number)
        if not recipient:
            return jsonify({'error': 'test recipient required'}), 400
    else:
        recipient = (setting.group_id or '').strip() or _fallback_whatsapp_group_id(setting.event_key)
    log = _log_whatsapp_message(setting, message, recipient)
    _record_admin_audit(user, 'send', 'whatsapp_notification', log.id, f'Sent WhatsApp notification {setting.title}', {'status': log.status, 'test': bool(data.get('test')), 'recipient': log.recipient})
    return jsonify({'status': log.status, 'message': message, 'log': log.to_dict()})


@bookings_bp.route('/admin/whatsapp-notifications/<int:setting_id>/test', methods=['POST'])
def test_whatsapp_notification(setting_id):
    user, error = _require_admin()
    if error:
        return error
    from .models import WhatsAppNotificationLog, WhatsAppNotificationSetting
    setting = WhatsAppNotificationSetting.query.get_or_404(setting_id)
    data = request.get_json() or {}
    message = _render_template(setting.template, _whatsapp_sample_context(setting, data))
    recipient = _normalize_whatsapp_test_recipient(data.get('recipient') or setting.test_recipient_number)
    if not recipient:
        recipient = (setting.group_id or '').strip() or None
    status, response_text = _send_whatsapp_bot_message(message, recipient)
    log = WhatsAppNotificationLog(setting_id=setting.id, event_key=setting.event_key, recipient=recipient, message=message, status=status, response=response_text)
    db.session.add(log)
    db.session.commit()
    return jsonify({'message': message, 'log': log.to_dict()})

# --- Payment and bank-transfer invoice administration ---
import base64
from io import BytesIO
import re as _payment_re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import requests
try:
    import qrcode
except Exception:  # pragma: no cover - dependency is declared, fallback keeps app importable
    qrcode = None

from .models import PaymentAuditLog, PaymentInvoice, PaymentSettings, WiseWebhookEvent

PAYMENT_STATUSES = {'UNPAID', 'PAID', 'PARTIALLY_PAID', 'CANCELLED', 'EXPIRED'}


def _is_admin_user(user):
    return (user.role or '').lower() in {'admin', 'super_admin'}


def _is_super_admin_user(user):
    return (user.role or '').lower() == 'super_admin'


def _require_any_admin():
    user, error = _require_login()
    if error:
        return None, error
    if not _is_admin_user(user):
        return None, (jsonify({'error': 'admin_required'}), 403)
    return user, None


def _require_super_admin():
    user, error = _require_login()
    if error:
        return None, error
    if not _is_super_admin_user(user):
        return None, (jsonify({'error': 'super_admin_required'}), 403)
    return user, None


def _normalized_role(role):
    role = (role or 'member').strip().lower()
    return 'super_admin' if role == 'super_admin' else role


def _valid_iban(iban):
    iban = ''.join(ch for ch in (iban or '').upper() if ch.isalnum())
    if not iban:
        return False
    if not _payment_re.match(r'^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$', iban):
        return False
    rearranged = iban[4:] + iban[:4]
    digits = ''.join(str(ord(ch) - 55) if ch.isalpha() else ch for ch in rearranged)
    return int(digits) % 97 == 1


def _payment_settings():
    settings = PaymentSettings.query.order_by(PaymentSettings.id.asc()).first()
    if not settings:
        settings = PaymentSettings(payment_provider='WISE_API', test_mode=True, qr_enabled=True, default_due_days=14)
        db.session.add(settings)
        db.session.flush()
    elif settings.payment_provider != 'WISE_API':
        settings.payment_provider = 'WISE_API'
        db.session.flush()
    return settings


def _next_payment_reference():
    year = datetime.utcnow().year
    prefix = f'INV-{year}-'
    latest_numbers = PaymentInvoice.query.with_entities(PaymentInvoice.invoice_number).filter(PaymentInvoice.invoice_number.like(f'{prefix}%')).all()
    latest_suffix = 0
    for (invoice_number,) in latest_numbers:
        try:
            latest_suffix = max(latest_suffix, int((invoice_number or '').replace(prefix, '', 1)))
        except ValueError:
            continue
    next_id = latest_suffix + 1
    return f'{prefix}{next_id:05d}'


def _epc_payload(settings, amount, reference):
    name = settings.effective_account_holder_name()
    iban = settings.effective_iban().replace(' ', '')
    description = f'{settings.description_prefix or "Invoice"} {reference}'[:140]
    # Dutch banking apps are stricter with EPC QR parsing: for EEA IBANs use
    # version 002, Latin-1 character set marker, and omit the optional BIC.
    return '\n'.join(['BCD', '002', '2', 'SCT', '', name[:70], iban, f'EUR{float(amount or 0):.2f}', '', '', description])


def _wise_payment_url(settings, amount, reference):
    base_url = (settings.wise_payment_url or 'https://wise.com/pay/business/verenigingnieuwegeinbadminton?utm_source=open_link').strip()
    if not base_url:
        return None
    description = f'{settings.description_prefix or "Invoice"} {reference}'[:140]
    values = {
        'amount': f'{float(amount or 0):.2f}',
        'currency': 'EUR',
        'reference': reference,
        'description': description,
        'iban': settings.effective_iban().replace(' ', ''),
        'account_holder_name': settings.effective_account_holder_name(),
        'account_holder': settings.effective_account_holder_name(),
    }
    if any(f'{{{key}}}' in base_url for key in values):
        payment_url = base_url
        for key, value in values.items():
            payment_url = payment_url.replace(f'{{{key}}}', str(value))
        return payment_url
    split = urlsplit(base_url)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    query.setdefault('amount', values['amount'])
    query.setdefault('currency', values['currency'])
    query.setdefault('reference', values['reference'])
    query.setdefault('description', values['description'])
    query.setdefault('iban', values['iban'])
    query.setdefault('accountHolder', values['account_holder_name'])
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), split.fragment))


def _wise_api_base_url(settings):
    return (settings.wise_api_base_url or 'https://api.wise.com').rstrip('/')


def _wise_api_headers(settings):
    token = (settings.wise_api_token or '').strip()
    if not token:
        raise ValueError('wise_api_token_required')
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }


def _wise_business_profile_id(settings):
    if settings.wise_profile_id:
        return settings.wise_profile_id
    response = requests.get(f'{_wise_api_base_url(settings)}/v1/profiles', headers=_wise_api_headers(settings), timeout=10)
    response.raise_for_status()
    profiles = response.json() or []
    business = next((profile for profile in profiles if (profile.get('type') or '').upper() == 'BUSINESS'), None)
    if not business or not business.get('id'):
        raise ValueError('wise_business_profile_not_found')
    settings.wise_profile_id = str(business['id'])
    return settings.wise_profile_id


def _wise_create_payment_request(settings, invoice):
    profile_id = _wise_business_profile_id(settings)
    payload = {
        'amount': round(float(invoice.amount_due or 0.0), 2),
        'currency': 'EUR',
        'payInMethods': ['BANK_TRANSFER'],
        'reference': invoice.payment_reference or invoice.invoice_number,
    }
    if settings.wise_redirect_url:
        payload['redirectUrl'] = settings.wise_redirect_url
    base_url = _wise_api_base_url(settings)
    endpoints = [
        f'{base_url}/v3/profiles/{profile_id}/payment-requests',
        f'{base_url}/v1/profiles/{profile_id}/payment-requests',
        f'{base_url}/v1/payment-requests',
    ]
    response = None
    for endpoint in endpoints:
        response = requests.post(endpoint, headers=_wise_api_headers(settings), json=payload, timeout=15)
        if response.status_code != 404:
            break
    if response is None:
        raise ValueError('wise_payment_url_missing')
    response.raise_for_status()
    data = response.json() or {}
    payment_url = data.get('url') or data.get('checkoutUrl') or data.get('paymentUrl')
    if not payment_url:
        raise ValueError('wise_payment_url_missing')
    invoice.wise_payment_request_id = str(data.get('id') or '')
    return payment_url


def _wise_create_webhook_subscription(settings):
    client_key = (settings.wise_client_key or '').strip()
    webhook_url = (settings.wise_webhook_url or '').strip()
    if not client_key:
        raise ValueError('wise_client_key_required')
    if not webhook_url:
        raise ValueError('wise_webhook_url_required')
    payload = {
        'name': 'Badminton incoming transfer subscription',
        'trigger_on': 'incoming-transfer#credited',
        'delivery': {
            'version': '4.0.0',
            'url': webhook_url,
        },
    }
    response = requests.post(
        f'{_wise_api_base_url(settings)}/v3/applications/{client_key}/subscriptions',
        headers=_wise_api_headers(settings),
        json=payload,
        timeout=15,
    )
    response.raise_for_status()
    data = response.json() or {}
    subscription_id = data.get('id') or data.get('subscription_id')
    if not subscription_id:
        raise ValueError('wise_subscription_id_missing')
    settings.wise_webhook_subscription_id = str(subscription_id)
    return data


def _wise_request_error_message(exc):
    message = str(exc)
    if isinstance(exc, requests.exceptions.ConnectionError):
        message = 'Wise API is unreachable due to a network or DNS connection error. Retry once DNS/network connectivity is restored.'
    elif isinstance(exc, requests.exceptions.Timeout):
        message = 'Wise API request timed out. Retry once Wise is reachable.'
    if len(message) > 240:
        message = message[:240] + '...'
    return message


def _wise_fetch_incoming_transfer(settings, incoming_transfer_id):
    base_url = _wise_api_base_url(settings)
    profile_id = (settings.wise_profile_id or '').strip()
    endpoints = [
        f'{base_url}/v1/transfers/{incoming_transfer_id}',
        f'{base_url}/v1/incoming-transfers/{incoming_transfer_id}',
        f'{base_url}/v3/incoming-transfers/{incoming_transfer_id}',
    ]
    if profile_id:
        endpoints.extend([
            f'{base_url}/v3/profiles/{profile_id}/transfers/{incoming_transfer_id}',
            f'{base_url}/v1/profiles/{profile_id}/incoming-transfers/{incoming_transfer_id}',
            f'{base_url}/v3/profiles/{profile_id}/incoming-transfers/{incoming_transfer_id}',
        ])
    response = None
    last_request_error = None
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, headers=_wise_api_headers(settings), timeout=15)
        except requests.exceptions.RequestException as exc:
            last_request_error = exc
            continue
        if response.status_code != 404:
            break
    if response is None:
        if last_request_error is not None:
            raise last_request_error
        raise ValueError('wise_incoming_transfer_missing')
    response.raise_for_status()
    return response.json() or {}


def _flatten_text_values(value):
    values = []
    if isinstance(value, dict):
        for child in value.values():
            values.extend(_flatten_text_values(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_flatten_text_values(child))
    elif value is not None:
        values.append(str(value))
    return values


def _reference_parts(value):
    parts = []
    current = []
    for ch in str(value or '').upper():
        if ch.isalnum():
            current.append(ch)
            continue
        if current:
            parts.append(''.join(current))
            current = []
    if current:
        parts.append(''.join(current))
    return parts


def _reference_aliases(value):
    parts = _reference_parts(value)
    aliases = []
    if parts:
        aliases.append(''.join(parts))
        if len(parts[-1]) >= 4:
            aliases.append(parts[-1])
    deduped = []
    seen = set()
    for alias in aliases:
        if alias and alias not in seen:
            seen.add(alias)
            deduped.append(alias)
    return deduped


def _invoice_reference_aliases(invoice):
    exact = []
    suffix = []
    for candidate in [invoice.payment_reference, invoice.invoice_number]:
        aliases = _reference_aliases(candidate)
        if aliases:
            exact.append(aliases[0])
            if len(aliases) > 1 and len(aliases[1]) >= 5:
                suffix.append(aliases[1])
    return exact, suffix


def _transfer_reference_search(data):
    values = _flatten_text_values(data)
    text = ''.join(_reference_parts(' '.join(values)))
    aliases = set()
    for value in values:
        aliases.update(_reference_aliases(value))
    return text, aliases


def _deep_value(data, keys):
    if isinstance(data, dict):
        for key, value in data.items():
            if key in keys and value not in (None, ''):
                return value
            found = _deep_value(value, keys)
            if found not in (None, ''):
                return found
    elif isinstance(data, list):
        for item in data:
            found = _deep_value(item, keys)
            if found not in (None, ''):
                return found
    return None


def _incoming_transfer_id_from_payload(payload):
    data = payload.get('data') or {}
    candidates = [
        data.get('incoming_transfer_id') if isinstance(data, dict) else None,
        data.get('incomingTransferId') if isinstance(data, dict) else None,
        payload.get('incoming_transfer_id'),
        payload.get('incomingTransferId'),
        _deep_value(payload, {'incoming_transfer_id', 'incomingTransferId'}),
    ]
    resource = data.get('resource') if isinstance(data, dict) else None
    if isinstance(resource, dict):
        candidates.extend([resource.get('id'), resource.get('resourceId')])
    for candidate in candidates:
        if candidate not in (None, ''):
            return str(candidate)
    return None


def _incoming_transfer_amount(data):
    amount_value = _deep_value(data, {'amount', 'value', 'sourceAmount', 'sourceValue', 'targetAmount', 'targetValue'})
    try:
        if isinstance(amount_value, dict):
            amount_value = amount_value.get('value') or amount_value.get('amount')
        return round(float(amount_value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _incoming_transfer_currency(data):
    return _deep_value(data, {'currency', 'sourceCurrency', 'targetCurrency'})


def _incoming_transfer_reference(data):
    reference = _deep_value(data, {'reference', 'paymentReference', 'remittanceInformation', 'description', 'message'})
    return str(reference) if reference not in (None, '') else ''


def _incoming_transfer_sender(data):
    sender = _deep_value(data, {'senderName', 'debtorName', 'name'})
    return str(sender) if sender not in (None, '') else ''


def _match_invoice_for_reference_blob(invoices, data):
    text, aliases = _transfer_reference_search(data)
    exact_matches = []
    suffix_matches = []
    for invoice in invoices:
        exact_aliases, suffix_aliases = _invoice_reference_aliases(invoice)
        for alias in exact_aliases:
            if alias and (alias in aliases or alias in text):
                exact_matches.append((invoice, alias, 'full_reference'))
                break
        else:
            for alias in suffix_aliases:
                if alias and alias in aliases:
                    suffix_matches.append((invoice, alias, 'suffix_reference'))
                    break
    if exact_matches:
        invoice, alias, reason = exact_matches[0]
        return invoice, {'match_reason': reason, 'matched_alias': alias}
    unique_suffix_matches = {item[0].id: item for item in suffix_matches}
    if len(unique_suffix_matches) == 1:
        invoice, alias, reason = next(iter(unique_suffix_matches.values()))
        return invoice, {'match_reason': reason, 'matched_alias': alias}
    return None, {
        'match_reason': 'unmatched',
        'searched_aliases': sorted(aliases)[:12],
    }


def _find_invoice_for_incoming_transfer(data, invoices=None):
    invoice_list = invoices
    if invoice_list is None:
        # Wise webhooks can arrive after an invoice was manually marked paid, or
        # after a previous retry applied the payment but failed to attach the
        # event. Match across all invoices so diagnostics/retry can still link
        # the webhook event to the invoice reference.
        invoice_list = PaymentInvoice.query.order_by(PaymentInvoice.created_at.desc()).all()
    return _match_invoice_for_reference_blob(invoice_list, data)


def _payment_invoice_lookup(query, include_paid=True):
    query = (query or '').strip()
    if not query:
        return None
    query_aliases = _reference_aliases(query)
    if not query_aliases:
        return None
    invoices_query = PaymentInvoice.query.order_by(PaymentInvoice.created_at.desc())
    if not include_paid:
        invoices_query = invoices_query.filter(PaymentInvoice.payment_status != 'PAID')
    invoices = invoices_query.all()
    exact_matches = []
    suffix_matches = []
    for invoice in invoices:
        exact_aliases, suffix_aliases = _invoice_reference_aliases(invoice)
        if any(alias in exact_aliases for alias in query_aliases):
            exact_matches.append((invoice, 'full_reference'))
            continue
        for alias in query_aliases[1:]:
            if alias and alias in suffix_aliases:
                suffix_matches.append((invoice, 'suffix_reference'))
                break
        else:
            for alias in query_aliases:
                if any(candidate and alias in candidate for candidate in exact_aliases):
                    exact_matches.append((invoice, 'contains_reference'))
                    break
    if exact_matches:
        invoice, reason = exact_matches[0]
        return {'invoice': invoice, 'match_reason': reason}
    unique_suffix_matches = {item[0].id: item for item in suffix_matches}
    if len(unique_suffix_matches) == 1:
        invoice, reason = next(iter(unique_suffix_matches.values()))
        return {'invoice': invoice, 'match_reason': reason}
    return None


def _related_wise_events(invoice=None, query=None, limit=10):
    query_aliases = set(_reference_aliases(query))
    events = WiseWebhookEvent.query.order_by(WiseWebhookEvent.created_at.desc()).limit(max(limit, 1) * 4).all()
    related = []
    for event in events:
        if invoice and event.invoice_id == invoice.id:
            related.append(event)
            continue
        event_aliases = set(_reference_aliases(event.reference))
        if query_aliases and query_aliases.intersection(event_aliases):
            related.append(event)
    return related[:limit]


def _process_wise_incoming_transfer_event(event, settings, incoming_transfer_id):
    transfer = _wise_fetch_incoming_transfer(settings, incoming_transfer_id)
    event.fetched_json = json.dumps(transfer)
    event.amount = _incoming_transfer_amount(transfer)
    event.currency = _incoming_transfer_currency(transfer)
    event.reference = _incoming_transfer_reference(transfer)
    event.sender_name = _incoming_transfer_sender(transfer)
    invoice, match_meta = _find_invoice_for_incoming_transfer(transfer)
    if invoice:
        event.invoice_id = invoice.id
        invoice_fully_paid = float(invoice.paid_amount or 0.0) + 0.001 >= float(invoice.amount_due or 0.0)
        if event.status != 'MATCHED' and invoice.payment_status != 'PAID' and not invoice_fully_paid:
            _apply_incoming_transfer_to_invoice(invoice, event.amount, f'Wise incoming transfer {incoming_transfer_id}')
        event.status = 'MATCHED'
        event.error_message = None
        return invoice, match_meta
    event.invoice_id = None
    event.status = 'UNMATCHED'
    transfer_reference = event.reference or 'no reference'
    event.error_message = f"No invoice reference matched this incoming transfer ({transfer_reference})."
    return None, match_meta


def _apply_incoming_transfer_to_invoice(invoice, amount, note):
    old_status = invoice.payment_status
    invoice.paid_amount = round(float(invoice.paid_amount or 0.0) + float(amount or 0.0), 2)
    if invoice.paid_amount + 0.001 >= float(invoice.amount_due or 0.0):
        invoice.payment_status = 'PAID'
        if not invoice.paid_at:
            invoice.paid_at = datetime.utcnow()
    elif invoice.paid_amount > 0:
        invoice.payment_status = 'PARTIALLY_PAID'
    invoice.payment_note = note
    db.session.add(PaymentAuditLog(invoice_id=invoice.id, old_status=old_status, new_status=invoice.payment_status, amount=invoice.paid_amount, note=note))
    return invoice


def _wise_payment_error_response(exc):
    db.session.rollback()
    payload, status_code = _wise_payment_error_payload(exc)
    return jsonify(payload), status_code


def _wise_payment_error_payload(exc):
    if isinstance(exc, ValueError) and str(exc) == 'wise_api_token_required':
        return {
            'error': 'Wise API token is required before generating payment invoices.',
            'code': 'wise_api_token_required',
        }, 400
    if isinstance(exc, ValueError) and str(exc) == 'wise_business_profile_not_found':
        return {
            'error': 'No Wise business profile was found for this API token.',
            'code': 'wise_business_profile_not_found',
        }, 400
    if isinstance(exc, ValueError) and str(exc) == 'wise_payment_url_missing':
        return {
            'error': 'Wise did not return a payment link for this invoice.',
            'code': 'wise_payment_url_missing',
        }, 502
    if isinstance(exc, ValueError) and str(exc) == 'wise_client_key_required':
        return {
            'error': 'Wise client key is required before creating the webhook subscription.',
            'code': 'wise_client_key_required',
        }, 400
    if isinstance(exc, ValueError) and str(exc) == 'wise_webhook_url_required':
        return {
            'error': 'Wise webhook URL is required before creating the webhook subscription.',
            'code': 'wise_webhook_url_required',
        }, 400
    if isinstance(exc, ValueError) and str(exc) == 'wise_subscription_id_missing':
        return {
            'error': 'Wise created the webhook subscription but did not return a subscription ID.',
            'code': 'wise_subscription_id_missing',
        }, 502
    if isinstance(exc, requests.exceptions.HTTPError):
        status_code = exc.response.status_code if exc.response is not None else 502
        response_text = ''
        if exc.response is not None:
            response_text = (exc.response.text or '').strip()
            if len(response_text) > 240:
                response_text = response_text[:240] + '...'
        if status_code in {401, 403}:
            return {
                'error': 'Wise rejected the API token or profile ID. Check the token, business profile ID, and environment.',
                'code': 'wise_unauthorized',
            }, 400
        return {
            'error': f'Wise payment request failed ({status_code}). {response_text}'.strip(),
            'code': 'wise_api_error',
        }, 502
    if isinstance(exc, requests.exceptions.RequestException):
        return {
            'error': 'Wise payment request service is unreachable. Try again shortly.',
            'code': 'wise_unreachable',
        }, 502
    raise exc


def _qr_data_url(payload):
    if not qrcode:
        return None
    img = qrcode.make(payload)
    buf = BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def _attach_payment_details(invoice, settings):
    reference = invoice.payment_reference or invoice.invoice_number or _next_payment_reference()
    invoice.payment_reference = reference
    invoice.invoice_number = invoice.invoice_number or reference
    invoice.bank_account_holder = settings.effective_account_holder_name()
    invoice.bank_name = settings.effective_bank_name()
    invoice.iban = settings.effective_iban()
    invoice.bic = settings.effective_bic()

    try:
        invoice.payment_url = _wise_create_payment_request(settings, invoice)
    except ValueError as exc:
        if str(exc) not in {'wise_api_token_required', 'wise_payment_url_missing'}:
            raise
        invoice.payment_url = _wise_payment_url(settings, invoice.amount_due, reference)
    invoice.qr_payload = invoice.payment_url
    invoice.qr_code_data_url = _qr_data_url(invoice.qr_payload)
    return invoice


def _attach_payment_error(invoice, exc):
    payload, _ = _wise_payment_error_payload(exc)
    invoice.payment_url = None
    invoice.qr_payload = None
    invoice.qr_code_data_url = None
    invoice.wise_payment_request_id = None
    invoice._payment_generation_error = payload
    return invoice


def _check_whatsapp_bot_status():
    import os

    bot_url = (os.environ.get('WHATSAPP_BOT_URL') or '').strip()
    token_configured = bool(os.environ.get('WHATSAPP_BOT_TOKEN'))
    if not bot_url:
        return {
            'status': 'not_configured',
            'bot_url': None,
            'token_configured': token_configured,
            'ready': False,
            'message': 'WHATSAPP_BOT_URL is not configured.',
        }
    try:
        response = requests.get(f"{bot_url.rstrip('/')}/health", timeout=5)
        response.raise_for_status()
        payload = response.json() or {}
        return {
            'status': 'ok' if payload.get('ready') else 'warning',
            'bot_url': bot_url,
            'token_configured': token_configured,
            'ready': bool(payload.get('ready')),
            'message': 'WhatsApp bot is reachable.',
        }
    except requests.exceptions.RequestException as exc:
        return {
            'status': 'error',
            'bot_url': bot_url,
            'token_configured': token_configured,
            'ready': False,
            'message': str(exc),
        }


def _default_whatsapp_test_setting():
    from .models import WhatsAppNotificationSetting

    _ensure_whatsapp_notification_settings()
    setting = WhatsAppNotificationSetting.query.filter(
        WhatsAppNotificationSetting.test_recipient_number.isnot(None)
    ).order_by(WhatsAppNotificationSetting.updated_at.desc()).first()
    if setting:
        return setting
    return WhatsAppNotificationSetting.query.order_by(WhatsAppNotificationSetting.updated_at.desc()).first()


def _check_wise_profile_status(settings):
    if not (settings.wise_api_token or '').strip():
        return {
            'status': 'not_configured',
            'message': 'Wise API token is not configured.',
            'resolved_profile_id': settings.wise_profile_id,
        }
    try:
        response = requests.get(f'{_wise_api_base_url(settings)}/v1/profiles', headers=_wise_api_headers(settings), timeout=10)
        response.raise_for_status()
        profiles = response.json() or []
        business = next((profile for profile in profiles if (profile.get('type') or '').upper() == 'BUSINESS'), None)
        resolved_profile_id = str((business or {}).get('id') or settings.wise_profile_id or '')
        return {
            'status': 'ok' if resolved_profile_id else 'warning',
            'message': 'Wise profiles fetched successfully.' if resolved_profile_id else 'Wise token worked but no business profile was found.',
            'resolved_profile_id': resolved_profile_id or None,
            'profile_count': len(profiles),
        }
    except Exception as exc:
        payload, _ = _wise_payment_error_payload(exc) if isinstance(exc, (ValueError, requests.exceptions.RequestException, requests.exceptions.HTTPError)) else ({'error': str(exc)}, 502)
        return {
            'status': 'error',
            'message': payload.get('error') or str(exc),
            'resolved_profile_id': settings.wise_profile_id,
        }


def _fetch_wise_webhook_subscription(settings):
    client_key = (settings.wise_client_key or '').strip()
    subscription_id = (settings.wise_webhook_subscription_id or '').strip()
    if not client_key:
        raise ValueError('wise_client_key_required')
    if not subscription_id:
        raise ValueError('wise_subscription_id_missing')
    base_url = _wise_api_base_url(settings)
    endpoints = [
        f'{base_url}/v3/applications/{client_key}/subscriptions/{subscription_id}',
        f'{base_url}/v3/applications/{client_key}/subscriptions',
    ]
    for endpoint in endpoints:
        response = requests.get(endpoint, headers=_wise_api_headers(settings), timeout=10)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        data = response.json() or {}
        if endpoint.endswith(f'/{subscription_id}'):
            return data
        items = data.get('subscriptions') if isinstance(data, dict) else data
        if isinstance(items, list):
            match = next((item for item in items if str(item.get('id') or item.get('subscription_id') or '') == subscription_id), None)
            if match:
                return match
    raise ValueError('wise_subscription_id_missing')


def _check_wise_subscription_status(settings):
    if not (settings.wise_api_token or '').strip():
        return {
            'status': 'not_configured',
            'message': 'Wise API token is not configured.',
        }
    if not (settings.wise_client_key or '').strip():
        return {
            'status': 'not_configured',
            'message': 'Wise client key is not configured.',
        }
    if not (settings.wise_webhook_subscription_id or '').strip():
        return {
            'status': 'not_configured',
            'message': 'Wise webhook subscription ID is not configured.',
        }
    try:
        subscription = _fetch_wise_webhook_subscription(settings)
        delivery = subscription.get('delivery') or {}
        return {
            'status': 'ok',
            'message': 'Wise webhook subscription is reachable.',
            'subscription': {
                'id': str(subscription.get('id') or subscription.get('subscription_id') or settings.wise_webhook_subscription_id),
                'name': subscription.get('name'),
                'trigger_on': subscription.get('trigger_on') or subscription.get('triggerOn'),
                'delivery_url': delivery.get('url') or subscription.get('url'),
                'version': delivery.get('version'),
            },
        }
    except Exception as exc:
        payload, _ = _wise_payment_error_payload(exc) if isinstance(exc, (ValueError, requests.exceptions.RequestException, requests.exceptions.HTTPError)) else ({'error': str(exc)}, 502)
        return {
            'status': 'error',
            'message': payload.get('error') or str(exc),
        }


def _user_can_view_payment_invoice(user, invoice):
    if _is_admin_user(user):
        return True
    if invoice.user_id == user.id:
        return True
    owner = _family_owner_for_user(user)
    if invoice.user_id == owner.id:
        return True
    return False


def _create_payment_invoice_for_summary(user, month_value, summary, settings, is_test=False, allow_payment_failure=False):
    existing = None if is_test else PaymentInvoice.query.filter_by(user_id=user.id, month=month_value, is_test_invoice=False).first()
    invoice = existing or PaymentInvoice(user_id=user.id, month=month_value)
    if not existing:
        invoice.invoice_number = _next_payment_reference()
        invoice.payment_reference = invoice.invoice_number
        invoice.due_date = (datetime.utcnow().date() + timedelta(days=int(settings.default_due_days or 14))).strftime('%Y-%m-%d')
        invoice.is_test_invoice = bool(is_test)
        db.session.add(invoice)
        db.session.flush()
    invoice.amount_due = round(float(summary.get('total') or 0.0), 2)
    invoice.booking_items_json = json.dumps(summary.get('booking_items') or [])
    invoice.misc_items_json = json.dumps(summary.get('misc_items') or [])
    invoice.is_test_invoice = bool(is_test)
    invoice.payment_status = invoice.payment_status or 'UNPAID'
    try:
        _attach_payment_details(invoice, settings)
    except (ValueError, requests.exceptions.RequestException) as exc:
        if not allow_payment_failure:
            raise
        _attach_payment_error(invoice, exc)
    return invoice


def _create_payment_invoices_for_month(month_value, admin_user):
    settings = _payment_settings()
    users = User.query.order_by(User.name.asc(), User.email.asc(), User.phone.asc()).all()
    created = []
    seen_owner_ids = set()
    for item in users:
        owner = _family_owner_for_user(item)
        if owner.id in seen_owner_ids:
            continue
        seen_owner_ids.add(owner.id)
        summary = _monthly_invoice_summary(owner, month_value)
        if not summary or float(summary.get('total') or 0.0) <= 0:
            continue
        invoice = _create_payment_invoice_for_summary(owner, month_value, summary, settings, False)
        invoice.updated_by = admin_user.id
        created.append(invoice)
    return created


@bookings_bp.route('/admin/payment-settings', methods=['GET', 'PUT'])
def admin_payment_settings():
    user, error = _require_super_admin()
    if error:
        return error
    settings = _payment_settings()
    if request.method == 'GET':
        return jsonify(settings.to_dict(include_effective=True))
    data = request.get_json() or {}
    iban = (data.get('iban') or '').replace(' ', '').upper() or None
    if iban and not _valid_iban(iban):
        return jsonify({'error': 'invalid_iban'}), 400
    payment_provider = 'WISE_API'
    wise_api_token = (data.get('wise_api_token') or '').strip()
    if not (wise_api_token or settings.wise_api_token):
        return jsonify({'error': 'wise_api_token_required'}), 400
    for field in ['account_holder_name', 'bank_name', 'bic', 'description_prefix']:
        if field in data:
            setattr(settings, field, (data.get(field) or '').strip() or None)
    settings.iban = iban
    settings.payment_provider = payment_provider
    if wise_api_token:
        settings.wise_api_token = wise_api_token
    if 'wise_profile_id' in data:
        settings.wise_profile_id = (data.get('wise_profile_id') or '').strip() or None
    if 'wise_api_base_url' in data:
        settings.wise_api_base_url = (data.get('wise_api_base_url') or '').strip() or None
    if 'wise_redirect_url' in data:
        settings.wise_redirect_url = (data.get('wise_redirect_url') or '').strip() or None
    if 'wise_client_key' in data:
        settings.wise_client_key = (data.get('wise_client_key') or '').strip() or None
    if 'wise_webhook_url' in data:
        settings.wise_webhook_url = (data.get('wise_webhook_url') or '').strip() or None
    if 'default_due_days' in data:
        settings.default_due_days = max(1, min(60, int(data.get('default_due_days') or 14)))
    if 'qr_enabled' in data:
        settings.qr_enabled = bool(data.get('qr_enabled'))
    if 'test_mode' in data:
        settings.test_mode = bool(data.get('test_mode'))
    settings.updated_by = user.id
    _record_admin_audit(user, 'update', 'payment_settings', settings.id, 'Updated payment account settings', {'settings': settings.to_dict()})
    db.session.commit()
    return jsonify(settings.to_dict(include_effective=True))


@bookings_bp.route('/admin/payment-settings/wise-webhook-subscription', methods=['POST'])
def create_wise_webhook_subscription():
    user, error = _require_super_admin()
    if error:
        return error
    settings = _payment_settings()
    data = request.get_json() or {}
    wise_api_token = (data.get('wise_api_token') or '').strip()
    if wise_api_token:
        settings.wise_api_token = wise_api_token
    if 'wise_api_base_url' in data:
        settings.wise_api_base_url = (data.get('wise_api_base_url') or '').strip() or None
    if 'wise_client_key' in data:
        settings.wise_client_key = (data.get('wise_client_key') or '').strip() or None
    if 'wise_webhook_url' in data:
        settings.wise_webhook_url = (data.get('wise_webhook_url') or '').strip() or None
    try:
        subscription = _wise_create_webhook_subscription(settings)
    except (ValueError, requests.exceptions.RequestException) as exc:
        return _wise_payment_error_response(exc)
    settings.updated_by = user.id
    _record_admin_audit(user, 'create', 'wise_webhook_subscription', settings.wise_webhook_subscription_id, 'Created Wise incoming transfer webhook subscription', {'subscription': subscription})
    db.session.commit()
    return jsonify({'subscription': subscription, 'settings': settings.to_dict(include_effective=True)}), 201


@bookings_bp.route('/admin/payment-settings/wise-webhook-status', methods=['GET'])
def wise_webhook_status():
    user, error = _require_super_admin()
    if error:
        return error
    settings = _payment_settings()
    latest_events = WiseWebhookEvent.query.order_by(WiseWebhookEvent.created_at.desc()).limit(10).all()
    test_invoices = PaymentInvoice.query.filter_by(is_test_invoice=True).order_by(PaymentInvoice.created_at.desc()).limit(10).all()
    matched_event_count = WiseWebhookEvent.query.filter(WiseWebhookEvent.invoice_id.isnot(None)).count()
    unmatched_event_count = WiseWebhookEvent.query.filter_by(status='UNMATCHED').count()
    error_event_count = WiseWebhookEvent.query.filter_by(status='ERROR').count()
    return jsonify({
        'webhook_configured': bool(settings.wise_webhook_url),
        'subscription_configured': bool(settings.wise_webhook_subscription_id),
        'subscription_id': settings.wise_webhook_subscription_id,
        'webhook_url': settings.wise_webhook_url,
        'latest_event': latest_events[0].to_dict() if latest_events else None,
        'recent_events': [event.to_dict() for event in latest_events],
        'recent_test_invoices': [invoice.to_dict(include_qr=False) for invoice in test_invoices],
        'matched_event_count': matched_event_count,
        'unmatched_event_count': unmatched_event_count,
        'error_event_count': error_event_count,
    })


@bookings_bp.route('/admin/system-checks', methods=['GET'])
def admin_system_checks():
    user, error = _require_any_admin()
    if error:
        return error
    settings = _payment_settings()
    from .models import WhatsAppNotificationLog
    whatsapp_test_setting = _default_whatsapp_test_setting()
    recent_whatsapp_logs = WhatsAppNotificationLog.query.order_by(WhatsAppNotificationLog.created_at.desc()).limit(5).all()
    last_whatsapp_test_log = next((log for log in recent_whatsapp_logs if log.event_key == 'connection_test'), None)
    query = (request.args.get('query') or '').strip()
    lookup = _payment_invoice_lookup(query) if query else None
    invoice = lookup['invoice'] if lookup else None
    return jsonify({
        'checked_at': datetime.utcnow().isoformat(),
        'query': query or None,
        'backend': {
            'status': 'ok',
            'message': 'Backend API is reachable.',
        },
        'whatsapp': {
            **_check_whatsapp_bot_status(),
            'default_test_recipient': whatsapp_test_setting.test_recipient_number if whatsapp_test_setting else None,
            'last_test_log': last_whatsapp_test_log.to_dict() if last_whatsapp_test_log else None,
            'recent_logs': [log.to_dict() for log in recent_whatsapp_logs],
        },
        'wise': {
            'status': 'ok' if (settings.wise_api_token or '').strip() else 'not_configured',
            'settings': {
                'wise_api_base_url': settings.wise_api_base_url or 'https://api.wise.com',
                'wise_profile_id': settings.wise_profile_id,
                'wise_client_key_configured': bool((settings.wise_client_key or '').strip()),
                'wise_webhook_url': settings.wise_webhook_url,
                'wise_webhook_subscription_id': settings.wise_webhook_subscription_id,
                'wise_api_token_configured': bool((settings.wise_api_token or '').strip()),
            },
            'profile_check': _check_wise_profile_status(settings),
            'subscription_check': _check_wise_subscription_status(settings),
            'recent_events': [event.to_dict() for event in WiseWebhookEvent.query.order_by(WiseWebhookEvent.created_at.desc()).limit(10).all()],
        },
        'payment_lookup': {
            'match_reason': lookup['match_reason'] if lookup else None,
            'invoice': invoice.to_dict(include_qr=False) if invoice else None,
            'related_events': [event.to_dict() for event in _related_wise_events(invoice=invoice, query=query, limit=8)],
        } if query else None,
    })


@bookings_bp.route('/admin/system-checks/whatsapp-test', methods=['POST'])
def admin_system_checks_whatsapp_test():
    user, error = _require_any_admin()
    if error:
        return error
    from .models import WhatsAppNotificationLog

    data = request.get_json() or {}
    setting = _default_whatsapp_test_setting()
    raw_recipient = data.get('recipient')
    if raw_recipient in (None, '') and setting:
        raw_recipient = setting.test_recipient_number
    recipient = _normalize_whatsapp_test_recipient(raw_recipient)
    if not recipient:
        return jsonify({'error': 'Configure a WhatsApp test recipient first.'}), 400

    message = '\n'.join([
        'Badminton admin connection test',
        f'Time: {datetime.utcnow().isoformat()}Z',
        f'Admin: {user.name or user.email or user.phone or "Unknown admin"}',
    ])
    status, response_text = _send_whatsapp_bot_message(message, recipient)
    log = WhatsAppNotificationLog(
        setting_id=setting.id if setting else None,
        event_key='connection_test',
        recipient=recipient,
        message=message,
        status=status,
        response=response_text,
    )
    db.session.add(log)
    _record_admin_audit(
        user,
        'send',
        'whatsapp_connection_test',
        log.id,
        f'Sent WhatsApp connection test to {recipient}',
        {'status': status, 'recipient': recipient},
    )
    db.session.commit()
    return jsonify({
        'status': status,
        'recipient': recipient,
        'message': 'WhatsApp connection test sent.' if status == 'sent' else 'WhatsApp connection test completed with a non-sent status.',
        'log': log.to_dict(),
    })


@bookings_bp.route('/admin/wise-webhook-events/<int:event_id>/retry', methods=['POST'])
def retry_wise_webhook_event(event_id):
    user, error = _require_any_admin()
    if error:
        return error
    event = WiseWebhookEvent.query.get_or_404(event_id)
    if not event.incoming_transfer_id:
        return jsonify({'error': 'incoming_transfer_id_missing'}), 400
    settings = _payment_settings()
    event.status = 'RECEIVED'
    event.error_message = None
    try:
        invoice, match_meta = _process_wise_incoming_transfer_event(event, settings, event.incoming_transfer_id)
        _record_admin_audit(
            user,
            'retry',
            'wise_webhook_event',
            event.id,
            f'Retried Wise webhook event {event.incoming_transfer_id}',
            {'event': event.to_dict(), 'match_meta': match_meta},
        )
        db.session.commit()
        return jsonify({
            'status': event.status.lower(),
            'event': event.to_dict(),
            'invoice': invoice.to_dict(include_qr=False) if invoice else None,
            'match_meta': match_meta,
        })
    except Exception as exc:
        event.status = 'ERROR'
        event.error_message = _wise_request_error_message(exc)
        db.session.commit()
        return jsonify({'status': 'error', 'event': event.to_dict()}), 202


@bookings_bp.route('/payment-invoices/current', methods=['GET'])
def current_payment_invoice():
    user, error = _require_login()
    if error:
        return error
    month_value = request.args.get('month') or datetime.utcnow().strftime('%Y-%m')
    summary = _monthly_invoice_summary(user, month_value)
    if not summary:
        return jsonify({'error': 'month must use YYYY-MM'}), 400
    owner = _family_owner_for_user(user)
    month_status = _monthly_invoice_status(month_value)
    invoice = None
    if month_status and month_status.status in {'READY_FOR_PAYMENT', 'SETTLED'}:
        invoice = PaymentInvoice.query.filter_by(user_id=owner.id, month=month_value, is_test_invoice=False).first()
    if not invoice:
        return jsonify({
            'month': month_value,
            'month_status': (month_status or MonthlyInvoiceStatus(month=month_value, status='OPEN')).to_dict(),
            'invoice': None,
        })
    return jsonify(invoice.to_dict())


@bookings_bp.route('/webhooks/wise/incoming-transfer', methods=['GET', 'HEAD', 'POST'])
def wise_incoming_transfer_webhook():
    if request.method in {'GET', 'HEAD'}:
        return jsonify({'status': 'ok', 'webhook': 'wise-incoming-transfer'})
    payload = request.get_json(silent=True) or {}
    settings = _payment_settings()
    subscription_id = payload.get('subscription_id') or payload.get('subscriptionId')
    if settings.wise_webhook_subscription_id and subscription_id and subscription_id != settings.wise_webhook_subscription_id:
        return jsonify({'error': 'unknown_subscription'}), 403
    incoming_transfer_id = _incoming_transfer_id_from_payload(payload)
    if not incoming_transfer_id:
        event = WiseWebhookEvent(
            event_type=payload.get('event_type') or payload.get('eventType'),
            subscription_id=subscription_id,
            payload_json=json.dumps(payload),
            status='IGNORED',
            error_message='No incoming transfer id in webhook payload.',
        )
        db.session.add(event)
        db.session.commit()
        return jsonify({'status': 'ignored', 'message': 'No incoming transfer id in webhook validation payload.'})
    existing = WiseWebhookEvent.query.filter_by(incoming_transfer_id=str(incoming_transfer_id)).first()
    if existing and existing.status == 'MATCHED':
        return jsonify({'status': 'duplicate', 'event': existing.to_dict()})

    event = existing or WiseWebhookEvent(incoming_transfer_id=str(incoming_transfer_id))
    event.event_type = payload.get('event_type') or payload.get('eventType')
    event.subscription_id = subscription_id
    event.payload_json = json.dumps(payload)
    event.status = 'RECEIVED'
    event.error_message = None
    if not existing:
        db.session.add(event)
    try:
        _process_wise_incoming_transfer_event(event, settings, incoming_transfer_id)
        db.session.commit()
    except Exception as exc:
        event.status = 'ERROR'
        event.error_message = _wise_request_error_message(exc)
        db.session.commit()
        return jsonify({'status': 'error', 'event': event.to_dict()}), 202
    return jsonify({'status': event.status.lower(), 'event': event.to_dict()})


@bookings_bp.route('/admin/invoices/monthly/status', methods=['POST'])
def update_monthly_invoice_status():
    user, error = _require_any_admin()
    if error:
        return error
    data = request.get_json() or {}
    month_value = data.get('month') or datetime.utcnow().strftime('%Y-%m')
    start_date, _ = _month_bounds(month_value)
    if not start_date:
        return jsonify({'error': 'month must use YYYY-MM'}), 400
    new_status = (data.get('status') or '').upper()
    if new_status not in MONTHLY_INVOICE_STATUSES:
        return jsonify({'error': 'invalid_month_status'}), 400
    month_status = _monthly_invoice_status(month_value, create=True)
    old_status = month_status.status
    month_status.status = new_status
    month_status.note = data.get('note') or month_status.note
    month_status.updated_by = user.id
    generated = []
    if new_status == 'READY_FOR_PAYMENT':
        if not month_status.ready_at:
            month_status.ready_at = datetime.utcnow()
        try:
            generated = _create_payment_invoices_for_month(month_value, user)
        except (ValueError, requests.exceptions.RequestException) as exc:
            return _wise_payment_error_response(exc)
    if new_status == 'SETTLED':
        if not month_status.settled_at:
            month_status.settled_at = datetime.utcnow()
    _record_admin_audit(
        user,
        'update',
        'monthly_invoice_status',
        month_value,
        f'Changed monthly invoice status for {month_value} to {new_status}',
        {'old_status': old_status, 'new_status': new_status, 'generated_invoice_count': len(generated)},
    )
    db.session.commit()
    return jsonify({
        'month_status': month_status.to_dict(),
        'generated_invoice_count': len(generated),
        'payment_invoices': [invoice.to_dict(include_qr=False) for invoice in generated],
    })


@bookings_bp.route('/payment-invoices/<int:invoice_id>', methods=['GET'])
def get_payment_invoice(invoice_id):
    user, error = _require_login()
    if error:
        return error
    invoice = PaymentInvoice.query.get_or_404(invoice_id)
    if not _user_can_view_payment_invoice(user, invoice):
        return jsonify({'error': 'forbidden'}), 403
    payload = invoice.to_dict()
    payload['audit_logs'] = [log.to_dict() for log in sorted(invoice.audit_logs, key=lambda x: x.created_at or datetime.min)]
    return jsonify(payload)


@bookings_bp.route('/admin/payment-invoices', methods=['GET'])
def admin_payment_invoices():
    user, error = _require_any_admin()
    if error:
        return error
    status_filter = (request.args.get('status') or 'all').lower()
    query = PaymentInvoice.query.order_by(PaymentInvoice.created_at.desc())
    if status_filter != 'test':
        query = query.filter(PaymentInvoice.is_test_invoice.is_(False))
    if status_filter == 'unpaid':
        query = query.filter(PaymentInvoice.payment_status == 'UNPAID')
    elif status_filter == 'paid':
        query = query.filter(PaymentInvoice.payment_status == 'PAID')
    elif status_filter == 'test':
        query = query.filter(PaymentInvoice.is_test_invoice.is_(True))
    invoices = query.all()
    if status_filter == 'overdue':
        today = datetime.utcnow().date().strftime('%Y-%m-%d')
        invoices = [item for item in invoices if item.due_date and item.due_date < today and item.payment_status in {'UNPAID', 'PARTIALLY_PAID'}]
    return jsonify({'invoices': [item.to_dict(include_qr=False) for item in invoices]})


@bookings_bp.route('/admin/payment-invoices/<int:invoice_id>/status', methods=['POST'])
def update_payment_invoice_status(invoice_id):
    user, error = _require_any_admin()
    if error:
        return error
    invoice = PaymentInvoice.query.get_or_404(invoice_id)
    data = request.get_json() or {}
    new_status = (data.get('payment_status') or data.get('status') or '').upper()
    if new_status not in PAYMENT_STATUSES:
        return jsonify({'error': 'invalid_payment_status'}), 400
    old_status = invoice.payment_status
    amount = data.get('paid_amount')
    invoice.payment_status = new_status
    if amount is not None:
        invoice.paid_amount = round(float(amount or 0), 2)
    elif new_status == 'PAID':
        invoice.paid_amount = invoice.amount_due
    if new_status == 'PAID' and not invoice.paid_at:
        invoice.paid_at = datetime.utcnow()
    if data.get('paid_date'):
        invoice.paid_at = datetime.strptime(data.get('paid_date'), '%Y-%m-%d')
    invoice.payment_note = data.get('payment_note') or data.get('note') or invoice.payment_note
    invoice.updated_by = user.id
    db.session.add(PaymentAuditLog(invoice_id=invoice.id, old_status=old_status, new_status=new_status, amount=invoice.paid_amount, note=invoice.payment_note, updated_by=user.id))
    if invoice.month and not invoice.is_test_invoice:
        month_invoices = PaymentInvoice.query.filter_by(month=invoice.month, is_test_invoice=False).all()
        if month_invoices and all(item.payment_status == 'PAID' or item.id == invoice.id and new_status == 'PAID' for item in month_invoices):
            month_status = _monthly_invoice_status(invoice.month, create=True)
            month_status.status = 'SETTLED'
            if not month_status.settled_at:
                month_status.settled_at = datetime.utcnow()
            month_status.updated_by = user.id
    _record_admin_audit(user, 'update', 'payment_invoice', invoice.id, f'Changed payment status for {invoice.invoice_number} to {new_status}', {'old_status': old_status, 'new_status': new_status})
    db.session.commit()
    return jsonify(invoice.to_dict())


@bookings_bp.route('/admin/payment-invoices/test', methods=['POST'])
def generate_test_payment_invoice():
    user, error = _require_super_admin()
    if error:
        return error
    data = request.get_json() or {}
    target = User.query.get(data.get('user_id')) if data.get('user_id') else user
    settings = _payment_settings()
    total_amount = TEST_PAYMENT_INVOICE_AMOUNT
    summary = {
        'total': total_amount,
        'booking_items': [{'title': 'Wise webhook test payment', 'amount': total_amount, 'date': datetime.utcnow().strftime('%Y-%m-%d')}],
        'misc_items': [],
    }
    invoice = _create_payment_invoice_for_summary(target, datetime.utcnow().strftime('%Y-%m'), summary, settings, True, allow_payment_failure=True)
    invoice.payment_status = 'UNPAID'
    db.session.add(PaymentAuditLog(invoice_id=invoice.id, old_status=None, new_status='UNPAID', amount=invoice.amount_due, note='Generated test invoice', updated_by=user.id))
    _record_admin_audit(user, 'create', 'payment_invoice', invoice.id, f'Generated test payment invoice {invoice.invoice_number}', {'invoice': invoice.to_dict(include_qr=False)})
    db.session.commit()
    response = invoice.to_dict()
    if getattr(invoice, '_payment_generation_error', None):
        response['payment_generation_error'] = invoice._payment_generation_error
    return jsonify(response), 201


@bookings_bp.route('/admin/payment-invoices/test/latest', methods=['GET'])
def latest_test_payment_invoice():
    user, error = _require_super_admin()
    if error:
        return error
    invoice = PaymentInvoice.query.filter_by(is_test_invoice=True).order_by(PaymentInvoice.created_at.desc()).first()
    if not invoice:
        return jsonify({'invoice': None})
    payload = invoice.to_dict()
    payload['webhook_events'] = [
        event.to_dict()
        for event in WiseWebhookEvent.query.filter_by(invoice_id=invoice.id).order_by(WiseWebhookEvent.created_at.desc()).limit(10).all()
    ]
    return jsonify({'invoice': payload})


def _monthly_invoice_ready_preview(month_value=None):
    month_value = month_value or datetime.utcnow().strftime('%Y-%m')
    start_date, _ = _month_bounds(month_value)
    if not start_date:
        raise ValueError('month must use YYYY-MM')
    context = {
        'month': month_value,
        'app_url': request.host_url.rstrip('/'),
        'note': 'Monthly invoices are ready. Please open the app, review your family total, and pay by bank transfer using the displayed reference.',
    }
    setting = _whatsapp_setting('monthly_invoice_ready')
    message = _render_template(setting.template if setting else '💶 Monthly badminton invoices for {{month}} are ready. {{note}} Open: {{app_url}}', context)
    recipient = (setting.group_id or '').strip() or _fallback_whatsapp_group_id('monthly_invoice_ready') if setting else None
    return setting, context, message, recipient, month_value


@bookings_bp.route('/admin/payment-invoices/monthly/notify/preview', methods=['POST'])
def preview_monthly_invoice_ready():
    _, error = _require_any_admin()
    if error:
        return error
    data = request.get_json() or {}
    try:
        setting, context, message, recipient, month_value = _monthly_invoice_ready_preview(data.get('month'))
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({
        'message': message,
        'context': context,
        'recipient': recipient,
        'setting': setting.to_dict() if setting else None,
        'test_recipients': _whatsapp_known_test_recipients(),
        'month': month_value,
    })


@bookings_bp.route('/admin/payment-invoices/monthly/notify', methods=['POST'])
def notify_monthly_invoice_ready():
    user, error = _require_any_admin()
    if error:
        return error
    data = request.get_json() or {}
    try:
        setting, context, message, recipient, month_value = _monthly_invoice_ready_preview(data.get('month'))
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    message = (data.get('message') or message).strip()
    if not message:
        return jsonify({'error': 'message required'}), 400
    send_test = bool(data.get('test'))
    recipient_override = None
    if send_test:
        recipient_override = _normalize_whatsapp_test_recipient(data.get('recipient'))
        if not recipient_override:
            return jsonify({'error': 'test recipient required'}), 400
    log = _send_whatsapp_event(
        'monthly_invoice_ready',
        context,
        dedupe_key=None if send_test else f'monthly_invoice_ready:{month_value}',
        message_override=message,
        recipient_override=recipient_override,
        force=send_test,
    )
    return jsonify({'status': 'sent' if log else 'skipped', 'message': message, 'log': log.to_dict() if log else None})
