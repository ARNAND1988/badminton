"""Read-only participation ledger. Allocate money before applying report filters."""
import csv
import io
import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from flask import Response, jsonify, request
from .bookings import bookings_bp, _require_admin, _family_owner_for_user, _normalize_person_name
from .models import Booking, FamilyMember, PaymentInvoice, User, rounded_up_cost_split


def cents(value):
    return int((Decimal(str(value or 0)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def apportion(total, weights):
    """Stable largest-remainder allocation, in cents, with deterministic ties."""
    denominator = sum(weights)
    if not denominator:
        return [0] * len(weights)
    result = [total * weight // denominator for weight in weights]
    order = sorted(range(len(weights)), key=lambda i: (-(total * weights[i] % denominator), i))
    for i in order[:total - sum(result)]:
        result[i] += 1
    return result


def build_report(args, now=None):
    now = now or datetime.now(ZoneInfo('Europe/Amsterdam'))
    start, end = args.get('start', ''), args.get('end', '')
    for value in (start, end):
        if value:
            if datetime.strptime(value, '%Y-%m-%d').strftime('%Y-%m-%d') != value:
                raise ValueError('Dates must use YYYY-MM-DD')
    if start and end and start > end:
        raise ValueError('Start date must be on or before end date')
    status = args.get('status', 'all')
    view = args.get('view', 'both')
    if status not in {'all', 'paid', 'partial', 'invoiced_unpaid', 'not_invoiced'} or view not in {'person', 'family', 'both'}:
        raise ValueError('Invalid status or view')
    people, keys, families = {}, {}, {}
    users = User.query.order_by(User.id).all()
    for user in users:
        owner = _family_owner_for_user(user)
        fid = f'user:{owner.id}'
        families[fid] = owner.name or owner.email or owner.phone
        pid = f'user:{user.id}'
        people[pid] = {'id': pid, 'name': user.name or user.email or user.phone, 'family_id': fid}
        keys[user.phone] = pid
    for member in FamilyMember.query.order_by(FamilyMember.id).all():
        pid = f'user:{member.linked_user_id}' if member.linked_user_id else f'family:{member.id}'
        keys[f'family:{member.id}'] = pid
        if pid not in people:
            people[pid] = {'id': pid, 'name': member.name, 'family_id': people[f'user:{member.user_id}']['family_id']}

    charges = []
    for booking in Booking.query.order_by(Booking.booking_date, Booking.id).all():
        # Past confirmed bookings are logically completed without mutating them.
        ended = datetime.strptime(f'{booking.booking_date} {booking.end_time}', '%Y-%m-%d %H:%M').replace(tzinfo=ZoneInfo('Europe/Amsterdam'))
        if booking.status == 'cancelled' or ended > now:
            continue
        attendees = {}
        for participant in sorted(booking.participants, key=lambda p: p.id):
            if participant.status not in {'attending', 'participated'}:
                continue
            pid = keys.get(participant.phone)
            if not pid:
                pid = f'guest:{participant.phone or participant.id}'
                if pid not in people:
                    people[pid] = {'id': pid, 'name': participant.name or participant.phone, 'family_id': pid}
                    families[pid] = people[pid]['name']
            attendees[pid] = participant
        split = rounded_up_cost_split(booking.cost, len(attendees))
        for pid, amount in zip(attendees, split['participant_shares']):
            charges.append({'person_id': pid, 'family_id': people[pid]['family_id'], 'booking_id': booking.id,
                            'date': booking.booking_date, 'created_at': booking.created_at,
                            'cost': cents(amount), 'paid': 0, 'invoiced': False})

    # A stored empty snapshot is authoritative, unlike a legacy NULL snapshot.
    for invoice in PaymentInvoice.query.filter_by(is_test_invoice=False).order_by(PaymentInvoice.created_at.desc(), PaymentInvoice.id.desc()).all():
        fid = people.get(f'user:{invoice.user_id}', {}).get('family_id') or invoice.subject_key
        if fid not in families and invoice.billing_name:
            matches = [key for key, name in families.items() if key.startswith('guest:') and _normalize_person_name(name) == _normalize_person_name(invoice.billing_name)]
            fid = matches[0] if len(matches) == 1 else fid
        candidates = [c for c in charges if c['family_id'] == fid and not c['invoiced'] and c['date'][:7] == invoice.month]
        if invoice.booking_items_json is not None:
            items = json.loads(invoice.booking_items_json or '[]')
        else:
            # Legacy invoices lack snapshots; never attach bookings created later.
            by_booking = defaultdict(int)
            for charge in candidates:
                if charge['created_at'] <= invoice.created_at:
                    by_booking[charge['booking_id']] += charge['cost']
            items = [{'booking_id': bid, 'amount': amount / 100} for bid, amount in by_booking.items()]
        due = max(0, cents(invoice.amount_due))
        paid = due if invoice.payment_status == 'PAID' else min(due, max(0, cents(invoice.paid_amount)))
        # Include misc and any other invoice charges in the denominator.
        weights = [max(0, cents(item.get('amount'))) for item in items]
        allocation = apportion(paid, weights + [max(0, due - sum(weights))])
        for item, line_paid in zip(items, allocation):
            matching = [c for c in candidates if c['booking_id'] == item.get('booking_id') and not c['invoiced']]
            if not matching:
                continue
            line_cost = max(0, cents(item.get('amount')))
            costs = apportion(line_cost, [c['cost'] for c in matching])
            payments = apportion(min(line_cost, line_paid), costs)
            for charge, cost, payment in zip(matching, costs, payments):
                charge.update(cost=cost, paid=payment, invoiced=True)

    for charge in charges:
        charge['status'] = ('paid' if charge['paid'] >= charge['cost'] else 'partial' if charge['paid'] else 'invoiced_unpaid') if charge['invoiced'] else 'not_invoiced'
    selected_family = args.get('family', '')
    if selected_family and selected_family not in families:
        raise ValueError('Unknown family')
    filtered = [c for c in charges if (not start or c['date'] >= start) and (not end or c['date'] <= end)
                and (not selected_family or c['family_id'] == selected_family) and (status == 'all' or c['status'] == status)]

    def rows(kind):
        output = []
        for key, person in people.items() if kind == 'person' else ((fid, {'name': name, 'family_id': fid}) for fid, name in families.items()):
            if selected_family and person['family_id'] != selected_family:
                continue
            subset = [c for c in filtered if c['person_id' if kind == 'person' else 'family_id'] == key]
            if not subset and status != 'all':
                continue
            cost, paid = sum(c['cost'] for c in subset), sum(c['paid'] for c in subset)
            output.append({'id': key, 'name': person['name'], 'family_id': person['family_id'],
                           'sessions': len({c['booking_id'] for c in subset}), 'appearances': len(subset),
                           'court_cost': cost / 100, 'paid_amount': paid / 100, 'balance': (cost - paid) / 100,
                           'payment_statuses': sorted({c['status'] for c in subset})})
        return sorted(output, key=lambda row: (row['name'].casefold(), row['id']))
    return {'people': rows('person') if view != 'family' else [], 'families': rows('family') if view != 'person' else [],
            'family_options': [{'id': key, 'name': name} for key, name in families.items()],
            'timezone': 'Europe/Amsterdam', 'through': now.isoformat()}


@bookings_bp.route('/admin/reports/participation', methods=['GET'])
def participation_report():
    _, error = _require_admin()
    if error:
        return error
    try:
        report = build_report(request.args)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    if request.args.get('format') != 'csv':
        response = jsonify(report)
        response.headers['Cache-Control'] = 'no-store'
        return response
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['View', 'ID', 'Name', 'Family ID', 'Sessions played', 'Player appearances', 'Court cost EUR', 'Paid EUR', 'Outstanding EUR', 'Payment statuses'])
    for kind, rows in [('Person', report['people']), ('Family', report['families'])]:
        for row in rows:
            # Prevent spreadsheet formulas in user-controlled labels.
            name = row['name']
            if name.startswith(('=', '+', '-', '@', '\t', '\r')):
                name = "'" + name
            writer.writerow([kind, row['id'], name, row['family_id'], row['sessions'], row['appearances'],
                             f"{row['court_cost']:.2f}", f"{row['paid_amount']:.2f}", f"{row['balance']:.2f}", ', '.join(row['payment_statuses'])])
    return Response(stream.getvalue(), mimetype='text/csv', headers={
        'Content-Disposition': 'attachment; filename="participation-report.csv"', 'Cache-Control': 'no-store'})
