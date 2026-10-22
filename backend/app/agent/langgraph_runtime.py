"""LangGraph 适配层：只替换调度，不替换业务能力。

主实现仍然是 ``app.agent.runtime.run_agent`` 的显式循环。本模块把同一套
LLM 客户端、工具、提示词、持久化与 SSE 事件放进一个 ``StateGraph``：

    START -> agent -> (有工具调用) -> tools -> agent
                   -> (没有工具调用 / 出错 / 超轮次) -> finish -> END

它用于对照实验与论文中的框架选型论证，生产默认不启用。通过
``AGENT_ENGINE=langgraph`` 或在评测里加 ``--engine langgraph`` 打开。

设计约束：
- 直接调用 ``runtime`` 模块属性，而不是 ``from ... import`` 复制名字，
  这样评测变体对 ``TOOL_DEFINITIONS`` / ``execute_tool`` / ``build_system_prompt``
  的 monkeypatch 在两种引擎下都生效。
- 不引入 checkpointer：会话历史仍由 ``agent_messages`` 表负责，
  图实例按请求构建，避免两套状态源。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agent import runtime
from app.agent.registry import ToolRegistry
from app.agent.runtime import AgentRunResult, EventSink, LLMClient, ToolCall
from app.agent.tools import ToolContext
from app.config import settings
from app.models.agent import AgentMessage, AgentToolCall
from app.models.user import User

logger = logging.getLogger(__name__)

MAX_FALLBACK_CONTENT = "这次对话没有顺利结束，请稍后再试。"
MAX_ROUNDS_CONTENT = (
    "这次需要连续查询的内容比较多，我先停在这里。"
    "你可以把问题拆小一点，或者直接告诉我想先看哪一部分。"
)
EMPTY_ANSWER_CONTENT = "我暂时没有生成回答，请换个说法再试一次。"


class AgentState(TypedDict, total=False):
    messages: list[dict]
    round: int
    pending_calls: list[dict]
    assistant_message_id: int | None
    tool_events: list[dict]
    draft_id: int | None
    final_content: str | None
    token_in: int
    token_out: int
    latency_ms: int


def _route_after_agent(state: AgentState) -> str:
    return "tools" if state.get("pending_calls") else "finish"


def build_graph(
    db: Session,
    user: User,
    conversation_id: int,
    llm: LLMClient,
    trace_id: str,
    on_event: EventSink | None = None,
    registry: ToolRegistry | None = None,
):
    """按请求构建并编译状态图；节点通过闭包拿到 db / user / llm。"""
    max_tool_rounds = max(1, settings.AGENT_MAX_TOOL_CALLS)

    def tool_definitions() -> list[dict]:
        # 运行时读取 runtime.TOOL_DEFINITIONS，评测变体的 monkeypatch 仍然生效。
        external = registry.definitions() if registry else []
        return [*runtime.TOOL_DEFINITIONS, *external]

    async def agent_node(state: AgentState) -> AgentState:
        round_no = state.get("round", 0) + 1
        messages = state["messages"]

        await runtime._emit(on_event, "llm_start", {"round": round_no})
        started = time.perf_counter()
        try:
            response = await asyncio.wait_for(
                llm.complete(messages, tool_definitions()),
                timeout=settings.AGENT_TIMEOUT_SECONDS + 5,
            )
        except asyncio.TimeoutError:
            return {
                "round": round_no,
                "final_content": runtime._friendly_failure("timeout"),
                "pending_calls": [],
            }
        except Exception:
            logger.exception("LLM 调用异常（langgraph）")
            return {
                "round": round_no,
                "final_content": runtime._friendly_failure("error"),
                "pending_calls": [],
            }

        latency_ms = int((time.perf_counter() - started) * 1000)
        await runtime._emit(
            on_event,
            "llm_end",
            {
                "round": round_no,
                "latency_ms": latency_ms,
                "has_tool_calls": bool(response.tool_calls),
            },
        )

        if response.tool_calls:
            # 与显式循环一致：第 max_tool_rounds + 1 次仍要求调用工具时停止。
            if round_no > max_tool_rounds:
                return {
                    "round": round_no,
                    "final_content": MAX_ROUNDS_CONTENT,
                    "pending_calls": [],
                    "token_in": response.token_in,
                    "token_out": response.token_out,
                    "latency_ms": latency_ms,
                }

            wire_calls = runtime._wire_tool_calls(response.tool_calls)
            assistant_message = runtime._persist_assistant(
                db,
                conversation_id,
                trace_id,
                response.content or "",
                response.token_in,
                response.token_out,
                latency_ms,
                tool_calls=wire_calls,
            )
            return {
                "round": round_no,
                "messages": [
                    *messages,
                    {
                        "role": "assistant",
                        "content": response.content or None,
                        "tool_calls": wire_calls,
                    },
                ],
                "pending_calls": [
                    {"id": call.id, "name": call.name, "arguments": call.arguments}
                    for call in response.tool_calls
                ],
                "assistant_message_id": assistant_message.id,
                "token_in": response.token_in,
                "token_out": response.token_out,
                "latency_ms": latency_ms,
            }

        return {
            "round": round_no,
            "final_content": response.content or EMPTY_ANSWER_CONTENT,
            "pending_calls": [],
            "token_in": response.token_in,
            "token_out": response.token_out,
            "latency_ms": latency_ms,
        }

    async def tools_node(state: AgentState) -> AgentState:
        messages = list(state["messages"])
        tool_events = list(state.get("tool_events") or [])
        draft_id = state.get("draft_id")
        assistant_message_id = state.get("assistant_message_id")

        for item in state.get("pending_calls") or []:
            call = ToolCall(**item)
            await runtime._emit(
                on_event,
                "tool_start",
                {"name": call.name, "arguments": call.arguments},
            )
            tool_started = time.perf_counter()
            context = ToolContext(
                trace_id=trace_id,
                tool_call_id=call.id,
                idempotency_key=runtime._idempotency_key(trace_id, call.id),
            )
            if registry and registry.handles(call.name):
                result = await registry.execute(
                    call.name, call.arguments
                )
            else:
                result = runtime.execute_tool(
                    db, user, call.name, call.arguments, context
                )
            tool_latency = int((time.perf_counter() - tool_started) * 1000)
            result_text = json.dumps(result, ensure_ascii=False)

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
                    message_id=assistant_message_id,
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
            tool_events.append(
                {
                    "name": call.name,
                    "status": "ok" if result.get("ok") else "error",
                    "summary": runtime._summarize(call.name, result),
                    "latency_ms": tool_latency,
                }
            )
            if result.get("ok") and call.name == "create_boarding_draft":
                draft_id = (result.get("data") or {}).get("draft_id")
            await runtime._emit(on_event, "tool_end", tool_events[-1])

        db.commit()
        return {
            "messages": messages,
            "pending_calls": [],
            "tool_events": tool_events,
            "draft_id": draft_id,
        }

    async def finish_node(state: AgentState) -> AgentState:
        content = state.get("final_content") or MAX_FALLBACK_CONTENT
        runtime._persist_assistant(
            db,
            conversation_id,
            trace_id,
            content,
            state.get("token_in", 0),
            state.get("token_out", 0),
            state.get("latency_ms", 0),
        )
        db.commit()
        await runtime._emit(on_event, "assistant", {"content": content})
        return {"final_content": content}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("finish", finish_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent", _route_after_agent, {"tools": "tools", "finish": "finish"}
    )
    graph.add_edge("tools", "agent")
    graph.add_edge("finish", END)
    return graph.compile()


async def run_agent(
    db: Session,
    user: User,
    conversation_id: int,
    history: list[dict],
    llm: LLMClient,
    trace_id: str,
    on_event: EventSink | None = None,
) -> AgentRunResult:
    """与 ``runtime.run_agent`` 同签名的 LangGraph 实现。"""
    registry = await runtime.load_tool_registry()
    system_prompt = runtime.build_system_prompt(user)
    if registry.definitions():
        system_prompt = (
            f"{system_prompt}\n\n{runtime.EXTERNAL_TOOL_NOTICE}"
        )
    messages = [{"role": "system", "content": system_prompt}, *history]
    initial: AgentState = {
        "messages": messages,
        "round": 0,
        "pending_calls": [],
        "assistant_message_id": None,
        "tool_events": [],
        "draft_id": None,
        "final_content": None,
        "token_in": 0,
        "token_out": 0,
        "latency_ms": 0,
    }

    compiled = build_graph(
        db=db,
        user=user,
        conversation_id=conversation_id,
        llm=llm,
        trace_id=trace_id,
        on_event=on_event,
        registry=registry,
    )
    # 每个 agent / tools / finish 节点各占一步；留出余量避免长工具链撞默认上限。
    max_steps = 2 * (max(1, settings.AGENT_MAX_TOOL_CALLS) + 2) + 5
    final_state: dict[str, Any] = await compiled.ainvoke(
        initial, config={"recursion_limit": max_steps}
    )

    return AgentRunResult(
        content=str(final_state.get("final_content") or MAX_FALLBACK_CONTENT),
        trace_id=trace_id,
        tool_events=list(final_state.get("tool_events") or []),
        draft_id=final_state.get("draft_id"),
    )
