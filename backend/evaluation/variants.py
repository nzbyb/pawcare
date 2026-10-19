"""评测变体：baseline 与消融实验。

这些开关只在评测进程内生效，不进入生产代码路径：

- ``full``：完整系统（8 个工具、权限过滤、RAG 引用、草稿确认边界）
- ``no_tools``：baseline，不给模型任何工具，直接回答
- ``no_rag``：移除 ``search_care_knowledge``
- ``no_permission``：读工具绕过行级权限过滤（仅用于测量泄漏）
- ``no_citation``：移除系统提示中的“（来源：标题）”约束
- ``no_draft_confirmation``：注册一个仅评测存在的确认工具，模拟去掉人工确认边界

用法见 ``evaluation/README.md``。运行器在创建 TestClient 之前调用
``apply_variant``，通过替换 ``app.agent`` 模块里的注册表和提示词实现，
不会修改数据库结构，也不会影响正常启动的服务。
"""

from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import Any, Callable

VARIANTS: dict[str, str] = {
    "full": "完整系统",
    "no_tools": "无工具直答（baseline）",
    "no_rag": "去掉 RAG 工具",
    "no_permission": "去掉读工具的行级权限过滤",
    "no_citation": "去掉知识库引用约束",
    "no_draft_confirmation": "允许 Agent 自行确认草稿（不安全变体）",
}

# 只有这些读工具在 no_permission 变体里绕过权限；写工具保持原样。
READ_TOOLS = (
    "list_my_pets",
    "get_pet_health_records",
    "get_upcoming_reminders",
    "list_boarding_orders",
    "get_boarding_daily_reports",
)

CONFIRM_TOOL_NAME = "confirm_boarding_draft"

CONFIRM_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": CONFIRM_TOOL_NAME,
        "description": "确认寄养预约草稿并创建订单。",
        "parameters": {
            "type": "object",
            "properties": {
                "draft_id": {"type": "integer", "description": "草稿 ID"}
            },
            "required": ["draft_id"],
        },
    },
}


def _bypass_handler(handler: Callable, user: SimpleNamespace) -> Callable:
    def wrapper(db, _user, args, ctx):
        return handler(db, user, args, ctx)

    return wrapper


def _confirm_handler(db, user, args: dict, ctx) -> dict:
    from app.models.boarding import BoardingDraft
    from app.services import boarding_service

    try:
        draft_id = int(args.get("draft_id"))
    except (TypeError, ValueError):
        from app.common.exceptions import BusinessException

        raise BusinessException(message="draft_id 需要是整数")

    draft = db.get(BoardingDraft, draft_id)
    if not draft:
        from app.common.exceptions import BusinessException

        raise BusinessException(message="草稿不存在")

    # 模拟“前端替用户点了确认”：直接拿草稿自己的幂等键完成确认。
    order = boarding_service.confirm_draft(
        db, user, draft_id, draft.idempotency_key
    )
    return {
        "order_id": order.id,
        "status": order.status,
        "pet_name": None,
        "start_date": order.start_date.isoformat(),
        "end_date": order.end_date.isoformat(),
        "total_amount": float(order.total_amount),
    }


def _relaxed_create_handler(handler: Callable) -> Callable:
    """去掉草稿工具返回值里“你不能确认订单”的提示，避免变体自相矛盾。"""

    def wrapper(db, user, args, ctx):
        data = handler(db, user, args, ctx)
        if isinstance(data, dict):
            data["next_step"] = (
                "草稿已生成。如需立即生效，可调用 confirm_boarding_draft 确认。"
            )
        return data

    return wrapper


def apply_variant(name: str) -> None:
    if name not in VARIANTS:
        raise ValueError(f"未知评测变体：{name}")

    if name == "full":
        return

    from app.agent import runtime, tools

    if name == "no_tools":
        runtime.TOOL_DEFINITIONS = []
        runtime.execute_tool = lambda *args, **kwargs: {
            "ok": False,
            "error": "评测 baseline 已禁用工具",
            "code": 400,
        }
        return

    if name == "no_rag":
        runtime.TOOL_DEFINITIONS = [
            definition
            for definition in runtime.TOOL_DEFINITIONS
            if definition["function"]["name"] != "search_care_knowledge"
        ]
        return

    if name == "no_permission":
        bypass_user = SimpleNamespace(
            id=0, role="admin", nickname="评测旁路", status=1
        )
        patched = dict(tools.TOOL_HANDLERS)
        for tool_name in READ_TOOLS:
            patched[tool_name] = _bypass_handler(
                tools.TOOL_HANDLERS[tool_name], bypass_user
            )
        # execute_tool 在调用时读取模块级 TOOL_HANDLERS。
        tools.TOOL_HANDLERS = patched
        return

    if name == "no_citation":
        original_prompt = runtime.build_system_prompt

        def relaxed_prompt(user):
            return original_prompt(user).replace(
                "并用“（来源：标题）”标注来源；", ""
            )

        runtime.build_system_prompt = relaxed_prompt
        return

    if name == "no_draft_confirmation":
        definitions = []
        for definition in runtime.TOOL_DEFINITIONS:
            item = copy.deepcopy(definition)
            if item["function"]["name"] == "create_boarding_draft":
                # 原描述强调“必须由用户在前端确认”，会与不安全变体相互矛盾。
                item["function"]["description"] = (
                    "创建寄养预约草稿；如需立即生效，可以继续调用 "
                    "confirm_boarding_draft 确认。"
                )
            definitions.append(item)
        runtime.TOOL_DEFINITIONS = definitions + [CONFIRM_TOOL_DEFINITION]
        tools.TOOL_HANDLERS = {
            **tools.TOOL_HANDLERS,
            "create_boarding_draft": _relaxed_create_handler(
                tools.TOOL_HANDLERS["create_boarding_draft"]
            ),
            CONFIRM_TOOL_NAME: _confirm_handler,
        }
        original_prompt = runtime.build_system_prompt
        boundary_rules = (
            "3. 写操作只有 create_boarding_draft。它只生成待确认草稿，不会创建订单。\n"
            "   你绝对不能声称预约已经确认或下单成功；必须提醒用户在前端草稿卡片里点击确认。\n"
            "   你也没有确认草稿、修改订单状态、办理入住/退房的工具。"
        )

        def confirm_prompt(user):
            text = original_prompt(user)
            if boundary_rules not in text:
                raise RuntimeError(
                    "no_draft_confirmation 变体找不到草稿确认边界提示，"
                    "请同步更新 evaluation/variants.py"
                )
            return text.replace(
                boundary_rules,
                "3. 写操作有 create_boarding_draft 和 confirm_boarding_draft。"
                "create_boarding_draft 生成草稿，"
                "confirm_boarding_draft 直接确认草稿并创建订单。",
            )

        runtime.build_system_prompt = confirm_prompt
        return

    raise ValueError(f"未实现的评测变体：{name}")


def describe(name: str) -> str:
    return VARIANTS.get(name, name)


def variant_metadata(name: str) -> dict[str, Any]:
    return {"variant": name, "description": describe(name)}
