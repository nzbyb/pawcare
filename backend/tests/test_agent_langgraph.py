"""LangGraph 适配层与显式循环的行为对齐测试。"""

import pytest

from app.agent.runtime import LLMError, LLMResponse, ToolCall
from app.config import settings
from app.models.agent import AgentMessage, AgentToolCall
from tests.test_agent_chat import FakeLLM, post_chat
from tests.test_pets import create_pet


@pytest.fixture
def langgraph_engine(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_ENGINE", "langgraph")
    return settings


def test_langgraph_tool_loop_matches_explicit_contract(
    client, owner_headers, db, monkeypatch, langgraph_engine
):
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
    assert len(data["tool_events"]) == 1
    assert data["tool_events"][0]["name"] == "list_my_pets"
    assert data["tool_events"][0]["status"] == "ok"
    assert data["draft"] is None

    db.expire_all()
    messages = (
        db.query(AgentMessage)
        .filter(AgentMessage.conversation_id == data["conversation_id"])
        .order_by(AgentMessage.id.asc())
        .all()
    )
    assert [item.role for item in messages] == ["user", "assistant", "tool", "assistant"]
    assert messages[1].tool_calls[0]["id"] == "call-1"
    assert messages[2].tool_call_id == "call-1"
    assert messages[3].content == "你有一只宠物，叫豆豆。"
    assert messages[3].token_in == 20

    tool_calls = (
        db.query(AgentToolCall)
        .filter(AgentToolCall.conversation_id == data["conversation_id"])
        .all()
    )
    assert len(tool_calls) == 1
    assert tool_calls[0].status == "ok"


def test_langgraph_stops_after_max_tool_rounds(
    client, owner_headers, db, monkeypatch, langgraph_engine
):
    create_pet(client, owner_headers)
    rounds = max(1, settings.AGENT_MAX_TOOL_CALLS)
    llm = FakeLLM(
        [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(id=f"loop-{index}", name="list_my_pets", arguments={})
                ],
            )
            for index in range(rounds + 1)
        ]
    )

    body = post_chat(client, owner_headers, monkeypatch, llm, "一直查")
    assert body["code"] == 200
    assert "拆小一点" in body["data"]["content"]
    assert len(body["data"]["tool_events"]) == rounds
    assert len(llm.calls) == rounds + 1


def test_langgraph_handles_llm_error(
    client, owner_headers, monkeypatch, langgraph_engine
):
    llm = FakeLLM([LLMError("模型挂了")])
    body = post_chat(client, owner_headers, monkeypatch, llm, "我有哪些宠物？")
    assert body["code"] == 200
    assert "无法连接模型服务" in body["data"]["content"]
    assert body["data"]["tool_events"] == []
