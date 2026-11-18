from datetime import datetime, timedelta, timezone
from itertools import count

import jwt
import pytest

from app import db
from app.bookings import AMSTERDAM_TZ
from app.models import (
    Booking, Court, FamilyMember, MiscCost, MonthlyInvoiceStatus, PaymentInvoice,
    User, WhatsAppAccountLink, WhatsAppInboundEvent, WhatsAppMemberLink,
)

SETTINGS = '/api/account/whatsapp'
CALLBACK = '/internal/whatsapp/member-message'
BOT_TOKEN = 'fixture-only-whatsapp-bot-token'
SENDER = '123456@lid'


@pytest.fixture
def members(app, monkeypatch):
    monkeypatch.setenv('WHATSAPP_BOT_TOKEN', BOT_TOKEN)
    monkeypatch.setenv('WHATSAPP_BOT_NUMBER', '+31600000001')
    monkeypatch.setenv('WHATSAPP_MEMBER_SITE_URL', 'https://club.example/')
    users = [
        User(phone='+31600000002', whatsapp_number='+31600000003', name='Test Player', role='user'),
        User(phone='+31600000004', name='Another Player', role='user'),
    ]
    db.session.add_all(users)
    db.session.commit()

    def headers(user):
        token = jwt.encode({'user_id': user.id}, app.config['JWT_SECRET'], algorithm='HS256')
        return {'Authorization': f'Bearer {token}'}

    return [(user, headers(user)) for user in users]


@pytest.fixture
def receive(client):
    sequence = count()

    def message(text, *, sender=SENDER, message_id=None, private=True,
                provider='whatsapp_web', token=BOT_TOKEN):
        return client.post(CALLBACK, json={
            'provider': provider, 'private': private, 'sender': sender,
            'message_id': message_id or f'message-{next(sequence)}', 'text': text,
        }, headers={'X-Bot-Token': token})

    return message


def _issue(client, headers):
    result = client.post(SETTINGS, headers=headers)
    assert result.status_code == 200
    assert 'no-store' in result.headers['Cache-Control']
    return result.get_json()


def _reply(response):
    assert response.status_code == 200
    return response.get_json()['reply']


def test_private_verified_link_uses_inbound_identity_and_consumes_code(client, members, receive):
    user, headers = members[0]
    assert client.get(SETTINGS).status_code == 401
    assert client.get(SETTINGS, headers=headers).get_json() == {'linked': False, 'available': True}
    payload = _issue(client, headers)
    code = payload['message'].split()[1]
    assert payload['whatsapp_url'] == f'https://wa.me/31600000001?text=LINK+{code}'
    assert timedelta(minutes=9) < datetime.fromisoformat(payload['expires_at']) - datetime.now(timezone.utc) <= timedelta(minutes=10)
    assert db.session.get(WhatsAppMemberLink, user.id).code_digest != code
    assert receive(payload['message'], token='wrong').status_code == 403
    assert db.session.query(WhatsAppInboundEvent).count() == 0

    assert 'WhatsApp linked' in _reply(receive(f'  link {code.lower()}  '))
    assert client.get(SETTINGS, headers=headers).get_json()['linked'] is True
    assert db.session.get(WhatsAppMemberLink, user.id).identity == f'whatsapp_web:{SENDER}'
    assert db.session.get(WhatsAppMemberLink, user.id).code_digest is None
    assert 'invalid or expired' in _reply(receive(payload['message'], sender='67890@lid'))
    assert client.post(SETTINGS, headers=headers).status_code == 409
    assert user.phone == '+31600000002'
    assert user.whatsapp_number == '+31600000003'


