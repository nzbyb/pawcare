from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from sqlalchemy.orm.attributes import set_committed_value

from app.database import SessionLocal
from app.models.payment import PaymentOrder
from app.services import payment_service
from tests.test_boarding import create_draft, create_kennel, day
from tests.test_pets import create_pet


def make_order(client, owner_headers, admin_headers, offset: int = 30) -> dict:
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    start, end = day(offset), day(offset + 2)
    draft = create_draft(
        client, owner_headers, pet["id"], kennel["id"], start, end
    ).json()["data"]
    resp = client.post(
        f"/api/boarding/drafts/{draft['id']}/confirm",
        headers=owner_headers,
        json={"idempotency_key": draft["idempotency_key"]},
    )
    body = resp.json()
    assert body["code"] == 200, resp.text
    return body["data"]


def create_payment(client, headers, order_id: int):
    return client.post("/api/payments", headers=headers, json={"order_id": order_id})


def token_of(payment: dict) -> str:
    query = parse_qs(urlparse(payment["qr_content"]).query)
    return query["token"][0]


def test_create_payment_and_reuse(
    client, owner_headers, admin_headers
):
    order = make_order(client, owner_headers, admin_headers)
    assert order["payment_status"] == "unpaid"

    resp = create_payment(client, owner_headers, order["id"])
    body = resp.json()
    assert body["code"] == 200, resp.text
    payment = body["data"]
    assert payment["channel"] == "mock"
    assert payment["status"] == "created"
    assert payment["amount"] == order["total_amount"]
    assert payment["qr_content"].startswith("http://localhost:5173/pay/")
    assert len(token_of(payment)) >= 20

    # 未过期的支付单复用，不重复生成二维码。
    again = create_payment(client, owner_headers, order["id"]).json()["data"]
    assert again["payment_no"] == payment["payment_no"]

    detail = client.get(
        f"/api/payments/{payment['payment_no']}", headers=owner_headers
    ).json()
    assert detail["code"] == 200
    assert detail["data"]["payment_no"] == payment["payment_no"]


def test_payment_permissions(client, owner_headers, admin_headers, other_owner_headers):
    order = make_order(client, owner_headers, admin_headers)

    resp = create_payment(client, other_owner_headers, order["id"])
    assert resp.json()["code"] == 403

    resp = client.get("/api/payments/PAY-NOT-EXIST", headers=owner_headers)
    assert resp.json()["code"] == 404

    payment = create_payment(client, owner_headers, order["id"]).json()["data"]
    resp = client.get(
        f"/api/payments/{payment['payment_no']}", headers=other_owner_headers
    )
    assert resp.json()["code"] == 403

    # 管理员可以查看支付单，但不能替用户发起支付。
    resp = client.get(
        f"/api/payments/{payment['payment_no']}", headers=admin_headers
    )
    assert resp.json()["code"] == 200


def test_staff_cannot_pay(client, owner_headers, admin_headers, staff_headers):
    order = make_order(client, owner_headers, admin_headers)
    resp = create_payment(client, staff_headers, order["id"])
    assert resp.json()["code"] == 403


def test_mock_scan_and_notify(client, owner_headers, admin_headers):
    order = make_order(client, owner_headers, admin_headers)
    payment = create_payment(client, owner_headers, order["id"]).json()["data"]
    token = token_of(payment)

    # 二维码页：凭证错误返回 403，不泄露支付单细节。
    resp = client.get(f"/api/payments/mock/{payment['payment_no']}", params={"token": "x" * 20})
    assert resp.json()["code"] == 403

    resp = client.get(
        f"/api/payments/mock/{payment['payment_no']}", params={"token": token}
    )
    body = resp.json()
    assert body["code"] == 200
    assert body["data"]["amount"] == payment["amount"]
    assert "owner_id" not in body["data"]

    # 回调凭证错误不能入账。
    resp = client.post(
        "/api/payments/mock/notify",
        json={"payment_no": payment["payment_no"], "token": "y" * 20},
    )
    assert resp.json()["code"] == 403

    resp = client.post(
        "/api/payments/mock/notify",
        json={"payment_no": payment["payment_no"], "token": token},
    )
    body = resp.json()
    assert body["code"] == 200, resp.text
    assert body["data"]["status"] == "paid"

    detail = client.get(
        f"/api/boarding/orders/{order['id']}", headers=owner_headers
    ).json()["data"]
    assert detail["payment_status"] == "paid"
    assert detail["paid_amount"] == order["total_amount"]

    # 重复回调幂等，不再改订单。
    resp = client.post(
        "/api/payments/mock/notify",
        json={"payment_no": payment["payment_no"], "token": token},
    )
    assert resp.json()["code"] == 200

    # 已支付订单不能再发起支付。
    resp = create_payment(client, owner_headers, order["id"])
    assert resp.json()["code"] == 409


