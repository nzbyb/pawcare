"""异常日报处置闭环：建单、认领、处置、告知宠物主。"""

from tests.test_boarding import create_draft, create_kennel, day, pay_order
from tests.test_pets import create_pet


def _checked_in_order(client, admin_headers, owner_headers, staff_headers) -> dict:
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
    client.post(f"/api/boarding/orders/{order['id']}/confirm", headers=staff_headers)
    pay_order(client, owner_headers, order["id"])
    client.post(f"/api/boarding/orders/{order['id']}/check-in", headers=staff_headers)
    return order


def _report(client, staff_headers, order_id: int, **overrides):
    payload = {
        "report_date": day(0),
        "appetite": "normal",
        "stool": "normal",
        "spirit": "good",
        "note": "常规观察",
    }
    payload.update(overrides)
    return client.post(
        f"/api/boarding/orders/{order_id}/reports",
        headers=staff_headers,
        json=payload,
    )


def _cases(client, headers, order_id: int | None = None, **params) -> dict:
    if order_id is not None:
        params["order_id"] = order_id
    resp = client.get("/api/boarding/abnormal-cases", headers=headers, params=params)
    body = resp.json()
    assert body["code"] == 200, resp.text
    return body["data"]


def _notifications(client, headers) -> list[dict]:
    data = client.get(
        "/api/notifications", headers=headers, params={"limit": 50}
    ).json()["data"]
    return data["items"]


def test_abnormal_report_creates_case_and_notifies_handlers(
    client, admin_headers, owner_headers, staff_headers
):
    order = _checked_in_order(client, admin_headers, owner_headers, staff_headers)
    resp = _report(
        client, staff_headers, order["id"], appetite="poor", stool="soft", note="吃得少"
    )
    assert resp.json()["code"] == 200

    data = _cases(client, staff_headers, order["id"])
    assert data["total"] == 1
    case = data["items"][0]
    assert case["order_id"] == order["id"]
    assert case["status"] == "open"
    # 两项异常按紧急处理
    assert case["severity"] == "critical"
    assert case["reason_labels"] == ["食欲较差", "便便偏软"]
    assert case["report"]["appetite"] == "poor"
    assert case["pet_name"]
    assert data["counts"]["open"] == 1
    assert data["counts"]["critical_open"] == 1
    assert data["stats"]["open"] == 1

    # 填日报的人被排除，其他管理员收到待处置提醒
    titles = [item["title"] for item in _notifications(client, admin_headers)]
    assert any("异常待处置" in title for title in titles)


def test_normal_report_creates_no_case(
    client, admin_headers, owner_headers, staff_headers
):
    order = _checked_in_order(client, admin_headers, owner_headers, staff_headers)
    assert _report(client, staff_headers, order["id"]).json()["code"] == 200
    data = _cases(client, staff_headers, order["id"])
    assert data["total"] == 0
    assert data["counts"]["open"] == 0


def test_sync_is_idempotent_per_report(
    client, db, admin_headers, owner_headers, staff_headers
):
    from app.models.boarding import BoardingAbnormalCase, BoardingDailyReport
    from app.services import abnormal_service

    order = _checked_in_order(client, admin_headers, owner_headers, staff_headers)
    _report(client, staff_headers, order["id"], stool="diarrhea")
    report = (
        db.query(BoardingDailyReport)
        .filter(BoardingDailyReport.order_id == order["id"])
        .one()
    )
    abnormal_service.sync_report_case(db, report, None)
    abnormal_service.sync_report_case(db, report, None)
    db.commit()
    assert (
        db.query(BoardingAbnormalCase)
        .filter(BoardingAbnormalCase.report_id == report.id)
        .count()
        == 1
    )


def test_claim_then_resolve_and_owner_is_notified(
    client, admin_headers, owner_headers, staff_headers
):
    order = _checked_in_order(client, admin_headers, owner_headers, staff_headers)
    _report(client, staff_headers, order["id"], spirit="low")
    case = _cases(client, staff_headers, order["id"])["items"][0]
    assert case["severity"] == "critical"

    # 紧急异常在生成处置单时就提醒宠物主
    owner_titles = [item["title"] for item in _notifications(client, owner_headers)]
    assert any("护理员正在处理" in title for title in owner_titles)

    claimed = client.post(
        f"/api/boarding/abnormal-cases/{case['id']}/claim", headers=staff_headers
    ).json()
    assert claimed["code"] == 200, claimed
    assert claimed["data"]["status"] == "processing"
    assert claimed["data"]["handler_name"] == "寄养员"
    assert claimed["data"]["claimed_at"] is not None

    resp = client.post(
        f"/api/boarding/abnormal-cases/{case['id']}/resolve",
        headers=staff_headers,
        json={"action_taken": "已加喂营养罐头并陪伴活动，精神恢复正常", "notify_owner": True},
    )
    body = resp.json()
    assert body["code"] == 200, resp.text
    resolved = body["data"]
    assert resolved["status"] == "resolved"
    assert resolved["vet_contacted"] is False
    assert resolved["owner_notified"] is True
    assert resolved["resolver_name"] == "寄养员"

    # 宠物主能看到处置结果，也能收到站内信
    owner_cases = _cases(client, owner_headers, order_id=order["id"])["items"]
    assert owner_cases[0]["status"] == "resolved"
    assert "营养罐头" in owner_cases[0]["action_taken"]
    owner_titles = [item["title"] for item in _notifications(client, owner_headers)]
    assert any("异常情况已处理" in title for title in owner_titles)

    # 已完成的单不能重复处置
    again = client.post(
        f"/api/boarding/abnormal-cases/{case['id']}/resolve",
        headers=staff_headers,
        json={"action_taken": "重复提交"},
    ).json()
    assert again["code"] == 409


