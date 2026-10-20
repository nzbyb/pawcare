"""LLM 客户端与 Agent 循环。

选择直接走 OpenAI 兼容的 /chat/completions，而不是引入完整框架：
工具调用、循环、trace 都是显式的，方便测试和写论文。
LangGraph 对照适配层见 app/agent/langgraph_runtime.py；生产默认仍用本模块。
"""

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from app.agent.prompts import build_system_prompt
from app.agent.tools import TOOL_DEFINITIONS, ToolContext, execute_tool
from app.common.exceptions import BusinessException
from app.config import settings
from app.models.agent import AgentMessage, AgentToolCall
from app.models.user import User

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 30


class LLMError(Exception):
    pass


EventSink = Callable[[dict], Awaitable[None]]


async def _emit(sink: EventSink | None, event: str, data: dict) -> None:
    """向流式调用方推送步骤事件；回调失败不能影响 Agent 主流程。"""
    if sink is None:
        return
    try:
        await sink({"event": event, "data": data})
    except Exception:
        logger.exception("Agent 事件回调失败")


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    token_in: int = 0
    token_out: int = 0


class LLMClient(Protocol):
    async def complete(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        ...


class OpenAICompatibleClient:
    def __init__(self) -> None:
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL

    async def complete(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": settings.LLM_MAX_TOKENS,
        }
        # 评测 baseline 会传入空列表；部分模型服务不接受空 tools 数组。
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        timeout = httpx.Timeout(settings.AGENT_TIMEOUT_SECONDS, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.status_code >= 400:
            logger.error(
                "LLM 调用失败: HTTP %s %s",
                response.status_code,
                response.text[:500],
            )
            raise LLMError("模型服务返回错误")

        try:
            data = response.json()
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError("模型返回格式异常") from exc

        tool_calls: list[ToolCall] = []
        for item in message.get("tool_calls") or []:
            function = item.get("function") or {}
            raw_args = function.get("arguments") or "{}"
            try:
                arguments = json.loads(raw_args)
            except (TypeError, json.JSONDecodeError):
                arguments = {"__invalid_arguments__": str(raw_args)[:500]}
            tool_calls.append(
                ToolCall(
                    id=item.get("id") or uuid4().hex,
                    name=function.get("name") or "",
                    arguments=arguments if isinstance(arguments, dict) else {},
                )
            )

        usage = data.get("usage") or {}
        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            token_in=int(usage.get("prompt_tokens") or 0),
            token_out=int(usage.get("completion_tokens") or 0),
        )


def get_llm() -> LLMClient:
    if not settings.LLM_API_KEY:
        raise BusinessException(message="助手尚未配置模型密钥", code=503)
    return OpenAICompatibleClient()


@dataclass
class AgentRunResult:
    content: str
    trace_id: str
    tool_events: list[dict]
    draft_id: int | None = None


def _wire_tool_calls(tool_calls: list[ToolCall]) -> list[dict]:
    return [
        {
            "id": call.id,
            "type": "function",
            "function": {
                "name": call.name,
                "arguments": json.dumps(call.arguments, ensure_ascii=False),
            },
        }
        for call in tool_calls
    ]


def _idempotency_key(trace_id: str, tool_call_id: str) -> str:
    digest = hashlib.sha256(f"{trace_id}:{tool_call_id}".encode()).hexdigest()
    return f"agent-{digest[:40]}"


def _summarize(name: str, result: dict) -> str:
    if not result.get("ok"):
        return str(result.get("error") or "工具执行失败")
    data = result.get("data") or {}
    if name == "list_my_pets":
        return f"找到 {len(data.get('pets', []))} 只宠物"
    if name == "get_pet_health_records":
        return f"找到 {len(data.get('records', []))} 条健康记录"
    if name == "get_upcoming_reminders":
        return f"找到 {len(data.get('reminders', []))} 条提醒"
    if name == "check_kennel_availability":
        return f"找到 {len(data.get('kennels', []))} 间可用笼舍"
    if name == "create_boarding_draft":
        return (
            f"生成草稿 #{data.get('draft_id')}，"
            f"¥{data.get('total_amount')}，等待用户确认"
        )
    if name == "list_boarding_orders":
        return f"返回 {len(data.get('orders', []))} 笔订单"
    if name == "get_boarding_daily_reports":
        return f"返回 {len(data.get('reports', []))} 条日报"
    if name == "search_care_knowledge":
        chunks = data.get("chunks", [])
        if not chunks:
            return "知识库未检索到相关内容"
        return f"检索到 {len(chunks)} 条护理知识（{data.get('retrieval_mode')}）"
    return "执行成功"


def _friendly_failure(reason: str) -> str:
    if reason == "timeout":
        return "这次查询超时了，请稍后再试，或者把问题说得更具体一点。"
    return "助手暂时无法连接模型服务，请稍后再试。"


def _persist_assistant(
    db: Session,
    conversation_id: int,
    trace_id: str,
    content: str,
    token_in: int = 0,
    token_out: int = 0,
    latency_ms: int = 0,
    tool_calls: list[dict] | None = None,
) -> AgentMessage:
    message = AgentMessage(
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        tool_calls=tool_calls,
        trace_id=trace_id,
        token_in=token_in or None,
        token_out=token_out or None,
        latency_ms=latency_ms or None,
    )
    db.add(message)
    db.flush()
    return message


async def run_agent(
    db: Session,
    user: User,
    conversation_id: int,
    history: list[dict],
    llm: LLMClient,
    trace_id: str,
    on_event: EventSink | None = None,
) -> AgentRunResult:
    messages = [{"role": "system", "content": build_system_prompt(user)}, *history]
    events: list[dict] = []
    draft_id: int | None = None

    max_tool_rounds = max(1, settings.AGENT_MAX_TOOL_CALLS)

    async def finish(
        content: str,
        token_in: int = 0,
        token_out: int = 0,
        latency_ms: int = 0,
    ) -> AgentRunResult:
        _persist_assistant(
            db,
            conversation_id,
            trace_id,
            content,
            token_in,
            token_out,
            latency_ms,
        )
        db.commit()
        await _emit(on_event, "assistant", {"content": content})
        return AgentRunResult(
            content=content,
            trace_id=trace_id,
            tool_events=events,
            draft_id=draft_id,
        )

    for step in range(max_tool_rounds + 1):
        started = time.perf_counter()
        await _emit(on_event, "llm_start", {"round": step + 1})
        try:
            response = await asyncio.wait_for(
                llm.complete(messages, TOOL_DEFINITIONS),
                timeout=settings.AGENT_TIMEOUT_SECONDS + 5,
            )
        except asyncio.TimeoutError:
            return await finish(_friendly_failure("timeout"))
        except Exception:
            logger.exception("LLM 调用异常")
            return await finish(_friendly_failure("error"))

        latency_ms = int((time.perf_counter() - started) * 1000)
        await _emit(
            on_event,
            "llm_end",
            {
                "round": step + 1,
                "latency_ms": latency_ms,
                "has_tool_calls": bool(response.tool_calls),
            },
        )

        if response.tool_calls:
            if step >= max_tool_rounds:
                return await finish(
                    "这次需要连续查询的内容比较多，我先停在这里。"
                    "你可以把问题拆小一点，或者直接告诉我想先看哪一部分。",
                    response.token_in,
                    response.token_out,
                    latency_ms,
                )

            wire_calls = _wire_tool_calls(response.tool_calls)
            assistant_message = _persist_assistant(
                db,
                conversation_id,
                trace_id,
                response.content or "",
                response.token_in,
                response.token_out,
                latency_ms,
                tool_calls=wire_calls,
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": response.content or None,
                    "tool_calls": wire_calls,
                }
            )

            for call in response.tool_calls:
                await _emit(
                    on_event,
                    "tool_start",
                    {"name": call.name, "arguments": call.arguments},
                )
                tool_started = time.perf_counter()
                context = ToolContext(
                    trace_id=trace_id,
                    tool_call_id=call.id,
                    idempotency_key=_idempotency_key(trace_id, call.id),
                )
                result = execute_tool(
                    db, user, call.name, call.arguments, context
                )
                tool_latency = int((time.perf_counter() - tool_started) * 1000)
                result_text = json.dumps(result, ensure_ascii=False)
                summary = _summarize(call.name, result)

                db.add(
                    AgentMessage(
                        conversation_id=conversation_id,
                        role="tool",
                        content=result_text,
                        tool_call_id=call.id,
                        trace_id=trace_id,
                        latency_ms=tool_latency,
                    )
                )
                db.add(
                    AgentToolCall(
                        trace_id=trace_id,
                        conversation_id=conversation_id,
                        message_id=assistant_message.id,
                        tool_name=call.name,
                        arguments=call.arguments,
                        result_summary=result_text[:2000],
                        status="ok" if result.get("ok") else "error",
                        error_code=(
                            None if result.get("ok") else str(result.get("code") or "")
                        ),
                        latency_ms=tool_latency,
                    )
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result_text,
                    }
                )
                events.append(
                    {
                        "name": call.name,
                        "status": "ok" if result.get("ok") else "error",
                        "summary": summary,
                        "latency_ms": tool_latency,
                    }
                )
                if result.get("ok") and call.name == "create_boarding_draft":
                    draft_id = (result.get("data") or {}).get("draft_id")
                await _emit(on_event, "tool_end", events[-1])
            db.commit()
            continue

        return await finish(
            response.content or "我暂时没有生成回答，请换个说法再试一次。",
            response.token_in,
            response.token_out,
            latency_ms,
        )

    # 理论上到不了这里，保留兜底。
    return await finish("这次对话没有顺利结束，请稍后再试。")
