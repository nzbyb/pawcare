from datetime import date, datetime, timedelta
from uuid import uuid4

from app.models.boarding import BoardingDraft
from tests.test_pets import create_pet


def day(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def create_kennel(
    client, headers, code: str | None = None, size: str = "medium", price: float = 88
):
    code = code or f"K-{uuid4().hex[:8].upper()}"
    resp = client.post(
        "/api/kennels",
        headers=headers,
        json={"code": code, "size": size, "daily_price": price, "note": "测试笼舍"},
    )
    body = resp.json()
    assert body["code"] == 200, resp.text
    return body["data"]


def create_draft(
    client,
    headers,
    pet_id: int,
    kennel_id: int,
    start: str,
    end: str,
    idempotency_key: str | None = None,
):
    payload = {
        "pet_id": pet_id,
        "kennel_id": kennel_id,
        "start_date": start,
        "end_date": end,
        "note": "测试预约",
    }
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key
    return client.post("/api/boarding/drafts", headers=headers, json=payload)


def pay_order(client, headers, order_id: int):
    from urllib.parse import parse_qs, urlparse

    payment = client.post("/api/payments", headers=headers, json={"order_id": order_id}).json()["data"]
    token = parse_qs(urlparse(payment["qr_content"]).query)["token"][0]
    response = client.post("/api/payments/mock/notify", json={"payment_no": payment["payment_no"], "token": token})
    assert response.json()["code"] == 200, response.text


def test_kennel_admin_only_crud(client, admin_headers, owner_headers, staff_headers):
    resp = client.post(
        "/api/kennels",
        headers=owner_headers,
        json={"code": f"K-{uuid4().hex[:6]}", "size": "small", "daily_price": 60},
    )
    assert resp.json()["code"] == 403

    resp = client.post(
        "/api/kennels",
        headers=staff_headers,
        json={"code": f"K-{uuid4().hex[:6]}", "size": "small", "daily_price": 60},
    )
    assert resp.json()["code"] == 403

    kennel = create_kennel(client, admin_headers, size="small", price=60)
    assert kennel["code"].startswith("K-")

    resp = client.post(
        "/api/kennels",
        headers=admin_headers,
        json={"code": kennel["code"], "size": "small", "daily_price": 60},
    )
    assert resp.json()["code"] == 400

    resp = client.put(
        f"/api/kennels/{kennel['id']}",
        headers=admin_headers,
        json={"daily_price": 66},
    )
    assert resp.json()["data"]["daily_price"] == 66

    resp = client.get("/api/kennels", headers=owner_headers)
    assert resp.json()["code"] == 200
    assert any(item["id"] == kennel["id"] for item in resp.json()["data"])


def test_availability_and_draft_confirm(
    client, admin_headers, owner_headers, db
):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)

    start, end = day(20), day(23)
    draft_resp = create_draft(
        client, owner_headers, pet["id"], kennel["id"], start, end
    )
    draft = draft_resp.json()["data"]
    assert draft["status"] == "pending"
    assert draft["nights"] == 3
    assert draft["total_amount"] == 264
    assert draft["pet_name"] == pet["name"]
    assert draft["kennel_code"] == kennel["code"]

    # 草稿本身不占档期
    resp = client.get(
        "/api/kennels/availability",
        headers=owner_headers,
        params={"start_date": start, "end_date": end},
    )
    assert any(item["id"] == kennel["id"] for item in resp.json()["data"])

    confirm_resp = client.post(
        f"/api/boarding/drafts/{draft['id']}/confirm",
        headers=owner_headers,
        json={"idempotency_key": draft["idempotency_key"]},
    )
    order = confirm_resp.json()["data"]
    assert confirm_resp.json()["code"] == 200
    assert order["status"] == "pending"
    assert order["draft_id"] == draft["id"]
    assert order["deposit"] == 0  # 新订单统一全款，保留字段兼容历史数据。

    # 订单落库后，重叠档期不再可用；半开区间边界仍可用
    resp = client.get(
        "/api/kennels/availability",
        headers=owner_headers,
        params={"start_date": day(21), "end_date": day(22)},
    )
    assert all(item["id"] != kennel["id"] for item in resp.json()["data"])

    resp = client.get(
        "/api/kennels/availability",
        headers=owner_headers,
        params={"start_date": end, "end_date": day(25)},
    )
    assert any(item["id"] == kennel["id"] for item in resp.json()["data"])

    # 重复确认返回同一笔订单
    again = client.post(
        f"/api/boarding/drafts/{draft['id']}/confirm",
        headers=owner_headers,
        json={"idempotency_key": draft["idempotency_key"]},
    )
    assert again.json()["data"]["id"] == order["id"]

    orders = client.get("/api/boarding/orders", headers=owner_headers).json()["data"]
    assert len(orders) == 1


