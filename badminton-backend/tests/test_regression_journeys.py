"""Critical isolated API journeys used by the repository regression gate."""
from datetime import datetime, timedelta

def _login(client, username, password='admin123'):
    response = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert response.status_code == 200
    return response.get_json()['token']

def _auth(token):
    return {'Authorization': f'Bearer {token}'}

def test_critical_member_login_participation_persistence_and_logout_boundary(client):
    registration = client.post('/api/auth/register', json={
        'email': 'journey.member@example.test', 'password': 'test-password',
        'name': 'Journey Member', 'whatsapp_number': '+3197000000001',
    })
    assert registration.status_code == 201
    token = _login(client, 'journey.member@example.test', 'test-password')
    assert client.get('/api/auth/me', headers=_auth(token)).status_code == 200
    initial_days = client.get('/api/play-availability', headers=_auth(token)).get_json()['days']
    play_date = initial_days[0]['date']
    saved = client.post('/api/play-availability', headers=_auth(token), json={
        'play_date': play_date, 'status': 'available',
        'attendees': [{'type': 'self', 'status': 'available'}],
    })
    assert saved.status_code == 200
    refreshed = client.get('/api/play-availability', headers=_auth(token))
    assert refreshed.status_code == 200
    matching_day = next(day for day in refreshed.get_json()['days'] if day['date'] == play_date)
    assert matching_day['vote']['status'] == 'available'
    assert client.get('/api/invoices/monthly', headers=_auth(token)).status_code == 200
    assert client.get('/api/auth/me').status_code == 401

def test_critical_admin_dashboard_resources_and_authorization(client):
    admin_token = _login(client, 'arnand0413@gmail.com')
    for path in ('/api/admin/users', '/api/admin/courts', '/api/admin/invoices/monthly'):
        assert client.get(path, headers=_auth(admin_token)).status_code == 200
    client.post('/api/auth/register', json={
        'email': 'ordinary.member@example.test', 'password': 'test-password', 'name': 'Ordinary Member',
    })
    member_token = _login(client, 'ordinary.member@example.test', 'test-password')
    assert client.get('/api/admin/users', headers=_auth(member_token)).status_code == 403
