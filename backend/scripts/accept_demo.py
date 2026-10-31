"""Exercise real HTTP endpoints with four demo accounts, only on the isolated mock server."""
import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx

BASE = 'http://127.0.0.1:8001'
RESULT = Path(__file__).resolve().parents[1] / 'demo-data' / 'acceptance.json'


def main():
    evidence = []
    client = httpx.Client(base_url=BASE, timeout=15)

    def call(role, method, path, expected=200, **kwargs):
        body = client.request(method, path, headers={'Authorization': 'Bearer ' + tokens[role]}, **kwargs).json()
        assert body['code'] == expected, (role, path, body.get('message'))
        evidence.append({'role': role, 'method': method, 'path': path, 'code': body['code']})
        return body.get('data')

    tokens = {}
    for username, password in [('owner', 'Owner12345'), ('owner2', 'Owner12345'), ('staff', 'Staff12345'), ('admin', 'Admin12345')]:
        body = client.post('/api/auth/login', json={'username': username, 'password': password}).json()
        assert body['code'] == 200
        tokens[username] = body['data']['token']
    baseline = call('admin', 'GET', '/api/admin/statistics', params={'days': 7})
    marker = 'acceptance-' + uuid4().hex[:10]
    today = date.today()

    def reserve(offset):
        start, end = str(today + timedelta(days=offset)), str(today + timedelta(days=offset + 1))
        rooms = call('owner', 'GET', '/api/kennels/availability', params={'start_date': start, 'end_date': end})
        assert rooms
        draft = call('owner', 'POST', '/api/boarding/drafts', json={'pet_id': 1, 'kennel_id': rooms[0]['id'],
            'start_date': start, 'end_date': end, 'note': marker})
        call('owner2', 'GET', f"/api/boarding/drafts/{draft['id']}", expected=403)
        order = call('owner', 'POST', f"/api/boarding/drafts/{draft['id']}/confirm", json={'idempotency_key': draft['idempotency_key']})
        assert order['deposit'] == 0
        return order

    def pay(order):
        payment = call('owner', 'POST', '/api/payments', json={'order_id': order['id']})
        assert payment['channel'] == 'mock', 'Only the isolated mock environment can run this script'
        token = parse_qs(urlparse(payment['qr_content']).query)['token'][0]
        for _ in range(2):
            result = client.post('/api/payments/mock/notify', json={'payment_no': payment['payment_no'], 'token': token}).json()
            assert result['code'] == 200 and result['data']['status'] == 'paid'
        evidence.append({'step': 'mock_payment_duplicate', 'order_id': order['id'], 'paid_amount': payment['amount']})

    order = reserve(0)
    oid = order['id']
    call('owner', 'POST', f'/api/boarding/orders/{oid}/confirm', expected=403)
    call('staff', 'POST', f'/api/boarding/orders/{oid}/confirm')
    call('staff', 'POST', f'/api/boarding/orders/{oid}/check-in', expected=409)
    pay(order)
    checked = call('staff', 'POST', f'/api/boarding/orders/{oid}/check-in')
    assert checked['status'] == 'checked_in'
    call('owner', 'POST', f'/api/boarding/orders/{oid}/reports', expected=403, json={'report_date': str(today)})
    call('staff', 'POST', f'/api/boarding/orders/{oid}/reports', expected=400, json={'report_date': str(today + timedelta(days=1))})
    report = call('staff', 'POST', f'/api/boarding/orders/{oid}/reports', json={'report_date': str(today),
        'appetite': 'good', 'stool': 'normal', 'spirit': 'good', 'note': '独立环境验收日报：正常进食与活动。'})
    reports = call('owner', 'GET', f'/api/boarding/orders/{oid}/reports')
    assert report['id'] in {r['id'] for r in reports}
    call('owner2', 'GET', f'/api/boarding/orders/{oid}', expected=403)
    call('owner', 'POST', f'/api/boarding/orders/{oid}/check-out', expected=403)
    handover = call('owner', 'GET', f'/api/boarding/orders/{oid}/handover')
    assert handover
    finished = call('staff', 'POST', f'/api/boarding/orders/{oid}/check-out')
    assert finished['status'] == 'completed' and finished['checked_out_at']

    cancel_order = reserve(1)
    pay(cancel_order)
    cancelled = call('owner', 'POST', f"/api/boarding/orders/{cancel_order['id']}/cancel")
    refund = cancelled['refund']
    assert refund['status'] == 'requested' and cancelled['status'] == 'cancelled'
    for role in ('owner', 'staff'):
        call(role, 'POST', f"/api/payments/refunds/{refund['id']}/process", expected=403)
    call('owner2', 'POST', f"/api/payments/refunds/orders/{cancel_order['id']}", expected=403)
    for _ in range(2):
        processed = call('admin', 'POST', f"/api/payments/refunds/{refund['id']}/process")
        assert processed['status'] == 'succeeded' and processed['refund_no'] == refund['refund_no']
    final = call('owner', 'GET', f"/api/boarding/orders/{cancel_order['id']}")
    assert final['payment_status'] == 'refunded' and final['refunded_amount'] == final['paid_amount']
    stats = call('admin', 'GET', '/api/admin/statistics', params={'days': 7})
    assert round(stats['received'] - baseline['received'], 2) == round(order['total_amount'] + cancel_order['total_amount'], 2)
    assert round(stats['refunded'] - baseline['refunded'], 2) == cancel_order['total_amount']
    assert stats['net'] == round(stats['received'] - stats['refunded'], 2)
    call('owner', 'GET', '/api/admin/statistics', expected=403)
    RESULT.parent.mkdir(exist_ok=True)
    RESULT.write_text(json.dumps({'date': str(today), 'base': BASE, 'passed': True,
        'completed_order': oid, 'refunded_order': cancel_order['id'], 'checks': evidence}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'PASS: {len(evidence)} checks; completed order #{oid}, refunded order #{cancel_order["id"]}')
    print(RESULT)
    client.close()


if __name__ == '__main__':
    main()
