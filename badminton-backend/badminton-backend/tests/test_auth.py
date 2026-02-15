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
