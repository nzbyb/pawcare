from tests.test_boarding import create_draft, create_kennel, day
from tests.test_pets import create_pet


def test_admin_endpoints_reject_non_admin(client, owner_headers, staff_headers):
    for headers in (owner_headers, staff_headers):
        assert client.get("/api/admin/users", headers=headers).json()["code"] == 403
        assert (
            client.get("/api/admin/kennels/occupancy", headers=headers).json()["code"]
            == 403
        )
        assert (
            client.get("/api/admin/audit-logs", headers=headers).json()["code"] == 403
        )


def test_list_users_search_and_filters(client, admin_headers, owner_credentials):
    username = owner_credentials["username"]
    body = client.get(
        "/api/admin/users",
        headers=admin_headers,
        params={"keyword": username},
    ).json()
    assert body["code"] == 200, body
    data = body["data"]
    assert data["total"] == 1
    item = data["items"][0]
    assert item["username"] == username
    assert item["role"] == "pet_owner"
    assert item["status"] == 1
    assert item["pet_count"] == 0
    assert item["order_count"] == 0

    admin_only = client.get(
        "/api/admin/users",
        headers=admin_headers,
        params={"role": "admin", "page_size": 50},
    ).json()["data"]
    assert admin_only["items"] and all(
        user["role"] == "admin" for user in admin_only["items"]
    )

    disabled = client.get(
        "/api/admin/users",
        headers=admin_headers,
        params={"status": 0},
    ).json()["data"]
    assert all(user["status"] == 0 for user in disabled["items"])

    assert (
        client.get(
            "/api/admin/users", headers=admin_headers, params={"role": "nobody"}
        ).json()["code"]
        == 400
    )


def test_disable_and_enable_user(client, admin_headers, owner_credentials, owner_headers):
    admin_id = client.get("/api/auth/me", headers=admin_headers).json()["data"]["id"]
    owner_id = client.get("/api/auth/me", headers=owner_headers).json()["data"]["id"]

    # 管理员不能停用自己。
    resp = client.put(
        f"/api/admin/users/{admin_id}/status",
        headers=admin_headers,
        json={"status": 0},
    ).json()
    assert resp["code"] == 400

    resp = client.put(
        f"/api/admin/users/{owner_id}/status",
        headers=admin_headers,
        json={"status": 0},
    ).json()
    assert resp["code"] == 200, resp
    assert resp["data"]["status"] == 0

    # 停用后旧令牌立即失效，也不能再登录。
    assert client.get("/api/auth/me", headers=owner_headers).status_code == 401
    login = client.post(
        "/api/auth/login",
        json={
            "username": owner_credentials["username"],
            "password": owner_credentials["password"],
        },
    ).json()
    assert login["code"] == 400
    assert "禁用" in login["message"]

    resp = client.put(
        f"/api/admin/users/{owner_id}/status",
        headers=admin_headers,
        json={"status": 1},
    ).json()
    assert resp["code"] == 200
    assert (
        client.post(
            "/api/auth/login",
            json={
                "username": owner_credentials["username"],
                "password": owner_credentials["password"],
            },
        ).json()["code"]
        == 200
    )

    logs = client.get(
        "/api/admin/audit-logs",
        headers=admin_headers,
        params={"action": "user."},
    ).json()["data"]["items"]
    assert [log["action"] for log in logs[:2]] == ["user.enable", "user.disable"]


def test_kennel_occupancy_shows_current_guest(
    client, admin_headers, owner_headers
):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    draft = create_draft(
        client, owner_headers, pet["id"], kennel["id"], day(0), day(2)
    ).json()["data"]
    order = client.post(
        f"/api/boarding/drafts/{draft['id']}/confirm",
        headers=owner_headers,
        json={"idempotency_key": draft["idempotency_key"]},
    ).json()["data"]

    data = client.get(
        "/api/admin/kennels/occupancy", headers=admin_headers
    ).json()["data"]
    assert data["summary"]["total"] >= 1
    item = next(row for row in data["items"] if row["id"] == kennel["id"])
    assert item["display_status"] == "occupied"
    assert item["occupancy"]["order_id"] == order["id"]
    assert item["occupancy"]["pet_name"] == pet["name"]
    assert item["occupancy"]["order_status"] == "pending"

    # 查未来某天时该笼舍恢复为空闲（订单结束于 day(2)）。
    future = client.get(
        "/api/admin/kennels/occupancy",
        headers=admin_headers,
        params={"day": day(3)},
    ).json()["data"]
    future_item = next(row for row in future["items"] if row["id"] == kennel["id"])
    assert future_item["display_status"] == "available"


def test_audit_log_records_boarding_actions(
    client, admin_headers, owner_headers
):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    draft = create_draft(
        client, owner_headers, pet["id"], kennel["id"], day(10), day(12)
    ).json()["data"]
    order = client.post(
        f"/api/boarding/drafts/{draft['id']}/confirm",
        headers=owner_headers,
        json={"idempotency_key": draft["idempotency_key"]},
    ).json()["data"]

    data = client.get(
        "/api/admin/audit-logs",
        headers=admin_headers,
        params={"action": "boarding_draft.confirm"},
    ).json()["data"]
    assert data["total"] >= 1
    log = data["items"][0]
    assert log["action"] == "boarding_draft.confirm"
    assert log["target_type"] == "boarding_order"
    assert log["target_id"] == order["id"]
    assert log["actor_username"]
    assert log["after_data"]["kennel_id"] == kennel["id"]
