import uuid

from app.config import settings
from app.models.agent import AgentConversation, AgentMessage, AgentToolCall
from app.models.user import User
from app.services import agent_metrics_service


def _user(db, role: str = "pet_owner") -> User:
    user = User(
        username=f"metrics_{uuid.uuid4().hex[:8]}",
        password_hash="x",
        nickname="指标用户",
        role=role,
        status=1,
    )
    db.add(user)
    db.commit()
    return user


def _seed_trace(
    db,
    user: User,
    *,
    tool_name: str,
    error: bool = False,
    latency_ms: int = 50,
    token_in: int = 120,
    token_out: int = 80,
    trace_id: str | None = None,
) -> str:
    """写入一轮完整的 Agent 调用：用户消息、助手消息、工具消息和一条工具调用。"""
    trace = trace_id or uuid.uuid4().hex
    conversation = AgentConversation(user_id=user.id, title="指标测试")
    db.add(conversation)
    db.flush()
    db.add(
        AgentMessage(
            conversation_id=conversation.id,
            role="user",
            content="我的猫今天怎么样？",
            trace_id=trace,
        )
    )
    assistant = AgentMessage(
        conversation_id=conversation.id,
        role="assistant",
        content="我查一下。",
        trace_id=trace,
        token_in=token_in,
        token_out=token_out,
        latency_ms=900,
    )
    db.add(assistant)
    db.flush()
    db.add(
        AgentMessage(
            conversation_id=conversation.id,
            role="tool",
            content='{"ok": true}',
            tool_call_id="call_1",
            trace_id=trace,
            latency_ms=latency_ms,
        )
    )
    db.add(
        AgentToolCall(
            trace_id=trace,
            conversation_id=conversation.id,
            message_id=assistant.id,
            tool_name=tool_name,
            arguments={"pet_id": 1},
            result_summary='{"ok": true}' if not error else '{"ok": false}',
            status="error" if error else "ok",
            error_code="PET_NOT_FOUND" if error else None,
            latency_ms=latency_ms,
        )
    )
    db.commit()
    return trace


def test_agent_metrics_endpoints_require_admin(client, owner_headers, staff_headers):
    for headers in (owner_headers, staff_headers):
        for path in (
            "/api/admin/agent/overview",
            "/api/admin/agent/tool-calls",
            "/api/admin/agent/traces/whatever",
        ):
            assert client.get(path, headers=headers).json()["code"] == 403


def test_overview_aggregates_tool_calls(client, admin_headers, db):
    user = _user(db)
    tool_name = f"metrics_tool_{uuid.uuid4().hex[:6]}"
    before = client.get(
        "/api/admin/agent/overview", headers=admin_headers, params={"days": 7}
    ).json()["data"]
    assert before["range"]["days"] == 7

    trace = _seed_trace(db, user, tool_name=tool_name, error=True, latency_ms=320)
    _seed_trace(db, user, tool_name=tool_name, latency_ms=80)

    body = client.get(
        "/api/admin/agent/overview", headers=admin_headers, params={"days": 7}
    ).json()
    assert body["code"] == 200, body
    data = body["data"]
    assert data["turns"] == before["turns"] + 2
    assert data["tool_calls"] == before["tool_calls"] + 2
    assert data["tool_errors"] == before["tool_errors"] + 1
    assert data["tool_success_rate"] is not None
    assert data["tool_latency_p95_ms"] is not None
    assert data["turn_latency_p95_ms"] is not None
    assert data["tokens"]["total"] == data["tokens"]["input"] + data["tokens"]["output"]

    tool = next(row for row in data["tools"] if row["tool_name"] == tool_name)
    assert tool["calls"] == 2
    assert tool["errors"] == 1
    assert tool["success_rate"] == 50.0
    assert tool["max_latency_ms"] == 320

    error_codes = {row["error_code"]: row["count"] for row in data["error_codes"]}
    assert error_codes["PET_NOT_FOUND"] >= 1
    assert any(row["trace_id"] == trace for row in data["recent_failures"])

    assert len(data["daily"]) == 7
    today = data["daily"][-1]
    assert today["turns"] >= 2
    assert today["tool_calls"] >= 2
    assert today["tool_errors"] >= 1


