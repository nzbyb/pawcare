from datetime import date, timedelta

import pytest

from app.agent.tools import ToolContext, execute_tool
from app.models.boarding import BoardingDailyReport, BoardingDraft, BoardingOrder
from app.models.health import HealthRecord
from tests.test_agent_tools import user_from_headers
from tests.test_boarding import create_draft, create_kennel, day, pay_order
from tests.test_pets import create_pet


def reserve(client, owner_headers, pet, kennel, start=0, end=3):
    body = create_draft(client, owner_headers, pet["id"], kennel["id"], day(start), day(end)).json()
    assert body["code"] == 200, body
    draft = body["data"]
    response = client.post(f"/api/boarding/drafts/{draft['id']}/confirm", headers=owner_headers,
                           json={"idempotency_key": draft["idempotency_key"]}).json()
    assert response["code"] == 200, response
    return response["data"]


def health(client, headers, pet_id, start=0, end=3):
    return client.get("/api/boarding/health-check", headers=headers, params={
        "pet_id": pet_id, "start_date": day(start), "end_date": day(end),
    }).json()


def test_health_missing_data_and_permissions(client, owner_headers, other_owner_headers, staff_headers):
    pet = create_pet(client, owner_headers).json()["data"]
    client.put(f"/api/pets/{pet['id']}", headers=owner_headers, json={"allergies": None})
    result = health(client, owner_headers, pet["id"])
    assert result["code"] == 200
    assert result["data"]["warning_count"] == 2
    assert {item["code"] for item in result["data"]["items"]} == {"vaccine_missing", "deworm_missing", "allergies_unknown"}
    assert health(client, other_owner_headers, pet["id"])["code"] == 403
    assert health(client, staff_headers, pet["id"])["code"] == 200
    assert health(client, owner_headers, pet["id"], end=0)["code"] == 400
    assert health(client, owner_headers, pet["id"], end=61)["code"] == 400


def test_health_ready_keeps_information_notice(client, owner_headers, db):
    pet = create_pet(client, owner_headers).json()["data"]
    client.put(f"/api/pets/{pet['id']}", headers=owner_headers, json={"allergies": None})
    for kind in ("vaccine", "deworm"):
        db.add(HealthRecord(pet_id=pet["id"], record_type=kind, title=kind,
                            record_date=date.today(), next_due_date=date.today() + timedelta(days=20)))
    db.commit()
    result = health(client, owner_headers, pet["id"])["data"]
    assert result["status"] == "ready" and result["warning_count"] == 0
    assert any(item["code"] == "allergies_unknown" for item in result["items"])
    assert "不代表已获准入住" in result["notice"]


def test_health_tracks_latest_per_project_and_ignores_deleted_future(client, owner_headers, db):
    pet = create_pet(client, owner_headers).json()["data"]
    def record(kind, title, record_offset=-1, due_offset=20, **extra):
        row = HealthRecord(pet_id=pet["id"], record_type=kind, title=title,
                           record_date=date.today() + timedelta(days=record_offset),
                           next_due_date=date.today() + timedelta(days=due_offset) if due_offset is not None else None,
                           **extra)
        db.add(row)
        return row

    record("vaccine", "联合疫苗", record_offset=-10, due_offset=-2)
    latest = record("vaccine", "联合疫苗", due_offset=10)
    record("vaccine", "狂犬疫苗", due_offset=2)
    record("vaccine", "未来项目", record_offset=1)
    from datetime import datetime
    record("vaccine", "已删除项目", deleted_at=datetime.now())
    record("deworm", "体外驱虫", due_offset=3)
    record("symptom", "咳嗽", record_offset=-2, due_offset=None)
    record("symptom", "旧症状", record_offset=-10, due_offset=None)
    db.commit()
    result = health(client, owner_headers, pet["id"])["data"]
    items = result["items"]
    joint = [item for item in items if item["title"] == "联合疫苗"]
    assert len(joint) == 1 and joint[0]["source_record_id"] == latest.id
    assert joint[0]["level"] == "ok"
    assert any(item["code"] == "vaccine_during" for item in items)
    # 退房日不计入寄养区间，驱虫到期日恰为退房日。
    assert any(item["code"] == "deworm_ok" for item in items)
    assert sum(item["code"] == "recent_symptom" for item in items) == 1
    assert not any(item["title"] in ("未来项目", "已删除项目", "近期症状：旧症状") for item in items)


