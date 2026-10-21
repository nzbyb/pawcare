from datetime import date, timedelta

from tests.test_boarding import create_draft, create_kennel, day
from tests.test_pets import create_pet


def test_handover_sheet_gathers_pet_health_and_owner(
    client, admin_headers, owner_headers, staff_headers, other_owner_headers
):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    draft = create_draft(
        client, owner_headers, pet["id"], kennel["id"], day(20), day(22)
    ).json()["data"]
    order = client.post(
        f"/api/boarding/drafts/{draft['id']}/confirm",
        headers=owner_headers,
        json={"idempotency_key": draft["idempotency_key"]},
    ).json()["data"]

    due = (date.today() + timedelta(days=5)).isoformat()
    client.post(
        f"/api/pets/{pet['id']}/health-records",
        headers=owner_headers,
        json={
            "record_type": "vaccine",
            "title": "狂犬疫苗",
            "record_date": date.today().isoformat(),
            "next_due_date": due,
            "note": "年度加强针",
        },
    )
    client.post(
        f"/api/pets/{pet['id']}/weights",
        headers=owner_headers,
        json={"record_date": date.today().isoformat(), "weight_kg": 12.4},
    )

    body = client.get(
        f"/api/boarding/orders/{order['id']}/handover", headers=owner_headers
    ).json()
    assert body["code"] == 200
    data = body["data"]

    assert data["order"]["id"] == order["id"]
    assert data["order"]["kennel_code"] == kennel["code"]
    assert data["pet"]["name"] == pet["name"]
    assert data["pet"]["allergies"] == "鸡肉"
    assert data["pet"]["latest_weight"] == 12.4
    assert data["owner"]["email"].endswith("@example.com")
    assert data["health_records"][0]["title"] == "狂犬疫苗"
    assert data["reminders"][0]["due_date"] == due
    assert data["generated_at"]

    # 寄养员需要按交接单核对宠物状态，也应能查看。
    staff_view = client.get(
        f"/api/boarding/orders/{order['id']}/handover", headers=staff_headers
    )
    assert staff_view.json()["code"] == 200

    denied = client.get(
        f"/api/boarding/orders/{order['id']}/handover",
        headers=other_owner_headers,
    )
    assert denied.json()["code"] == 403
