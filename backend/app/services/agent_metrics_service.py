"""Agent 运行可观测：工具成功率、延迟分位、token 与成本、失败 trace 回放。

数据全部来自运行时已经落库的 `agent_messages` / `agent_tool_calls`，
这里只读不写，不改动 Agent 循环本身。成本按配置的单价估算，单价留 0 时
明确显示「未配置」，避免展示一个编出来的价格。
"""

import math
from datetime import date, datetime, time, timedelta

from sqlalchemy import case as sql_case
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.config import settings
from app.models.agent import AgentConversation, AgentMessage, AgentToolCall
from app.models.user import User

MAX_DAYS = 90
MAX_PAGE_SIZE = 50
# 分位数只需要一个近似值，取最近一段样本即可，避免把整表 latency 读进内存。
LATENCY_SAMPLE = 5000
FAILURE_LIMIT = 8


def _range(days: int) -> tuple[date, date, datetime]:
    days = min(max(1, days), MAX_DAYS)
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    return start_date, end_date, datetime.combine(start_date, time.min)


def _percentile(values: list[int], ratio: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    # 最近秩法：p95 取第 ceil(0.95 * n) 个样本。
    index = min(len(ordered) - 1, max(0, math.ceil(ratio * len(ordered)) - 1))
    return int(ordered[index])


def _rate(part: int, total: int) -> float | None:
    if not total:
        return None
    return round(part * 100 / total, 2)


def _cost(token_in: int, token_out: int) -> dict:
    price_in = max(0.0, float(settings.LLM_PRICE_INPUT_PER_M or 0))
    price_out = max(0.0, float(settings.LLM_PRICE_OUTPUT_PER_M or 0))
    cost_in = token_in / 1_000_000 * price_in
    cost_out = token_out / 1_000_000 * price_out
    return {
        "input": round(cost_in, 4),
        "output": round(cost_out, 4),
        "total": round(cost_in + cost_out, 4),
        "configured": bool(price_in or price_out),
        "price_input_per_m": price_in,
        "price_output_per_m": price_out,
    }


def _date_key(value) -> str:
    return str(value)[:10]


def overview(db: Session, days: int = 7) -> dict:
    """面板顶部指标 + 每日趋势 + 按工具聚合 + 错误码分布 + 最近失败。"""
    start_date, end_date, start_at = _range(days)

    message_scope = db.query(AgentMessage).filter(AgentMessage.create_time >= start_at)
    turn_count = message_scope.filter(AgentMessage.role == "assistant").count()
    conversation_count = (
        db.query(func.count(func.distinct(AgentMessage.conversation_id)))
        .filter(AgentMessage.create_time >= start_at)
        .scalar()
        or 0
    )
    token_in, token_out = db.query(
        func.coalesce(func.sum(AgentMessage.token_in), 0),
        func.coalesce(func.sum(AgentMessage.token_out), 0),
    ).filter(AgentMessage.create_time >= start_at).one()

    call_scope = db.query(AgentToolCall).filter(AgentToolCall.create_time >= start_at)
    call_count = call_scope.count()
    error_count = call_scope.filter(AgentToolCall.status != "ok").count()
    tool_latencies = [
        int(row[0])
        for row in db.query(AgentToolCall.latency_ms)
        .filter(
            AgentToolCall.create_time >= start_at,
            AgentToolCall.latency_ms.isnot(None),
        )
        .order_by(AgentToolCall.id.desc())
        .limit(LATENCY_SAMPLE)
        .all()
    ]
    turn_latencies = [
        int(row[0])
        for row in db.query(AgentMessage.latency_ms)
        .filter(
            AgentMessage.create_time >= start_at,
            AgentMessage.role == "assistant",
            AgentMessage.latency_ms.isnot(None),
        )
        .order_by(AgentMessage.id.desc())
        .limit(LATENCY_SAMPLE)
        .all()
    ]

    tool_rows = (
        db.query(
            AgentToolCall.tool_name,
            func.count(AgentToolCall.id),
            func.coalesce(
                func.sum(sql_case((AgentToolCall.status != "ok", 1), else_=0)), 0
            ),
            func.avg(AgentToolCall.latency_ms),
            func.max(AgentToolCall.latency_ms),
        )
        .filter(AgentToolCall.create_time >= start_at)
        .group_by(AgentToolCall.tool_name)
        .order_by(func.count(AgentToolCall.id).desc())
        .all()
    )
    tools = [
        {
            "tool_name": name,
            "calls": int(calls),
            "errors": int(errors),
            "success_rate": _rate(int(calls) - int(errors), int(calls)),
            "avg_latency_ms": round(float(avg or 0)),
            "max_latency_ms": int(max_latency or 0),
        }
        for name, calls, errors, avg, max_latency in tool_rows
    ]

    error_codes = [
        {"error_code": code or "unknown", "count": int(count)}
        for code, count in db.query(AgentToolCall.error_code, func.count(AgentToolCall.id))
        .filter(
            AgentToolCall.create_time >= start_at,
            AgentToolCall.status != "ok",
        )
        .group_by(AgentToolCall.error_code)
        .order_by(func.count(AgentToolCall.id).desc())
        .all()
    ]

    recent_failures = [
        {
            "id": row.id,
            "trace_id": row.trace_id,
            "conversation_id": row.conversation_id,
            "tool_name": row.tool_name,
            "error_code": row.error_code,
            "latency_ms": row.latency_ms,
            "create_time": row.create_time,
        }
        for row in call_scope.filter(AgentToolCall.status != "ok")
        .order_by(AgentToolCall.id.desc())
        .limit(FAILURE_LIMIT)
        .all()
    ]

    # 每日趋势：消息和工具调用分开聚合，再按日期合并，避免多表 join 放大计数。
    daily: dict[str, dict] = {
        (start_date + timedelta(days=offset)).isoformat(): {
            "date": (start_date + timedelta(days=offset)).isoformat(),
            "turns": 0,
            "tool_calls": 0,
            "tool_errors": 0,
            "token_in": 0,
            "token_out": 0,
        }
        for offset in range((end_date - start_date).days + 1)
    }
    for day, turns, day_in, day_out in (
        db.query(
            func.date(AgentMessage.create_time),
            func.count(AgentMessage.id),
            func.coalesce(func.sum(AgentMessage.token_in), 0),
            func.coalesce(func.sum(AgentMessage.token_out), 0),
        )
        .filter(
            AgentMessage.create_time >= start_at,
            AgentMessage.role == "assistant",
        )
        .group_by(func.date(AgentMessage.create_time))
        .all()
    ):
        bucket = daily.get(_date_key(day))
        if bucket is not None:
            bucket["turns"] = int(turns)
            bucket["token_in"] = int(day_in or 0)
            bucket["token_out"] = int(day_out or 0)
    for day, calls, errors in (
        db.query(
            func.date(AgentToolCall.create_time),
            func.count(AgentToolCall.id),
            func.coalesce(
                func.sum(sql_case((AgentToolCall.status != "ok", 1), else_=0)), 0
            ),
        )
        .filter(AgentToolCall.create_time >= start_at)
        .group_by(func.date(AgentToolCall.create_time))
        .all()
    ):
        bucket = daily.get(_date_key(day))
        if bucket is not None:
            bucket["tool_calls"] = int(calls)
            bucket["tool_errors"] = int(errors or 0)

    token_in = int(token_in or 0)
    token_out = int(token_out or 0)
    return {
        "range": {
            "days": (end_date - start_date).days + 1,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "conversations": int(conversation_count),
        "turns": turn_count,
        "tool_calls": call_count,
        "tool_errors": error_count,
        "tool_success_rate": _rate(call_count - error_count, call_count),
        "tool_latency_p95_ms": _percentile(tool_latencies, 0.95),
        "tool_latency_p50_ms": _percentile(tool_latencies, 0.5),
        "turn_latency_p95_ms": _percentile(turn_latencies, 0.95),
        "tokens": {"input": token_in, "output": token_out, "total": token_in + token_out},
        "cost": _cost(token_in, token_out),
        "daily": list(daily.values()),
        "tools": tools,
        "error_codes": error_codes,
        "recent_failures": recent_failures,
    }


def _call_payload(row: AgentToolCall) -> dict:
    return {
        "id": row.id,
        "trace_id": row.trace_id,
        "conversation_id": row.conversation_id,
        "message_id": row.message_id,
        "tool_name": row.tool_name,
        "arguments": row.arguments,
        "result_summary": row.result_summary,
        "status": row.status,
        "error_code": row.error_code,
        "latency_ms": row.latency_ms,
        "create_time": row.create_time,
    }


def list_tool_calls(
    db: Session,
    *,
    status: str | None = None,
    tool_name: str | None = None,
    keyword: str | None = None,
    days: int = 30,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """工具调用明细，支持按状态、工具名和 trace_id 过滤。"""
    _, _, start_at = _range(days)
    page = max(1, page)
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)

    query = db.query(AgentToolCall).filter(AgentToolCall.create_time >= start_at)
    if status in ("ok", "error"):
        query = query.filter(AgentToolCall.status == status)
    if tool_name:
        query = query.filter(AgentToolCall.tool_name == tool_name)
    if keyword:
        query = query.filter(AgentToolCall.trace_id.contains(keyword.strip()))

    total = query.count()
    rows = (
        query.order_by(AgentToolCall.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for row in rows:
        item = _call_payload(row)
        # 列表只放结果摘要，完整参数和结果在 trace 回放里看。
        item["result_summary"] = (row.result_summary or "")[:300] or None
        items.append(item)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def trace_detail(db: Session, trace_id: str) -> dict:
    """一次对话轮次的完整回放：消息按时间顺序 + 工具调用。"""
    trace_id = (trace_id or "").strip()
    if not trace_id:
        raise BusinessException(message="trace_id 不能为空", code=404)

    messages = (
        db.query(AgentMessage)
        .filter(AgentMessage.trace_id == trace_id)
        .order_by(AgentMessage.id.asc())
        .all()
    )
    calls = (
        db.query(AgentToolCall)
        .filter(AgentToolCall.trace_id == trace_id)
        .order_by(AgentToolCall.id.asc())
        .all()
    )
    if not messages and not calls:
        raise BusinessException(message="trace 不存在", code=404)

    conversation_id = next(
        (item.conversation_id for item in messages if item.conversation_id),
        None,
    ) or next((item.conversation_id for item in calls if item.conversation_id), None)
    conversation = None
    if conversation_id:
        row = (
            db.query(AgentConversation, User)
            .join(User, User.id == AgentConversation.user_id)
            .filter(AgentConversation.id == conversation_id)
            .first()
        )
        if row:
            conversation = {
                "id": row[0].id,
                "title": row[0].title,
                "user_id": row[1].id,
                "username": row[1].username,
                "nickname": row[1].nickname,
                "role": row[1].role,
            }

    token_in = sum(int(item.token_in or 0) for item in messages)
    token_out = sum(int(item.token_out or 0) for item in messages)
    return {
        "trace_id": trace_id,
        "conversation": conversation,
        "messages": [
            {
                "id": item.id,
                "role": item.role,
                "content": item.content,
                "tool_calls": item.tool_calls,
                "tool_call_id": item.tool_call_id,
                "latency_ms": item.latency_ms,
                "token_in": item.token_in,
                "token_out": item.token_out,
                "create_time": item.create_time,
            }
            for item in messages
        ],
        "tool_calls": [_call_payload(row) for row in calls],
        "summary": {
            "status": "error"
            if any(row.status != "ok" for row in calls)
            else "ok",
            "tool_calls": len(calls),
            "errors": sum(1 for row in calls if row.status != "ok"),
            "latency_ms": sum(int(row.latency_ms or 0) for row in calls),
            "token_in": token_in,
            "token_out": token_out,
        },
    }
