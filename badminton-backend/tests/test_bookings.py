import jwt
from datetime import datetime, timedelta, timezone

from app import db
from app.models import AdminAuditLog, Booking, BookingParticipant, Court, CourtFreezePeriod, FamilyMember, Invoice, MiscCost, PaymentInvoice, PaymentSettings, PlayAvailabilityVote, User, WhatsAppNotificationLog, WhatsAppNotificationSetting, WiseWebhookEvent


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




def test_admin_audit_logs_capture_admin_booking_and_court_activity(client, app):
    with app.app_context():
        admin = User(phone='+31100003001', email='audit-admin@example.com', name='Audit Admin', role='admin')
        db.session.add(admin)
        db.session.commit()
        token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    headers = {'Authorization': f'Bearer {token}'}
    court_resp = client.post('/api/admin/courts', json={
        'name': 'Audit Court',
        'location': 'Audit Hall',
        'hourly_rate': 20,
    }, headers=headers)
    assert court_resp.status_code == 200
    court_id = court_resp.get_json()['id']

    booking_resp = client.post('/api/bookings', json={
        'court_id': court_id,
        'booking_date': '2030-08-01',
        'start_time': '18:00',
        'end_time': '19:00',
        'notes': 'Audit booking',
    }, headers=headers)
    assert booking_resp.status_code == 200
    booking_id = booking_resp.get_json()['id']

    update_resp = client.put(f'/api/bookings/{booking_id}', json={
        'court_id': court_id,
        'booking_date': '2030-08-01',
        'start_time': '18:30',
        'end_time': '19:30',
        'notes': 'Audit booking updated',
    }, headers=headers)
    assert update_resp.status_code == 200

    delete_resp = client.delete(f'/api/bookings/{booking_id}', headers=headers)
    assert delete_resp.status_code == 200

    logs_resp = client.get('/api/admin/audit-logs', headers=headers)
    assert logs_resp.status_code == 200
    logs = logs_resp.get_json()['logs']
    assert any(log['event_type'] == 'create' and log['entity_type'] == 'court' and log['admin_email'] == 'audit-admin@example.com' for log in logs)
    assert any(log['event_type'] == 'create' and log['entity_type'] == 'booking' and log['entity_id'] == str(booking_id) for log in logs)
    update_logs = [log for log in logs if log['event_type'] == 'update' and log['entity_type'] == 'booking']
    assert update_logs
    assert 'start_time' in update_logs[0]['details']['changes']
    assert any(log['event_type'] == 'delete' and log['entity_type'] == 'booking' and log['entity_id'] == str(booking_id) for log in logs)

    with app.app_context():
        assert AdminAuditLog.query.count() >= 4

