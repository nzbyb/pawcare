from datetime import date, timedelta
from uuid import uuid4

from tests.test_boarding import create_draft, create_kennel, day
from tests.test_pets import create_pet


def test_update_profile_and_reset_verification(client, owner_headers):
    email = f"new_{uuid4().hex[:8]}@example.com"
    resp = client.put(
        "/api/auth/me",
        headers=owner_headers,
        json={"nickname": "小满", "email": email, "phone": None},
    )
    body = resp.json()
    assert body["code"] == 200, body
    data = body["data"]
    assert data["nickname"] == "小满"
    assert data["email"] == email
    assert data["phone"] is None
    assert data["email_verified_at"] is None
    assert data["notify_health"] is True
    assert data["notify_order"] is True
    assert data["notify_system"] is True

    me = client.get("/api/auth/me", headers=owner_headers).json()["data"]
    assert me["nickname"] == "小满"
    assert me["email"] == email


def test_update_profile_rejects_used_contact(client, owner_headers, other_owner_headers):
    other_email = client.get("/api/auth/me", headers=other_owner_headers).json()["data"][
        "email"
    ]
    resp = client.put(
        "/api/auth/me",
        headers=owner_headers,
        json={"nickname": "小满", "email": other_email},
    )
    assert resp.json()["code"] == 400
    assert "已被其他账号使用" in resp.json()["message"]


def test_update_profile_requires_contact_and_valid_format(client, owner_headers):
    resp = client.put(
        "/api/auth/me",
        headers=owner_headers,
        json={"nickname": "小满", "email": None, "phone": None},
    )
    assert resp.json()["code"] == 400

    resp = client.put(
        "/api/auth/me",
        headers=owner_headers,
        json={"nickname": "小满", "email": "not-an-email"},
    )
    assert resp.json()["code"] == 400


def test_change_password_rotates_token(client, owner_credentials):
    old_headers = {"Authorization": f"Bearer {owner_credentials['token']}"}
    resp = client.put(
        "/api/auth/password",
        headers=old_headers,
        json={"old_password": "Passw0rd!", "new_password": "NewPassw0rd!"},
    )
    body = resp.json()
    assert body["code"] == 200, body
    new_token = body["data"]["token"]

    # 旧令牌立即失效，新令牌可以继续使用。
    assert client.get("/api/auth/me", headers=old_headers).status_code == 401
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {new_token}"}
        ).json()["code"]
        == 200
    )

    old_login = client.post(
        "/api/auth/login",
        json={"username": owner_credentials["username"], "password": "Passw0rd!"},
    ).json()
    assert old_login["code"] == 400
    new_login = client.post(
        "/api/auth/login",
        json={
            "username": owner_credentials["username"],
            "password": "NewPassw0rd!",
        },
    ).json()
    assert new_login["code"] == 200


def test_order_notifications_respect_preferences(
    client, admin_headers, owner_headers, staff_headers
):
    prefs = client.put(
        "/api/auth/notification-prefs",
        headers=owner_headers,
        json={"notify_health": True, "notify_order": False, "notify_system": True},
    ).json()
    assert prefs["code"] == 200
    assert prefs["data"]["notify_order"] is False

    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    draft = create_draft(
        client, owner_headers, pet["id"], kennel["id"], day(20), day(22)
    ).json()["data"]
    client.post(
        f"/api/boarding/drafts/{draft['id']}/confirm",
        headers=owner_headers,
        json={"idempotency_key": draft["idempotency_key"]},
    )

    owner_items = client.get("/api/notifications", headers=owner_headers).json()[
        "data"
    ]["items"]
    assert owner_items == []

    # 寄养员没有关闭通知，仍然能收到新订单。
    staff_items = client.get("/api/notifications", headers=staff_headers).json()[
        "data"
    ]["items"]
    assert [item["title"] for item in staff_items] == ["新的寄养预约"]


def test_health_notifications_respect_preferences(client, owner_headers):
    client.put(
        "/api/auth/notification-prefs",
        headers=owner_headers,
        json={"notify_health": False, "notify_order": True, "notify_system": True},
    )

    pet = create_pet(client, owner_headers).json()["data"]
    client.post(
        f"/api/pets/{pet['id']}/health-records",
        headers=owner_headers,
        json={
            "record_type": "vaccine",
            "title": "狂犬疫苗",
            "record_date": date.today().isoformat(),
            "next_due_date": (date.today() + timedelta(days=3)).isoformat(),
        },
    )

    items = client.get("/api/notifications", headers=owner_headers).json()["data"][
        "items"
    ]
    assert items == []
