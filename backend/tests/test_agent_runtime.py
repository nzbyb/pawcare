"""LLM 客户端请求体测试：空工具列表不能发空 tools 字段。"""

import asyncio

from app.agent import runtime


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }


class FakeAsyncClient:
    payloads: list[dict] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None):
        FakeAsyncClient.payloads.append(json)
        return FakeResponse()


def run_complete(monkeypatch, tools):
    FakeAsyncClient.payloads = []
    monkeypatch.setattr(runtime.httpx, "AsyncClient", FakeAsyncClient)
    client = runtime.OpenAICompatibleClient()
    asyncio.run(
        client.complete([{"role": "user", "content": "hi"}], tools)
    )
    return FakeAsyncClient.payloads[-1]


def test_empty_tools_omits_tools_field(monkeypatch) -> None:
    payload = run_complete(monkeypatch, [])
    assert "tools" not in payload
    assert "tool_choice" not in payload


def test_tools_field_kept_when_present(monkeypatch) -> None:
    tools = [{"type": "function", "function": {"name": "x", "parameters": {}}}]
    payload = run_complete(monkeypatch, tools)
    assert payload["tools"] == tools
    assert payload["tool_choice"] == "auto"
