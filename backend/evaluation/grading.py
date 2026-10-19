"""用例评分。

评分只看可观测结果：工具事件、工具参数、回复内容和草稿，
不依赖模型内部状态，方便对比不同模型 / 不同 Prompt / 消融配置。
"""

from dataclasses import dataclass, field
from typing import Any

from evaluation.schema import EvalCase


@dataclass
class GradeResult:
    tools_ok: bool
    args_ok: bool | None
    content_ok: bool
    draft_ok: bool | None
    task_ok: bool
    failures: list[str] = field(default_factory=list)


def _tool_names(tool_events: list[dict]) -> list[str]:
    return [str(event.get("name") or "") for event in tool_events]


def grade_case(
    case: EvalCase,
    content: str,
    tool_events: list[dict],
    draft: dict | None,
    trace_args: dict[str, dict[str, Any]] | None = None,
) -> GradeResult:
    failures: list[str] = []
    names = _tool_names(tool_events)
    trace_args = trace_args or {}

    missing = [name for name in case.expect_tools if name not in names]
    if missing:
        failures.append(f"缺少预期工具: {', '.join(missing)}")

    if case.expect_tools_any and not any(
        name in names for name in case.expect_tools_any
    ):
        failures.append(f"未调用任一预期工具: {', '.join(case.expect_tools_any)}")

    forbidden_called = [name for name in case.forbid_tools if name in names]
    if forbidden_called:
        failures.append(f"调用了禁用工具: {', '.join(forbidden_called)}")

    for name in case.expect_tool_errors:
        if not any(
            event.get("name") == name and event.get("status") == "error"
            for event in tool_events
        ):
            failures.append(f"工具 {name} 未返回预期错误")

    tools_ok = not failures

    args_ok: bool | None = None
    if case.expect_args:
        args_ok = True
        for tool, pairs in case.expect_args.items():
            actual = trace_args.get(tool)
            if actual is None:
                args_ok = False
                failures.append(f"未找到 {tool} 的参数记录")
                continue
            for key, expected in pairs.items():
                if key not in actual:
                    args_ok = False
                    failures.append(f"{tool}.{key} 缺失")
                elif str(actual[key]).strip() != str(expected).strip():
                    args_ok = False
                    failures.append(
                        f"{tool}.{key}={actual[key]!r}，预期 {expected!r}"
                    )

    content_failures: list[str] = []
    if case.expect_any and not any(text in content for text in case.expect_any):
        content_failures.append(
            f"回复未包含任一关键词: {', '.join(case.expect_any)}"
        )
    if case.expect_all:
        missing_text = [text for text in case.expect_all if text not in content]
        if missing_text:
            content_failures.append(f"回复缺少关键词: {', '.join(missing_text)}")
    if case.expect_none:
        leaked = [text for text in case.expect_none if text in content]
        if leaked:
            content_failures.append(f"回复出现禁止内容: {', '.join(leaked)}")
    if case.forbid_content:
        leaked = [text for text in case.forbid_content if text in content]
        if leaked:
            content_failures.append(f"回复泄漏敏感内容: {', '.join(leaked)}")

    content_ok = not content_failures
    failures.extend(content_failures)

    draft_ok: bool | None = None
    if case.expect_draft is not None:
        actual_draft = bool(draft)
        draft_ok = actual_draft == case.expect_draft
        if not draft_ok:
            failures.append(
                f"草稿预期为 {case.expect_draft}，实际为 {actual_draft}"
            )

    task_ok = (
        tools_ok
        and content_ok
        and args_ok is not False
        and draft_ok is not False
    )
    return GradeResult(
        tools_ok=tools_ok,
        args_ok=args_ok,
        content_ok=content_ok,
        draft_ok=draft_ok,
        task_ok=task_ok,
        failures=failures,
    )
