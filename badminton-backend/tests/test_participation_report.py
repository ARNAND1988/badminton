import csv
import io
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import jwt
import pytest
from app import db
from app.models import Booking, BookingParticipant, Court, FamilyMember, PaymentInvoice, User
from app.participation import build_report


@pytest.fixture
def ledger(app):
    with app.app_context():
        owner = User(phone='owner', name='Owner', role='admin')
        linked = User(phone='linked', name='Linked')
        other = User(phone='other', name='Other')
        zero = User(phone='zero', name='Zero')
        court = Court(name='Report court')
        db.session.add_all([owner, linked, other, zero, court])
        db.session.flush()
        family = FamilyMember(user_id=owner.id, linked_user_id=linked.id, name='Linked')
        child = FamilyMember(user_id=owner.id, name='Child')
        db.session.add_all([family, child])
        db.session.flush()

        def booking(date, phones, status='completed', cost=30, end='19:00'):
            b = Booking(court_id=court.id, booking_date=date, start_time='18:00', end_time=end, status=status, cost=cost)
            db.session.add(b)
            db.session.flush()
            for phone, attendance in phones:
                db.session.add(BookingParticipant(booking_id=b.id, phone=phone, name=phone, status=attendance))
            db.session.flush()
            return b

        archived = booking('2020-01-02', [('owner', 'participated'), ('linked', 'attending'), (f'family:{family.id}', 'participated')])
        partial = booking('2020-02-03', [('owner', 'participated'), (f'family:{child.id}', 'participated')], cost=20)
        later = booking('2020-02-04', [('owner', 'participated')], cost=12)
        unpaid = booking('2020-03-01', [('owner', 'participated')], cost=7)
        booking('2020-04-01', [('other', 'tentative'), ('owner', 'not_attending')])
        booking('2020-04-02', [('owner', 'participated')], status='cancelled')
        booking('2099-01-01', [('owner', 'participated')], status='settled')
        booking('2020-05-01', [('guest:1', 'attending')], cost=9)
        for index, (b, amount, paid, state, misc) in enumerate([
            (archived, 30, 30, 'PAID', 0), (partial, 20, 15, 'PARTIALLY_PAID', 10), (unpaid, 7, 0, 'UNPAID', 0)
        ]):
            db.session.add(PaymentInvoice(user_id=owner.id, month=b.booking_date[:7], invoice_number=f'R{index}', payment_reference=f'REF{index}',
                amount_due=amount + misc, paid_amount=paid, payment_status=state,
                booking_items_json=json.dumps([{'booking_id': b.id, 'amount': amount}]), misc_items_json=json.dumps([{'amount': misc}])))
        db.session.commit()
        return {'owner': owner.id, 'linked': linked.id, 'child': child.id, 'later': later.id,
                'token': jwt.encode({'user_id': owner.id}, app.config['JWT_SECRET'], algorithm='HS256'),
                'member_token': jwt.encode({'user_id': other.id}, app.config['JWT_SECRET'], algorithm='HS256')}


def test_linked_people_archived_exclusions_and_financials(app, ledger):
    with app.app_context():
        result = build_report({})
        people = {p['name']: p for p in result['people']}
        assert people['Owner']['sessions'] == 4
        assert people['Linked']['sessions'] == 1
        assert people['Linked']['court_cost'] == 15
        assert people['Zero']['sessions'] == 0
        assert people['Other']['sessions'] == 0
        assert people['Child']['court_cost'] == 10
        assert people['Child']['paid_amount'] == 5
        family = next(f for f in result['families'] if f['id'] == f"user:{ledger['owner']}")
        assert family['sessions'] == 4
        assert family['appearances'] == 6
        assert family['court_cost'] == 69
        assert family['paid_amount'] == 40
        assert family['balance'] == 29
        assert family['payment_statuses'] == ['invoiced_unpaid', 'not_invoiced', 'paid', 'partial']
        assert any(p['name'] == 'guest:1' for p in result['people'])


def test_partial_allocation_is_stable_and_snapshot_excludes_later_booking(app, ledger):
    with app.app_context():
        report = build_report({'start': '2020-02-03', 'end': '2020-02-03', 'status': 'partial', 'view': 'family'})
        assert report['people'] == []
        assert report['families'][0]['paid_amount'] == 10  # 15 / (20 court + 10 misc)
        report = build_report({'start': '2020-02-04', 'end': '2020-02-04', 'status': 'not_invoiced'})
        assert report['families'][0]['court_cost'] == 12
        assert report['families'][0]['paid_amount'] == 0
        assert build_report({'status': 'invoiced_unpaid'})['families'][0]['balance'] == 7


