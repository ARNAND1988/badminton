import jwt
from datetime import datetime, timedelta

from app import db
from app.models import FamilyMember, User


def _auth_headers(app, user):
    token = jwt.encode(
        {'user_id': user.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
        app.config['JWT_SECRET'],
        algorithm='HS256',
    )
    return {'Authorization': f'Bearer {token}'}


def test_family_members_and_play_availability_vote(client, app):
    with app.app_context():
        user = User(phone='+31100000002', email='family@example.com', name='Family User', role='member')
        db.session.add(user)
        db.session.commit()
        family = FamilyMember(user_id=user.id, name='Sam')
        db.session.add(family)
        db.session.commit()
        family_id = family.id
        headers = _auth_headers(app, user)

    member_resp = client.post('/api/family-members', json={'name': 'Sam'}, headers=headers)
    assert member_resp.status_code == 200
    member_data = member_resp.get_json()
    assert member_data['name'] == 'Sam'
    assert member_data['relationship'] is None

    list_resp = client.get('/api/family-members', headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.get_json()['members']) == 2

    vote_resp = client.post('/api/play-availability', json={
        'play_date': '2030-01-05',
        'available': True,
        'attendee_count': 2,
        'attendees': [
            {'type': 'self'},
            {'type': 'family', 'family_member_id': family_id},
        ],
        'notes': 'Can play after lunch'
    }, headers=headers)
    assert vote_resp.status_code == 200
    vote_data = vote_resp.get_json()
    assert vote_data['available'] is True
    assert vote_data['status'] == 'available'
    assert vote_data['attendee_count'] == 2
    assert [item['name'] for item in vote_data['attendee_details']] == ['Family User', 'Sam']

    availability_resp = client.get('/api/play-availability?start_date=2030-01-05&days=2', headers=headers)
    assert availability_resp.status_code == 200
    days = availability_resp.get_json()['days']
    assert days[0]['date'] == '2030-01-05'
    assert days[0]['vote']['attendee_count'] == 2
    assert days[0]['totals']['attendee_count'] == 2
    assert [item['name'] for item in days[0]['totals']['available_attendees']] == ['Family User', 'Sam']

    tentative_resp = client.post('/api/play-availability', json={
        'play_date': '2030-01-06',
        'status': 'tentative',
        'attendee_count': 2,
        'attendees': [{'type': 'family', 'family_member_id': family_id}],
    }, headers=headers)
    assert tentative_resp.status_code == 200
    tentative_data = tentative_resp.get_json()
    assert tentative_data['available'] is False
    assert tentative_data['status'] == 'tentative'
    assert tentative_data['attendee_count'] == 0
    assert tentative_data['attendee_details'][0]['name'] == 'Sam'

    availability_resp = client.get('/api/play-availability?start_date=2030-01-05&days=2', headers=headers)
    days = availability_resp.get_json()['days']
    assert days[1]['totals']['tentative_families'] == 1
    assert days[1]['totals']['tentative_attendees'][0]['name'] == 'Sam'

    delete_resp = client.delete(f"/api/family-members/{member_data['id']}", headers=headers)
    assert delete_resp.status_code == 200

    list_resp = client.get('/api/family-members', headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.get_json()['members']) == 1


def test_play_availability_defaults_to_today_and_clamps_past_start_date(client):
    today = datetime.utcnow().date()
    yesterday = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    today_value = today.strftime('%Y-%m-%d')

    default_resp = client.get('/api/play-availability?days=7')
    assert default_resp.status_code == 200
    default_days = default_resp.get_json()['days']
    assert len(default_days) == 7
    assert default_days[0]['date'] == today_value
    assert yesterday not in [day['date'] for day in default_days]

    clamped_resp = client.get(f'/api/play-availability?start_date={yesterday}&days=7')
    assert clamped_resp.status_code == 200
    clamped_days = clamped_resp.get_json()['days']
    assert len(clamped_days) == 7
    assert clamped_days[0]['date'] == today_value
    assert yesterday not in [day['date'] for day in clamped_days]


def test_play_availability_public_totals_without_login(client, app):
    with app.app_context():
        user = User(phone='+31100000004', email='public@example.com', name='Public User', role='member')
        db.session.add(user)
        db.session.commit()
        headers = _auth_headers(app, user)

    vote_resp = client.post('/api/play-availability', json={
        'play_date': '2030-02-01',
        'available': True,
        'attendee_count': 3,
    }, headers=headers)
    assert vote_resp.status_code == 200

    public_resp = client.get('/api/play-availability?start_date=2030-02-01&days=7')
    assert public_resp.status_code == 200
    days = public_resp.get_json()['days']
    assert len(days) == 7
    assert days[0]['date'] == '2030-02-01'
    assert days[0]['vote'] is None
    assert days[0]['totals']['available_families'] == 1
    assert days[0]['totals']['attendee_count'] == 3
