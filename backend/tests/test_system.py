from datetime import date, timedelta
from uuid import uuid4

from app.models.audit import AuditLog
from app.models.boarding import BoardingOrder, Kennel
from app.models.knowledge import KnowledgeChunk
from app.models.system import LoginLog
from app.models.user import User
from app.utils.password import hash_password


def tag() -> str:
    return uuid4().hex[:6]


def make_user(db, role: str = "pet_owner", password: str = "Passw0rd!") -> User:
    user = User(
        username=f"sys_{tag()}",
        password_hash=hash_password(password),
        nickname=f"系统测试{tag()}",
        role=role,
        status=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_public_settings_and_admin_update(
    client, admin_headers, owner_headers, db
):
    owner_view = client.get("/api/settings", headers=owner_headers).json()
    assert owner_view["code"] == 200
    assert owner_view["data"]["store_name"]
    assert set(owner_view["data"]) == {
        "store_name",
        "service_phone",
        "store_address",
        "business_hours",
        "booking_notice",
    }

    denied = client.put(
        "/api/admin/settings",
        headers=owner_headers,
        json={"items": [{"key": "store_name", "value": "越权修改"}]},
    ).json()
    assert denied["code"] == 403

    marker = f"测试寄养中心-{tag()}"
    saved = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={
            "items": [
                {"key": "store_name", "value": marker},
                {"key": "service_phone", "value": "010-00000000"},
                {"key": "business_hours", "value": "每天 09:00 - 20:00"},
            ]
        },
    ).json()
    assert saved["code"] == 200
    values = {item["key"]: item["value"] for item in saved["data"]}
    assert values["store_name"] == marker
    assert values["service_phone"] == "010-00000000"

    # 前台读到的是保存后的值。
    assert (
        client.get("/api/settings", headers=owner_headers).json()["data"]["store_name"]
        == marker
    )

    log = (
        db.query(AuditLog)
        .filter(AuditLog.action == "setting.update")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert log is not None and log.after_data["store_name"] == marker

    # 未声明的键在 schema 层被拒绝；短字段超长返回业务错误。
    unknown = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={"items": [{"key": "unknown_key", "value": "x"}]},
    )
    assert unknown.status_code == 422
    too_long = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={"items": [{"key": "store_name", "value": "长" * 61}]},
    ).json()
    assert too_long["code"] == 400


def test_login_logs_record_and_admin_query(client, admin_headers, owner_headers, db):
    user = make_user(db)
    ghost = f"ghost_{tag()}"

    client.post("/api/auth/login", json={"username": user.username, "password": "wrong"})
    client.post(
        "/api/auth/login", json={"username": user.username, "password": "Passw0rd!"}
    )
    client.post("/api/auth/login", json={"username": ghost, "password": "whatever"})

    rows = (
        db.query(LoginLog)
        .filter(LoginLog.username.in_((user.username, ghost)))
        .order_by(LoginLog.id)
        .all()
    )
    assert [(row.success, row.reason) for row in rows] == [
        (False, "wrong_password"),
        (True, "success"),
        (False, "no_user"),
    ]
    assert rows[1].user_id == user.id

    # 普通用户不能查看登录日志。
    assert (
        client.get("/api/admin/login-logs", headers=owner_headers).json()["code"] == 403
    )

    listed = client.get(
        "/api/admin/login-logs", headers=admin_headers, params={"keyword": user.username}
    ).json()["data"]
    assert listed["total"] == 2
    assert {item["reason"] for item in listed["items"]} == {"wrong_password", "success"}

    failed = client.get(
        "/api/admin/login-logs",
        headers=admin_headers,
        params={"keyword": user.username, "success": False},
    ).json()["data"]
    assert failed["total"] == 1
    assert "user_agent" in failed["items"][0]


def test_search_groups_permissions_and_order_link(
    client, admin_headers, owner_headers, other_owner_headers, db
):
    name = f"搜索狗{tag()}"
    pet = client.post(
        "/api/pets",
        headers=owner_headers,
        json={"name": name, "species": "dog", "breed": "柯基"},
    ).json()["data"]

    kennel = Kennel(code=f"K{tag()}", size="small", status="available", daily_price=88)
    db.add(kennel)
    db.flush()
    order = BoardingOrder(
        pet_id=pet["id"],
        owner_id=pet["owner_id"],
        kennel_id=kennel.id,
        start_date=date.today() + timedelta(days=3),
        end_date=date.today() + timedelta(days=6),
        status="confirmed",
        daily_price=88,
        deposit=0,
        total_amount=264,
        payment_status="unpaid",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    result = client.get(
        "/api/search", headers=owner_headers, params={"q": name}
    ).json()["data"]
    assert result["total"] >= 1
    pets = next(group for group in result["groups"] if group["type"] == "pet")
    assert pets["items"][0] == {
        "type": "pet",
        "id": pet["id"],
        "title": name,
        "subtitle": "犬 · 柯基",
        "url": f"/pets/{pet['id']}",
    }
    orders = next(group for group in result["groups"] if group["type"] == "order")
    assert orders["items"][0]["url"] == f"/boarding?order={order.id}"

    # 其他宠物主搜不到别人的宠物和订单。
    other = client.get(
        "/api/search", headers=other_owner_headers, params={"q": name}
    ).json()["data"]
    assert other["total"] == 0

    # 按笼舍编号也能定位订单。
    by_kennel = client.get(
        "/api/search", headers=owner_headers, params={"q": kennel.code}
    ).json()["data"]
    assert by_kennel["groups"][0]["items"][0]["id"] == order.id

    # 护理知识只对管理员开放。
    db.add(
        KnowledgeChunk(
            doc_id=f"search-doc-{tag()}",
            chunk_index=0,
            title="疫苗注意事项",
            content="疫苗前后一周避免洗澡，接种后观察 30 分钟。",
            meta={"category": "健康"},
        )
    )
    db.commit()
    admin_result = client.get(
        "/api/search", headers=admin_headers, params={"q": "疫苗"}
    ).json()["data"]
    assert any(group["type"] == "knowledge" for group in admin_result["groups"])
    owner_result = client.get(
        "/api/search", headers=owner_headers, params={"q": "疫苗"}
    ).json()["data"]
    assert all(group["type"] != "knowledge" for group in owner_result["groups"])

    # 只有空白的关键词返回业务错误。
    assert (
        client.get("/api/search", headers=owner_headers, params={"q": " "}).json()[
            "code"
        ]
        == 400
    )


def test_search_announcements_respect_audience(
    client, admin_headers, owner_headers, staff_headers
):
    marker = tag()
    title = f"搜索公告-{marker}"
    created = client.post(
        "/api/admin/announcements",
        headers=admin_headers,
        json={
            "title": title,
            "content": "这条公告用于验证搜索的可见性。",
            "audience": "boarding_staff",
            "status": "published",
        },
    ).json()
    assert created["code"] == 200

    staff_hits = client.get(
        "/api/search", headers=staff_headers, params={"q": marker}
    ).json()["data"]
    announcements = next(
        group for group in staff_hits["groups"] if group["type"] == "announcement"
    )
    assert announcements["items"][0]["url"] == f"/announcements?id={created['data']['id']}"

    owner_hits = client.get(
        "/api/search", headers=owner_headers, params={"q": marker}
    ).json()["data"]
    assert owner_hits["total"] == 0
