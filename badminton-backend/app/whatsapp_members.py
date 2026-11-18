"""Verified member self-service for authenticated WhatsApp adapters."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from hmac import compare_digest
import os
import re
import secrets
from urllib.parse import urlencode

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError

from . import db
from .bookings import (
    AMSTERDAM_TZ,
    _apply_monthly_payment_status,
    _current_booking_cutoff_values,
    _monthly_invoice_summary,
    _payment_family_user_ids,
    _require_login,
    _upcoming_bookings_query,
)
from .models import (
    Booking,
    MonthlyInvoiceStatus,
    PaymentInvoice,
    User,
    WhatsAppInboundEvent,
    WhatsAppLinkRateLimit,
    WhatsAppMemberLink,
)

whatsapp_members_bp = Blueprint('whatsapp_members', __name__)
link_help = 'Open Account settings on the club website to link WhatsApp.'
menu_actions = (
    ('BALANCE', 'Check balance'),
    ('INVOICE', 'Latest invoice'),
    ('NEXT', 'Next booking'),
)
invalid_code = 'That code is invalid or expired. Generate a new code in Account settings.'
window = timedelta(minutes=10)
provider_senders = {
    'whatsapp_web': re.compile(r'[0-9]{1,32}@(?:lid|c\.us)'),
    'meta_cloud_api': re.compile(r'[0-9]{1,32}'),
}
status_labels = {
    'UNPAID': 'Payment pending',
    'PAID': 'Paid',
    'PARTIALLY_PAID': 'Partially paid',
    'CANCELLED': 'Cancelled',
    'EXPIRED': 'Expired',
}


def _bot_token():
    token = os.environ.get('WHATSAPP_BOT_TOKEN', '')
    # The public Compose stack has a known development default.
    jwt_secret = current_app.config['JWT_SECRET']
    if token == 'dev-whatsapp-bot-token' or jwt_secret in {'dev-secret', 'dev-jwt-secret'}:
        return ''
    return token


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _digest(value):
    return sha256(value.encode()).hexdigest()


def _insert(model):
    insert = sqlite_insert if db.engine.dialect.name == 'sqlite' else postgres_insert
    return insert(model)


def _allow_attempt(key, now, limit):
    rate = WhatsAppLinkRateLimit
    expired = rate.expires_at <= now
    expires_at = now + window
    statement = _insert(rate).values(key=_digest(key), expires_at=expires_at, attempts=1)
    statement = statement.on_conflict_do_update(
        index_elements=[rate.key],
        set_={
            'attempts': db.case((expired, 1), else_=rate.attempts + 1),
            'expires_at': db.case((expired, expires_at), else_=rate.expires_at),
        },
        where=db.or_(expired, rate.attempts < limit),
    )
    return db.session.execute(statement).rowcount == 1


def _chat_url(message):
    number = os.environ.get('WHATSAPP_BOT_NUMBER', '').strip().removeprefix('+')
    if re.fullmatch(r'[1-9][0-9]{6,14}', number):
        return f'https://wa.me/{number}?{urlencode({"text": message})}'
    return None


def _menu_reply():
    if not _chat_url('MENU'):
        return '\n'.join(f'{command} — {label}' for command, label in menu_actions)
    choices = '\n\n'.join(f'{label}\n{_chat_url(command)}' for command, label in menu_actions)
    return f'Choose an option, then tap Send.\n\n{choices}'


def _with_menu_link(reply):
    menu_url = _chat_url('MENU')
    return f'{reply}\n\nOpen menu\n{menu_url}' if menu_url else reply


@whatsapp_members_bp.route('/api/account/whatsapp', methods=['GET', 'POST', 'DELETE'])
def account_whatsapp():
    user, error = _require_login()
    if error:
        return error

    if request.method == 'GET':
        link = db.session.get(WhatsAppMemberLink, user.id)
        linked = bool(link and link.identity)
        available = bool(_bot_token())
        payload = {'linked': linked, 'available': available}
        if linked and available and (menu_url := _chat_url('MENU')):
            payload['menu_url'] = menu_url
        return jsonify(payload)

    if request.method == 'DELETE':
        WhatsAppMemberLink.query.filter_by(user_id=user.id).update({
            'identity': None, 'code_digest': None, 'code_expires_at': None,
        })
        db.session.commit()
        return jsonify(linked=False)

    if not _bot_token():
        return jsonify(error='WhatsApp linking is currently unavailable.'), 503

    now = _utcnow()
    if not _allow_attempt(f'issue:{user.id}', now, 5):
        db.session.rollback()
        return jsonify(error='Too many codes requested. Try again in 10 minutes.'), 429

    code = secrets.token_hex(8).upper()
    expires_at = now + window
    link = WhatsAppMemberLink
    statement = _insert(link).values(user_id=user.id, code_digest=_digest(code), code_expires_at=expires_at)
    result = db.session.execute(statement.on_conflict_do_update(
        index_elements=[link.user_id],
        set_={'code_digest': _digest(code), 'code_expires_at': expires_at},
        where=link.identity.is_(None),
    ))
    db.session.commit()
    if result.rowcount != 1:
        return jsonify(error='Unlink your current WhatsApp account before linking a new one.'), 409

    message = f'LINK {code}'
    return jsonify(message=message, whatsapp_url=_chat_url(message), expires_at=expires_at.isoformat() + 'Z')


def _redeem(identity, code):
    now = _utcnow()
    if not _allow_attempt(f'redeem:{identity}', now, 8):
        return 'Too many attempts. Try again in 10 minutes.'
    if not re.fullmatch(r'[0-9A-F]{16}', code):
        return invalid_code

    try:
        with db.session.begin_nested():
            updated = WhatsAppMemberLink.query.filter(
                WhatsAppMemberLink.code_digest == _digest(code),
                WhatsAppMemberLink.code_expires_at > now,
                WhatsAppMemberLink.identity.is_(None),
            ).update({'code_digest': None, 'code_expires_at': None, 'identity': identity})
    except IntegrityError:
        return 'This WhatsApp account is already linked. Unlink it in Account settings first.'
    if not updated:
        return invalid_code
    return f'WhatsApp linked.\n\n{_menu_reply()}'


def _member_invoices(user):
    # My Invoices shows one issued payment invoice per family and month,
    # newest first within each month. Keep standalone account invoices too.
    invoices = (
        PaymentInvoice.query.outerjoin(MonthlyInvoiceStatus, MonthlyInvoiceStatus.month == PaymentInvoice.month)
        .filter(
            PaymentInvoice.user_id.in_(_payment_family_user_ids(user)),
            PaymentInvoice.is_test_invoice.is_(False),
            db.or_(
                PaymentInvoice.month.is_(None),
                MonthlyInvoiceStatus.status.in_({'READY_FOR_PAYMENT', 'SETTLED'}),
            ),
        )
        .order_by(PaymentInvoice.created_at.desc(), PaymentInvoice.id.desc())
    )
    seen_months = set()
    for invoice in invoices:
        if invoice.month and invoice.month in seen_months:
            continue
        seen_months.add(invoice.month)
        yield invoice


def _invoice_reply(user, command):
    website = os.environ.get('WHATSAPP_MEMBER_SITE_URL', 'https://nieuwegeinbadminton.nl').rstrip('/')
    invoice_url = f'{website}/my-invoices'
    if command == 'INVOICE':
        invoice = next(_member_invoices(user), None)
        if not invoice:
            return f'You have no invoices.\n{invoice_url}'
        status = status_labels.get(invoice.payment_status, 'Unknown')
        due_date = f'\nDue {invoice.due_date}' if invoice.due_date else ''
        return f'Latest invoice: €{invoice.amount_due or 0:.2f} · {status}{due_date}\n{invoice_url}'

    count = 0
    total = Decimal('0')
    for invoice in _member_invoices(user):
        if invoice.payment_status in {'PAID', 'CANCELLED'}:
            continue
        summary = _monthly_invoice_summary(user, invoice.month, refresh_bookings=False) if invoice.month else None
        if summary is None:
            summary = {'total': invoice.amount_due}
        balance = _apply_monthly_payment_status(summary, invoice)['balance_amount']
        if balance > 0:
            count += 1
            total += Decimal(str(balance))
    if not count:
        return f'You have no outstanding balance.\n{invoice_url}'
    label = 'invoice' if count == 1 else 'invoices'
    return f'Outstanding balance: €{total:.2f} across {count} {label}.\n{invoice_url}'


def _next_booking():
    today, time = _current_booking_cutoff_values(datetime.now(AMSTERDAM_TZ))
    booking = _upcoming_bookings_query(today, time).filter(
        db.or_(Booking.booking_date > today, Booking.start_time >= time),
    ).first()
    if not booking:
        return 'There are no upcoming bookings.'
    date = datetime.strptime(booking.booking_date, '%Y-%m-%d').strftime('%d-%m-%Y')
    venue = booking.court.name if booking.court else 'Venue to be confirmed'
    if booking.court and booking.court.location:
        venue = f'{venue}, {booking.court.location}'
    return f'Next booking: {date}, {booking.start_time}–{booking.end_time} (Europe/Amsterdam)\n{venue}'


def _reply(identity, text):
    parts = text.strip().upper().split(maxsplit=1)
    if not parts:
        return None
    command = parts[0]
    if command == 'LINK':
        return _redeem(identity, parts[1] if len(parts) == 2 else '')
    if len(parts) != 1 or command not in {'MENU', 'BALANCE', 'INVOICE', 'NEXT'}:
        return _with_menu_link('Send MENU for available commands.')

    user = User.query.join(WhatsAppMemberLink, WhatsAppMemberLink.user_id == User.id).filter(
        WhatsAppMemberLink.identity == identity,
    ).first()
    if command == 'MENU':
        menu = _menu_reply()
        return menu if user else f'{menu}\n\n{link_help}'
    if not user:
        return link_help
    if command == 'NEXT':
        return _with_menu_link(_next_booking())
    return _with_menu_link(_invoice_reply(user, command))


@whatsapp_members_bp.post('/internal/whatsapp/member-message')
def receive_member_message():
    token = _bot_token()
    supplied = request.headers.get('X-Bot-Token', '')
    if not token or not compare_digest(supplied.encode(), token.encode()):
        return jsonify(error='bot_token_required'), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='invalid_message'), 400
    if data.get('private') is not True:
        return '', 204
    provider, sender, message_id, text = (data.get(key) for key in ('provider', 'sender', 'message_id', 'text'))
    if not all(isinstance(value, str) for value in (provider, sender, message_id, text)):
        return jsonify(error='invalid_message'), 400
    sender_pattern = provider_senders.get(provider)
    if not sender_pattern or not sender_pattern.fullmatch(sender) or not 0 < len(message_id) <= 512 or len(text) > 65536:
        return jsonify(error='invalid_message'), 400

    event = WhatsAppInboundEvent
    statement = _insert(event).values(event_digest=_digest(f'{provider}:{message_id}'))
    result = db.session.execute(statement.on_conflict_do_nothing(index_elements=[event.event_digest]))
    if result.rowcount != 1:
        db.session.rollback()
        return '', 204

    if provider == 'whatsapp_web' and sender.endswith('@c.us'):
        # This address can receive a diagnostic reply. Only a verified LID
        # can resolve the member or redeem a link code.
        reply = 'I could not verify your WhatsApp identity. Please try again or contact the club if this continues.'
    else:
        reply = _reply(f'{provider}:{sender}', text)
    db.session.commit()
    response = jsonify(reply=reply)
    response.headers['Cache-Control'] = 'no-store'
    return response