def test_overview_cost_follows_configured_prices(client, admin_headers, db, monkeypatch):
    monkeypatch.setattr(settings, "LLM_PRICE_INPUT_PER_M", 2.0)
    monkeypatch.setattr(settings, "LLM_PRICE_OUTPUT_PER_M", 8.0)

    body = client.get(
        "/api/admin/agent/overview", headers=admin_headers, params={"days": 7}
    ).json()
    assert body["code"] == 200, body
    data = body["data"]
    assert data["cost"]["configured"] is True
    expected = (
        data["tokens"]["input"] / 1_000_000 * 2.0
        + data["tokens"]["output"] / 1_000_000 * 8.0
    )
    assert data["cost"]["total"] == round(expected, 4)


def test_overview_cost_unconfigured(client, admin_headers):
    data = client.get(
        "/api/admin/agent/overview", headers=admin_headers
    ).json()["data"]
    assert settings.LLM_PRICE_INPUT_PER_M == 0
    assert data["cost"]["configured"] is False
    assert data["cost"]["total"] == 0


def test_tool_calls_filter_by_tool_and_status(client, admin_headers, db):
    user = _user(db)
    tool_name = f"metrics_filter_{uuid.uuid4().hex[:6]}"
    error_trace = _seed_trace(db, user, tool_name=tool_name, error=True)
    _seed_trace(db, user, tool_name=tool_name)

    data = client.get(
        "/api/admin/agent/tool-calls",
        headers=admin_headers,
        params={"tool_name": tool_name, "status": "error"},
    ).json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["trace_id"] == error_trace
    assert data["items"][0]["error_code"] == "PET_NOT_FOUND"

    by_keyword = client.get(
        "/api/admin/agent/tool-calls",
        headers=admin_headers,
        params={"keyword": error_trace},
    ).json()["data"]
    assert by_keyword["total"] == 1
    assert by_keyword["items"][0]["trace_id"] == error_trace


def test_tool_calls_reject_unknown_status(client, admin_headers):
    response = client.get(
        "/api/admin/agent/tool-calls",
        headers=admin_headers,
        params={"status": "oops"},
    )
    assert response.status_code == 422


def test_trace_replay_returns_messages_and_calls(client, admin_headers, db):
    user = _user(db)
    trace = _seed_trace(
        db, user, tool_name="list_pets", error=True, token_in=300, token_out=120
    )

    body = client.get(
        f"/api/admin/agent/traces/{trace}", headers=admin_headers
    ).json()
    assert body["code"] == 200, body
    data = body["data"]
    assert data["trace_id"] == trace
    assert data["conversation"]["user_id"] == user.id
    assert data["conversation"]["username"] == user.username
    assert [item["role"] for item in data["messages"]] == [
        "user",
        "assistant",
        "tool",
    ]
    assert data["tool_calls"][0]["tool_name"] == "list_pets"
    assert data["summary"]["status"] == "error"
    assert data["summary"]["errors"] == 1
    assert data["summary"]["token_in"] == 300
    assert data["summary"]["token_out"] == 120


def test_trace_missing_returns_404(client, admin_headers):
    body = client.get(
        f"/api/admin/agent/traces/{uuid.uuid4().hex}", headers=admin_headers
    ).json()
    assert body["code"] == 404


def test_percentile_matches_nearest_rank(db):
    assert agent_metrics_service._percentile([], 0.95) is None
    assert agent_metrics_service._percentile([100], 0.95) == 100
    values = list(range(1, 101))
    assert agent_metrics_service._percentile(values, 0.5) == 50
    assert agent_metrics_service._percentile(values, 0.95) == 95