def test_resolve_validation_and_role_boundaries(
    client, admin_headers, owner_headers, staff_headers, other_owner_headers
):
    order = _checked_in_order(client, admin_headers, owner_headers, staff_headers)
    _report(client, staff_headers, order["id"], appetite="poor")
    case = _cases(client, staff_headers, order["id"])["items"][0]

    resp = client.post(
        f"/api/boarding/abnormal-cases/{case['id']}/claim", headers=owner_headers
    ).json()
    assert resp["code"] == 403

    resp = client.post(
        f"/api/boarding/abnormal-cases/{case['id']}/resolve",
        headers=staff_headers,
        json={"action_taken": "好"},
    )
    assert resp.json()["code"] == 400

    # 未认领的单可以由寄养员直接处置，但必须先写措施
    resp = client.post(
        f"/api/boarding/abnormal-cases/{case['id']}/resolve",
        headers=staff_headers,
        json={"action_taken": "观察后恢复正常食欲"},
    )
    assert resp.json()["code"] == 200

    # 别人的订单看不到处置单
    assert _cases(client, other_owner_headers, order_id=order["id"])["total"] == 0
    resp = client.get(
        f"/api/boarding/abnormal-cases/{case['id']}", headers=other_owner_headers
    )
    assert resp.json()["code"] == 404


def test_claimed_case_is_exclusive(
    client, db, admin_headers, owner_headers, staff_headers
):
    from app.models.user import User
    from app.utils.password import hash_password
    from tests.conftest import login, unique_username

    order = _checked_in_order(client, admin_headers, owner_headers, staff_headers)
    _report(client, staff_headers, order["id"], stool="soft")
    case = _cases(client, staff_headers, order["id"])["items"][0]

    username = unique_username("staff2")
    db.add(
        User(
            username=username,
            password_hash=hash_password("Passw0rd!"),
            nickname="夜班寄养员",
            role="boarding_staff",
            status=1,
        )
    )
    db.commit()
    headers = {"Authorization": f"Bearer {login(client, username)}"}

    assert (
        client.post(
            f"/api/boarding/abnormal-cases/{case['id']}/claim", headers=staff_headers
        ).json()["code"]
        == 200
    )
    resp = client.post(
        f"/api/boarding/abnormal-cases/{case['id']}/claim", headers=headers
    ).json()
    assert resp["code"] == 409
    assert "寄养员" in resp["message"]

    resp = client.post(
        f"/api/boarding/abnormal-cases/{case['id']}/resolve",
        headers=headers,
        json={"action_taken": "擅自接手处置"},
    ).json()
    assert resp["code"] == 409

    # 管理员可以兜底处置
    resp = client.post(
        f"/api/boarding/abnormal-cases/{case['id']}/resolve",
        headers=admin_headers,
        json={"action_taken": "管理员代为处置", "vet_contacted": True},
    ).json()
    assert resp["code"] == 200
    assert resp["data"]["vet_contacted"] is True


def test_reopen_is_admin_only(
    client, admin_headers, owner_headers, staff_headers
):
    order = _checked_in_order(client, admin_headers, owner_headers, staff_headers)
    _report(client, staff_headers, order["id"], stool="diarrhea")
    case = _cases(client, staff_headers, order["id"])["items"][0]
    client.post(
        f"/api/boarding/abnormal-cases/{case['id']}/resolve",
        headers=staff_headers,
        json={"action_taken": "已联系兽医并按医嘱喂药"},
    )

    assert (
        client.post(
            f"/api/boarding/abnormal-cases/{case['id']}/reopen", headers=staff_headers
        ).json()["code"]
        == 403
    )
    resp = client.post(
        f"/api/boarding/abnormal-cases/{case['id']}/reopen", headers=admin_headers
    ).json()
    assert resp["code"] == 200
    assert resp["data"]["status"] == "open"
    assert resp["data"]["action_taken"] is None
    assert resp["data"]["resolved_at"] is None


def test_case_filters_and_today_tasks(
    client, admin_headers, owner_headers, staff_headers
):
    order = _checked_in_order(client, admin_headers, owner_headers, staff_headers)
    _report(client, staff_headers, order["id"], stool="soft")
    case = _cases(client, staff_headers, order["id"])["items"][0]
    assert case["severity"] == "warning"
    client.post(
        f"/api/boarding/abnormal-cases/{case['id']}/resolve",
        headers=staff_headers,
        json={"action_taken": "调整为易消化湿粮，排便恢复正常", "notify_owner": False},
    )

    assert _cases(client, staff_headers, order["id"], status="resolved")["total"] == 1
    assert _cases(client, staff_headers, order["id"], status="open")["total"] == 0
    assert _cases(client, staff_headers, order["id"], severity="warning")["total"] == 1

    tasks = client.get("/api/boarding/tasks/today", headers=staff_headers).json()["data"]
    abnormal = next(
        item for item in tasks["abnormal_reports"] if item["order_id"] == order["id"]
    )
    assert abnormal["case_id"] == case["id"]
    assert abnormal["case_status"] == "resolved"
    assert abnormal["severity"] == "warning"
    assert abnormal["abnormal_reasons"] == ["便便偏软"]


def test_list_rejects_unknown_status(client, staff_headers):
    resp = client.get(
        "/api/boarding/abnormal-cases", headers=staff_headers, params={"status": "done"}
    )
    assert resp.json()["code"] == 400


