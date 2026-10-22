from datetime import date, timedelta

from tests.test_boarding import create_draft, create_kennel, day
from tests.test_pets import create_pet


def list_notifications(client, headers, **params):
    body = client.get("/api/notifications", headers=headers, params=params).json()
    assert body["code"] == 200, body
    return body["data"]


def test_due_health_reminder_becomes_notification(client, owner_headers):
    pet = create_pet(client, owner_headers).json()["data"]
    due = (date.today() + timedelta(days=3)).isoformat()
    client.post(
        f"/api/pets/{pet['id']}/health-records",
        headers=owner_headers,
        json={
            "record_type": "vaccine",
            "title": "狂犬疫苗加强",
            "record_date": date.today().isoformat(),
            "next_due_date": due,
        },
    )

    data = list_notifications(client, owner_headers)
    assert data["unread"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["category"] == "health"
    assert item["title"] == f"健康提醒 · {pet['name']}"
    assert "还有 3 天到期" in item["content"]
    assert item["link"] == f"/pets/{pet['id']}"
    assert item["is_read"] is False

    # 再次拉取不会重复生成同一条提醒。
    again = list_notifications(client, owner_headers)
    assert again["unread"] == 1
    assert len(again["items"]) == 1


def test_far_future_reminder_is_not_pushed(client, owner_headers):
    pet = create_pet(client, owner_headers).json()["data"]
    client.post(
        f"/api/pets/{pet['id']}/health-records",
        headers=owner_headers,
        json={
            "record_type": "deworm",
            "title": "体内驱虫",
            "record_date": date.today().isoformat(),
            "next_due_date": (date.today() + timedelta(days=30)).isoformat(),
        },
    )

    assert list_notifications(client, owner_headers)["items"] == []


def test_mark_read_and_read_all(client, owner_headers):
    pet = create_pet(client, owner_headers).json()["data"]
    for title in ("疫苗到期", "驱虫到期"):
        client.post(
            f"/api/pets/{pet['id']}/health-records",
            headers=owner_headers,
            json={
                "record_type": "vaccine",
                "title": title,
                "record_date": date.today().isoformat(),
                "next_due_date": (date.today() + timedelta(days=2)).isoformat(),
            },
        )

    data = list_notifications(client, owner_headers)
    assert data["unread"] == 2

    first_id = data["items"][0]["id"]
    body = client.post(
        f"/api/notifications/{first_id}/read", headers=owner_headers
    ).json()
    assert body["code"] == 200
    assert body["data"]["unread"] == 1

    # 重复标记已读是幂等的。
    again = client.post(
        f"/api/notifications/{first_id}/read", headers=owner_headers
    ).json()
    assert again["data"]["unread"] == 1

    body = client.post("/api/notifications/read-all", headers=owner_headers).json()
    assert body["code"] == 200
    assert body["data"]["unread"] == 0
    assert list_notifications(client, owner_headers)["unread"] == 0


def test_notifications_are_per_user(client, owner_headers, other_owner_headers):
    pet = create_pet(client, owner_headers).json()["data"]
    client.post(
        f"/api/pets/{pet['id']}/health-records",
        headers=owner_headers,
        json={
            "record_type": "visit",
            "title": "术后复查",
            "record_date": date.today().isoformat(),
            "next_due_date": date.today().isoformat(),
        },
    )
    notice = list_notifications(client, owner_headers)["items"][0]

    assert list_notifications(client, other_owner_headers)["items"] == []

    body = client.post(
        f"/api/notifications/{notice['id']}/read",
        headers=other_owner_headers,
    ).json()
    assert body["code"] == 404


def test_order_events_notify_owner_and_staff(
    client, admin_headers, owner_headers, staff_headers
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

    owner_items = list_notifications(client, owner_headers)["items"]
    assert [item["title"] for item in owner_items] == ["预约已提交"]

    staff_items = list_notifications(client, staff_headers)["items"]
    assert [item["title"] for item in staff_items] == ["新的寄养预约"]
    assert order["status"] == "pending"

    resp = client.post(
        f"/api/boarding/orders/{order['id']}/confirm", headers=staff_headers
    )
    assert resp.json()["code"] == 200
    owner_items = list_notifications(client, owner_headers)["items"]
    assert owner_items[0]["title"] == "寄养订单已确认"

    resp = client.post(
        f"/api/boarding/orders/{order['id']}/check-in", headers=staff_headers
    )
    assert resp.json()["code"] == 200
    owner_items = list_notifications(client, owner_headers)["items"]
    assert owner_items[0]["title"] == "宠物已入住"

    # 重复调用不会重复通知。
    client.post(f"/api/boarding/orders/{order['id']}/check-in", headers=staff_headers)
    titles = [item["title"] for item in list_notifications(client, owner_headers)["items"]]
    assert titles.count("宠物已入住") == 1


def test_scheduled_sync_covers_all_owners(client, owner_headers, db):
    from app.models.reminder import Notification
    from app.models.user import User
    from app.services import notification_service

    pet = create_pet(client, owner_headers).json()["data"]
    client.post(
        f"/api/pets/{pet['id']}/health-records",
        headers=owner_headers,
        json={
            "record_type": "vaccine",
            "title": "定时扫描测试",
            "record_date": date.today().isoformat(),
            "next_due_date": (date.today() + timedelta(days=1)).isoformat(),
        },
    )

    created = notification_service.sync_all_reminders(db)
    assert created >= 1

    from app.models.pet import Pet

    owner = db.get(User, db.get(Pet, pet["id"]).owner_id)
    notice = (
        db.query(Notification)
        .filter(
            Notification.user_id == owner.id,
            Notification.category == "health",
        )
        .first()
    )
    assert notice is not None
    assert "定时扫描测试" in notice.content

    # 重复执行不会重复写通知。
    assert notification_service.sync_all_reminders(db) == 0
