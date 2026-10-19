"""评测用例的加载与校验。

用例全部写在 YAML 里，方便论文阶段扩充和做消融实验。
这里不导入 app，保证 `--dry-run` 可以脱离数据库和模型运行。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

KNOWN_TOOLS = frozenset(
    {
        "list_my_pets",
        "get_pet_health_records",
        "get_upcoming_reminders",
        "check_kennel_availability",
        "create_boarding_draft",
        "list_boarding_orders",
        "get_boarding_daily_reports",
        "search_care_knowledge",
    }
)

KNOWN_USERS = frozenset({"owner", "owner2", "staff", "admin"})

KNOWN_CATEGORIES = frozenset(
    {
        "pets",
        "health",
        "reminders",
        "availability",
        "draft",
        "orders",
        "reports",
        "knowledge",
        "permission",
        "refusal",
        "injection",
    }
)

CASE_FIELDS = frozenset(
    {
        "id",
        "category",
        "question",
        "user",
        "expect_tools",
        "expect_tools_any",
        "forbid_tools",
        "expect_tool_errors",
        "expect_args",
        "expect_any",
        "expect_all",
        "expect_none",
        "forbid_content",
        "expect_draft",
        "notes",
    }
)


class CaseError(ValueError):
    """用例格式错误。"""


@dataclass(frozen=True)
class EvalCase:
    id: str
    category: str
    question: str
    user: str = "owner"
    expect_tools: tuple[str, ...] = ()
    expect_tools_any: tuple[str, ...] = ()
    forbid_tools: tuple[str, ...] = ()
    expect_tool_errors: tuple[str, ...] = ()
    expect_args: dict[str, dict[str, Any]] = field(default_factory=dict)
    expect_any: tuple[str, ...] = ()
    expect_all: tuple[str, ...] = ()
    expect_none: tuple[str, ...] = ()
    forbid_content: tuple[str, ...] = ()
    expect_draft: bool | None = None
    notes: str | None = None


def _as_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise CaseError(f"{field_name} 必须是字符串列表")
    return tuple(value)


def _as_args(value: Any) -> dict[str, dict[str, Any]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise CaseError("expect_args 必须是对象")
    result: dict[str, dict[str, Any]] = {}
    for tool, pairs in value.items():
        if tool not in KNOWN_TOOLS:
            raise CaseError(f"expect_args 中出现未知工具：{tool}")
        if not isinstance(pairs, dict):
            raise CaseError(f"expect_args.{tool} 必须是对象")
        result[tool] = pairs
    return result


def load_cases(path: Path) -> list[EvalCase]:
    if not path.exists():
        raise CaseError(f"用例文件不存在：{path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise CaseError("用例文件顶层必须是对象")
    defaults = raw.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise CaseError("defaults 必须是对象")
    items = raw.get("cases") or []
    if not isinstance(items, list) or not items:
        raise CaseError("cases 必须是非空列表")

    cases: list[EvalCase] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise CaseError(f"第 {index} 条用例必须是对象")
        merged = {**defaults, **item}
        unknown = set(merged) - CASE_FIELDS
        if unknown:
            raise CaseError(f"第 {index} 条用例包含未知字段：{sorted(unknown)}")

        case_id = str(merged.get("id") or "").strip()
        if not case_id:
            raise CaseError(f"第 {index} 条用例缺少 id")
        if case_id in seen_ids:
            raise CaseError(f"用例 id 重复：{case_id}")
        seen_ids.add(case_id)

        category = str(merged.get("category") or "").strip()
        if category not in KNOWN_CATEGORIES:
            raise CaseError(f"{case_id}: category 不支持 {category!r}")

        question = str(merged.get("question") or "").strip()
        if not question:
            raise CaseError(f"{case_id}: question 不能为空")

        user = str(merged.get("user") or "owner").strip()
        if user not in KNOWN_USERS:
            raise CaseError(f"{case_id}: user 不支持 {user!r}")

        expect_tools = _as_tuple(merged.get("expect_tools"), f"{case_id}.expect_tools")
        expect_tools_any = _as_tuple(
            merged.get("expect_tools_any"), f"{case_id}.expect_tools_any"
        )
        expect_tool_errors = _as_tuple(
            merged.get("expect_tool_errors"), f"{case_id}.expect_tool_errors"
        )
        for name in expect_tools + expect_tools_any + expect_tool_errors:
            if name not in KNOWN_TOOLS:
                raise CaseError(f"{case_id}: 未知工具 {name!r}")

        expect_draft = merged.get("expect_draft")
        if expect_draft is not None and not isinstance(expect_draft, bool):
            raise CaseError(f"{case_id}: expect_draft 必须是布尔值")

        cases.append(
            EvalCase(
                id=case_id,
                category=category,
                question=question,
                user=user,
                expect_tools=expect_tools,
                expect_tools_any=expect_tools_any,
                forbid_tools=_as_tuple(
                    merged.get("forbid_tools"), f"{case_id}.forbid_tools"
                ),
                expect_tool_errors=expect_tool_errors,
                expect_args=_as_args(merged.get("expect_args")),
                expect_any=_as_tuple(merged.get("expect_any"), f"{case_id}.expect_any"),
                expect_all=_as_tuple(merged.get("expect_all"), f"{case_id}.expect_all"),
                expect_none=_as_tuple(
                    merged.get("expect_none"), f"{case_id}.expect_none"
                ),
                forbid_content=_as_tuple(
                    merged.get("forbid_content"), f"{case_id}.forbid_content"
                ),
                expect_draft=expect_draft,
                notes=(
                    str(merged["notes"]) if merged.get("notes") is not None else None
                ),
            )
        )
    return cases
