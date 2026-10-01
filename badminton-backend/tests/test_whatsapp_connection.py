import jwt
import pytest
from datetime import datetime, timedelta, timezone

from app import db
from app.models import AdminAuditLog, User, WhatsAppNotificationSetting, WhatsAppNotificationLog
from app import bookings, utils


@pytest.fixture
def admin_headers(app):
    with app.app_context():
        admin = User(phone='email:wa-admin@example.com', email='wa-admin@example.com', role='admin')
        db.session.add(admin)
        db.session.commit()
        return {'Authorization': 'Bearer ' + jwt.encode(
            {'user_id': admin.id, 'exp': datetime.now(timezone.utc) + timedelta(hours=1)},
            app.config['JWT_SECRET'], algorithm='HS256')}


class Response:
    ok = True
    text = ''

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        pass


def test_connection_qr_requires_admin_and_forwards_bot_token(client, admin_headers, monkeypatch):
    calls = []
    monkeypatch.setenv('WHATSAPP_BOT_URL', 'http://isolated-bot')
    monkeypatch.setenv('WHATSAPP_BOT_TOKEN', 'private-token')

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response({'provider': 'whatsapp_web', 'ready': False, 'state': 'qr_required',
                         'message': 'Scan QR', 'qr_image': 'data:image/png;base64,test'})

    monkeypatch.setattr(bookings.requests, 'get', get)
    endpoint = '/api/admin/system-checks/whatsapp-connection'
    assert client.get(endpoint).status_code == 401
    result = client.get(endpoint, headers=admin_headers)
    assert result.status_code == 200
    assert result.json['qr_image'] == 'data:image/png;base64,test'
    assert result.json['ready'] is False
    assert result.json['message'] == 'Scan QR'
    assert calls[-1][0] == 'http://isolated-bot/connection'
    assert calls[-1][1]['headers'] == {'X-Bot-Token': 'private-token'}


def test_connection_rejects_member_access(client, app, monkeypatch):
    with app.app_context():
        user = User(phone='email:wa-member@example.com', role='member')
        db.session.add(user)
        db.session.commit()
        headers = {'Authorization': 'Bearer ' + jwt.encode({'user_id': user.id}, app.config['JWT_SECRET'], algorithm='HS256')}
    monkeypatch.setattr(bookings.requests, 'get', lambda *a, **k: pytest.fail('Member reached bot'))
    assert client.get('/api/admin/system-checks/whatsapp-connection', headers=headers).status_code == 403
    assert client.post('/api/admin/system-checks/whatsapp-connection', headers=headers, json={'reset_session': True}).status_code == 403


@pytest.mark.parametrize('reset', [False, True])
def test_admin_reconnect_and_reset_are_forwarded_and_audited(client, app, admin_headers, monkeypatch, reset):
    sent = []
    monkeypatch.setenv('WHATSAPP_BOT_URL', 'http://isolated-bot')
    monkeypatch.setenv('WHATSAPP_BOT_TOKEN', 'private-token')
    monkeypatch.setattr(bookings.requests, 'post', lambda url, **kw: sent.append((url, kw)) or Response({'status': 'reconnecting'}))
    endpoint = '/api/admin/system-checks/whatsapp-connection'
    assert client.post(endpoint, json={'reset_session': reset}).status_code == 401
    assert client.post(endpoint, headers=admin_headers, json={'reset_session': 'false'}).status_code == 400
    response = client.post(endpoint, headers=admin_headers, json={'reset_session': reset})
    assert response.status_code == 200
    assert sent == [('http://isolated-bot/reconnect', {'json': {'reset_session': reset}, 'headers': {'X-Bot-Token': 'private-token'}, 'timeout': 20})]
    with app.app_context():
        assert AdminAuditLog.query.filter_by(entity_type='whatsapp_connection').count() == 1


def test_meta_without_credentials_does_not_report_connected(app, monkeypatch):
    monkeypatch.setenv('WHATSAPP_BOT_URL', 'http://isolated-bot')
    monkeypatch.setattr(bookings.requests, 'get', lambda *a, **k: Response({'provider': 'meta_cloud_api', 'ready': False}))
    with app.app_context():
        result = bookings._check_whatsapp_bot_status()
    assert result['status'] == 'warning'
    assert 'WHATSAPP_ACCESS_TOKEN' in result['message']


def test_provider_failure_is_preserved_for_password_reset_diagnostics(app, monkeypatch):
    monkeypatch.setenv('WHATSAPP_BOT_URL', 'http://isolated-bot')
    monkeypatch.delenv('TWILIO_ACCOUNT_SID', raising=False)
    failure = Response({})
    failure.ok = False
    failure.text = '{"error":"whatsapp_not_ready"}'
    monkeypatch.setattr(utils.requests, 'post', lambda *a, **k: failure)
    with app.app_context():
        result = utils.send_whatsapp_message('+31612345678', 'test')
    assert result['status'] == 'failed'
    assert 'whatsapp_not_ready' in result['error']


def test_failed_reminder_retries_after_reconnection_then_deduplicates(app, monkeypatch):
    replies = iter([('failed', 'disconnected'), ('sent', 'ok')])
    monkeypatch.setattr(bookings, '_send_whatsapp_bot_message', lambda *a: next(replies))
    with app.app_context():
        db.session.add(WhatsAppNotificationSetting(event_key='booking_reminder', title='Reminder', template='Hi', is_enabled=True, send_to_group=True, group_id='123@g.us'))
        db.session.commit()
        first = bookings._send_whatsapp_event('booking_reminder', {}, dedupe_key='retry-1')
        assert first.status == 'failed'
        second = bookings._send_whatsapp_event('booking_reminder', {}, dedupe_key='retry-1')
        assert second.status == 'sent'
        assert bookings._send_whatsapp_event('booking_reminder', {}, dedupe_key='retry-1') is None
        assert WhatsAppNotificationLog.query.filter_by(event_key='booking_reminder').count() == 2