def test_completed_booking_update_converts_attending_members_to_participated(client, app):
    with app.app_context():
        admin = User(phone='+31100002001', email='participated-admin@example.com', name='Participated Admin', role='admin')
        court = Court(name='Participated Court', hourly_rate=20.0, is_active=True)
        db.session.add_all([admin, court])
        db.session.commit()
        booking = Booking(court_id=court.id, booking_date='2030-06-01', start_time='18:00', end_time='19:00', cost=20, status='confirmed')
        db.session.add(booking)
        db.session.commit()
        participant = BookingParticipant(booking_id=booking.id, phone='player-1', name='Player One', status='attending')
        db.session.add(participant)
        db.session.commit()
        token = jwt.encode({'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)}, app.config['JWT_SECRET'], algorithm='HS256')
        booking_id = booking.id
        court_id = court.id

    resp = client.put(f'/api/bookings/{booking_id}', json={
        'court_id': court_id,
        'booking_date': '2030-06-01',
        'start_time': '18:00',
        'end_time': '19:00',
        'status': 'completed',
    }, headers={'Authorization': f'Bearer {token}'})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'completed'
    assert data['participants'][0]['status'] == 'participated'


def test_completed_booking_participant_write_normalizes_attending_to_participated(client, app):
    with app.app_context():
        admin = User(phone='+31100002002', email='completed-write-admin@example.com', name='Completed Write Admin', role='admin')
        court = Court(name='Completed Write Court', hourly_rate=20.0, is_active=True)
        db.session.add_all([admin, court])
        db.session.commit()
        booking = Booking(court_id=court.id, booking_date='2030-06-02', start_time='18:00', end_time='19:00', cost=20, status='completed')
        db.session.add(booking)
        db.session.commit()
        participant = BookingParticipant(booking_id=booking.id, phone='player-2', name='Player Two', status='tentative')
        db.session.add(participant)
        db.session.commit()
        token = jwt.encode({'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)}, app.config['JWT_SECRET'], algorithm='HS256')
        booking_id = booking.id
        participant_id = participant.id

    headers = {'Authorization': f'Bearer {token}'}
    update_resp = client.put(f'/api/bookings/{booking_id}/participants/{participant_id}', json={
        'name': 'Player Two',
        'phone': 'player-2',
        'status': 'attending',
    }, headers=headers)

    assert update_resp.status_code == 200
    assert update_resp.get_json()['status'] == 'participated'

    add_resp = client.post(f'/api/bookings/{booking_id}/participants', json={
        'name': 'Player Three',
        'phone': 'player-3',
        'status': 'attending',
    }, headers=headers)

    assert add_resp.status_code == 200
    assert add_resp.get_json()['status'] == 'participated'


def test_update_booking_status_dropdown_can_complete_settle_and_reject_old_invoice_status(client, app):
    with app.app_context():
        admin = User(phone='+31100002003', email='status-invoice-admin@example.com', name='Status Invoice Admin', role='admin')
        court = Court(name='Status Invoice Court', hourly_rate=30.0, is_active=True)
        db.session.add_all([admin, court])
        db.session.commit()
        booking = Booking(court_id=court.id, booking_date='2030-06-03', start_time='18:00', end_time='19:00', cost=30, status='confirmed')
        db.session.add(booking)
        db.session.commit()
        token = jwt.encode({'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)}, app.config['JWT_SECRET'], algorithm='HS256')
        booking_id = booking.id
        court_id = court.id

    headers = {'Authorization': f'Bearer {token}'}
    payload = {
        'court_id': court_id,
        'booking_date': '2030-06-03',
        'start_time': '18:00',
        'end_time': '19:00',
        'status': 'completed',
    }
    completed_resp = client.put(f'/api/bookings/{booking_id}', json=payload, headers=headers)

    assert completed_resp.status_code == 200
    completed_data = completed_resp.get_json()
    assert completed_data['status'] == 'completed'

    payload['status'] = 'generated'
    generated_resp = client.put(f'/api/bookings/{booking_id}', json=payload, headers=headers)
    assert generated_resp.status_code == 400
    assert generated_resp.get_json()['error'] == 'invalid_status'

    payload['status'] = 'settled'
    settled_resp = client.put(f'/api/bookings/{booking_id}', json=payload, headers=headers)

    assert settled_resp.status_code == 200
    settled_data = settled_resp.get_json()
    assert settled_data['status'] == 'settled'
    assert settled_data['invoice']['status'] == 'settled'

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


def test_due_booking_reminder_sends_once_when_enabled(client, app, monkeypatch):
    from app import bookings as bookings_module

    sent_messages = []

    def fake_send(message, recipient=None):
        sent_messages.append({'message': message, 'recipient': recipient})
        return 'sent', 'ok'

    monkeypatch.setattr(bookings_module, '_send_whatsapp_bot_message', fake_send)

    reminder_now = datetime(2026, 7, 3, 17, 0)
    with app.app_context():
        court = Court(name='Reminder Court', hourly_rate=20.0, is_active=True)
        db.session.add(court)
        db.session.commit()
        booking = Booking(
            court_id=court.id,
            booking_date='2026-07-03',
            start_time='18:00',
            end_time='19:00',
            cost=20,
            status='confirmed',
        )
        db.session.add(booking)
        db.session.add(WhatsAppNotificationSetting(
            event_key='booking_reminder',
            title='Booking reminder',
            description='Reminder',
            template='Reminder for {{court}} at {{start_time}}',
            is_enabled=False,
            send_to_group=True,
            group_id='group-1',
        ))
        db.session.commit()
        booking_id = booking.id

        assert bookings_module._send_due_booking_reminders(now=reminder_now) == []
        assert sent_messages == []

        setting = WhatsAppNotificationSetting.query.filter_by(event_key='booking_reminder').first()
        setting.is_enabled = True
        db.session.commit()

        logs = bookings_module._send_due_booking_reminders(now=reminder_now)
        assert len(logs) == 1
        assert sent_messages == [{'message': 'Reminder for Reminder Court at 18:00', 'recipient': 'group-1'}]
        assert f'booking_reminder:{booking_id}:2026-07-03:18:00:Europe/Amsterdam' in logs[0].response

        assert bookings_module._send_due_booking_reminders(now=reminder_now) == []
        assert len(sent_messages) == 1



def test_due_booking_reminder_uses_amsterdam_timezone_for_utc_scheduler(app, monkeypatch):
    from app import bookings as bookings_module

    sent_messages = []
    monkeypatch.setattr(bookings_module, '_send_whatsapp_bot_message', lambda message, recipient=None: sent_messages.append(message) or ('sent', 'ok'))

    with app.app_context():
        court = Court(name='Amsterdam Reminder Court', hourly_rate=20.0, is_active=True)
        db.session.add(court)
        db.session.commit()
        db.session.add(Booking(
            court_id=court.id,
            booking_date='2026-07-03',
            start_time='18:00',
            end_time='19:00',
            cost=20,
            status='confirmed',
        ))
        db.session.add(WhatsAppNotificationSetting(
            event_key='booking_reminder',
            title='Booking reminder',
            description='Reminder',
            template='Amsterdam reminder for {{court}} at {{start_time}}',
            is_enabled=True,
            send_to_group=True,
            group_id='group-ams',
        ))
        db.session.commit()

        logs = bookings_module._send_due_booking_reminders(now=datetime(2026, 7, 3, 15, 0, tzinfo=timezone.utc))
        assert len(logs) == 1
        assert sent_messages == ['Amsterdam reminder for Amsterdam Reminder Court at 18:00']

def test_due_booking_reminder_respects_send_to_group_flag(app, monkeypatch):
    from app import bookings as bookings_module

    sent_messages = []
    monkeypatch.setattr(bookings_module, '_send_whatsapp_bot_message', lambda message, recipient=None: sent_messages.append(message) or ('sent', 'ok'))

    with app.app_context():
        court = Court(name='Silent Reminder Court', hourly_rate=20.0, is_active=True)
        db.session.add(court)
        db.session.commit()
        db.session.add(Booking(
            court_id=court.id,
            booking_date='2026-07-03',
            start_time='18:00',
            end_time='19:00',
            cost=20,
            status='confirmed',
        ))
        db.session.add(WhatsAppNotificationSetting(
            event_key='booking_reminder',
            title='Booking reminder',
            description='Reminder',
            template='Reminder for {{court}}',
            is_enabled=True,
            send_to_group=False,
            group_id='group-1',
        ))
        db.session.commit()

        assert bookings_module._send_due_booking_reminders(now=datetime(2026, 7, 3, 17, 30)) == []
        assert sent_messages == []


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
        'password': 'newpass123',
    }, headers=headers)
    assert update_resp.status_code == 200
    updated_user = update_resp.get_json()
    assert updated_user['name'] == 'Club Member Updated'
    assert updated_user['role'] == 'admin'
    assert updated_user['is_club_member'] is True
    assert updated_user['whatsapp_number'] == '+31600000009'

    login_resp = client.post('/api/auth/login', json={'username': 'club-member@example.com', 'password': 'newpass123'})
    assert login_resp.status_code == 200
    assert login_resp.get_json()['user']['role'] == 'admin'
    phone_login_resp = client.post('/api/auth/login', json={'username': '+31100000009', 'password': 'newpass123'})
    assert phone_login_resp.status_code == 200
    whatsapp_login_resp = client.post('/api/auth/login', json={'username': '+31600000009', 'password': 'newpass123'})
    assert whatsapp_login_resp.status_code == 200

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


def test_booking_cost_split_rounds_each_share_up_and_tolerates_cent_difference(client, app):
    with app.app_context():
        court = Court(name='Rounding Court', hourly_rate=10.0, is_active=True)
        booking = Booking(
            court=court,
            booking_date='2030-05-01',
            start_time='18:00',
            end_time='19:00',
            cost=10.00,
            status='confirmed',
        )
        db.session.add_all([court, booking])
        db.session.flush()
        db.session.add_all([
            BookingParticipant(booking_id=booking.id, phone='round-1', name='Round One', status='attending'),
            BookingParticipant(booking_id=booking.id, phone='round-2', name='Round Two', status='attending'),
            BookingParticipant(booking_id=booking.id, phone='round-3', name='Round Three', status='attending'),
        ])
        db.session.commit()
        booking_id = booking.id

    resp = client.get('/api/bookings')
    assert resp.status_code == 200
    booking = next(item for item in resp.get_json()['bookings'] if item['id'] == booking_id)
    shares = [participant['cost_share'] for participant in booking['participants'] if participant['status'] == 'attending']
    assert shares == [3.34, 3.34, 3.34]
    assert round(sum(shares), 2) == 10.02
    assert abs(round(sum(shares), 2) - booking['cost_split']['total_cost']) <= 0.02
    assert booking['cost_split']['cost_per_person'] == 3.34
    assert booking['cost_split']['rounded_total'] == 10.02
    assert booking['cost_split']['rounding_adjustment'] == -0.02
    assert booking['cost_split']['rounding_tolerance'] == 0.01

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


def test_linked_family_booking_attendance_updates_single_participant(client, app):
    with app.app_context():
        admin = User(phone='+31100003000', email='linked-booking-admin@example.com', name='Linked Booking Admin', role='admin')
        owner = User(phone='+31100003001', email='linked-booking-owner@example.com', name='Linked Booking Owner', role='member')
        child = User(phone='+31100003002', email='linked-booking-child@example.com', name='Linked Booking Child', role='member')
        court = Court(name='Linked Family Court', hourly_rate=60.0, is_active=True)
        db.session.add_all([admin, owner, child, court])
        db.session.commit()
        family = FamilyMember(user_id=owner.id, name='Linked Child Family Name', linked_user_id=child.id)
        db.session.add(family)
        db.session.commit()
        court_id = court.id
        family_id = family.id
        child_phone = child.phone
        admin_token = jwt.encode({'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)}, app.config['JWT_SECRET'], algorithm='HS256')
        owner_token = jwt.encode({'user_id': owner.id, 'exp': datetime.utcnow() + timedelta(hours=2)}, app.config['JWT_SECRET'], algorithm='HS256')
        child_token = jwt.encode({'user_id': child.id, 'exp': datetime.utcnow() + timedelta(hours=2)}, app.config['JWT_SECRET'], algorithm='HS256')

    admin_headers = {'Authorization': f'Bearer {admin_token}'}
    owner_headers = {'Authorization': f'Bearer {owner_token}'}
    child_headers = {'Authorization': f'Bearer {child_token}'}

    create_resp = client.post('/api/bookings', json={
        'court_id': court_id,
        'booking_date': '2030-04-02',
        'start_time': '18:00',
        'end_time': '19:00',
        'cost': 60,
    }, headers=admin_headers)
    assert create_resp.status_code == 200
    booking_id = create_resp.get_json()['id']

    family_resp = client.post(f'/api/bookings/{booking_id}/family-attendance', json={
        'attendees': [{'type': 'family', 'family_member_id': family_id, 'status': 'attending'}]
    }, headers=owner_headers)
    assert family_resp.status_code == 200
    assert family_resp.get_json()['participants'][0]['phone'] == child_phone

    rsvp_resp = client.post(f'/api/bookings/{booking_id}/rsvp', json={'status': 'not_attending'}, headers=child_headers)
    assert rsvp_resp.status_code == 200

    list_resp = client.get('/api/bookings')
    booking = next(item for item in list_resp.get_json()['bookings'] if item['id'] == booking_id)
    linked_participants = [item for item in booking['participants'] if item['phone'] == child_phone]
    assert len(linked_participants) == 1
    assert linked_participants[0]['status'] == 'not_attending'
    assert booking['cost_split']['attended_count'] == 0

    with app.app_context():
        assert BookingParticipant.query.filter_by(booking_id=booking_id).count() == 1


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
    assert member_invoice['booking_items'][0]['booking_status'] == 'completed'
    assert member_invoice['booking_items'][0]['invoice_status'] == 'generated'

    admin_resp = client.get('/api/admin/invoices/monthly?month=2026-05', headers={'Authorization': f'Bearer {admin_token}'})
    assert admin_resp.status_code == 200
    admin_data = admin_resp.get_json()
    assert admin_data['month'] == '2026-05'
    member_admin_invoice = next(invoice for invoice in admin_data['invoices'] if invoice['user']['email'] == 'invoice-member@example.com')
    assert member_admin_invoice['total'] == 40.0
    assert member_admin_invoice['booking_items'][0]['booking_status'] == 'completed'
    assert member_admin_invoice['booking_items'][0]['invoice_status'] == 'generated'


def test_monthly_invoice_includes_completed_booking_on_current_day_without_mixing_misc(client, app):
    today = datetime.utcnow().strftime('%Y-%m-%d')
    month = datetime.utcnow().strftime('%Y-%m')
    with app.app_context():
        member = User(phone='+31100000918', email='today-invoice-member@example.com', name='Today Invoice Member', role='member')
        court = Court(name='Today Invoice Court', hourly_rate=40.0, is_active=True)
        db.session.add_all([member, court])
        db.session.commit()

        booking = Booking(
            court_id=court.id,
            booking_date=today,
            start_time='19:00',
            end_time='20:00',
            cost=50,
            status='completed',
        )
        db.session.add(booking)
        db.session.commit()
        db.session.add_all([
            BookingParticipant(booking_id=booking.id, phone=member.phone, name='Today Invoice Member', status='attending'),
            Invoice(booking_id=booking.id, total_amount=50, split_count=1, status='generated'),
            MiscCost(title='Current month shuttles', amount=15, purchase_date=today, split_count=1, status='open'),
        ])
        db.session.commit()

        member_token = jwt.encode(
            {'user_id': member.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    resp = client.get(f'/api/invoices/monthly?month={month}', headers={'Authorization': f'Bearer {member_token}'})
    assert resp.status_code == 200
    invoice = resp.get_json()
    assert invoice['booking_total'] == 50.0
    assert invoice['misc_total'] == 15.0
    assert invoice['total'] == 65.0
    assert invoice['booking_items'][0]['total_cost'] == 50.0
    assert invoice['misc_items'][0]['amount'] == 15.0


def test_completed_bookings_can_be_filtered_by_invoice_month(client, app):
    with app.app_context():
        user = User(phone='+31100000919', email='month-completed@example.com', name='Month Completed', role='member')
        court = Court(name='Month Filter Court', hourly_rate=20.0, is_active=True)
        db.session.add_all([user, court])
        db.session.commit()

        july_booking = Booking(court_id=court.id, booking_date='2026-07-04', start_time='18:00', end_time='19:00', cost=20, status='completed')
        august_booking = Booking(court_id=court.id, booking_date='2026-08-04', start_time='18:00', end_time='19:00', cost=20, status='completed')
        db.session.add_all([july_booking, august_booking])
        db.session.commit()
        db.session.add_all([
            BookingParticipant(booking_id=july_booking.id, phone=user.phone, name=user.name, status='attending'),
            BookingParticipant(booking_id=august_booking.id, phone=user.phone, name=user.name, status='attending'),
        ])
        db.session.commit()
        july_id = july_booking.id
        august_id = august_booking.id
        token = jwt.encode(
            {'user_id': user.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    resp = client.get('/api/bookings?status=completed&month=2026-07&page=1&per_page=100', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    ids = {item['id'] for item in resp.get_json()['bookings']}
    assert july_id in ids
    assert august_id not in ids

    bad_resp = client.get('/api/bookings?status=completed&month=May-2026', headers={'Authorization': f'Bearer {token}'})
    assert bad_resp.status_code == 400
    assert bad_resp.get_json()['error'] == 'month must use YYYY-MM'


def test_completed_bookings_for_july_so_far_include_yesterday_and_ended_today(client, app, monkeypatch):
    from app import bookings as bookings_module

    class FixedDateTime(datetime):
        @classmethod
        def utcnow(cls):
            return cls(2026, 7, 3, 12, 0, 0)

    monkeypatch.setattr(bookings_module, 'datetime', FixedDateTime)

    with app.app_context():
        user = User(phone='+31100000920', email='july-so-far@example.com', name='July So Far', role='member')
        court = Court(name='July So Far Court', hourly_rate=20.0, is_active=True)
        db.session.add_all([user, court])
        db.session.commit()

        june_booking = Booking(court_id=court.id, booking_date='2026-06-30', start_time='18:00', end_time='19:00', cost=20, status='confirmed')
        july_first_booking = Booking(court_id=court.id, booking_date='2026-07-01', start_time='18:00', end_time='19:00', cost=20, status='confirmed')
        yesterday_booking = Booking(court_id=court.id, booking_date='2026-07-02', start_time='18:00', end_time='19:00', cost=20, status='confirmed')
        today_ended_booking = Booking(court_id=court.id, booking_date='2026-07-03', start_time='10:00', end_time='11:00', cost=20, status='confirmed')
        today_future_booking = Booking(court_id=court.id, booking_date='2026-07-03', start_time='13:00', end_time='14:00', cost=20, status='confirmed')
        future_booking = Booking(court_id=court.id, booking_date='2026-07-04', start_time='18:00', end_time='19:00', cost=20, status='confirmed')
        db.session.add_all([june_booking, july_first_booking, yesterday_booking, today_ended_booking, today_future_booking, future_booking])
        db.session.commit()

        token = jwt.encode(
            {'user_id': user.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )
        june_id = june_booking.id
        july_first_id = july_first_booking.id
        yesterday_id = yesterday_booking.id
        today_ended_id = today_ended_booking.id
        today_future_id = today_future_booking.id
        future_id = future_booking.id

    resp = client.get(
        '/api/bookings?status=completed&month=2026-07&page=1&per_page=100',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert resp.status_code == 200
    returned_ids = {booking['id'] for booking in resp.get_json()['bookings']}
    assert yesterday_id in returned_ids
    assert july_first_id in returned_ids
    assert today_ended_id in returned_ids
    assert today_future_id not in returned_ids
    assert future_id not in returned_ids
    assert june_id not in returned_ids

def test_openapi_and_swagger_docs_are_available(client):
    spec_resp = client.get('/api/openapi.json')
    assert spec_resp.status_code == 200
    spec = spec_resp.get_json()
    assert spec['openapi'] == '3.0.3'
    assert '/api/bookings' in spec['paths']
    assert '/api/admin/whatsapp-notifications' in spec['paths']
    assert '/api/admin/system-checks' in spec['paths']
    assert '/api/admin/system-checks/whatsapp-test' in spec['paths']

    swagger_resp = client.get('/api/swagger.json')
    assert swagger_resp.status_code == 200
    assert swagger_resp.get_json()['info']['title'] == 'Nieuwegein Badminton API'

    docs_resp = client.get('/api/docs')
    assert docs_resp.status_code == 200
    assert b'SwaggerUIBundle' in docs_resp.data

    missing_api_resp = client.get('/api/does-not-exist')
    assert missing_api_resp.status_code == 404
    assert missing_api_resp.get_json()['error'] == 'not_found'


def test_list_bookings_does_not_create_demo_upcoming_seed_data(client):
    from app import db
    from app.models import Booking, Court

    db.session.query(Booking).delete()
    db.session.query(Court).delete()
    db.session.commit()

    resp = client.get('/api/bookings')

    assert resp.status_code == 200
    assert resp.get_json()['bookings'] == []
    assert Booking.query.count() == 0
    assert Court.query.count() == 0


def test_yesterday_booking_moves_from_upcoming_to_completed(client, app):
    with app.app_context():
        user = User(phone='+31100000777', email='member777@example.com', name='Member 777', role='member')
        court = Court(name='Yesterday Court', hourly_rate=20.0, is_active=True)
        db.session.add_all([user, court])
        db.session.commit()
        yesterday = (datetime.utcnow() - timedelta(days=1)).date().strftime('%Y-%m-%d')
        booking = Booking(
            court_id=court.id,
            booking_date=yesterday,
            start_time='18:00',
            end_time='19:00',
            cost=20,
            status='confirmed',
        )
        db.session.add(booking)
        db.session.commit()
        booking_id = booking.id
        token = jwt.encode(
            {'user_id': user.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    upcoming_resp = client.get('/api/bookings?status=upcoming&page=1&per_page=100')
    assert upcoming_resp.status_code == 200
    assert all(item['id'] != booking_id for item in upcoming_resp.get_json()['bookings'])

    completed_resp = client.get('/api/bookings?status=completed&page=1&per_page=100', headers={'Authorization': f'Bearer {token}'})
    assert completed_resp.status_code == 200
    completed_bookings = completed_resp.get_json()['bookings']
    assert any(item['id'] == booking_id and item['status'] == 'completed' for item in completed_bookings)

    current_month = datetime.utcnow().strftime('%Y-%m')
    monthly_resp = client.get(
        f'/api/bookings?status=completed&month={current_month}&page=1&per_page=100',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert monthly_resp.status_code == 200
    monthly_bookings = monthly_resp.get_json()['bookings']
    assert any(item['id'] == booking_id and item['booking_date'] == yesterday for item in monthly_bookings)

    with app.app_context():
        assert Booking.query.get(booking_id).status == 'completed'


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
        august_booking = Booking(court_id=court.id, booking_date='2026-06-30', start_time='18:00', end_time='19:00', cost=20, status='completed')
        july_booking = Booking(court_id=court.id, booking_date='2026-07-01', start_time='18:00', end_time='19:00', cost=20, status='completed')
        db.session.add_all([august_booking, july_booking])
        db.session.commit()
        db.session.add(BookingParticipant(booking_id=august_booking.id, phone='archived-player', name='Archived Player', status='attending'))
        db.session.commit()
        participant_id = august_booking.participants[0].id
        token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )
        august_id = august_booking.id
        july_id = july_booking.id

    headers = {'Authorization': f'Bearer {token}'}
    archive_resp = client.get('/api/bookings?status=archive&page=1&per_page=10000', headers=headers)
    assert archive_resp.status_code == 200
    archive_dates = {booking['id']: booking['booking_date'] for booking in archive_resp.get_json()['bookings']}
    assert archive_dates[august_id] == '2026-06-30'
    assert july_id not in archive_dates

    completed_resp = client.get('/api/bookings?status=completed&page=1&per_page=10000', headers=headers)
    assert completed_resp.status_code == 200
    completed_dates = {booking['id']: booking['booking_date'] for booking in completed_resp.get_json()['bookings']}
    assert completed_dates[july_id] == '2026-07-01'
    assert august_id not in completed_dates

    update_resp = client.put(f'/api/bookings/{august_id}/participants/{participant_id}', json={
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


def test_admin_monthly_invoice_lists_family_and_name_matched_participants_once(client, app):
    with app.app_context():
        admin = User(phone='+31100001001', email='split-admin@example.com', name='Split Admin', role='admin')
        renjith = User(phone='+31100001002', email='renjith@example.com', name='Renjith R', role='member')
        court = Court(name='Split Court', hourly_rate=80.0, is_active=True)
        db.session.add_all([admin, renjith, court])
        db.session.commit()
        reema = FamilyMember(user_id=renjith.id, name='Reema', relationship='family')
        booking = Booking(court_id=court.id, booking_date='2026-07-03', start_time='19:30', end_time='20:30', cost=80, status='completed')
        db.session.add_all([reema, booking])
        db.session.commit()
        db.session.add_all([
            BookingParticipant(booking_id=booking.id, phone='Renjith', name='Renjith', status='participated', is_adhoc=True),
            BookingParticipant(booking_id=booking.id, phone='Reema', name='Reema', status='participated', is_adhoc=True),
            BookingParticipant(booking_id=booking.id, phone='Guest', name='Guest', status='participated', is_adhoc=True),
            BookingParticipant(booking_id=booking.id, phone='Skipped', name='Skipped', status='tentative', is_adhoc=True),
        ])
        db.session.commit()
        token = jwt.encode({'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)}, app.config['JWT_SECRET'], algorithm='HS256')

    resp = client.get('/api/admin/invoices/monthly?month=2026-07', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    invoices = {invoice['user']['name']: invoice for invoice in data['invoices']}
    assert invoices['Renjith R']['booking_total'] == 53.34
    assert 'Reema' not in invoices
    assert invoices['Guest']['booking_total'] == 26.67
    assert data['totals']['booking_total'] == 80.01


def test_current_user_monthly_invoice_deduplicates_name_matched_participant(client, app):
    with app.app_context():
        member = User(phone='+31100001003', email='renjith-current@example.com', name='Renjith R', role='member')
        court = Court(name='Current Split Court', hourly_rate=80.0, is_active=True)
        db.session.add_all([member, court])
        db.session.commit()
        booking = Booking(court_id=court.id, booking_date='2026-07-03', start_time='19:30', end_time='20:30', cost=40, status='completed')
        db.session.add(booking)
        db.session.commit()
        db.session.add_all([
            BookingParticipant(booking_id=booking.id, phone=member.phone, name='Renjith R', status='participated'),
            BookingParticipant(booking_id=booking.id, phone='Renjith', name='Renjith', status='participated', is_adhoc=True),
        ])
        db.session.commit()
        token = jwt.encode({'user_id': member.id, 'exp': datetime.utcnow() + timedelta(hours=2)}, app.config['JWT_SECRET'], algorithm='HS256')

    resp = client.get('/api/invoices/monthly?month=2026-07', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['booking_total'] == 20.0
    assert data['booking_items'][0]['attendee_count'] == 1
    assert data['booking_items'][0]['participants'] == ['Renjith R']


def test_deleted_court_is_hidden_from_active_list_and_booking_creation(client, app):
    with app.app_context():
        admin = User(phone='+31100001004', email='court-delete@example.com', name='Court Admin', role='admin')
        court = Court(name='Delete Me Court', hourly_rate=30.0, is_active=True)
        db.session.add_all([admin, court])
        db.session.commit()
        court_id = court.id
        token = jwt.encode({'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)}, app.config['JWT_SECRET'], algorithm='HS256')

    headers = {'Authorization': f'Bearer {token}'}
    delete_resp = client.delete(f'/api/admin/courts/{court_id}', headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.get_json()['is_active'] is False

    active_resp = client.get('/api/admin/courts?include_inactive=0', headers=headers)
    assert active_resp.status_code == 200
    assert court_id not in {court['id'] for court in active_resp.get_json()['courts']}

    booking_resp = client.post('/api/bookings', json={
        'court_id': court_id,
        'booking_date': '2030-01-01',
        'start_time': '18:00',
        'end_time': '19:00',
    }, headers=headers)
    assert booking_resp.status_code == 404


def test_api_responses_disable_cache_for_session_safety(client):
    resp = client.get('/api/health')
    assert resp.status_code == 200
    assert 'no-store' in resp.headers['Cache-Control']
    assert resp.headers['Pragma'] == 'no-cache'


def test_super_admin_generates_one_euro_test_payment_invoice_by_default(client, app, monkeypatch):
    from app import bookings as bookings_module

    payment_requests = []

    def fake_create_payment_request(settings, invoice):
        payment_requests.append({'amount': invoice.amount_due, 'reference': invoice.payment_reference})
        invoice.wise_payment_request_id = 'test-payment-request'
        return 'https://wise.example/pay/test'

    monkeypatch.setattr(bookings_module, '_wise_create_payment_request', fake_create_payment_request)

    with app.app_context():
        admin = User(phone='+31100009992', email='payment-admin@example.com', name='Payment Admin', role='super_admin')
        settings = PaymentSettings(wise_api_token='token', wise_profile_id='profile-1', test_mode=True)
        db.session.add_all([admin, settings])
        db.session.commit()
        token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    resp = client.post('/api/admin/payment-invoices/test', json={'amount': 17.50}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 201
    payload = resp.get_json()
    assert payload['is_test_invoice'] is True
    assert payload['amount_due'] == 1.0
    assert payment_requests == [{'amount': 1.0, 'reference': payload['payment_reference']}]

    with app.app_context():
        invoice = PaymentInvoice.query.filter_by(is_test_invoice=True).one()
        assert invoice.amount_due == 1.0


def test_admin_previews_edits_and_tests_monthly_invoice_notification(client, app, monkeypatch):
    from app import bookings as bookings_module

    sent = []
    monkeypatch.setattr(bookings_module, '_send_whatsapp_bot_message', lambda message, recipient=None: sent.append({'message': message, 'recipient': recipient}) or ('sent', 'ok'))

    with app.app_context():
        admin = User(phone='+31100009995', email='monthly-notify-admin@example.com', name='Monthly Notify Admin', role='admin')
        setting = WhatsAppNotificationSetting(
            event_key='monthly_invoice_ready',
            title='Monthly invoices ready',
            template='Invoices for {{month}}: {{note}} {{app_url}}',
            is_enabled=True,
            send_to_group=True,
            group_id='group-monthly',
            test_recipient_number='+31 6 2222 3333',
        )
        db.session.add_all([admin, setting])
        db.session.commit()
        token = jwt.encode({'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)}, app.config['JWT_SECRET'], algorithm='HS256')

    headers = {'Authorization': f'Bearer {token}'}
    preview_resp = client.post('/api/admin/payment-invoices/monthly/notify/preview', json={'month': '2030-04'}, headers=headers)
    assert preview_resp.status_code == 200
    preview = preview_resp.get_json()
    assert '2030-04' in preview['message']
    assert preview['recipient'] == 'group-monthly'
    assert preview['test_recipients'][0]['normalized'] == '31622223333@c.us'

    test_resp = client.post('/api/admin/payment-invoices/monthly/notify', json={
        'month': '2030-04',
        'message': 'Edited monthly invoice notification',
        'test': True,
        'recipient': '+31 6 2222 3333',
    }, headers=headers)
    assert test_resp.status_code == 200
    assert sent[-1] == {'message': 'Edited monthly invoice notification', 'recipient': '31622223333@c.us'}

    send_resp = client.post('/api/admin/payment-invoices/monthly/notify', json={
        'month': '2030-04',
        'message': 'Final monthly invoice notification',
    }, headers=headers)
    assert send_resp.status_code == 200
    assert sent[-1] == {'message': 'Final monthly invoice notification', 'recipient': 'group-monthly'}


def test_wise_transfer_state_webhook_matches_invoice_reference_after_error_retry(client, app, monkeypatch):
    from app import bookings as bookings_module

    class FakeResponse:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = ''
            self.content = b'{}'

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise AssertionError(f'unexpected status {self.status_code}')

    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)
        if url.endswith('/v1/transfers/2238838788'):
            return FakeResponse(200, {
                'id': 2238838788,
                'business': 84642112,
                'targetAccount': 1358290420,
                'status': 'outgoing_payment_sent',
                'reference': 'INV-2026-00039',
                'details': {'reference': 'INV-2026-00039'},
                'sourceCurrency': 'EUR',
                'sourceValue': 1.0,
                'targetCurrency': 'EUR',
                'targetValue': 1.0,
            })
        return FakeResponse(404)

    monkeypatch.setattr(bookings_module.requests, 'get', fake_get)

    payload = {
        'data': {
            'resource': {
                'id': 2238838788,
                'profile_id': 84642112,
                'account_id': 1358290420,
                'type': 'transfer',
            },
            'current_state': 'incoming_payment_waiting',
            'previous_state': None,
            'occurred_at': '2026-07-08T21:59:49Z',
        },
        'subscription_id': 'sub-1',
        'event_type': 'transfers#state-change',
        'schema_version': '2.0.0',
        'sent_at': '2026-07-08T21:59:49Z',
    }

    with app.app_context():
        admin = User(phone='+31100009993', email='wise-webhook@example.com', name='Wise Webhook', role='super_admin')
        settings = PaymentSettings(wise_api_token='token', wise_profile_id='84642112', wise_webhook_subscription_id='sub-1')
        invoice = PaymentInvoice(
            user=admin,
            invoice_number='INV-2026-00039',
            payment_reference='INV-2026-00039',
            amount_due=1.0,
            payment_status='UNPAID',
            is_test_invoice=True,
        )
        errored_event = WiseWebhookEvent(
            event_type='transfers#state-change',
            subscription_id='sub-1',
            incoming_transfer_id='2238838788',
            payload_json='{}',
            status='ERROR',
            error_message='404 Client Error',
        )
        db.session.add_all([admin, settings, invoice, errored_event])
        db.session.commit()

    resp = client.post('/api/webhooks/wise/incoming-transfer', json=payload)
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'matched'
    assert any(url.endswith('/v1/transfers/2238838788') for url in calls)

    with app.app_context():
        invoice = PaymentInvoice.query.filter_by(invoice_number='INV-2026-00039').one()
        event = WiseWebhookEvent.query.filter_by(incoming_transfer_id='2238838788').one()
        assert invoice.payment_status == 'PAID'
        assert invoice.paid_amount == 1.0
        assert event.status == 'MATCHED'
        assert event.invoice_id == invoice.id
        assert event.amount == 1.0
        assert event.reference == 'INV-2026-00039'


def test_wise_webhook_retry_links_already_paid_invoice_without_double_counting(client, app, monkeypatch):
    from app import bookings as bookings_module

    class FakeResponse:
        status_code = 200
        text = ''
        content = b'{}'

        def json(self):
            return {
                'id': 2238838788,
                'reference': 'INV-2026-00039',
                'sourceCurrency': 'EUR',
                'sourceValue': 1.0,
            }

        def raise_for_status(self):
            pass

    monkeypatch.setattr(bookings_module.requests, 'get', lambda *args, **kwargs: FakeResponse())

    with app.app_context():
        admin = User(phone='+31100009994', email='wise-paid@example.com', name='Wise Paid', role='super_admin')
        settings = PaymentSettings(wise_api_token='token', wise_profile_id='84642112', wise_webhook_subscription_id='sub-1')
        invoice = PaymentInvoice(
            user=admin,
            invoice_number='INV-2026-00039',
            payment_reference='INV-2026-00039',
            amount_due=1.0,
            paid_amount=1.0,
            payment_status='PAID',
            is_test_invoice=True,
        )
        event = WiseWebhookEvent(
            event_type='transfers#state-change',
            subscription_id='sub-1',
            incoming_transfer_id='2238838788',
            payload_json='{}',
            status='UNMATCHED',
            reference='INV-2026-00039',
            error_message='No invoice reference matched this incoming transfer (INV-2026-00039).',
        )
        db.session.add_all([admin, settings, invoice, event])
        db.session.commit()
        event_id = event.id
        token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    headers = {'Authorization': f'Bearer {token}'}
    resp = client.post(f'/api/admin/wise-webhook-events/{event_id}/retry', headers=headers)

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['status'] == 'matched'
    assert payload['invoice']['invoice_number'] == 'INV-2026-00039'

    with app.app_context():
        invoice = PaymentInvoice.query.filter_by(invoice_number='INV-2026-00039').one()
        event = WiseWebhookEvent.query.filter_by(incoming_transfer_id='2238838788').one()
        assert invoice.payment_status == 'PAID'
        assert invoice.paid_amount == 1.0
        assert event.status == 'MATCHED'
        assert event.invoice_id == invoice.id
        assert event.error_message is None


def test_admin_can_save_test_whatsapp_number_and_send_direct_test(client, app, monkeypatch):
    from app import bookings as bookings_module

    sent = []

    def fake_send(message, recipient=None):
        sent.append({'message': message, 'recipient': recipient})
        return 'sent', 'ok'

    monkeypatch.setattr(bookings_module, '_send_whatsapp_bot_message', fake_send)

    with app.app_context():
        admin = User(phone='+31100009991', email='whatsapp-admin@example.com', name='WhatsApp Admin', role='admin')
        db.session.add(admin)
        db.session.commit()
        token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    headers = {'Authorization': f'Bearer {token}'}
    list_resp = client.get('/api/admin/whatsapp-notifications', headers=headers)
    assert list_resp.status_code == 200
    setting_id = next(item['id'] for item in list_resp.get_json()['settings'] if item['event_key'] == 'booking_created')
    update_resp = client.put(
        f'/api/admin/whatsapp-notifications/{setting_id}',
        json={'test_recipient_number': '+31 6 1234 5678'},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.get_json()['test_recipient_number'] == '+31 6 1234 5678'

    test_resp = client.post(
        f'/api/admin/whatsapp-notifications/{setting_id}/test',
        json={},
        headers=headers,
    )
    assert test_resp.status_code == 200
    payload = test_resp.get_json()
    assert payload['log']['status'] == 'sent'
    assert payload['log']['recipient'] == '31612345678@c.us'
    assert sent[-1]['recipient'] == '31612345678@c.us'
    assert 'Sample court' in sent[-1]['message']


def test_admin_can_run_whatsapp_connection_test_from_system_checks(client, app, monkeypatch):
    from app import bookings as bookings_module

    sent = []

    def fake_send(message, recipient=None):
        sent.append({'message': message, 'recipient': recipient})
        return 'sent', 'ok'

    monkeypatch.setattr(bookings_module, '_send_whatsapp_bot_message', fake_send)

    with app.app_context():
        admin = User(phone='+31100009994', email='system-check-admin@example.com', name='System Check Admin', role='admin')
        db.session.add(admin)
        db.session.commit()
        token = jwt.encode(
            {'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)},
            app.config['JWT_SECRET'],
            algorithm='HS256',
        )

    headers = {'Authorization': f'Bearer {token}'}
    list_resp = client.get('/api/admin/whatsapp-notifications', headers=headers)
    setting_id = next(item['id'] for item in list_resp.get_json()['settings'] if item['event_key'] == 'booking_created')
    update_resp = client.put(
        f'/api/admin/whatsapp-notifications/{setting_id}',
        json={'test_recipient_number': '+31 6 1111 2222'},
        headers=headers,
    )
    assert update_resp.status_code == 200

    test_resp = client.post('/api/admin/system-checks/whatsapp-test', json={}, headers=headers)
    assert test_resp.status_code == 200
    payload = test_resp.get_json()
    assert payload['status'] == 'sent'
    assert payload['recipient'] == '31611112222@c.us'
    assert payload['log']['event_key'] == 'connection_test'
    assert sent[-1]['recipient'] == '31611112222@c.us'

    checks_resp = client.get('/api/admin/system-checks', headers=headers)
    assert checks_resp.status_code == 200
    checks_payload = checks_resp.get_json()
    assert checks_payload['whatsapp']['default_test_recipient'] == '+31 6 1111 2222'
    assert checks_payload['whatsapp']['last_test_log']['recipient'] == '31611112222@c.us'


def test_wise_webhook_records_concise_error_when_wise_dns_fails(client, app, monkeypatch):
    from app import bookings as bookings_module

    def fake_get(url, headers=None, timeout=None):
        raise bookings_module.requests.exceptions.ConnectionError(
            "HTTPSConnectionPool(host='api.wise.com', port=443): Max retries exceeded with url: /v1/transfers/2238838788 "
            "(Caused by NameResolutionError(\"HTTPSConnection(host='api.wise.com', port=443): Failed to resolve 'api.wise.com'\"))"
        )

    monkeypatch.setattr(bookings_module.requests, 'get', fake_get)

    payload = {
        'data': {'resource': {'id': 2238838788, 'type': 'transfer'}},
        'subscription_id': 'sub-1',
        'event_type': 'transfers#state-change',
    }

    with app.app_context():
        settings = PaymentSettings(wise_api_token='token', wise_profile_id='84642112', wise_webhook_subscription_id='sub-1')
        db.session.add(settings)
        db.session.commit()

    resp = client.post('/api/webhooks/wise/incoming-transfer', json=payload)

    assert resp.status_code == 202
    data = resp.get_json()
    assert data['status'] == 'error'
    assert data['event']['status'] == 'ERROR'
    assert data['event']['error_message'] == 'Wise API is unreachable due to a network or DNS connection error. Retry once DNS/network connectivity is restored.'

    with app.app_context():
        event = WiseWebhookEvent.query.filter_by(incoming_transfer_id='2238838788').one()
        assert event.error_message == data['event']['error_message']


def test_only_super_admin_can_grant_super_admin_role(client, app):
    with app.app_context():
        admin = User(phone='+31100000100', email='role-admin@example.com', name='Role Admin', role='admin')
        super_admin = User(phone='+31100000101', email='role-super@example.com', name='Role Super', role='super_admin')
        member = User(phone='+31100000102', email='role-member@example.com', name='Role Member', role='member')
        db.session.add_all([admin, super_admin, member])
        db.session.commit()
        admin_token = jwt.encode({'user_id': admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)}, app.config['JWT_SECRET'], algorithm='HS256')
        super_token = jwt.encode({'user_id': super_admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)}, app.config['JWT_SECRET'], algorithm='HS256')
        member_id = member.id

    admin_headers = {'Authorization': f'Bearer {admin_token}'}
    super_headers = {'Authorization': f'Bearer {super_token}'}

    denied_resp = client.put(f'/api/admin/users/{member_id}', json={'role': 'super_admin'}, headers=admin_headers)
    assert denied_resp.status_code == 403
    assert denied_resp.get_json()['error'] == 'super_admin_required_for_role_changes'

    allowed_resp = client.put(f'/api/admin/users/{member_id}', json={'role': 'super_admin'}, headers=super_headers)
    assert allowed_resp.status_code == 200
    assert allowed_resp.get_json()['role'] == 'super_admin'


def test_super_admin_payment_settings_schema_matches_frontend(client, app):
    with app.app_context():
        super_admin = User(phone='+31100000103', email='payment-super@example.com', name='Payment Super', role='super_admin')
        db.session.add(super_admin)
        db.session.add(PaymentSettings(
            account_holder_name='Club Treasurer',
            bank_name='Club Bank',
            iban='NL02ABNA0123456789',
            bic='ABNANL2A',
            wise_api_token='secret-token',
            wise_profile_id='12345',
            wise_api_base_url='https://api.wise.com',
            wise_redirect_url='https://example.test/my-invoices',
            wise_client_key='client-key',
            wise_webhook_url='https://example.test/api/webhooks/wise/incoming-transfer',
            description_prefix='Club Invoice',
            default_due_days=21,
            qr_enabled=True,
            test_mode=False,
        ))
        db.session.commit()
        token = jwt.encode({'user_id': super_admin.id, 'exp': datetime.utcnow() + timedelta(hours=2)}, app.config['JWT_SECRET'], algorithm='HS256')

    resp = client.get('/api/admin/payment-settings', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    expected_fields = {
        'id', 'account_holder_name', 'bank_name', 'iban', 'bic', 'payment_provider',
        'wise_payment_url', 'wise_profile_id', 'wise_api_base_url', 'wise_redirect_url',
        'wise_client_key', 'wise_webhook_url', 'wise_webhook_subscription_id',
        'wise_api_token_configured', 'description_prefix', 'default_due_days', 'qr_enabled',
        'test_mode', 'created_at', 'updated_at', 'updated_by', 'effective_account_holder_name',
        'effective_bank_name', 'effective_iban', 'effective_bic',
    }
    assert expected_fields.issubset(data.keys())
    assert 'wise_api_token' not in data
    assert data['wise_api_token_configured'] is True
    assert isinstance(data['default_due_days'], int)
    assert isinstance(data['qr_enabled'], bool)
    assert isinstance(data['test_mode'], bool)
