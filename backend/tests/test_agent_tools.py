from datetime import date, timedelta
from uuid import uuid4

from app.agent.tools import TOOL_HANDLERS, ToolContext, execute_tool
from app.models.boarding import BoardingOrder
from app.models.knowledge import KnowledgeChunk
from app.models.user import User
from app.rag import retriever
from tests.fakes import FakeEmbedder
from tests.test_pets import create_pet


def ctx() -> ToolContext:
    return ToolContext(
        trace_id="trace-test", tool_call_id="call-1", idempotency_key="agent-test-key"
    )


def user_from_headers(client, headers, db) -> User:
    body = client.get("/api/auth/me", headers=headers).json()
    assert body["code"] == 200, body
    return db.get(User, body["data"]["id"])


def create_kennel(client, admin_headers, code: str | None = None):
    code = code or f"K-{uuid4().hex[:8].upper()}"
    body = client.post(
        "/api/kennels",
        headers=admin_headers,
        json={"code": code, "size": "medium", "daily_price": 88},
    ).json()
    assert body["code"] == 200, body
    return body["data"]


def test_agent_has_no_confirm_tool():
    assert "confirm_draft" not in TOOL_HANDLERS
    assert "confirm_boarding_draft" not in TOOL_HANDLERS
    assert "create_boarding_draft" in TOOL_HANDLERS


def test_list_my_pets_respects_owner(
    client, owner_headers, other_owner_headers, staff_headers, db
):
    owner_pet = create_pet(client, owner_headers).json()["data"]
    other_pet = create_pet(client, other_owner_headers, name="可乐").json()["data"]

    owner = user_from_headers(client, owner_headers, db)
    result = execute_tool(db, owner, "list_my_pets", {}, ctx())
    assert result["ok"] is True
    names = [item["name"] for item in result["data"]["pets"]]
    assert owner_pet["name"] in names
    assert other_pet["name"] not in names

    staff = user_from_headers(client, staff_headers, db)
    result = execute_tool(db, staff, "list_my_pets", {}, ctx())
    names = [item["name"] for item in result["data"]["pets"]]
    assert owner_pet["name"] in names
    assert other_pet["name"] in names


def test_health_tool_blocks_other_owner(
    client, owner_headers, other_owner_headers, db
):
    pet = create_pet(client, owner_headers).json()["data"]
    resp = client.post(
        f"/api/pets/{pet['id']}/health-records",
        headers=owner_headers,
        json={
            "record_type": "vaccine",
            "title": "狂犬疫苗",
            "record_date": "2026-01-01",
            "next_due_date": "2027-01-01",
        },
    )
    assert resp.json()["code"] == 200

    owner = user_from_headers(client, owner_headers, db)
    result = execute_tool(
        db, owner, "get_pet_health_records", {"pet_name": pet["name"]}, ctx()
    )
    assert result["ok"] is True
    assert len(result["data"]["records"]) == 1
    assert result["data"]["records"][0]["title"] == "狂犬疫苗"

    other = user_from_headers(client, other_owner_headers, db)
    result = execute_tool(
        db, other, "get_pet_health_records", {"pet_name": pet["name"]}, ctx()
    )
    assert result["ok"] is False
    assert "没有找到" in result["error"]


def test_kennel_availability_tool(client, admin_headers, owner_headers, db):
    kennel = create_kennel(client, admin_headers)
    owner = user_from_headers(client, owner_headers, db)
    start = date.today() + timedelta(days=20)
    end = start + timedelta(days=3)

    result = execute_tool(
        db,
        owner,
        "check_kennel_availability",
        {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "size": "medium",
        },
        ctx(),
    )
    assert result["ok"] is True
    data = result["data"]
    assert data["nights"] == 3
    item = next(k for k in data["kennels"] if k["code"] == kennel["code"])
    assert item["estimated_total"] == 264


def test_create_draft_tool_only_creates_draft(
    client, admin_headers, owner_headers, db
):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    owner = user_from_headers(client, owner_headers, db)
    start = date.today() + timedelta(days=25)
    end = start + timedelta(days=2)

    result = execute_tool(
        db,
        owner,
        "create_boarding_draft",
        {
            "pet_name": pet["name"],
            "kennel_code": kennel["code"],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "note": "每天喂一次药",
        },
        ctx(),
    )
    assert result["ok"] is True
    data = result["data"]
    assert data["status"] == "pending"
    assert data["draft_id"] > 0
    assert data["total_amount"] == 176

    # 工具只写草稿，不产生订单
    orders = (
        db.query(BoardingOrder).filter(BoardingOrder.pet_id == pet["id"]).all()
    )
    assert orders == []


def test_unknown_tool_returns_error(client, owner_headers, db):
    owner = user_from_headers(client, owner_headers, db)
    result = execute_tool(
        db, owner, "confirm_boarding_draft", {"draft_id": 1}, ctx()
    )
    assert result["ok"] is False
    assert result["code"] == 400


def test_reports_tool_blocks_other_owner(
    client, admin_headers, owner_headers, other_owner_headers, staff_headers, db
):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    start = date.today() + timedelta(days=40)
    end = start + timedelta(days=2)

    draft = client.post(
        "/api/boarding/drafts",
        headers=owner_headers,
        json={
            "pet_id": pet["id"],
            "kennel_id": kennel["id"],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    ).json()["data"]
    order = client.post(
        f"/api/boarding/drafts/{draft['id']}/confirm",
        headers=owner_headers,
        json={"idempotency_key": draft["idempotency_key"]},
    ).json()["data"]

    staff = user_from_headers(client, staff_headers, db)
    execute_tool(db, staff, "get_boarding_daily_reports", {"order_id": order["id"]}, ctx())

    other = user_from_headers(client, other_owner_headers, db)
    result = execute_tool(
        db, other, "get_boarding_daily_reports", {"order_id": order["id"]}, ctx()
    )
    assert result["ok"] is False
    assert result["code"] == 403


def test_search_care_knowledge_tool(client, owner_headers, db, monkeypatch):
    db.add(
        KnowledgeChunk(
            doc_id=f"tool-{uuid4().hex[:10]}",
            chunk_index=0,
            title="寄养准备测试",
            content="测试甲：寄养前准备疫苗本和牵引绳。",
            meta={"category": "boarding", "source": "测试知识库"},
        )
    )
    db.commit()
    monkeypatch.setattr(retriever, "get_embedder", lambda: FakeEmbedder())

    owner = user_from_headers(client, owner_headers, db)
    result = execute_tool(
        db,
        owner,
        "search_care_knowledge",
        {"query": "测试甲 寄养要带什么"},
        ctx(),
    )

    assert result["ok"] is True, result
    data = result["data"]
    assert data["retrieval_mode"] == "hybrid"
    assert data["chunks"]
    assert data["chunks"][0]["title"] == "寄养准备测试"
    assert data["chunks"][0]["trust"] == "untrusted"
    assert "不能替代兽医诊断" in data["disclaimer"]


def test_search_care_knowledge_rejects_bad_category(
    client, owner_headers, db, monkeypatch
):
    monkeypatch.setattr(retriever, "get_embedder", lambda: FakeEmbedder())
    owner = user_from_headers(client, owner_headers, db)

    result = execute_tool(
        db,
        owner,
        "search_care_knowledge",
        {"query": "寄养", "category": "stock"},
        ctx(),
    )

    assert result["ok"] is False
    assert "category" in result["error"]
