from datetime import date, timedelta
from uuid import uuid4

from app.agent.runtime import LLMError, LLMResponse, ToolCall
from app.config import settings
from app.models.agent import AgentConversation, AgentMessage, AgentToolCall
from app.models.boarding import BoardingOrder
from app.services import agent_service
from tests.test_pets import create_pet


class FakeLLM:
    """按脚本返回响应的假模型，用来测试 Agent 循环本身。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    async def complete(self, messages, tools):
        self.calls.append(messages)
        if not self.responses:
            return LLMResponse(content="（脚本已用完）")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def create_kennel(client, admin_headers):
    body = client.post(
        "/api/kennels",
        headers=admin_headers,
        json={
            "code": f"K-{uuid4().hex[:8].upper()}",
            "size": "medium",
            "daily_price": 88,
        },
    ).json()
    assert body["code"] == 200, body
    return body["data"]


def post_chat(client, headers, monkeypatch, llm, content, conversation_id=None):
    monkeypatch.setattr(agent_service, "get_llm", lambda: llm)
    payload = {"messages": [{"role": "user", "content": content}]}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    response = client.post("/api/agent/chat", headers=headers, json=payload)
    return response.json()


def test_chat_tool_loop_and_history(client, owner_headers, db, monkeypatch):
    create_pet(client, owner_headers)
    llm = FakeLLM(
        [
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="call-1", name="list_my_pets", arguments={})],
                token_in=12,
                token_out=8,
            ),
            LLMResponse(content="你有一只宠物，叫豆豆。", token_in=20, token_out=10),
        ]
    )

    body = post_chat(client, owner_headers, monkeypatch, llm, "我有哪些宠物？")
    assert body["code"] == 200, body
    data = body["data"]
    assert data["content"] == "你有一只宠物，叫豆豆。"
    assert data["conversation_id"] > 0
    assert len(data["tool_events"]) == 1
    assert data["tool_events"][0]["name"] == "list_my_pets"
    assert data["tool_events"][0]["status"] == "ok"
    assert data["draft"] is None

    # 第二轮对话：模型能拿到第一轮落库的历史。
    llm2 = FakeLLM([LLMResponse(content="不客气。")])
    body2 = post_chat(
        client, owner_headers, monkeypatch, llm2, "谢谢", data["conversation_id"]
    )
    assert body2["code"] == 200
    assert body2["data"]["conversation_id"] == data["conversation_id"]
    assert body2["data"]["content"] == "不客气。"

    roles = [item["role"] for item in llm2.calls[0]]
    assert roles[0] == "system"
    assert "tool" in roles
    assert roles[-1] == "user"

    db.expire_all()
    messages = (
        db.query(AgentMessage)
        .filter(AgentMessage.conversation_id == data["conversation_id"])
        .order_by(AgentMessage.id.asc())
        .all()
    )
    assert [item.role for item in messages] == [
        "user",
        "assistant",
        "tool",
        "assistant",
        "user",
        "assistant",
    ]
    assert messages[2].tool_call_id == "call-1"
    assert messages[3].token_in == 20

    tool_calls = (
        db.query(AgentToolCall)
        .filter(AgentToolCall.conversation_id == data["conversation_id"])
        .all()
    )
    assert len(tool_calls) == 1
    assert tool_calls[0].tool_name == "list_my_pets"
    assert tool_calls[0].status == "ok"

    conversations = client.get(
        "/api/agent/conversations", headers=owner_headers
    ).json()["data"]
    assert len(conversations) == 1
    assert conversations[0]["title"] == "我有哪些宠物？"

    detail = client.get(
        f"/api/agent/conversations/{data['conversation_id']}", headers=owner_headers
    ).json()["data"]
    assert len(detail["messages"]) == 6


def test_chat_draft_returns_pending_draft_only(
    client, owner_headers, admin_headers, db, monkeypatch
):
    pet = create_pet(client, owner_headers).json()["data"]
    kennel = create_kennel(client, admin_headers)
    start = date.today() + timedelta(days=30)
    end = start + timedelta(days=2)

    llm = FakeLLM(
        [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call-draft",
                        name="create_boarding_draft",
                        arguments={
                            "pet_name": pet["name"],
                            "kennel_code": kennel["code"],
                            "start_date": start.isoformat(),
                            "end_date": end.isoformat(),
                            "note": "怕生",
                        },
                    )
                ],
            ),
            LLMResponse(content="草稿已生成，请在页面上确认。"),
        ]
    )
    body = post_chat(
        client, owner_headers, monkeypatch, llm, f"帮{pet['name']}预约{kennel['code']}"
    )
    assert body["code"] == 200, body
    draft = body["data"]["draft"]
    assert draft["status"] == "pending"
    assert draft["idempotency_key"]
    assert draft["total_amount"] == 176
    assert body["data"]["tool_events"][0]["name"] == "create_boarding_draft"

    db.expire_all()
    assert (
        db.query(BoardingOrder).filter(BoardingOrder.pet_id == pet["id"]).count() == 0
    )


def test_chat_tool_permission_isolation(
    client, owner_headers, other_owner_headers, db, monkeypatch
):
    pet = create_pet(client, owner_headers).json()["data"]
    llm = FakeLLM(
        [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call-health",
                        name="get_pet_health_records",
                        arguments={"pet_name": pet["name"]},
                    )
                ],
            ),
            LLMResponse(content="没有找到这只宠物的记录。"),
        ]
    )

    body = post_chat(
        client,
        other_owner_headers,
        monkeypatch,
        llm,
        f"看看{pet['name']}的疫苗记录",
    )
    assert body["code"] == 200
    event = body["data"]["tool_events"][0]
    assert event["status"] == "error"
    assert "没有找到" in event["summary"]

    db.expire_all()
    conversation_id = body["data"]["conversation_id"]
    tool_message = (
        db.query(AgentMessage)
        .filter(
            AgentMessage.conversation_id == conversation_id,
            AgentMessage.role == "tool",
        )
        .one()
    )
    assert "没有找到" in tool_message.content
    trace = (
        db.query(AgentToolCall)
        .filter(AgentToolCall.conversation_id == conversation_id)
        .one()
    )
    assert trace.status == "error"
    assert trace.error_code == "400"


def test_chat_stops_after_max_tool_rounds(
    client, owner_headers, db, monkeypatch
):
    create_pet(client, owner_headers)
    rounds = max(1, settings.AGENT_MAX_TOOL_CALLS)
    responses = [
        LLMResponse(
            content=None,
            tool_calls=[ToolCall(id=f"loop-{index}", name="list_my_pets", arguments={})],
        )
        for index in range(rounds + 1)
    ]
    llm = FakeLLM(responses)

    body = post_chat(client, owner_headers, monkeypatch, llm, "一直查")
    assert body["code"] == 200
    assert "拆小一点" in body["data"]["content"]
    assert len(body["data"]["tool_events"]) == rounds
    assert len(llm.calls) == rounds + 1


def test_chat_handles_llm_error(client, owner_headers, monkeypatch):
    llm = FakeLLM([LLMError("模型挂了")])
    body = post_chat(client, owner_headers, monkeypatch, llm, "我有哪些宠物？")
    assert body["code"] == 200
    assert "无法连接模型服务" in body["data"]["content"]
    assert body["data"]["tool_events"] == []


def test_chat_requires_user_last_message(client, owner_headers):
    response = client.post(
        "/api/agent/chat",
        headers=owner_headers,
        json={"messages": [{"role": "assistant", "content": "你好"}]},
    )
    assert response.json()["code"] == 400

    response = client.post(
        "/api/agent/chat", headers=owner_headers, json={"messages": []}
    )
    assert response.json()["code"] == 400


def test_conversation_is_private(client, owner_headers, other_owner_headers, db, monkeypatch):
    llm = FakeLLM([LLMResponse(content="你好。")])
    body = post_chat(client, owner_headers, monkeypatch, llm, "你好")
    conversation_id = body["data"]["conversation_id"]

    response = client.get(
        f"/api/agent/conversations/{conversation_id}",
        headers=other_owner_headers,
    )
    assert response.json()["code"] == 404

    llm2 = FakeLLM([LLMResponse(content="不该出现。")])
    body2 = post_chat(
        client,
        other_owner_headers,
        monkeypatch,
        llm2,
        "继续",
        conversation_id,
    )
    assert body2["code"] == 404

    db.expire_all()
    other_id = client.get(
        "/api/auth/me", headers=other_owner_headers
    ).json()["data"]["id"]
    assert (
        db.query(AgentConversation)
        .filter(AgentConversation.user_id == other_id)
        .count()
        == 0
    )