def test_expired_replaced_and_unlinked_codes_are_invalid(client, members, receive):
    user, headers = members[0]
    expired = _issue(client, headers)['message']
    link = db.session.get(WhatsAppMemberLink, user.id)
    link.code_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    db.session.commit()
    assert 'invalid or expired' in _reply(receive(expired))

    replaced = _issue(client, headers)['message']
    current = _issue(client, headers)['message']
    assert 'invalid or expired' in _reply(receive(replaced))
    assert client.delete(SETTINGS, headers=headers).get_json() == {'linked': False}
    assert 'invalid or expired' in _reply(receive(current))

    assert 'WhatsApp linked' in _reply(receive(_issue(client, headers)['message']))
    assert client.delete(SETTINGS, headers=headers).status_code == 200
    assert 'Account settings' in _reply(receive('BALANCE'))


def test_link_conflict_keeps_original_member_and_allows_explicit_unlink(client, members, receive):
    _, first = members[0]
    _, second = members[1]
    assert 'WhatsApp linked' in _reply(receive(_issue(client, first)['message']))
    second_code = _issue(client, second)['message']
    assert 'already linked' in _reply(receive(second_code))
    assert client.get(SETTINGS, headers=first).get_json()['linked'] is True
    assert client.get(SETTINGS, headers=second).get_json()['linked'] is False
    client.delete(SETTINGS, headers=first)
    assert 'WhatsApp linked' in _reply(receive(second_code))


def test_inbound_duplicate_and_group_messages_do_not_send_replies(client, members, receive):
    _, headers = members[0]
    code = _issue(client, headers)['message']
    assert receive(code, private=False, message_id='group-1').status_code == 204
    assert receive(code, sender='9876@g.us').status_code == 400
    assert db.session.query(WhatsAppInboundEvent).count() == 0
    assert 'WhatsApp linked' in _reply(receive(code, message_id='link-1'))
    assert receive(code, message_id='link-1').status_code == 204
    assert 'no outstanding balance' in _reply(receive('BALANCE', message_id='balance-1'))
    assert receive('BALANCE', message_id='balance-1').status_code == 204
    assert receive('BALANCE', private=False).status_code == 204


def test_profile_delivery_number_cannot_access_commands_and_private_menu_is_available(client, members, receive):
    user, _ = members[0]
    db.session.add(WhatsAppAccountLink(user_id=user.id, whatsapp_number=user.whatsapp_number))
    db.session.commit()
    assert 'Account settings' in _reply(receive('  balance  ', sender='31600000003', provider='meta_cloud_api'))
    assert 'NEXT' in _reply(receive(' mEnU '))
    assert 'Account settings' in _reply(receive('MENU'))
    assert _reply(receive('BALANCE 31600000003')) == 'Send MENU for available commands.'


def test_rate_limits_are_scoped_and_do_not_reset_on_unlink(client, members, receive):
    _, first = members[0]
    _, second = members[1]
    for _ in range(5):
        _issue(client, first)
    client.delete(SETTINGS, headers=first)
    assert client.post(SETTINGS, headers=first).status_code == 429
    second_code = _issue(client, second)['message']

    for _ in range(8):
        assert 'invalid or expired' in _reply(receive('LINK bad-code'))
    assert 'Too many attempts' in _reply(receive(second_code))
    assert 'WhatsApp linked' in _reply(receive(second_code, sender='98765@lid'))