def test_draft_idempotency_key_reuses_draft(client, admin_headers, owner_headers):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    key = uuid4().hex

    first = create_draft(
        client, owner_headers, pet["id"], kennel["id"], day(30), day(32), key
    ).json()["data"]
    second = create_draft(
        client, owner_headers, pet["id"], kennel["id"], day(30), day(32), key
    ).json()["data"]
    assert first["id"] == second["id"]

    other_pet = create_pet(client, owner_headers, name="年糕").json()["data"]
    resp = create_draft(
        client, owner_headers, other_pet["id"], kennel["id"], day(30), day(32), key
    )
    # 幂等键只能对应同一组参数，避免把 A 的草稿当成 B 的返回值
    assert resp.json()["code"] == 409


def test_draft_ownership_and_expiry(
    client, admin_headers, owner_headers, other_owner_headers, staff_headers, db
):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    draft = create_draft(
        client, owner_headers, pet["id"], kennel["id"], day(35), day(37)
    ).json()["data"]

    resp = client.get(
        f"/api/boarding/drafts/{draft['id']}", headers=other_owner_headers
    )
    assert resp.json()["code"] == 403

    resp = client.post(
        f"/api/boarding/drafts/{draft['id']}/confirm",
        headers=other_owner_headers,
        json={"idempotency_key": draft["idempotency_key"]},
    )
    assert resp.json()["code"] == 403

    resp = create_draft(
        client,
        other_owner_headers,
        pet["id"],
        kennel["id"],
        day(35),
        day(37),
    )
    assert resp.json()["code"] == 403

    # 寄养员不能创建草稿
    resp = create_draft(
        client,
        staff_headers,
        pet["id"],
        kennel["id"],
        day(35),
        day(37),
    )
    assert resp.json()["code"] == 403

    # 手动把草稿改成已过期
    db.query(BoardingDraft).filter(BoardingDraft.id == draft["id"]).update(
        {"expires_at": datetime.now() - timedelta(minutes=1)}
    )
    db.commit()
    db.expire_all()

    resp = client.post(
        f"/api/boarding/drafts/{draft['id']}/confirm",
        headers=owner_headers,
        json={"idempotency_key": draft["idempotency_key"]},
    )
    assert resp.json()["code"] == 409

    resp = client.get(f"/api/boarding/drafts/{draft['id']}", headers=owner_headers)
    assert resp.json()["data"]["status"] == "expired"


def test_confirm_rechecks_conflicting_draft(
    client, admin_headers, owner_headers
):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)

    first = create_draft(
        client, owner_headers, pet["id"], kennel["id"], day(40), day(43)
    ).json()["data"]
    second = create_draft(
        client, owner_headers, pet["id"], kennel["id"], day(42), day(45)
    ).json()["data"]

    resp = client.post(
        f"/api/boarding/drafts/{first['id']}/confirm",
        headers=owner_headers,
        json={"idempotency_key": first["idempotency_key"]},
    )
    assert resp.json()["code"] == 200

    resp = client.post(
        f"/api/boarding/drafts/{second['id']}/confirm",
        headers=owner_headers,
        json={"idempotency_key": second["idempotency_key"]},
    )
    assert resp.json()["code"] == 409

    orders = client.get("/api/boarding/orders", headers=owner_headers).json()["data"]
    assert len(orders) == 1


