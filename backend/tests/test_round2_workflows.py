from datetime import date, datetime, timedelta

import pytest

from app.models.audit import AuditLog
from app.models.boarding import BoardingOrder
from app.models.payment import PaymentOrder
from app.models.refund import RefundOrder
from app.payments import alipay
from app.services import payment_service
from tests.test_boarding import create_draft, create_kennel, day, pay_order
from tests.test_boarding_readiness import reserve
from tests.test_payments import create_payment, make_order, token_of
from tests.test_pets import create_pet
from tests.test_alipay_payment import alipay_env, _sign_bytes


def detail(client, headers, order):
    return client.get(f"/api/boarding/orders/{order['id']}", headers=headers).json()["data"]


def test_overdue_stay_blocks_kennel_pet_and_remains_in_daily_tasks(
    client, owner_headers, admin_headers, staff_headers, db,
):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    order = reserve(client, owner_headers, pet, kennel)
    row = db.get(BoardingOrder, order["id"])
    row.start_date = date.today() - timedelta(days=5)
    row.end_date = date.today() - timedelta(days=2)
    row.checked_in_at = datetime.now() - timedelta(days=5)
    row.status = "checked_in"
    db.commit()

    occupancy = client.get("/api/admin/kennels/occupancy", headers=admin_headers).json()["data"]
    card = next(item for item in occupancy["items"] if item["id"] == kennel["id"])
    assert card["display_status"] == "occupied"
    assert card["occupancy"]["overdue"] is True
    available = client.get("/api/kennels/availability", headers=owner_headers,
                           params={"start_date": day(1), "end_date": day(3)}).json()["data"]
    assert kennel["id"] not in {item["id"] for item in available}
    other_pet = create_pet(client, owner_headers).json()["data"]
    assert create_draft(client, owner_headers, other_pet["id"], kennel["id"], day(1), day(3)).json()["code"] == 409
    other_kennel = create_kennel(client, admin_headers)
    assert create_draft(client, owner_headers, pet["id"], other_kennel["id"], day(1), day(3)).json()["code"] == 409
    tasks = client.get("/api/boarding/tasks/today", headers=staff_headers).json()["data"]
    assert order["id"] in {item["order_id"] for item in tasks["missing_reports"]}
    assert order["id"] in {item["order_id"] for item in tasks["departures"]}
    report = client.post(f"/api/boarding/orders/{order['id']}/reports", headers=staff_headers,
                         json={"report_date": day(0), "appetite": "poor"}).json()
    assert report["code"] == 200, report
    tasks = client.get("/api/boarding/tasks/today", headers=staff_headers).json()["data"]
    assert order["id"] not in {item["order_id"] for item in tasks["missing_reports"]}
    assert order["id"] in {item["order_id"] for item in tasks["abnormal_reports"]}
    assert client.post(f"/api/boarding/orders/{order['id']}/reports", headers=staff_headers,
                       json={"report_date": day(1)}).json()["code"] == 400
    client.post(f"/api/boarding/orders/{order['id']}/check-out", headers=staff_headers)
    assert create_draft(client, owner_headers, pet["id"], kennel["id"], day(1), day(3)).json()["code"] == 200


def test_confirm_rechecks_newly_overdue_stay(client, owner_headers, admin_headers, db):
    pet1 = create_pet(client, owner_headers).json()["data"]
    pet2 = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    occupied = reserve(client, owner_headers, pet1, kennel, start=0, end=1)
    draft = create_draft(client, owner_headers, pet2["id"], kennel["id"], day(2), day(4)).json()["data"]
    row = db.get(BoardingOrder, occupied["id"])
    row.status = "boarding"
    row.start_date = date.today() - timedelta(days=3)
    row.end_date = date.today() - timedelta(days=1)
    db.commit()
    assert client.post(f"/api/boarding/drafts/{draft['id']}/confirm", headers=owner_headers,
                       json={"idempotency_key": draft["idempotency_key"]}).json()["code"] == 409


def test_refund_full_flow_permissions_and_idempotency(
    client, owner_headers, other_owner_headers, staff_headers, admin_headers, db,
):
    order = make_order(client, owner_headers, admin_headers)
    pay_order(client, owner_headers, order["id"])
    assert client.post(f"/api/payments/refunds/orders/{order['id']}", headers=owner_headers).json()["code"] == 409
    cancelled = client.post(f"/api/boarding/orders/{order['id']}/cancel", headers=owner_headers).json()["data"]
    refund = cancelled["refund"]
    assert refund["status"] == "requested" and refund["amount"] == order["total_amount"]
    assert cancelled["payment_status"] == "paid" and cancelled["refunded_amount"] == 0
    for headers in (staff_headers, other_owner_headers):
        assert client.post(f"/api/payments/refunds/orders/{order['id']}", headers=headers).json()["code"] == 403
    assert client.post(f"/api/payments/refunds/orders/{order['id']}", headers=owner_headers).json()["data"]["id"] == refund["id"]
    for headers in (owner_headers, staff_headers):
        assert client.post(f"/api/payments/refunds/{refund['id']}/process", headers=headers).json()["code"] == 403
    processed = client.post(f"/api/payments/refunds/{refund['id']}/process", headers=admin_headers).json()
    assert processed["data"]["status"] == "succeeded", processed
    assert client.post(f"/api/payments/refunds/{refund['id']}/process", headers=admin_headers).json()["data"]["status"] == "succeeded"
    updated = detail(client, owner_headers, order)
    assert updated["payment_status"] == "refunded"
    assert updated["refunded_amount"] == updated["paid_amount"] == order["total_amount"]
    assert db.query(RefundOrder).filter(RefundOrder.order_id == order["id"]).count() == 1
    assert db.query(AuditLog).filter(AuditLog.action == "refund.succeeded", AuditLog.target_id == refund["id"]).count() == 1
    stats = client.get("/api/admin/statistics", headers=admin_headers, params={"days": 7}).json()["data"]
    assert len(stats["daily"]) == 7
    assert stats["refunded"] >= order["total_amount"]
    assert stats["net"] == round(stats["received"] - stats["refunded"], 2)
    revenue = client.get("/api/admin/overview", headers=admin_headers).json()["data"]["revenue"]
    assert revenue["net_total"] == round(revenue["paid_total"] - revenue["refunded_total"], 2)
    assert client.get("/api/admin/statistics", headers=owner_headers).json()["code"] == 403
    assert client.get("/api/admin/statistics", headers=admin_headers, params={"days": 999}).json()["code"] == 400