def test_family_balance_matches_website_and_latest_invoice_excludes_unissued_or_unrelated_records(client, members, receive):
    spouse, headers = members[0]
    owner, _ = members[1]
    outsider = User(phone='+31600000005', name='Unrelated Player', role='user')
    db.session.add(outsider)
    db.session.add(FamilyMember(user_id=owner.id, linked_user_id=spouse.id, name=spouse.name))
    db.session.flush()

    def invoice(number, month, user_id, *, amount, paid=0, status='UNPAID', test=False, day=1):
        return PaymentInvoice(
            user_id=user_id, month=month, amount_due=amount, paid_amount=paid,
            invoice_number=number, payment_reference=number, payment_status=status,
            is_test_invoice=test, due_date='2026-05-20', created_at=datetime(2026, 5, day),
            payment_url='https://payments.example/private',
        )

    db.session.add_all([
        MonthlyInvoiceStatus(month='2026-03', status='READY_FOR_PAYMENT'),
        MonthlyInvoiceStatus(month='2026-04', status='READY_FOR_PAYMENT'),
        MonthlyInvoiceStatus(month='2026-05', status='SETTLED'),
        MiscCost(title='March shuttles', amount=10, purchase_date='2026-03-12'),
        MiscCost(title='April shuttles', amount=30, purchase_date='2026-04-12'),
        MiscCost(title='May shuttles', amount=22, purchase_date='2026-05-12'),
        invoice('older-family-duplicate', '2026-04', spouse.id, amount=500),
        invoice('family-partial', '2026-04', owner.id, amount=30, paid=12.54, status='PARTIALLY_PAID', day=4),
        invoice('family-paid', '2026-05', owner.id, amount=22, status='PAID', day=2),
        invoice('family-unpaid', '2026-03', owner.id, amount=10),
        invoice('unreleased', '2026-06', owner.id, amount=100, day=10),
        invoice('unrelated', '2026-04', outsider.id, amount=200, day=10),
        invoice('test-only', '2026-04', owner.id, amount=300, test=True, day=10),
    ])
    db.session.commit()
    _reply(receive(_issue(client, headers)['message']))
    months = ('2026-03', '2026-04', '2026-05')
    website_balance = sum(client.get(f'/api/invoices/monthly?month={month}', headers=headers).get_json()['balance_amount'] for month in months)
    assert website_balance == 27.46
    assert _reply(receive(' balance ')) == f'Outstanding balance: €{website_balance:.2f} across 2 invoices.\nhttps://club.example/my-invoices'
    latest = _reply(receive('invoice'))
    assert '€30.00 · Partially paid' in latest
    assert 'Due 2026-05-20' in latest
    assert latest.endswith('https://club.example/my-invoices')
    assert 'payments.example' not in latest


def test_next_uses_amsterdam_times_for_a_visible_booking_and_handles_empty_schedule(client, members, receive):
    _, headers = members[0]
    _reply(receive(_issue(client, headers)['message']))
    assert _reply(receive('INVOICE')).startswith('You have no invoices.')
    assert _reply(receive('NEXT')) == 'There are no upcoming bookings.'

    venue = Court(name='Club court', location='Nieuwegein')
    tomorrow = (datetime.now(AMSTERDAM_TZ) + timedelta(days=1)).date()
    db.session.add_all([
        Booking(court=venue, booking_date=tomorrow.isoformat(), start_time='10:00', end_time='11:00', status='cancelled'),
        Booking(court=venue, booking_date=tomorrow.isoformat(), start_time='18:00', end_time='19:00'),
    ])
    db.session.commit()
    reply = _reply(receive('NeXt'))
    assert f'{tomorrow:%d-%m-%Y}, 18:00–19:00 (Europe/Amsterdam)' in reply
    assert 'Club court, Nieuwegein' in reply


def test_default_bot_token_cannot_enable_member_self_service(client, members, receive, monkeypatch):
    _, headers = members[0]
    monkeypatch.setenv('WHATSAPP_BOT_TOKEN', 'dev-whatsapp-bot-token')
    assert client.get(SETTINGS, headers=headers).get_json()['available'] is False
    assert client.post(SETTINGS, headers=headers).status_code == 503
    assert receive('MENU', token='dev-whatsapp-bot-token').status_code == 403


def test_unresolved_web_sender_gets_deduplicated_feedback_without_consuming_code(client, members, receive):
    _, headers = members[0]
    code = _issue(client, headers)['message']
    unresolved = {'sender': '31600000003@c.us', 'message_id': 'unresolved'}
    assert 'could not verify' in _reply(receive(code, **unresolved))
    assert receive(code, **unresolved).status_code == 204
    assert client.get(SETTINGS, headers=headers).get_json()['linked'] is False
    assert 'WhatsApp linked' in _reply(receive(code))
    assert 'could not verify' in _reply(receive('BALANCE', sender='31600000003@c.us'))
