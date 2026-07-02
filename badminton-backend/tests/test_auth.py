import json


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


def test_seeded_admin_login_credentials(client):
    resp = client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('status') == 'ok'
    assert data.get('user', {}).get('role') == 'admin'


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