def test_health_due_on_arrival_allergies_and_agent(client, owner_headers, other_owner_headers, db):
    pet = create_pet(client, owner_headers).json()["data"]
    client.put(f"/api/pets/{pet['id']}", headers=owner_headers, json={"allergies": "鸡肉"})
    db.add(HealthRecord(pet_id=pet["id"], record_type="vaccine", title="联合疫苗",
                        record_date=date.today(), next_due_date=date.today()))
    db.add(HealthRecord(pet_id=pet["id"], record_type="deworm", title="驱虫",
                        record_date=date.today()))
    db.commit()
    result = health(client, owner_headers, pet["id"])["data"]
    assert {item["code"] for item in result["items"]} == {"vaccine_due", "deworm_unknown", "allergies"}
    owner = user_from_headers(client, owner_headers, db)
    args = {"pet_name": pet["name"], "start_date": day(0), "end_date": day(3)}
    ctx = ToolContext(trace_id="health", tool_call_id="health", idempotency_key="health-test")
    answer = execute_tool(db, owner, "get_boarding_health_check", args, ctx)
    assert answer["ok"] and answer["data"]["warning_count"] == 3
    import json
    json.dumps(answer)
    other = user_from_headers(client, other_owner_headers, db)
    assert execute_tool(db, other, "get_boarding_health_check", args, ctx)["ok"] is False


def test_past_dates_rejected_and_confirm_revalidates(client, owner_headers, admin_headers, db):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    assert create_draft(client, owner_headers, pet["id"], kennel["id"], day(-1), day(2)).json()["code"] == 400
    assert client.get("/api/kennels/availability", headers=owner_headers,
                      params={"start_date": day(-1), "end_date": day(2)}).json()["code"] == 400
    draft = create_draft(client, owner_headers, pet["id"], kennel["id"], day(0), day(2)).json()["data"]
    db.query(BoardingDraft).filter_by(id=draft["id"]).update({"start_date": date.today() - timedelta(days=1)})
    db.commit()
    response = client.post(f"/api/boarding/drafts/{draft['id']}/confirm", headers=owner_headers,
                           json={"idempotency_key": draft["idempotency_key"]}).json()
    assert response["code"] == 400


def test_pet_overlap_checked_again_on_confirmation(client, owner_headers, admin_headers):
    pet = create_pet(client, owner_headers).json()["data"]
    first, second = create_kennel(client, admin_headers), create_kennel(client, admin_headers)
    draft = create_draft(client, owner_headers, pet["id"], second["id"], day(1), day(4)).json()["data"]
    reserve(client, owner_headers, pet, first, 0, 3)
    response = client.post(f"/api/boarding/drafts/{draft['id']}/confirm", headers=owner_headers,
                           json={"idempotency_key": draft["idempotency_key"]}).json()
    assert response["code"] == 409
    assert create_draft(client, owner_headers, pet["id"], second["id"], day(1), day(4)).json()["code"] == 409
    assert create_draft(client, owner_headers, pet["id"], second["id"], day(3), day(4)).json()["code"] == 200


def test_deleted_pet_cannot_confirm_existing_draft(client, owner_headers, admin_headers):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    draft = create_draft(client, owner_headers, pet["id"], kennel["id"], day(0), day(2)).json()["data"]
    assert draft["health_check"]["pet_id"] == pet["id"]
    assert client.delete(f"/api/pets/{pet['id']}", headers=owner_headers).json()["code"] == 200
    response = client.post(f"/api/boarding/drafts/{draft['id']}/confirm", headers=owner_headers,
                           json={"idempotency_key": draft["idempotency_key"]}).json()
    assert response["code"] == 409