def test_expired_payment_cannot_be_paid(client, owner_headers, admin_headers, db):
    order = make_order(client, owner_headers, admin_headers)
    payment = create_payment(client, owner_headers, order["id"]).json()["data"]
    token = token_of(payment)

    row = (
        db.query(PaymentOrder)
        .filter(PaymentOrder.payment_no == payment["payment_no"])
        .first()
    )
    row.expires_at = datetime.now() - timedelta(seconds=1)
    db.commit()

    resp = client.post(
        "/api/payments/mock/notify",
        json={"payment_no": payment["payment_no"], "token": token},
    )
    assert resp.json()["code"] == 409

    detail = client.get(
        f"/api/payments/{payment['payment_no']}", headers=owner_headers
    ).json()["data"]
    assert detail["status"] == "closed"

    # 过期后可以重新发起，生成新的支付单。
    renewed = create_payment(client, owner_headers, order["id"]).json()["data"]
    assert renewed["payment_no"] != payment["payment_no"]
    assert renewed["status"] == "created"


def test_cancelled_order_cannot_pay(client, owner_headers, admin_headers):
    order = make_order(client, owner_headers, admin_headers)
    resp = client.post(
        f"/api/boarding/orders/{order['id']}/cancel", headers=owner_headers
    )
    assert resp.json()["code"] == 200

    resp = create_payment(client, owner_headers, order["id"])
    assert resp.json()["code"] == 409


def test_settle_paid_twice_keeps_payment_paid(
    client, owner_headers, admin_headers, db
):
    """重复核销同一张支付单，不能把它从 paid 改成 closed。"""
    order = make_order(client, owner_headers, admin_headers)
    payment = create_payment(client, owner_headers, order["id"]).json()["data"]
    token = token_of(payment)
    paid = client.post(
        "/api/payments/mock/notify",
        json={"payment_no": payment["payment_no"], "token": token},
    ).json()["data"]
    assert paid["status"] == "paid"

    db.expire_all()
    row = (
        db.query(PaymentOrder)
        .filter(PaymentOrder.payment_no == payment["payment_no"])
        .one()
    )
    # 模拟并发下第二次核销（异步通知与主动查单撞在一起）。
    payment_service._settle_paid(
        db, row, transaction_id="MOCK-DUP", payload={"source": "dup"}
    )
    db.commit()
    db.refresh(row)
    assert row.status == "paid"


def test_locked_read_refreshes_stale_payment_snapshot(
    client, owner_headers, admin_headers, db
):
    """锁行读取必须覆盖会话里缓存的旧状态，否则会重复核销。"""
    order = make_order(client, owner_headers, admin_headers)
    payment = create_payment(client, owner_headers, order["id"]).json()["data"]
    token = token_of(payment)

    other = SessionLocal()
    try:
        payment_service.mock_notify(other, payment["payment_no"], token)
    finally:
        other.close()

    db.commit()
    stale = (
        db.query(PaymentOrder)
        .filter(PaymentOrder.payment_no == payment["payment_no"])
        .one()
    )
    assert stale.status == "paid"
    # 伪造并发请求里读到的旧快照：只改内存，不标记为待写库。
    set_committed_value(stale, "status", "created")

    locked = payment_service._get_payment(db, payment["payment_no"])
    assert locked.status == "paid"