def test_staff_workflow_and_daily_reports(
    client, admin_headers, owner_headers, staff_headers, other_owner_headers
):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    draft = create_draft(
        client, owner_headers, pet["id"], kennel["id"], day(0), day(3)
    ).json()["data"]

    order = client.post(
        f"/api/boarding/drafts/{draft['id']}/confirm",
        headers=owner_headers,
        json={"idempotency_key": draft["idempotency_key"]},
    ).json()["data"]

    resp = client.get(
        f"/api/boarding/orders/{order['id']}", headers=other_owner_headers
    )
    assert resp.json()["code"] == 403

    resp = client.post(
        f"/api/boarding/orders/{order['id']}/confirm", headers=owner_headers
    )
    assert resp.json()["code"] == 403

    resp = client.post(
        f"/api/boarding/orders/{order['id']}/confirm", headers=staff_headers
    )
    confirmed = resp.json()["data"]
    assert confirmed["status"] == "confirmed"
    assert confirmed["confirmed_at"] is not None

    pay_order(client, owner_headers, order["id"])

    resp = client.post(
        f"/api/boarding/orders/{order['id']}/check-in", headers=staff_headers
    )
    assert resp.json()["data"]["status"] == "checked_in"

    kennels = client.get("/api/kennels", headers=staff_headers).json()["data"]
    current = next(item for item in kennels if item["id"] == kennel["id"])
    assert current["status"] == "occupied"

    report_payload = {
        "report_date": day(0),
        "appetite": "good",
        "stool": "normal",
        "spirit": "good",
        "note": "今天胃口很好",
        "photos": ["/uploads/report/demo.png"],
    }
    resp = client.post(
        f"/api/boarding/orders/{order['id']}/reports",
        headers=staff_headers,
        json=report_payload,
    )
    assert resp.json()["code"] == 200

    resp = client.post(
        f"/api/boarding/orders/{order['id']}/reports",
        headers=staff_headers,
        json=report_payload,
    )
    assert resp.json()["code"] == 409

    resp = client.post(
        f"/api/boarding/orders/{order['id']}/reports",
        headers=owner_headers,
        json={**report_payload, "report_date": day(2)},
    )
    assert resp.json()["code"] == 403

    resp = client.post(
        f"/api/boarding/orders/{order['id']}/reports",
        headers=staff_headers,
        json={
            **report_payload,
            "report_date": day(2),
            "photos": ["https://example.com/tracker.png"],
        },
    )
    assert resp.json()["code"] == 400

    reports = client.get(
        f"/api/boarding/orders/{order['id']}/reports", headers=owner_headers
    ).json()["data"]
    assert len(reports) == 1
    assert reports[0]["note"] == "今天胃口很好"
    assert reports[0]["photos"] == ["/uploads/report/demo.png"]

    resp = client.post(
        f"/api/boarding/orders/{order['id']}/check-out", headers=staff_headers
    )
    assert resp.json()["data"]["status"] == "completed"

    kennels = client.get("/api/kennels", headers=staff_headers).json()["data"]
    current = next(item for item in kennels if item["id"] == kennel["id"])
    assert current["status"] == "available"

    resp = client.post(
        f"/api/boarding/orders/{order['id']}/cancel", headers=owner_headers
    )
    assert resp.json()["code"] == 409


def test_cancel_draft_and_order_frees_slot(
    client, admin_headers, owner_headers, staff_headers
):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)

    draft = create_draft(
        client, owner_headers, pet["id"], kennel["id"], day(60), day(62)
    ).json()["data"]

    resp = client.delete(
        f"/api/boarding/drafts/{draft['id']}", headers=owner_headers
    )
    assert resp.json()["code"] == 200

    resp = client.post(
        f"/api/boarding/drafts/{draft['id']}/confirm",
        headers=owner_headers,
        json={"idempotency_key": draft["idempotency_key"]},
    )
    assert resp.json()["code"] == 409

    draft2 = create_draft(
        client, owner_headers, pet["id"], kennel["id"], day(60), day(62)
    ).json()["data"]
    order = client.post(
        f"/api/boarding/drafts/{draft2['id']}/confirm",
        headers=owner_headers,
        json={"idempotency_key": draft2["idempotency_key"]},
    ).json()["data"]

    resp = client.post(
        f"/api/boarding/orders/{order['id']}/cancel", headers=owner_headers
    )
    assert resp.json()["data"]["status"] == "cancelled"

    # 取消后档期释放
    resp = client.get(
        "/api/kennels/availability",
        headers=owner_headers,
        params={"start_date": day(60), "end_date": day(62)},
    )
    assert any(item["id"] == kennel["id"] for item in resp.json()["data"])


def test_invalid_period_rejected(client, admin_headers, owner_headers):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)

    resp = create_draft(
        client, owner_headers, pet["id"], kennel["id"], day(70), day(70)
    )
    assert resp.json()["code"] == 400

    resp = create_draft(
        client, owner_headers, pet["id"], kennel["id"], day(72), day(70)
    )
    assert resp.json()["code"] == 400

    resp = client.get(
        "/api/kennels/availability",
        headers=owner_headers,
        params={"start_date": day(70), "end_date": day(70)},
    )
    assert resp.json()["code"] == 400