def test_admin_only_and_single_family_csv(client, ledger):
    url = '/api/admin/reports/participation'
    assert client.get(url).status_code == 401
    assert client.get(url, headers={'Authorization': f"Bearer {ledger['member_token']}"}).status_code == 403
    headers = {'Authorization': f"Bearer {ledger['token']}"}
    fid = f"user:{ledger['owner']}"
    response = client.get(url, query_string={'family': fid, 'format': 'csv', 'view': 'both'}, headers=headers)
    assert response.status_code == 200
    assert 'attachment' in response.headers['Content-Disposition']
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert {r['Family ID'] for r in rows} == {fid}
    assert {r['View'] for r in rows} == {'Person', 'Family'}
    assert {r['Name'] for r in rows} == {'Owner', 'Linked', 'Child'}
    assert client.get(url + '?start=invalid', headers=headers).status_code == 400
    assert client.get(url + '?start=2021-01-01&end=2020-01-01', headers=headers).status_code == 400
    assert client.get(url + '?status=bad', headers=headers).status_code == 400
    assert client.get(url + '?family=unknown', headers=headers).status_code == 400


def test_amsterdam_cutoff_and_read_only(app, ledger):
    with app.app_context():
        b = Booking(court_id=Court.query.first().id, booking_date='2020-06-01', start_time='18:00', end_time='19:00', cost=11, status='confirmed')
        db.session.add(b)
        db.session.flush()
        db.session.add(BookingParticipant(booking_id=b.id, phone='owner', status='attending'))
        db.session.commit()
        before = (Booking.query.count(), PaymentInvoice.query.count())
        args = {'start': '2020-06-01', 'end': '2020-06-01', 'family': f"user:{ledger['owner']}"}
        assert build_report(args, datetime(2020, 6, 1, 18, 59, tzinfo=ZoneInfo('Europe/Amsterdam')))['families'][0]['sessions'] == 0
        assert build_report(args, datetime(2020, 6, 1, 17, 0, tzinfo=ZoneInfo('UTC')))['families'][0]['sessions'] == 1
        assert b.status == 'confirmed'
        assert (Booking.query.count(), PaymentInvoice.query.count()) == before
        assert not db.session.dirty


def test_rounding_and_empty_snapshot(app, ledger):
    with app.app_context():
        invoice = PaymentInvoice.query.filter_by(month='2020-02').one()
        invoice.booking_items_json = '[]'
        db.session.commit()
        result = build_report({'start': '2020-02-03', 'end': '2020-02-03', 'status': 'not_invoiced'})
        assert result['families'][0]['paid_amount'] == 0
        from app.participation import apportion
        assert apportion(1, [1, 1, 1]) == [1, 0, 0]
        assert apportion(10, [7, 7, 7]) == [4, 3, 3]


def test_guest_invoice_and_full_invoice_rounding(app, ledger):
    with app.app_context():
        guest_booking = Booking.query.filter_by(booking_date='2020-05-01').one()
        db.session.add(PaymentInvoice(subject_key='adhoc:guest1', billing_name='guest:1', month='2020-05',
            invoice_number='GUEST', payment_reference='GUEST', amount_due=12, paid_amount=1,
            payment_status='PARTIALLY_PAID', booking_items_json=json.dumps([{'booking_id': guest_booking.id, 'amount': 9}]),
            misc_items_json=json.dumps([{'amount': 3}])))
        db.session.commit()
        row = build_report({'start': '2020-05-01', 'end': '2020-05-01', 'status': 'partial'})['people'][0]
        assert row['court_cost'] == 9
        assert row['paid_amount'] == 0.75
        assert row['balance'] == 8.25


def test_legacy_invoice_and_test_invoice_exclusion(app, ledger):
    with app.app_context():
        invoice = PaymentInvoice.query.filter_by(month='2020-02').one()
        invoice.booking_items_json = None
        invoice.created_at = datetime(2021, 1, 1)
        for booking in Booking.query.filter(Booking.booking_date.like('2020-02%')).all():
            booking.created_at = datetime(2020, 1, 1) if booking.id != ledger['later'] else datetime(2022, 1, 1)
        invoice.is_test_invoice = True
        db.session.commit()
        result = build_report({'start': '2020-02-03', 'end': '2020-02-03', 'status': 'not_invoiced'})
        assert result['families'][0]['paid_amount'] == 0
        invoice.is_test_invoice = False
        db.session.commit()
        result = build_report({'start': '2020-02-03', 'end': '2020-02-03', 'status': 'partial'})
        assert result['families'][0]['paid_amount'] == 10
        result = build_report({'start': '2020-02-04', 'end': '2020-02-04', 'status': 'not_invoiced'})
        assert result['families'][0]['paid_amount'] == 0