def test_late_payment_after_cancel_is_recorded_and_queued(client, owner_headers, admin_headers):
    order = make_order(client, owner_headers, admin_headers)
    payment = create_payment(client, owner_headers, order["id"]).json()["data"]
    client.post(f"/api/boarding/orders/{order['id']}/cancel", headers=owner_headers)
    result = client.post('/api/payments/mock/notify', json={"payment_no": payment["payment_no"], "token": token_of(payment)}).json()
    assert result["data"]["status"] == "paid"
    updated = detail(client, owner_headers, order)
    assert updated["status"] == "cancelled" and updated["refund"]["status"] == "requested"
    assert updated["paid_amount"] == order["total_amount"]


def test_refund_channel_failure_retries_same_number(client, owner_headers, admin_headers, db, monkeypatch):
    order = make_order(client, owner_headers, admin_headers)
    pay_order(client, owner_headers, order["id"])
    cancelled = client.post(f"/api/boarding/orders/{order['id']}/cancel", headers=owner_headers).json()["data"]
    refund = cancelled["refund"]
    payment = db.query(PaymentOrder).filter(PaymentOrder.order_id == order["id"], PaymentOrder.status == "paid").one()
    payment.channel = "alipay"
    db.commit()
    monkeypatch.setattr(payment_service, "_alipay_config", lambda: ("app", "private", "public", "gateway"))
    calls = []
    def channel(**kwargs):
        calls.append(kwargs["out_request_no"])
        if len(calls) == 1:
            raise alipay.AlipayError("timeout")
        return {"code": "10000"}
    monkeypatch.setattr(alipay, "refund_trade", channel)
    first = client.post(f"/api/payments/refunds/{refund['id']}/process", headers=admin_headers).json()["data"]
    assert first["status"] == "failed"
    assert detail(client, owner_headers, order)["payment_status"] == "paid"
    second = client.post(f"/api/payments/refunds/{refund['id']}/process", headers=admin_headers).json()["data"]
    assert second["status"] == "succeeded" and second["error"] is None
    assert calls == [refund["refund_no"], refund["refund_no"]]


@pytest.mark.parametrize('variant', ['valid', 'tampered', 'wrong_amount', 'wrong_trade', 'rejected'])
def test_alipay_refund_checks_signed_channel_result(alipay_env, monkeypatch, variant):
    import json
    import httpx
    from app.config import settings
    node = {"code": "10000", "out_trade_no": "PAY-TEST", "refund_fee": "88.00", "fund_change": "Y"}
    if variant == 'wrong_amount':
        node['refund_fee'] = '8.00'
    if variant == 'wrong_trade':
        node['out_trade_no'] = 'OTHER-TRADE'
    if variant == 'rejected':
        node['code'] = '40004'
    raw = json.dumps(node, separators=(',', ':')).encode()
    signature = _sign_bytes(raw, alipay_env['alipay']['private_pem'])
    if variant == 'tampered':
        raw = raw.replace(b'88.00', b'99.00')
    content = b'{"alipay_trade_refund_response":' + raw + b',"sign":' + json.dumps(signature).encode() + b'}'
    def post(url, *, data, timeout):
        from urllib.parse import parse_qs, urlsplit
        assert parse_qs(urlsplit(url).query)['charset'] == ['utf-8']
        encoded = httpx.Request('POST', url, data=data).content.decode('ascii')
        decoded = {key: values[0] for key, values in parse_qs(encoded, encoding='utf-8').items()}
        assert alipay.verify_params(decoded, alipay_env['app']['public_pem'])
        assert json.loads(decoded['biz_content'])['refund_reason'] == '已取消寄养订单全额退款'
        assert data['method'] == 'alipay.trade.refund'
        biz = json.loads(data['biz_content'])
        assert biz['out_request_no'] == 'REFUND-FIXED-KEY'
        assert biz['refund_amount'] == '88.00'
        return httpx.Response(200, content=content, request=httpx.Request('POST', url))
    monkeypatch.setattr(alipay.httpx, 'post', post)
    args = dict(app_id=settings.ALIPAY_APP_ID, private_key=settings.ALIPAY_PRIVATE_KEY,
                public_key=settings.ALIPAY_PUBLIC_KEY, gateway=settings.ALIPAY_GATEWAY,
                out_trade_no='PAY-TEST', out_request_no='REFUND-FIXED-KEY', amount='88.00')
    if variant == 'valid':
        assert alipay.refund_trade(**args)['code'] == '10000'
    else:
        with pytest.raises(alipay.AlipayError):
            alipay.refund_trade(**args)
