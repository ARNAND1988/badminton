import jwt
from datetime import datetime, timedelta

from app import db
from app.models import Booking, BookingParticipant, Court, CourtFreezePeriod, FamilyMember, Invoice, MiscCost, PlayAvailabilityVote, User, WhatsAppNotificationLog, WhatsAppNotificationSetting


def test_booking_availability_and_invoice(client, app):
    with app.app_context():
        user = User(phone='+31100000000', email='owner@example.com', name='Owner', role='admin')
        db.session.add(user)
        db.session.commit()
        court = Court(name='Court 1', hourly_rate=25.0, is_active=True)
        db.session.add(court)
        db.session.commit()
        court_id = court.id
        token = jwt.encode(
            {'user_id': user.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    headers = {'Authorization': f'Bearer {token}'}

    availability_resp = client.get('/api/bookings/availability?date=2030-01-01', headers=headers)
    assert availability_resp.status_code == 200
    availability_data = availability_resp.get_json()
    assert availability_data['date'] == '2030-01-01'
    assert isinstance(availability_data['slots'], list)

    create_resp = client.post('/api/bookings', json={
        'court_id': court_id,
        'booking_date': '2030-01-01',
        'start_time': '18:00',
        'end_time': '19:00',
        'notes': 'Friendly match',
        'participants': ['+31111111111', '+31111111112']
    }, headers=headers)
    assert create_resp.status_code == 200
    booking_data = create_resp.get_json()
    assert booking_data['status'] == 'confirmed'
    assert booking_data['court']['id'] == court.id
    assert 'map_link' in booking_data['court']

    invoice_resp = client.post(f"/api/bookings/{booking_data['id']}/invoice", headers=headers)
    assert invoice_resp.status_code == 200
    invoice_data = invoice_resp.get_json()
    assert invoice_data['booking_id'] == booking_data['id']
    assert invoice_data['total_amount'] == 25.0

    update_resp = client.put(f"/api/bookings/{booking_data['id']}", json={
        'court_id': court_id,
        'booking_date': '2030-01-02',
        'start_time': '19:00',
        'end_time': '20:00',
        'cost': 30,
        'notes': 'Updated match'
    }, headers=headers)
    assert update_resp.status_code == 200
    update_data = update_resp.get_json()
    assert update_data['booking_date'] == '2030-01-02'
    assert update_data['start_time'] == '19:00'
    assert update_data['notes'] == 'Updated match'
    assert update_data['cost'] == 25.0


def test_admin_can_delete_booking_with_participants_invoice_and_cancel_notification(client, app, monkeypatch):
    import app.bookings as bookings_module

    sent_messages = []

    def fake_send(message, recipient=None):
        sent_messages.append({'message': message, 'recipient': recipient})
        return 'sent', '{"status":"sent"}'

    monkeypatch.setattr(bookings_module, '_send_whatsapp_bot_message', fake_send)

    with app.app_context():
        admin = User(phone='+31100000900', email='delete-admin@example.com', name='Delete Admin', role='admin')
        member = User(phone='+31100000901', email='delete-member@example.com', name='Delete Member', role='member')
        court = Court(name='Delete Court', hourly_rate=25.0, is_active=True)
        db.session.add_all([admin, member, court])
        db.session.commit()
        booking = Booking(
            court_id=court.id,
            booking_date='2030-03-01',
            start_time='18:00',
            end_time='19:00',
            cost=25,
            status='confirmed',
        )
        db.session.add(booking)
        db.session.commit()
        db.session.add_all([
            BookingParticipant(booking_id=booking.id, phone=member.phone, name=member.name, status='attending'),
            Invoice(booking_id=booking.id, total_amount=25, split_count=1, status='pending'),
            WhatsAppNotificationSetting(
                event_key='booking_cancelled',
                title='Booking cancelled',
                template='Cancelled {{court.name}} on {{date}} at {{start_time}}',
                is_enabled=True,
                send_to_group=True,
                group_id='120363409786593643@g.us',
            ),
        ])
        db.session.commit()
        booking_id = booking.id
        token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    resp = client.delete(f'/api/bookings/{booking_id}', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'deleted'
    assert sent_messages == [{
        'message': 'Cancelled Delete Court on 2030-03-01 at 18:00',
        'recipient': '120363409786593643@g.us',
    }]

    with app.app_context():
        assert Booking.query.get(booking_id) is None
        assert BookingParticipant.query.filter_by(booking_id=booking_id).count() == 0
        assert Invoice.query.filter_by(booking_id=booking_id).count() == 0
        log = WhatsAppNotificationLog.query.filter_by(event_key='booking_cancelled').order_by(WhatsAppNotificationLog.id.desc()).first()
        assert log.status == 'sent'
        assert 'Delete Court' in log.message


def test_booking_create_triggers_whatsapp_notification_with_court_name(client, app, monkeypatch):
    import app.bookings as bookings_module

    sent_messages = []

    def fake_send(message, recipient=None):
        sent_messages.append({'message': message, 'recipient': recipient})
        return 'sent', '{"status":"sent"}'

    monkeypatch.setattr(bookings_module, '_send_whatsapp_bot_message', fake_send)

    with app.app_context():
        admin = User(phone='+31100000910', email='notify-admin@example.com', name='Notify Admin', role='admin')
        court = Court(name='Real Notification Court', hourly_rate=25.0, is_active=True)
        db.session.add_all([admin, court])
        db.session.commit()
        setting = WhatsAppNotificationSetting.query.filter_by(event_key='booking_created').first()
        if not setting:
            setting = WhatsAppNotificationSetting(
                event_key='booking_created',
                title='New booking created',
                template='Court: {{court_name}} / {{court}} on {{date}}',
                is_enabled=True,
                send_to_group=True,
                group_id='120363409786593643@g.us',
            )
            db.session.add(setting)
        setting.template = 'Court: {{court_name}} / {{court}} / {{court.name}} on {{date}}'
        setting.is_enabled = True
        setting.group_id = '120363409786593643@g.us'
        db.session.commit()
        court_id = court.id
        token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    resp = client.post('/api/bookings', json={
        'court_id': court_id,
        'booking_date': '2030-04-01',
        'start_time': '18:00',
        'end_time': '19:00',
        'notes': 'Notify test',
        'participants': []
    }, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert sent_messages == [{
        'message': 'Court: Real Notification Court / Real Notification Court / Real Notification Court on 2030-04-01',
        'recipient': '120363409786593643@g.us',
    }]

    with app.app_context():
        log = WhatsAppNotificationLog.query.filter_by(event_key='booking_created').order_by(WhatsAppNotificationLog.id.desc()).first()
        assert log.status == 'sent'
        assert 'Real Notification Court' in log.message


def test_freeze_periods_skip_play_availability_days_and_are_admin_managed(client, app):
    with app.app_context():
        admin = User(phone='+31100000920', email='freeze-admin@example.com', name='Freeze Admin', role='admin')
        member = User(phone='+31100000921', email='freeze-member@example.com', name='Freeze Member', role='member')
        db.session.add_all([admin, member])
        db.session.commit()
        admin_token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )
        member_token = jwt.encode(
            {'user_id': member.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    admin_headers = {'Authorization': f'Bearer {admin_token}'}
    create_resp = client.post('/api/admin/freeze-periods', json={
        'title': 'School vacation',
        'start_date': '2030-05-02',
        'end_date': '2030-05-03',
        'reason': 'No hall availability',
    }, headers=admin_headers)
    assert create_resp.status_code == 201
    period = create_resp.get_json()
    assert period['is_active'] is True

    member_resp = client.get('/api/admin/freeze-periods', headers={'Authorization': f'Bearer {member_token}'})
    assert member_resp.status_code == 403

    availability_resp = client.get('/api/play-availability?start_date=2030-05-01&days=4')
    assert availability_resp.status_code == 200
    dates = [day['date'] for day in availability_resp.get_json()['days']]
    assert dates == ['2030-05-01', '2030-05-04', '2030-05-05', '2030-05-06']

    update_resp = client.put(f"/api/admin/freeze-periods/{period['id']}", json={
        **period,
        'is_active': False,
    }, headers=admin_headers)
    assert update_resp.status_code == 200

    availability_resp = client.get('/api/play-availability?start_date=2030-05-01&days=4')
    dates = [day['date'] for day in availability_resp.get_json()['days']]
    assert dates == ['2030-05-01', '2030-05-02', '2030-05-03', '2030-05-04']

    delete_resp = client.delete(f"/api/admin/freeze-periods/{period['id']}", headers=admin_headers)
    assert delete_resp.status_code == 200
    with app.app_context():
        assert CourtFreezePeriod.query.get(period['id']) is None


def test_recurring_booking_creation_with_end_date_and_notifications(client, app, monkeypatch):
    import app.bookings as bookings_module

    sent_messages = []

    def fake_send(message, recipient=None):
        sent_messages.append({'message': message, 'recipient': recipient})
        return 'sent', '{"status":"sent"}'

    monkeypatch.setattr(bookings_module, '_send_whatsapp_bot_message', fake_send)

    with app.app_context():
        user = User(phone='+31100000001', email='owner2@example.com', name='Owner 2', role='admin')
        db.session.add(user)
        db.session.commit()
        court = Court(name='Court 2', hourly_rate=30.0, half_hour_rate=18.0, is_active=True)
        db.session.add_all([
            court,
            WhatsAppNotificationSetting(
                event_key='booking_created',
                title='New booking created',
                template='Created {{court}} {{date}} €{{cost}}',
                is_enabled=True,
                send_to_group=True,
                group_id='120363409786593643@g.us',
            ),
        ])
        db.session.commit()
        court_id = court.id
        token = jwt.encode(
            {'user_id': user.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    headers = {'Authorization': f'Bearer {token}'}

    resp = client.post('/api/bookings', json={
        'court_id': court_id,
        'booking_date': '2030-01-04',
        'start_time': '20:00',
        'end_time': '21:30',
        'recurring': True,
        'recurring_interval_weeks': 1,
        'recurring_end_date': '2030-01-18',
        'notes': 'Weekly Saturday slot'
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'confirmed'
    assert data['notes'] == 'Weekly Saturday slot'
    assert data['booking_date'] == '2030-01-18'
    assert data['cost'] == 48.0
    assert [item['message'] for item in sent_messages] == [
        'Created Court 2 2030-01-04 €48.0',
        'Created Court 2 2030-01-11 €48.0',
        'Created Court 2 2030-01-18 €48.0',
    ]


def test_booking_admin_actions_require_admin_login(client, app):
    with app.app_context():
        member = User(phone='+31100000003', email='member@example.com', name='Member', role='member')
        db.session.add(member)
        db.session.commit()
        member_token = jwt.encode(
            {'user_id': member.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    create_resp = client.post('/api/bookings', json={
        'court_id': 1,
        'booking_date': '2030-01-04',
        'start_time': '20:00',
        'end_time': '21:00'
    })
    assert create_resp.status_code == 401

    member_resp = client.post('/api/admin/courts', json={
        'name': 'Court 3'
    }, headers={'Authorization': f'Bearer {member_token}'})
    assert member_resp.status_code == 403


def test_admin_can_update_and_soft_delete_court(client, app):
    with app.app_context():
        admin = User(phone='+31100000005', email='admin-court@example.com', name='Court Admin', role='admin')
        court = Court(name='Court Editable', hourly_rate=20.0, is_active=True)
        db.session.add(admin)
        db.session.add(court)
        db.session.commit()
        court_id = court.id
        token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    headers = {'Authorization': f'Bearer {token}'}

    update_resp = client.put(f'/api/admin/courts/{court_id}', json={
        'name': 'Court Updated',
        'location': 'Main hall',
        'description': 'Freshly lined',
        'map_link': 'https://maps.google.com/?q=Main+hall',
        'hourly_rate': 28,
        'half_hour_rate': 15,
    }, headers=headers)
    assert update_resp.status_code == 200
    update_data = update_resp.get_json()
    assert update_data['name'] == 'Court Updated'
    assert update_data['location'] == 'Main hall'
    assert update_data['map_link'] == 'https://maps.google.com/?q=Main+hall'
    assert update_data['hourly_rate'] == 28
    assert update_data['half_hour_rate'] == 15

    delete_resp = client.delete(f'/api/admin/courts/{court_id}', headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.get_json()['is_active'] is False


def test_admin_can_manage_users_and_family_members(client, app):
    with app.app_context():
        admin = User(phone='+31100000008', email='member-admin@example.com', name='Member Admin', role='admin')
        member = User(phone='+31100000009', email='club-member@example.com', name='Club Member', role='member')
        db.session.add(admin)
        db.session.add(member)
        db.session.commit()
        family = FamilyMember(user_id=member.id, name='Junior Member')
        db.session.add(family)
        db.session.commit()
        admin_id = admin.id
        member_id = member.id
        family_id = family.id
        token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    headers = {'Authorization': f'Bearer {token}'}

    list_resp = client.get('/api/admin/users', headers=headers)
    assert list_resp.status_code == 200
    listed_member = next(item for item in list_resp.get_json()['users'] if item['id'] == member_id)
    assert listed_member['family_members'][0]['name'] == 'Junior Member'

    update_resp = client.put(f'/api/admin/users/{member_id}', json={
        'name': 'Club Member Updated',
        'role': 'admin',
        'is_club_member': True,
        'whatsapp_number': '+31600000009',
    }, headers=headers)
    assert update_resp.status_code == 200
    updated_user = update_resp.get_json()
    assert updated_user['name'] == 'Club Member Updated'
    assert updated_user['role'] == 'admin'
    assert updated_user['is_club_member'] is True
    assert updated_user['whatsapp_number'] == '+31600000009'

    family_resp = client.put(f'/api/admin/family-members/{family_id}', json={
        'relationship': 'Child',
        'is_club_member': True,
    }, headers=headers)
    assert family_resp.status_code == 200
    updated_family = family_resp.get_json()
    assert updated_family['relationship'] == 'Child'
    assert updated_family['is_club_member'] is True

    create_family_resp = client.post('/api/admin/family-members', json={
        'user_id': member_id,
        'name': 'Second Junior',
        'relationship': 'Child',
    }, headers=headers)
    assert create_family_resp.status_code == 200
    created_family = create_family_resp.get_json()
    assert created_family['name'] == 'Second Junior'

    delete_family_resp = client.delete(f"/api/admin/family-members/{created_family['id']}", headers=headers)
    assert delete_family_resp.status_code == 200
    assert delete_family_resp.get_json()['status'] == 'deleted'

    self_demote_resp = client.put(f'/api/admin/users/{admin_id}', json={
        'role': 'member',
    }, headers=headers)
    assert self_demote_resp.status_code == 200
    assert self_demote_resp.get_json()['role'] == 'member'


def test_admin_can_remove_family_account_without_losing_vote_history(client, app):
    with app.app_context():
        admin = User(phone='+31100000010', email='remove-admin@example.com', name='Remove Admin', role='admin')
        member = User(phone='+31100000011', email='remove-family@example.com', name='Remove Family', role='member')
        db.session.add(admin)
        db.session.add(member)
        db.session.commit()
        family = FamilyMember(user_id=member.id, name='Detached Junior')
        vote = PlayAvailabilityVote(
            user_id=member.id,
            play_date='2030-04-01',
            available=True,
            status='available',
            attendee_count=2,
            attendee_details='[{"type":"self","name":"Remove Family"},{"type":"family","family_member_id":1,"name":"Detached Junior"}]',
        )
        db.session.add(family)
        db.session.add(vote)
        db.session.commit()
        member_id = member.id
        vote_id = vote.id
        token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    headers = {'Authorization': f'Bearer {token}'}
    delete_resp = client.delete(f'/api/admin/users/{member_id}', headers=headers)
    assert delete_resp.status_code == 200

    with app.app_context():
        assert User.query.get(member_id) is None
        assert FamilyMember.query.filter_by(user_id=member_id).count() == 0
        vote = PlayAvailabilityVote.query.get(vote_id)
        assert vote is not None
        assert vote.user_id is None
        assert vote.to_dict()['attendee_details'][0]['name'] == 'Remove Family'

    availability_resp = client.get('/api/play-availability?start_date=2030-04-01&days=1')
    assert availability_resp.status_code == 200
    totals = availability_resp.get_json()['days'][0]['totals']
    assert totals['attendee_count'] == 2
    assert [item['name'] for item in totals['available_attendees']] == ['Remove Family', 'Detached Junior']


def test_booking_rsvp_admin_attendance_and_cost_split(client, app):
    with app.app_context():
        admin = User(phone='+31100000006', email='split-admin@example.com', name='Split Admin', role='admin')
        member = User(phone='+31100000007', email='split-member@example.com', name='Split Member', role='member')
        court = Court(name='Split Court', hourly_rate=40.0, is_active=True)
        db.session.add(admin)
        db.session.add(member)
        db.session.add(court)
        db.session.commit()
        court_id = court.id
        admin_token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )
        member_token = jwt.encode(
            {'user_id': member.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    admin_headers = {'Authorization': f'Bearer {admin_token}'}
    member_headers = {'Authorization': f'Bearer {member_token}'}

    create_resp = client.post('/api/bookings', json={
        'court_id': court_id,
        'booking_date': '2030-03-01',
        'start_time': '18:00',
        'end_time': '20:00',
        'cost': 60,
    }, headers=admin_headers)
    assert create_resp.status_code == 200
    booking_id = create_resp.get_json()['id']

    rsvp_resp = client.post(f'/api/bookings/{booking_id}/rsvp', json={
        'status': 'attending'
    }, headers=member_headers)
    assert rsvp_resp.status_code == 200
    assert rsvp_resp.get_json()['status'] == 'attending'

    adhoc_resp = client.post(f'/api/bookings/{booking_id}/participants', json={
        'name': 'Guest Player',
        'phone': 'guest-player',
        'status': 'attending',
        'is_adhoc': True,
    }, headers=admin_headers)
    assert adhoc_resp.status_code == 200
    assert adhoc_resp.get_json()['is_adhoc'] is True

    list_resp = client.get('/api/bookings')
    assert list_resp.status_code == 200
    booking = next(item for item in list_resp.get_json()['bookings'] if item['id'] == booking_id)
    assert booking['cost_split']['attended_count'] == 2
    assert booking['cost_split']['cost_per_person'] == 40.0

    invoice_resp = client.post(f'/api/bookings/{booking_id}/invoice', headers=admin_headers)
    assert invoice_resp.status_code == 200
    assert invoice_resp.get_json()['split_count'] == 2

    settle_resp = client.post(f'/api/bookings/{booking_id}/settle', headers=admin_headers)
    assert settle_resp.status_code == 200
    assert settle_resp.get_json()['status'] == 'settled'


def test_member_can_set_family_attendance_for_booking(client, app):
    with app.app_context():
        admin = User(phone='+31100000009', email='family-att-admin@example.com', name='Family Admin', role='admin')
        member = User(phone='+31100000010', email='family-att-member@example.com', name='Family Booker', role='member')
        court = Court(name='Family Court', hourly_rate=50.0, is_active=True)
        db.session.add(admin)
        db.session.add(member)
        db.session.add(court)
        db.session.commit()
        family_member = FamilyMember(user_id=member.id, name='Junior Booker')
        db.session.add(family_member)
        db.session.commit()
        court_id = court.id
        family_member_id = family_member.id
        admin_token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )
        member_token = jwt.encode(
            {'user_id': member.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    admin_headers = {'Authorization': f'Bearer {admin_token}'}
    member_headers = {'Authorization': f'Bearer {member_token}'}

    create_resp = client.post('/api/bookings', json={
        'court_id': court_id,
        'booking_date': '2030-04-01',
        'start_time': '18:00',
        'end_time': '19:00',
        'cost': 50,
    }, headers=admin_headers)
    assert create_resp.status_code == 200
    booking_id = create_resp.get_json()['id']

    attendance_resp = client.post(f'/api/bookings/{booking_id}/family-attendance', json={
        'attendees': [
            {'type': 'self', 'status': 'not_attending'},
            {'type': 'family', 'family_member_id': family_member_id, 'status': 'attending'},
        ]
    }, headers=member_headers)
    assert attendance_resp.status_code == 200
    assert len(attendance_resp.get_json()['participants']) == 2

    list_resp = client.get('/api/bookings')
    booking = next(item for item in list_resp.get_json()['bookings'] if item['id'] == booking_id)
    assert booking['cost_split']['attended_count'] == 1
    assert booking['cost_split']['cost_per_person'] == 50.0
    family_participant = next(item for item in booking['participants'] if item['phone'] == f'family:{family_member_id}')
    assert family_participant['name'] == 'Junior Booker'
    assert family_participant['status'] == 'attending'


def test_misc_costs_admin_crud_and_authenticated_list(client, app):
    with app.app_context():
        admin = User(phone='+31100000008', email='misc-admin@example.com', name='Misc Admin', role='admin')
        db.session.add(admin)
        db.session.commit()
        token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    headers = {'Authorization': f'Bearer {token}'}

    create_resp = client.post('/api/misc-costs', json={
        'title': 'New rackets',
        'description': 'Shared club rackets',
        'amount': 120,
        'paid_by': 'Admin',
        'purchase_date': '2030-04-01',
        'split_count': 4,
    }, headers=headers)
    assert create_resp.status_code == 200
    cost = create_resp.get_json()
    assert cost['cost_per_person'] == 30.0
    assert cost['purchase_date'] == '2030-04-01'

    public_resp = client.get('/api/misc-costs', headers=headers)
    assert public_resp.status_code == 200
    assert len(public_resp.get_json()['costs']) == 1

    update_resp = client.put(f"/api/misc-costs/{cost['id']}", json={
        'title': 'New rackets and grips',
        'amount': 150,
        'purchase_date': '2030-04-02',
        'split_count': 5,
        'status': 'settled',
    }, headers=headers)
    assert update_resp.status_code == 200
    assert update_resp.get_json()['cost_per_person'] == 30.0
    assert update_resp.get_json()['purchase_date'] == '2030-04-02'
    assert update_resp.get_json()['status'] == 'settled'

    delete_resp = client.delete(f"/api/misc-costs/{cost['id']}", headers=headers)
    assert delete_resp.status_code == 200


def test_monthly_invoice_summary_for_member_and_admin(client, app):
    with app.app_context():
        member = User(phone='+31100000018', email='invoice-member@example.com', name='Invoice Member', role='member')
        admin = User(phone='+31100000019', email='invoice-admin@example.com', name='Invoice Admin', role='admin')
        court = Court(name='Invoice Court', hourly_rate=40.0, is_active=True)
        db.session.add_all([member, admin, court])
        db.session.commit()

        booking = Booking(
            court_id=court.id,
            booking_date='2026-05-12',
            start_time='19:00',
            end_time='20:00',
            cost=60,
            status='completed',
        )
        db.session.add(booking)
        db.session.commit()
        db.session.add_all([
            BookingParticipant(booking_id=booking.id, phone=member.phone, name='Invoice Member', status='attending'),
            BookingParticipant(booking_id=booking.id, phone=admin.phone, name='Invoice Admin', status='attending'),
            Invoice(booking_id=booking.id, total_amount=60, split_count=2, status='generated'),
            MiscCost(title='May shuttles', amount=30, purchase_date='2026-05-02', split_count=3, status='open'),
        ])
        db.session.commit()

        member_token = jwt.encode(
            {'user_id': member.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )
        admin_token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    member_resp = client.get('/api/invoices/monthly?month=2026-05', headers={'Authorization': f'Bearer {member_token}'})
    assert member_resp.status_code == 200
    member_invoice = member_resp.get_json()
    assert member_invoice['booking_total'] == 30.0
    assert member_invoice['misc_total'] == 10.0
    assert member_invoice['total'] == 40.0
    assert member_invoice['booking_items'][0]['invoice_status'] == 'generated'

    admin_resp = client.get('/api/admin/invoices/monthly?month=2026-05', headers={'Authorization': f'Bearer {admin_token}'})
    assert admin_resp.status_code == 200
    admin_data = admin_resp.get_json()
    assert admin_data['month'] == '2026-05'
    assert any(invoice['user']['email'] == 'invoice-member@example.com' and invoice['total'] == 40.0 for invoice in admin_data['invoices'])


def test_openapi_and_swagger_docs_are_available(client):
    spec_resp = client.get('/api/openapi.json')
    assert spec_resp.status_code == 200
    spec = spec_resp.get_json()
    assert spec['openapi'] == '3.0.3'
    assert '/api/bookings' in spec['paths']
    assert '/api/admin/whatsapp-notifications' in spec['paths']

    swagger_resp = client.get('/api/swagger.json')
    assert swagger_resp.status_code == 200
    assert swagger_resp.get_json()['info']['title'] == 'Nieuwegein Badminton API'

    docs_resp = client.get('/api/docs')
    assert docs_resp.status_code == 200
    assert b'SwaggerUIBundle' in docs_resp.data

    missing_api_resp = client.get('/api/does-not-exist')
    assert missing_api_resp.status_code == 404
    assert missing_api_resp.get_json()['error'] == 'not_found'


def test_list_bookings_repopulates_upcoming_seed_data(client):
    from app import db
    from app.models import Booking

    db.session.query(Booking).delete()
    db.session.commit()

    resp = client.get('/api/bookings')

    assert resp.status_code == 200
    bookings = resp.get_json()['bookings']
    assert len(bookings) == 3
    assert all(booking['status'] == 'confirmed' for booking in bookings)
    assert {booking['court']['name'] for booking in bookings} == {'Court 1', 'Court 2', 'Training Court'}


def test_create_app_adds_court_map_link_to_existing_database(tmp_path, monkeypatch):
    db_path = tmp_path / 'legacy.sqlite'
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{db_path}')

    from app import create_app, db

    app = create_app()
    with app.app_context():
        db.session.execute(db.text('ALTER TABLE courts DROP COLUMN map_link'))
        db.session.commit()
        db.session.remove()
        db.engine.dispose()

    app = create_app()
    with app.app_context():
        columns = {column['name'] for column in db.inspect(db.engine).get_columns('courts')}
        assert 'map_link' in columns


def test_archive_bookings_require_login_and_include_past_confirmed_bookings(client, app):
    from app.models import Booking

    with app.app_context():
        user = User(phone='+31100000444', email='member444@example.com', name='Member 444', role='member')
        court = Court(name='History Court', hourly_rate=20.0, is_active=True)
        db.session.add_all([user, court])
        db.session.commit()
        db.session.add(Booking(
            court_id=court.id,
            booking_date='2020-01-01',
            start_time='18:00',
            end_time='19:00',
            cost=20,
            status='confirmed',
        ))
        db.session.commit()
        token = jwt.encode(
            {'user_id': user.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    anonymous_resp = client.get('/api/bookings?status=archive')
    assert anonymous_resp.status_code == 401

    resp = client.get('/api/bookings?status=archive&page=1&per_page=100', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['pagination']['page'] == 1
    assert data['pagination']['per_page'] == 100
    assert data['pagination']['total'] >= 1
    assert data['bookings'][0]['status'] == 'completed'
    assert any(booking['booking_date'] == '2020-01-01' for booking in data['bookings'])


def test_archive_bookings_backfill_historical_loaded_data(client, app):
    with app.app_context():
        user = User(phone='+31100000555', email='member555@example.com', name='Member 555', role='member')
        db.session.add(user)
        db.session.commit()
        token = jwt.encode(
            {'user_id': user.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    resp = client.get('/api/bookings?status=archive&page=1&per_page=10000', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    historical = [
        booking for booking in data['bookings']
        if booking['notes'] == 'Historical booking imported from invoiced rental data'
    ]
    assert len(historical) == 38
    assert data['pagination']['total'] >= 38
    assert all(booking['status'] == 'completed' for booking in historical)
    assert all(booking['invoice']['status'] == 'settled' for booking in historical)
    assert {booking['court']['name'] for booking in historical} >= {'Gymzaal de Driemaster', 'Sportzaal De Sluis'}


def test_misc_costs_require_login(client):
    resp = client.get('/api/misc-costs')
    assert resp.status_code == 401


def test_fiscal_year_archive_keeps_july_to_june_active_and_locks_archived_bookings(client, app):
    with app.app_context():
        admin = User(phone='+31100000666', email='archive-admin@example.com', name='Archive Admin', role='admin')
        court = Court(name='Fiscal Court', hourly_rate=20.0, is_active=True)
        db.session.add_all([admin, court])
        db.session.commit()
        june_booking = Booking(court_id=court.id, booking_date='2026-06-30', start_time='18:00', end_time='19:00', cost=20, status='completed')
        july_booking = Booking(court_id=court.id, booking_date='2026-07-01', start_time='18:00', end_time='19:00', cost=20, status='completed')
        db.session.add_all([june_booking, july_booking])
        db.session.commit()
        db.session.add(BookingParticipant(booking_id=june_booking.id, phone='archived-player', name='Archived Player', status='attending'))
        db.session.commit()
        participant_id = june_booking.participants[0].id
        token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )
        june_id = june_booking.id
        july_id = july_booking.id

    headers = {'Authorization': f'Bearer {token}'}
    archive_resp = client.get('/api/bookings?status=archive&page=1&per_page=10000', headers=headers)
    assert archive_resp.status_code == 200
    archive_dates = {booking['id']: booking['booking_date'] for booking in archive_resp.get_json()['bookings']}
    assert archive_dates[june_id] == '2026-06-30'
    assert july_id not in archive_dates

    completed_resp = client.get('/api/bookings?status=completed&page=1&per_page=10000', headers=headers)
    assert completed_resp.status_code == 200
    completed_dates = {booking['id']: booking['booking_date'] for booking in completed_resp.get_json()['bookings']}
    assert completed_dates[july_id] == '2026-07-01'
    assert june_id not in completed_dates

    update_resp = client.put(f'/api/bookings/{june_id}/participants/{participant_id}', json={
        'name': 'Changed',
        'status': 'not_attending',
    }, headers=headers)
    assert update_resp.status_code == 409
    assert update_resp.get_json()['error'] == 'booking_archived'


def test_misc_costs_archive_by_july_to_june_cost_year(client, app):
    with app.app_context():
        admin = User(phone='+31100000667', email='misc-archive-admin@example.com', name='Misc Archive Admin', role='admin')
        db.session.add(admin)
        db.session.commit()
        db.session.add_all([
            MiscCost(title='June upload', amount=10, purchase_date='2026-06-30', split_count=1),
            MiscCost(title='July active', amount=20, purchase_date='2026-07-01', split_count=1),
        ])
        db.session.commit()
        token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    headers = {'Authorization': f'Bearer {token}'}
    active_resp = client.get('/api/misc-costs', headers=headers)
    assert active_resp.status_code == 200
    active_data = active_resp.get_json()
    assert active_data['archive_cutoff_date'] == '2026-07-01'
    assert 'July active' in {cost['title'] for cost in active_data['costs']}
    assert 'June upload' not in {cost['title'] for cost in active_data['costs']}

    archive_resp = client.get('/api/misc-costs?status=archive', headers=headers)
    assert archive_resp.status_code == 200
    archive_titles = {cost['title'] for cost in archive_resp.get_json()['costs']}
    assert 'June upload' in archive_titles
    assert 'July active' not in archive_titles
