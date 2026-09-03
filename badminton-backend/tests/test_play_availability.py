import jwt
from datetime import datetime, timedelta

from app import db
from app.models import FamilyMember, PlayAvailabilityVote, User, WhatsAppNotificationLog, WhatsAppNotificationSetting


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



def test_admin_can_send_availability_overview_notification(client, app, monkeypatch):
    from app import bookings as bookings_module

    sent_messages = []
    monkeypatch.setattr(bookings_module, '_send_whatsapp_bot_message', lambda message, recipient=None: sent_messages.append({'message': message, 'recipient': recipient}) or ('sent', 'ok'))

    with app.app_context():
        admin = User(phone='+31100001000', email='availability-admin@example.com', name='Availability Admin', role='admin')
        member = User(phone='+31100001001', email='availability-member@example.com', name='Availability Member', role='member')
        db.session.add_all([admin, member])
        db.session.commit()
        today = bookings_module._amsterdam_now().date()
        tomorrow = today + timedelta(days=1)
        db.session.add_all([
            PlayAvailabilityVote(user_id=member.id, play_date=today.strftime('%Y-%m-%d'), available=True, status='available', attendee_count=1, attendee_details='[{"name":"Alex","status":"available"}]'),
            PlayAvailabilityVote(user_id=member.id, play_date=tomorrow.strftime('%Y-%m-%d'), available=False, status='tentative', attendee_count=0, attendee_details='[{"name":"Sam","status":"tentative"}]'),
            WhatsAppNotificationSetting(event_key='availability_summary', title='Availability overview', template='{{overview}}', is_enabled=True, send_to_group=True, group_id='group-availability', test_recipient_number='+31 6 1234 5678'),
        ])
        db.session.commit()
        headers = _auth_headers(app, admin)

    preview_resp = client.post('/api/admin/availability-summary/preview', json={'days': 2}, headers=headers)
    assert preview_resp.status_code == 200
    preview = preview_resp.get_json()
    assert 'Alex' in preview['message']
    assert preview['test_recipients'][0]['normalized'] == '31612345678@c.us'

    test_resp = client.post('/api/admin/availability-summary/send', json={'days': 2, 'message': 'Custom preview message', 'test': True, 'recipient': '+31 6 1234 5678'}, headers=headers)
    assert test_resp.status_code == 200
    assert test_resp.get_json()['log']['recipient'] == '31612345678@c.us'
    assert sent_messages[0] == {'message': 'Custom preview message', 'recipient': '31612345678@c.us'}

    resp = client.post('/api/admin/availability-summary/send', json={'days': 2}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['sent'] == 1
    assert 'Availability overview' in data['message']
    assert 'Alex' in data['message']
    assert 'Sam' in data['message']
    assert sent_messages[1]['recipient'] == 'group-availability'
    assert '✅ Available (1): Alex' in sent_messages[1]['message']
    assert '🤔 Tentative (1): Sam' in sent_messages[1]['message']

    with app.app_context():
        log = WhatsAppNotificationLog.query.filter_by(event_key='availability_summary').first()
        assert log.status == 'sent'


def test_availability_overview_notification_is_enabled_by_default(client, app, monkeypatch):
    from app import bookings as bookings_module

    sent_messages = []
    monkeypatch.setattr(bookings_module, '_send_whatsapp_bot_message', lambda message, recipient=None: sent_messages.append(message) or ('sent', 'ok'))

    with app.app_context():
        admin = User(phone='+31100001010', email='availability-default-admin@example.com', name='Default Admin', role='admin')
        db.session.add(admin)
        db.session.commit()
        headers = _auth_headers(app, admin)

    resp = client.post('/api/admin/availability-summary/send', json={'days': 1}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['sent'] == 1
    assert data['log']['status'] == 'sent'
    assert sent_messages

    with app.app_context():
        setting = WhatsAppNotificationSetting.query.filter_by(event_key='availability_summary').first()
        assert setting is not None
        assert setting.is_enabled is True


def test_admin_can_send_whatsapp_availability_polls_for_multiple_days(client, app, monkeypatch):
    from app import bookings as bookings_module

    sent_polls = []
    monkeypatch.setattr(
        bookings_module,
        '_send_whatsapp_bot_poll',
        lambda question, options, recipient=None: sent_polls.append({
            'question': question,
            'options': options,
            'recipient': recipient,
        }) or ('sent', 'ok'),
    )

    with app.app_context():
        admin = User(phone='+31100001020', email='poll-admin@example.com', name='Poll Admin', role='admin')
        member = User(phone='+31100001021', email='poll-member@example.com', name='Poll Member', role='member')
        db.session.add_all([admin, member])
        db.session.commit()
        db.session.add(WhatsAppNotificationSetting(
            event_key='availability_summary',
            title='Availability overview',
            template='{{overview}}',
            is_enabled=True,
            send_to_group=True,
            group_id='poll-group@g.us',
        ))
        db.session.commit()
        admin_headers = _auth_headers(app, admin)
        member_headers = _auth_headers(app, member)

    forbidden = client.post('/api/admin/availability-polls/send', json={'dates': ['2030-04-01']}, headers=member_headers)
    assert forbidden.status_code == 403

    response = client.post('/api/admin/availability-polls/send', json={
        'dates': ['2030-04-01', '2030-04-03'],
        'question_prefix': 'Badminton availability',
    }, headers=admin_headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['sent'] == 2
    assert len(payload['polls']) == 2
    assert payload['options'] == [
        '1 person available',
        '2 persons available',
        'Tentatively available',
        'Not available',
    ]
    assert [poll['recipient'] for poll in sent_polls] == ['poll-group@g.us', 'poll-group@g.us']
    assert sent_polls[0]['question'] == 'Badminton availability — Monday, 01 April 2030'
    assert sent_polls[1]['question'] == 'Badminton availability — Wednesday, 03 April 2030'

    with app.app_context():
        logs = WhatsAppNotificationLog.query.filter_by(event_key='availability_poll').all()
        assert len(logs) == 2
        assert all(log.status == 'sent' for log in logs)


def test_admin_can_override_availability_poll_recipient_for_test(client, app, monkeypatch):
    sent_polls = []

    def fake_send(question, options, recipient=None):
        sent_polls.append({'question': question, 'options': options, 'recipient': recipient})
        return 'sent', '{"status":"sent","id":"test-poll-id"}'

    monkeypatch.setattr('app.bookings._send_whatsapp_bot_poll', fake_send)
    with app.app_context():
        admin = User(phone='+31100001041', email='poll-test-admin@example.com', name='Poll Admin', role='admin')
        db.session.add(admin)
        db.session.commit()
        admin_headers = _auth_headers(app, admin)

    response = client.post('/api/admin/availability-polls/send', json={
        'dates': ['2030-04-01'],
        'question_prefix': 'Test availability',
        'test': True,
        'recipient': '+31 6 1234 5678',
    }, headers=admin_headers)

    assert response.status_code == 200
    assert response.get_json()['test'] is True
    assert response.get_json()['recipient'] == '31612345678@c.us'
    assert sent_polls[0]['recipient'] == '31612345678@c.us'


def test_whatsapp_poll_response_updates_member_availability(client, app, monkeypatch):
    monkeypatch.setenv('WHATSAPP_BOT_TOKEN', 'poll-secret')
    with app.app_context():
        member = User(
            phone='+31100001030',
            whatsapp_number='+31 6 1234 5678',
            email='poll-voter@example.com',
            name='Poll Voter',
            role='member',
        )
        db.session.add(member)
        db.session.flush()
        log = WhatsAppNotificationLog(
            event_key='availability_poll',
            recipient='poll-group@g.us',
            message='Who can play? — Friday, 05 April 2030',
            status='sent',
            response='{"status":"sent","id":"poll-message-123"}\nplay_date=2030-04-05',
        )
        db.session.add(log)
        db.session.commit()
        member_headers = _auth_headers(app, member)

    forbidden = client.post('/api/whatsapp/poll-vote', json={
        'poll_message_id': 'poll-message-123',
        'voter': '31612345678@c.us',
        'selected_option': '2 persons available',
    }, headers={'X-Bot-Token': 'wrong-secret'})
    assert forbidden.status_code == 403

    response = client.post('/api/whatsapp/poll-vote', json={
        'poll_message_id': 'poll-message-123',
        'voter': '31612345678@c.us',
        'selected_option': '2 persons available',
    }, headers={'X-Bot-Token': 'poll-secret'})
    assert response.status_code == 200
    assert response.get_json()['vote']['attendee_count'] == 2

    availability = client.get('/api/play-availability?start_date=2030-04-05&days=1', headers=member_headers)
    day = availability.get_json()['days'][0]
    assert day['vote']['status'] == 'available'
    assert day['totals']['available_count'] == 2
    assert [person['name'] for person in day['totals']['available_attendees']] == ['Poll Voter', 'Poll Voter guest']

    deselect = client.post('/api/whatsapp/poll-vote', json={
        'poll_message_id': 'poll-message-123',
        'voter': '31612345678@c.us',
        'selected_option': '',
    }, headers={'X-Bot-Token': 'poll-secret'})
    assert deselect.status_code == 200
    assert deselect.get_json()['vote']['status'] == 'not_available'


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


def test_startup_backfills_family_member_link_column(client, app):
    with app.app_context():
        columns = {column['name'] for column in db.inspect(db.engine).get_columns('family_members')}
    assert 'linked_user_id' in columns


def test_linked_family_member_availability_stays_in_sync_without_duplicate_totals(client, app):
    with app.app_context():
        owner = User(phone='+31100002000', email='owner-sync@example.com', name='Owner User', role='member')
        child = User(phone='+31100002001', email='child-sync@example.com', name='Child User', role='member')
        db.session.add_all([owner, child])
        db.session.commit()
        family = FamilyMember(user_id=owner.id, name='Child Family Name', linked_user_id=child.id)
        db.session.add(family)
        db.session.commit()
        owner_headers = _auth_headers(app, owner)
        child_headers = _auth_headers(app, child)
        family_id = family.id
        owner_id = owner.id

    owner_resp = client.post('/api/play-availability', json={
        'play_date': '2030-03-01',
        'status': 'available',
        'attendees': [
            {'type': 'self'},
            {'type': 'family', 'family_member_id': family_id},
        ],
    }, headers=owner_headers)
    assert owner_resp.status_code == 200

    child_view = client.get('/api/play-availability?start_date=2030-03-01&days=1', headers=child_headers)
    assert child_view.status_code == 200
    child_day = child_view.get_json()['days'][0]
    assert child_day['totals']['available_count'] == 2
    assert [item['name'] for item in child_day['totals']['available_attendees']] == ['Owner User', 'Child Family Name']

    child_resp = client.post('/api/play-availability', json={
        'play_date': '2030-03-01',
        'attendees': [
            {'type': 'self', 'status': 'tentative'},
        ],
    }, headers=child_headers)
    assert child_resp.status_code == 200

    owner_view = client.get('/api/play-availability?start_date=2030-03-01&days=1', headers=owner_headers)
    assert owner_view.status_code == 200
    owner_day = owner_view.get_json()['days'][0]
    assert owner_day['vote']['user_id'] == owner_id
    assert owner_day['totals']['available_count'] == 1
    assert owner_day['totals']['tentative_count'] == 1
    assert [item['name'] for item in owner_day['totals']['available_attendees']] == ['Owner User']
    assert [item['name'] for item in owner_day['totals']['tentative_attendees']] == ['Child Family Name']

    with app.app_context():
        votes = PlayAvailabilityVote.query.filter_by(play_date='2030-03-01').all()
        assert len(votes) == 2