def test_cleaning_kennel_blocks_check_in(client, owner_headers, admin_headers, staff_headers):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    order = reserve(client, owner_headers, pet, kennel)
    client.post(f"/api/boarding/orders/{order['id']}/confirm", headers=staff_headers)
    pay_order(client, owner_headers, order["id"])
    client.put(f"/api/kennels/{kennel['id']}", headers=admin_headers, json={"status": "cleaning"})
    response = client.post(f"/api/boarding/orders/{order['id']}/check-in", headers=staff_headers).json()
    assert response["code"] == 409
    client.put(f"/api/kennels/{kennel['id']}", headers=admin_headers, json={"status": "available"})
    assert client.post(f"/api/boarding/orders/{order['id']}/check-in", headers=staff_headers).json()["code"] == 200


@pytest.mark.parametrize("start,end,paid,expected", [(0, 3, False, 409), (1, 3, True, 409), (0, 3, True, 200)])
def test_check_in_requires_payment_and_dates(client, owner_headers, admin_headers, staff_headers, start, end, paid, expected):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    order = reserve(client, owner_headers, pet, kennel, start, end)
    client.post(f"/api/boarding/orders/{order['id']}/confirm", headers=staff_headers)
    if paid:
        pay_order(client, owner_headers, order["id"])
    response = client.post(f"/api/boarding/orders/{order['id']}/check-in", headers=staff_headers).json()
    assert response["code"] == expected, response


def test_checkout_day_and_partial_payment_cannot_check_in(client, owner_headers, admin_headers, staff_headers, db):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    order = reserve(client, owner_headers, pet, kennel)
    client.post(f"/api/boarding/orders/{order['id']}/confirm", headers=staff_headers)
    db.query(BoardingOrder).filter_by(id=order["id"]).update({"payment_status": "paid", "paid_amount": 1})
    db.commit()
    assert client.post(f"/api/boarding/orders/{order['id']}/check-in", headers=staff_headers).json()["code"] == 409
    db.query(BoardingOrder).filter_by(id=order["id"]).update({
        "paid_amount": order["total_amount"], "end_date": date.today(),
        "start_date": date.today() - timedelta(days=2),
    })
    db.commit()
    assert client.post(f"/api/boarding/orders/{order['id']}/check-in", headers=staff_headers).json()["code"] == 409


def test_today_tasks_permissions_categories_and_report_transition(client, owner_headers, admin_headers, staff_headers, db):
    assert client.get("/api/boarding/tasks/today", headers=owner_headers).json()["code"] == 403
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    order = reserve(client, owner_headers, pet, kennel)
    def tasks():
        response = client.get("/api/boarding/tasks/today", headers=staff_headers).json()
        assert response["code"] == 200, response
        result = response["data"]
        assert all(count == len(result[key]) for key, count in result["counts"].items())
        return {key: {item["order_id"] for item in result[key]} for key in result["counts"]}

    assert order["id"] in tasks()["pending"]
    client.post(f"/api/boarding/orders/{order['id']}/confirm", headers=staff_headers)
    assert order["id"] in tasks()["arrivals"]
    pay_order(client, owner_headers, order["id"])
    assert client.post(f"/api/boarding/orders/{order['id']}/check-in", headers=staff_headers).json()["code"] == 200
    assert order["id"] in tasks()["missing_reports"]
    db.add(BoardingDailyReport(order_id=order["id"], report_date=date.today(), appetite="poor", stool="diarrhea", spirit="low"))
    db.commit()
    current = tasks()
    assert order["id"] not in current["missing_reports"]
    assert order["id"] in current["abnormal_reports"]
    db.query(BoardingOrder).filter_by(id=order["id"]).update({"end_date": date.today()})
    db.commit()
    assert order["id"] in tasks()["departures"]
    assert client.post(f"/api/boarding/orders/{order['id']}/check-out", headers=staff_headers).json()["code"] == 200
    assert all(order["id"] not in ids for ids in tasks().values())
    assert client.get("/api/boarding/tasks/today", headers=admin_headers).json()["code"] == 200
