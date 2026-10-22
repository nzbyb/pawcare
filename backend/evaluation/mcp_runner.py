"""MCP 专项评测运行器。

不调用大模型，直接检查 MCP 的协议暴露面和接入边界：
工具白名单、只读约束、身份隔离、描述注入、超时、结果上限、故障降级。

用法（在 backend 目录）：
    .venv\\Scripts\\python.exe evaluation\\mcp_runner.py --list
    .venv\\Scripts\\python.exe evaluation\\mcp_runner.py --dry-run
    .venv\\Scripts\\python.exe evaluation\\mcp_runner.py
    .venv\\Scripts\\python.exe evaluation\\mcp_runner.py --only mcp-timeout --strict

依赖演示库中的 owner / owner2 账号（scripts/seed.py）；缺失时相关用例
标记为 skipped，其余用假 Server 的用例仍然执行。
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agent.mcp_client import MCPServerConfig  # noqa: E402
from app.agent.registry import ToolRegistry  # noqa: E402

FIXTURE = BACKEND_DIR / "evaluation" / "fixtures" / "fake_mcp_server.py"
DEFAULT_CASES = BACKEND_DIR / "evaluation" / "mcp_cases.yaml"
DEFAULT_REPORT_DIR = BACKEND_DIR / "evaluation" / "reports"

PASSED = "passed"
FAILED = "failed"
SKIPPED = "skipped"


@dataclass
class CheckResult:
    case_id: str
    kind: str
    title: str
    status: str
    detail: str
    elapsed_ms: int
    error: str | None = None


def _fake_config(mode: str, name: str | None = None) -> MCPServerConfig:
    return MCPServerConfig(
        name=name or f"fake_{mode}",
        transport="stdio",
        command=sys.executable,
        args=(str(FIXTURE), "--mode", mode),
        env={"PYTHONIOENCODING": "utf-8"},
    )


def _pawcare_config(token: str) -> MCPServerConfig:
    return MCPServerConfig(
        name="pawcare",
        transport="stdio",
        command=sys.executable,
        args=("-m", "app.mcp.server", "--transport", "stdio"),
        cwd=str(BACKEND_DIR),
        env={
            "PAWCARE_MCP_TOKEN": token,
            "PYTHONPATH": str(BACKEND_DIR),
            "PYTHONIOENCODING": "utf-8",
        },
    )


def _token_for(username: str) -> str | None:
    try:
        from app.database import SessionLocal
        from app.models.user import User
        from app.utils.jwt import create_access_token

        with SessionLocal() as db:
            user = (
                db.query(User)
                .filter(User.username == username, User.status == 1)
                .first()
            )
            if user is None:
                return None
            return create_access_token(user.id, user.token_version or 0)
    except Exception as exc:  # 数据库没起时不要整份评测崩掉
        print(f"读取演示账号失败：{exc}")
        return None


def _tool_names(registry: ToolRegistry) -> set[str]:
    return {
        item["function"]["name"] for item in registry.definitions()
    }


async def _registry(
    configs: list[MCPServerConfig],
    *,
    discovery_timeout: float = 20.0,
    call_timeout: float = 8.0,
) -> ToolRegistry:
    registry = ToolRegistry(
        configs=configs,
        discovery_timeout=discovery_timeout,
        call_timeout=call_timeout,
        cache_seconds=0,
    )
    await registry.ensure_loaded()
    return registry


async def check_pawcare_discovery(params: dict) -> tuple[str, str]:
    token = _token_for("owner")
    if not token:
        return SKIPPED, "演示库缺少 owner 账号，先运行 scripts/seed.py"

    registry = await _registry([_pawcare_config(token)])
    names = _tool_names(registry)
    expected = {
        f"mcp__pawcare__{name}" for name in params["expected_tools"]
    }
    forbidden = {
        f"mcp__pawcare__{name}" for name in params.get("forbidden_tools", [])
    }

    if names & forbidden:
        return FAILED, f"暴露了写工具：{sorted(names & forbidden)}"
    if names != expected:
        return FAILED, (
            f"工具集合不符：多出 {sorted(names - expected)}，"
            f"缺少 {sorted(expected - names)}"
        )
    return PASSED, f"{len(names)} 个只读工具，写工具未暴露"


async def check_pawcare_call(params: dict) -> tuple[str, str]:
    token = _token_for("owner")
    if not token:
        return SKIPPED, "演示库缺少 owner 账号"

    registry = await _registry([_pawcare_config(token)])
    tool = f"mcp__pawcare__{params['tool']}"
    result = await registry.execute(tool, {})
    if not result.get("ok"):
        return FAILED, f"调用失败：{result.get('error')}"
    pets = (result.get("data") or {}).get("pets")
    if not isinstance(pets, list):
        return FAILED, "返回结构缺少 pets 数组"
    return PASSED, f"返回 {len(pets)} 只宠物"


async def check_isolation(params: dict) -> tuple[str, str]:
    owner_token = _token_for("owner")
    other_token = _token_for("owner2")
    if not owner_token or not other_token:
        return SKIPPED, "演示库缺少 owner / owner2 账号"

    first = await _registry([_pawcare_config(owner_token)])
    second = await _registry([_pawcare_config(other_token)])
    first_result = await first.execute("mcp__pawcare__list_my_pets", {})
    second_result = await second.execute("mcp__pawcare__list_my_pets", {})

    if not first_result.get("ok") or not second_result.get("ok"):
        return FAILED, "至少一个用户的查询失败"
    first_pets = {
        pet["name"] for pet in (first_result.get("data") or {}).get("pets", [])
    }
    second_pets = {
        pet["name"] for pet in (second_result.get("data") or {}).get("pets", [])
    }
    overlap = first_pets & second_pets
    if overlap:
        return FAILED, f"出现跨用户数据：{sorted(overlap)}"
    if not first_pets and not second_pets:
        return SKIPPED, "演示数据里两个用户都没有宠物"
    return PASSED, (
        f"owner 看到 {len(first_pets)} 只，owner2 看到 {len(second_pets)} 只，无交集"
    )


async def check_description_filter(params: dict) -> tuple[str, str]:
    mode = params["mode"]
    registry = await _registry([_fake_config(mode)])
    key = f"mcp__fake_{mode}__{params['tool']}"
    definitions = {
        item["function"]["name"]: item["function"]
        for item in registry.definitions()
    }
    if key not in definitions:
        return FAILED, f"工具未加载：{key}"

    description = definitions[key]["description"]
    marker = params["require_marker"]
    leaked = [
        term for term in params.get("forbidden_terms", []) if term in description
    ]
    if marker not in description:
        return FAILED, f"缺少过滤标记：{description[:120]}"
    if leaked:
        return FAILED, f"描述仍包含注入内容：{leaked}"
    return PASSED, "工具描述已替换为过滤提示"


async def check_write_filter(params: dict) -> tuple[str, str]:
    mode = params["mode"]
    registry = await _registry([_fake_config(mode)])
    names = _tool_names(registry)
    prefix = f"mcp__fake_{mode}__"
    required = {f"{prefix}{name}" for name in params.get("expected", [])}
    forbidden = {f"{prefix}{name}" for name in params.get("forbidden", [])}

    missing = required - names
    leaked = names & forbidden
    if missing:
        return FAILED, f"缺少只读工具：{sorted(missing)}"
    if leaked:
        return FAILED, f"写工具进入注册表：{sorted(leaked)}"
    return PASSED, "只读工具保留，破坏性写工具被过滤"


async def check_timeout(params: dict) -> tuple[str, str]:
    mode = params["mode"]
    call_timeout = float(params.get("call_timeout", 1.0))
    registry = await _registry([_fake_config(mode)], call_timeout=call_timeout)

    started = time.perf_counter()
    result = await registry.execute(
        f"mcp__fake_{mode}__{params['tool']}", {}
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    if result.get("code") != params["expect_code"]:
        return FAILED, f"期望 {params['expect_code']}，实际 {result}"
    if elapsed_ms > 5000:
        return FAILED, f"超时没有及时返回：{elapsed_ms}ms"
    return PASSED, f"{elapsed_ms}ms 返回 {params['expect_code']}"


async def check_oversized(params: dict) -> tuple[str, str]:
    mode = params["mode"]
    registry = await _registry([_fake_config(mode)])
    result = await registry.execute(f"mcp__fake_{mode}__{params['tool']}", {})

    if result.get("code") != params["expect_code"]:
        return FAILED, f"期望 {params['expect_code']}，实际 {result}"
    return PASSED, f"{params['expect_code']} 拒绝超限结果"


async def check_unreachable(params: dict) -> tuple[str, str]:
    broken = MCPServerConfig(
        name="broken",
        transport="stdio",
        command=str(BACKEND_DIR / "no-such-python.exe"),
    )
    registry = await _registry([broken], discovery_timeout=3.0)

    if registry.definitions():
        return FAILED, "不可达 Server 仍然注册了工具"
    diagnostics = registry.diagnostics()
    if not diagnostics or diagnostics[0]["status"] != "error":
        return FAILED, f"诊断信息不符合预期：{diagnostics}"
    return PASSED, "发现失败已降级，注册表为空"


async def check_namespace(params: dict) -> tuple[str, str]:
    mode = params["mode"]
    registry = await _registry([_fake_config(mode)])
    names = _tool_names(registry)

    if params["expected_name"] not in names:
        return FAILED, f"缺少命名空间后的工具：{params['expected_name']}"
    if params["local_name"] in names:
        return FAILED, "外部工具与本地工具重名，可能覆盖本地工具"
    return PASSED, "同名工具已加 mcp__ 命名空间"


async def check_partial_failure(params: dict) -> tuple[str, str]:
    broken = MCPServerConfig(
        name="broken",
        transport="stdio",
        command=str(BACKEND_DIR / "no-such-python.exe"),
    )
    registry = await _registry(
        [broken, _fake_config(params["mode"])], discovery_timeout=5.0
    )
    names = _tool_names(registry)

    if len(names) != params["expected_count"]:
        return FAILED, f"期望 {params['expected_count']} 个工具，实际 {names}"
    statuses = {item["name"]: item["status"] for item in registry.diagnostics()}
    if statuses.get("broken") != "error":
        return FAILED, f"故障 Server 诊断异常：{statuses}"
    return PASSED, "故障 Server 被隔离，其他 Server 正常加载"


HANDLERS: dict[str, Callable[[dict], Awaitable[tuple[str, str]]]] = {
    "pawcare_discovery": check_pawcare_discovery,
    "pawcare_call": check_pawcare_call,
    "isolation": check_isolation,
    "description_filter": check_description_filter,
    "write_filter": check_write_filter,
    "timeout": check_timeout,
    "oversized": check_oversized,
    "unreachable": check_unreachable,
    "namespace": check_namespace,
    "partial_failure": check_partial_failure,
}


async def run_case(case: dict) -> CheckResult:
    case_id = str(case["id"])
    kind = str(case["kind"])
    title = str(case.get("title") or kind)
    started = time.perf_counter()

    handler = HANDLERS.get(kind)
    if handler is None:
        return CheckResult(
            case_id, kind, title, FAILED, "", 0, f"未知用例类型：{kind}"
        )

    try:
        status, detail = await handler(case.get("params") or {})
        error = None
    except Exception as exc:
        status, detail, error = FAILED, "", f"{type(exc).__name__}: {exc}"

    return CheckResult(
        case_id=case_id,
        kind=kind,
        title=title,
        status=status,
        detail=detail,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        error=error,
    )


async def run_all(cases: list[dict]) -> list[CheckResult]:
    return [await run_case(case) for case in cases]


def load_cases(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("用例文件缺少 cases 数组")

    seen: set[str] = set()
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"第 {index} 条用例不是对象")
        for key in ("id", "kind"):
            if not case.get(key):
                raise ValueError(f"第 {index} 条用例缺少 {key}")
        if case["kind"] not in HANDLERS:
            raise ValueError(f"用例 {case['id']} 的类型未知：{case['kind']}")
        if case["id"] in seen:
            raise ValueError(f"用例 id 重复：{case['id']}")
        seen.add(case["id"])
    return cases


def write_report(
    results: list[CheckResult], report_dir: Path
) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = report_dir / f"mcp_eval_{stamp}.json"
    csv_path = report_dir / f"mcp_eval_{stamp}.csv"

    summary = {
        "total": len(results),
        "passed": sum(1 for item in results if item.status == PASSED),
        "failed": sum(1 for item in results if item.status == FAILED),
        "skipped": sum(1 for item in results if item.status == SKIPPED),
    }
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "checks": [asdict(item) for item in results],
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "case_id",
                "kind",
                "title",
                "status",
                "detail",
                "elapsed_ms",
                "error",
            ]
        )
        for item in results:
            writer.writerow(
                [
                    item.case_id,
                    item.kind,
                    item.title,
                    item.status,
                    item.detail,
                    item.elapsed_ms,
                    item.error or "",
                ]
            )
    return json_path, csv_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PawCare MCP 专项评测")
    parser.add_argument(
        "--cases", default=str(DEFAULT_CASES), help="YAML 用例路径"
    )
    parser.add_argument(
        "--only", action="append", default=[], help="只跑指定 id，可重复"
    )
    parser.add_argument("--list", action="store_true", help="列出用例")
    parser.add_argument(
        "--dry-run", action="store_true", help="只校验用例文件，不执行"
    )
    parser.add_argument(
        "--no-report", action="store_true", help="不写 JSON / CSV 报告"
    )
    parser.add_argument(
        "--report-dir", default=str(DEFAULT_REPORT_DIR), help="报告输出目录"
    )
    parser.add_argument(
        "--strict", action="store_true", help="有失败用例时返回非零退出码"
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    try:
        cases = load_cases(Path(args.cases))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"用例校验失败：{exc}")
        return 2

    if args.only:
        wanted = set(args.only)
        cases = [case for case in cases if case["id"] in wanted]
    if not cases:
        print("没有匹配的用例。")
        return 2

    if args.list:
        for case in cases:
            print(f"{case['id']:<24} [{case['kind']}] {case.get('title', '')}")
        return 0

    if args.dry_run:
        print(f"用例校验通过：{len(cases)} 条")
        return 0

    results = asyncio.run(run_all(cases))

    for item in results:
        icon = {PASSED: "PASS", FAILED: "FAIL", SKIPPED: "SKIP"}[item.status]
        print(
            f"[{icon}] {item.case_id:<24} {item.elapsed_ms:>5}ms  "
            f"{item.detail or item.error or ''}"
        )

    summary = {
        PASSED: sum(1 for item in results if item.status == PASSED),
        FAILED: sum(1 for item in results if item.status == FAILED),
        SKIPPED: sum(1 for item in results if item.status == SKIPPED),
    }
    print(
        f"通过 {summary[PASSED]} / 失败 {summary[FAILED]} / "
        f"跳过 {summary[SKIPPED]}，共 {len(results)} 条"
    )

    if not args.no_report:
        json_path, csv_path = write_report(results, Path(args.report_dir))
        print(f"报告：{json_path}")
        print(f"      {csv_path}")

    if args.strict and summary[FAILED]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
