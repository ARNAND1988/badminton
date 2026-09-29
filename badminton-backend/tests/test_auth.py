import json

from passlib.hash import pbkdf2_sha256

from app import create_app, db
from app.models import FamilyMember, User


def test_send_otp_mock(client):
    resp = client.post('/api/auth/send-otp', json={'phone': '+10000000000'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('status') == 'otp_sent'
    assert 'mock_otp' in data


def test_verify_and_me(client):
    phone = '+19999999999'
    # request OTP (mock)
    r1 = client.post('/api/auth/send-otp', json={'phone': phone})
    assert r1.status_code == 200
    d1 = r1.get_json()
    otp = d1.get('mock_otp')
    assert otp is not None

    # verify
    r2 = client.post('/api/auth/verify', json={'phone': phone, 'otp': otp, 'name': 'Test User'})
    assert r2.status_code == 200
    d2 = r2.get_json()
    assert d2.get('status') == 'ok'
    token = d2.get('token')
    assert token

    # call /me
    r3 = client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert r3.status_code == 200
    d3 = r3.get_json()
    assert 'user' in d3
    assert d3['user']['phone'] == phone


def test_dummy_admin_login_credentials_are_not_seeded(client):
    resp = client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert resp.status_code == 401

    phone_resp = client.post('/api/auth/login', json={'username': '+10000000000', 'password': 'admin123'})
    assert phone_resp.status_code == 401


def test_register_and_login_with_email_password(client):
    register_resp = client.post('/api/auth/register', json={
        'email': 'new.member@example.com',
        'password': 'secret123',
        'name': 'New Member',
        'whatsapp_number': '+31612345678'
    })
    assert register_resp.status_code == 201
    register_data = register_resp.get_json()
    assert register_data.get('status') == 'ok'
    assert register_data.get('token')
    assert register_data.get('user', {}).get('email') == 'new.member@example.com'
    assert register_data.get('user', {}).get('whatsapp_number') == '+31612345678'

    login_resp = client.post('/api/auth/login', json={
        'email': 'new.member@example.com',
        'password': 'secret123'
    })
    assert login_resp.status_code == 200
    login_data = login_resp.get_json()
    assert login_data.get('status') == 'ok'
    assert login_data.get('user', {}).get('email') == 'new.member@example.com'

    username_resp = client.post('/api/auth/login', json={
        'username': 'New Member',
        'password': 'secret123'
    })
    assert username_resp.status_code == 200
    username_data = username_resp.get_json()
    assert username_data.get('status') == 'ok'
    assert username_data.get('user', {}).get('email') == 'new.member@example.com'


def test_register_without_whatsapp(client):
    resp = client.post('/api/auth/register', json={
        'email': 'plain.member@example.com',
        'password': 'secret123'
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data.get('user', {}).get('phone') == 'email:plain.member@example.com'
    assert data.get('user', {}).get('whatsapp_number') is None


def test_dummy_member_login_credentials_are_not_seeded(client):
    resp = client.post('/api/auth/login', json={'username': 'user', 'password': 'user123'})
    assert resp.status_code == 401


def test_startup_revokes_legacy_demo_login_without_deleting_related_data(monkeypatch, tmp_path):
    database_path = tmp_path / 'legacy.sqlite'
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{database_path}')
    monkeypatch.setenv('FLASK_ENV', 'development')

    first_app = create_app()
    with first_app.app_context():
        legacy_user = User(
            phone='+10000000000',
            email='admin@example.com',
            name='Demo Admin',
            role='admin',
            password_hash='legacy-demo-password-hash',
        )
        db.session.add(legacy_user)
        db.session.flush()
        db.session.add(FamilyMember(user_id=legacy_user.id, name='Demo Child'))
        db.session.commit()
        legacy_user_id = legacy_user.id
        db.session.remove()

    # A restart used to fail while trying to delete the legacy user because
    # family_members.user_id is non-nullable.
    restarted_app = create_app()
    restarted_app.config.update(TESTING=True)
    with restarted_app.test_client() as restarted_client:
        login_response = restarted_client.post('/api/auth/login', json={
            'username': 'admin',
            'password': 'admin123',
        })

    assert login_response.status_code == 401
    with restarted_app.app_context():
        legacy_user = db.session.get(User, legacy_user_id)
        assert legacy_user is not None
        assert legacy_user.password_hash is None
        assert legacy_user.role == 'member'
        assert FamilyMember.query.filter_by(user_id=legacy_user_id, name='Demo Child').one()
        db.session.remove()


def test_anand_parasuraman_is_seeded_as_super_admin(client):
    resp = client.post('/api/auth/login', json={
        'username': 'Anand Parasuraman',
        'password': 'admin123',
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('status') == 'ok'
    assert data.get('user', {}).get('name') == 'Anand Parasuraman'
    assert data.get('user', {}).get('email') == 'arnand0413@gmail.com'
    assert data.get('user', {}).get('role') == 'super_admin'

    email_resp = client.post('/api/auth/login', json={
        'username': 'arnand0413@gmail.com',
        'password': 'admin123',
    })
    assert email_resp.status_code == 200
    assert email_resp.get_json().get('user', {}).get('role') == 'super_admin'


def test_production_super_admin_password_can_be_configured(monkeypatch):
    """Production login must work through the proxy's internal HTTP connection."""
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.setenv('AUTH_MOCK', '0')
    monkeypatch.setenv('ANAND_SUPER_ADMIN_PASSWORD', 'deployment-secret')

    production_app = create_app()
    production_app.config.update(TESTING=True)
    with production_app.test_client() as production_client:
        response = production_client.post(
            '/api/auth/login',
            base_url='http://localhost',
            json={
                'username': 'arnand0413@gmail.com',
                'password': 'deployment-secret',
            },
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data['user']['role'] == 'super_admin'
    assert response.headers['Content-Security-Policy']

    with production_app.test_client() as production_client:
        me_response = production_client.get(
            '/api/auth/me',
            base_url='http://localhost',
            headers={'Authorization': f"Bearer {data['token']}"},
        )

    assert me_response.status_code == 200
    assert me_response.get_json()['user']['email'] == 'arnand0413@gmail.com'

    with production_app.app_context():
        db.session.remove()
        db.drop_all()


def test_startup_repairs_unsupported_seeded_admin_hash_instead_of_login_500(monkeypatch, tmp_path):
    """Regression: a legacy placeholder hash previously caused 'Error logging in.'."""
    database_path = tmp_path / 'legacy-admin.sqlite'
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{database_path}')
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.setenv('AUTH_MOCK', '0')
    monkeypatch.delenv('ANAND_SUPER_ADMIN_PASSWORD', raising=False)

    first_app = create_app()
    with first_app.app_context():
        admin = User.query.filter_by(email='arnand0413@gmail.com').one()
        admin.password_hash = 'legacy-placeholder-that-passlib-cannot-parse'
        db.session.commit()
        db.session.remove()

    monkeypatch.setenv('ANAND_SUPER_ADMIN_PASSWORD', 'deployment-secret')
    restarted_app = create_app()
    restarted_app.config.update(TESTING=True)
    with restarted_app.test_client() as restarted_client:
        response = restarted_client.post('/api/auth/login', json={
            'username': 'arnand0413@gmail.com',
            'password': 'deployment-secret',
        })

    assert response.status_code == 200
    assert response.is_json
    assert response.get_json()['user']['role'] == 'super_admin'
    with restarted_app.app_context():
        repaired = User.query.filter_by(email='arnand0413@gmail.com').one()
        assert pbkdf2_sha256.verify('deployment-secret', repaired.password_hash)
        db.session.remove()


def test_reset_password_with_linked_whatsapp(client):
    client.post('/api/auth/register', json={
        'email': 'reset.member@example.com',
        'password': 'old-secret',
        'name': 'Reset Member',
        'whatsapp_number': '+31611112222',
    })

    request_resp = client.post('/api/auth/forgot-password', json={
        'identifier': 'reset.member@example.com',
    })
    assert request_resp.status_code == 200
    otp = request_resp.get_json().get('mock_otp')
    assert otp

    reset_resp = client.post('/api/auth/reset-password', json={
        'identifier': 'reset.member@example.com',
        'otp': otp,
        'password': 'new-secret',
    })
    assert reset_resp.status_code == 200
    assert reset_resp.get_json() == {'status': 'password_reset'}

    old_login = client.post('/api/auth/login', json={
        'username': 'reset.member@example.com',
        'password': 'old-secret',
    })
    assert old_login.status_code == 401
    new_login = client.post('/api/auth/login', json={
        'username': 'reset.member@example.com',
        'password': 'new-secret',
    })
    assert new_login.status_code == 200


def test_production_password_reset_delivery_and_login(monkeypatch):
    """Exercise the production reset path, including the configured admin phone."""
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.setenv('AUTH_MOCK', '0')
    monkeypatch.setenv('ANAND_SUPER_ADMIN_PASSWORD', 'old-deployment-secret')
    monkeypatch.setenv('ANAND_SUPER_ADMIN_PHONE', '+31612345678')

    production_app = create_app()
    production_app.config.update(TESTING=True)
    delivered = {}

    def capture_reset_code(recipient, message):
        delivered['recipient'] = recipient
        delivered['otp'] = message.split(' code is ', 1)[1].split('.', 1)[0]
        return {'status': 'sent'}

    monkeypatch.setattr('app.auth.send_whatsapp_message', capture_reset_code)
    with production_app.test_client() as production_client:
        request_response = production_client.post('/api/auth/forgot-password', json={
            'identifier': 'ARNAND0413@GMAIL.COM',
        })
        assert request_response.status_code == 200
        assert request_response.get_json() == {'status': 'reset_code_sent'}
        assert delivered['recipient'] == '+31612345678'

        reset_response = production_client.post('/api/auth/reset-password', json={
            'identifier': 'ARNAND0413@GMAIL.COM',
            'otp': delivered['otp'],
            'password': 'new-deployment-secret',
        })
        assert reset_response.status_code == 200

        login_response = production_client.post('/api/auth/login', json={
            'username': 'ARNAND0413@GMAIL.COM',
            'password': 'new-deployment-secret',
        })
        assert login_response.status_code == 200
        assert login_response.get_json()['user']['role'] == 'super_admin'

    with production_app.app_context():
        db.session.remove()
        db.drop_all()


def test_forgot_password_does_not_reveal_account_or_whatsapp_status(client):
    no_account = client.post('/api/auth/forgot-password', json={'identifier': 'missing@example.com'})
    assert no_account.status_code == 200
    assert no_account.get_json() == {'status': 'reset_code_sent'}

    client.post('/api/auth/register', json={
        'email': 'no.whatsapp@example.com',
        'password': 'secret123',
    })
    no_whatsapp = client.post('/api/auth/forgot-password', json={'identifier': 'no.whatsapp@example.com'})
    assert no_whatsapp.status_code == 200
    assert no_whatsapp.get_json() == {'status': 'reset_code_sent'}


def test_forgot_password_reports_whatsapp_delivery_failure(client, app, monkeypatch):
    client.post('/api/auth/register', json={
        'email': 'delivery.failure@example.com',
        'password': 'old-secret',
        'name': 'Delivery Failure',
        'whatsapp_number': '+31611113333',
    })
    app.config['AUTH_MOCK'] = False
    monkeypatch.setattr('app.auth.send_whatsapp_message', lambda *_: {'status': 'unavailable'})

    response = client.post('/api/auth/forgot-password', json={'identifier': 'delivery.failure@example.com'})

    assert response.status_code == 502
    assert response.get_json()['error'] == 'whatsapp_delivery_failed'


def test_reset_password_rejects_invalid_code_and_short_password(client):
    short_password = client.post('/api/auth/reset-password', json={
        'identifier': 'somebody@example.com',
        'otp': '123456',
        'password': 'short',
    })
    assert short_password.status_code == 400
    assert short_password.get_json().get('error') == 'password_too_short'

    invalid_code = client.post('/api/auth/reset-password', json={
        'identifier': 'somebody@example.com',
        'otp': '123456',
        'password': 'long-enough',
    })
    assert invalid_code.status_code == 400
    assert invalid_code.get_json().get('error') == 'otp_invalid_or_expired'
