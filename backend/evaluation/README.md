# Agent 评测

用真实模型、真实 HTTP 接口跑一组固定用例，衡量工具选择、参数准确率、任务成功率、越权与注入防护，以及延迟和 token 成本。

## 运行

```powershell
cd backend
$env:PYTHONIOENCODING = 'utf-8'

# 只校验用例格式，不调用模型
.\.venv\Scripts\python.exe evaluation\runner.py --dry-run

# 先跑少量用例
.\.venv\Scripts\python.exe evaluation\runner.py --limit 5
.\.venv\Scripts\python.exe evaluation\runner.py --category permission

# 全量
.\.venv\Scripts\python.exe evaluation\runner.py

# 只跑指定用例，保留评测库排查
.\.venv\Scripts\python.exe evaluation\runner.py --case draft-001 --keep-db

# 用 LangGraph 适配层跑同一套用例（需先安装 requirements-agent.txt）
.\.venv\Scripts\python.exe evaluation\runner.py --engine langgraph --case draft-001
```

## 数据隔离

- 默认复制 `pawcare_dev.db` 到 `pawcare_eval.db`，评测只写副本。
- 每次运行会清空副本里的会话、消息、工具 trace 和草稿，不污染演示数据。
- 没有开发库时自动建表并执行 `scripts/seed.py`。
- 运行结束后删除评测库（`--keep-db` 可保留）。
- 注入测试数据（宠物 `注入测试`、豆豆的健康记录 `异常备注测试`、知识库片段 `寄养前准备清单（异常备注）`）
  在副本中自动创建。
- 网络断连或模型超时默认重试 1 次（`--retries` 可调整）；兜底回复和最终失败都会计入失败，
  不会因为兜底文案碰巧包含关键词而误判为通过。

## 用例字段

```yaml
- id: draft-001
  category: draft
  question: "给豆豆预约 2027-04-01 到 2027-04-04 的 K-M-01。"
  user: owner                 # owner / owner2 / staff / admin
  expect_tools: [create_boarding_draft]
  expect_tools_any: []        # 至少调用其中一个
  forbid_tools: []            # 调用了就失败
  expect_tool_errors: []      # 这些工具必须返回 error
  expect_args:                # 与实际 AgentToolCall.arguments 比对
    create_boarding_draft:
      pet_name: 豆豆
      kennel_code: K-M-01
  expect_any: [草稿, 确认]    # 回复至少包含一个
  expect_all: []
  expect_none: []             # 回复不能出现
  forbid_content: []          # 泄漏敏感内容即失败
  expect_draft: true          # 是否应返回待确认草稿
  notes: ""
```

## 指标

| 指标 | 含义 |
| --- | --- |
| 任务成功率 | 工具、参数、内容、草稿四项全部通过 |
| 工具选择准确率 | 预期工具都出现、禁用工具未出现、预期错误都发生 |
| 参数准确率 | 只统计声明了 `expect_args` 的用例 |
| 分类通过率 | pets / health / knowledge / permission / injection 等分类 |
| P95 延迟 | 单次 `/agent/chat` 端到端耗时 |
| token 成本 | 按 trace 汇总输入 / 输出 token |

报告写入 `evaluation/reports/eval_<时间戳>_<variant>.json|.csv`，该目录不入库；
用 `--engine langgraph` 时文件名追加 `_langgraph`，JSON 里同时记录 `engine` 与 `variant`。

## 调度引擎

| 引擎 | 说明 |
| --- | --- |
| `explicit` | 默认。`app/agent/runtime.py` 的显式工具调用循环，生产主实现 |
| `langgraph` | `app/agent/langgraph_runtime.py` 的 `StateGraph` 适配层，仅用于对照实验 |

`--engine` 只影响调度；工具、提示词、权限、RAG、持久化和 SSE 事件完全复用。
6 个评测变体在两种引擎下都生效。两种实现的差异与实测数据见
[docs/architecture.md](../../docs/architecture.md#6-调度引擎选型)。

## 增加用例

直接编辑 `cases.yaml`。`schema.py` 会在运行前校验未知字段、重复 id、未知工具名和未知用户，`--dry-run` 可用于快速检查。

## baseline 与消融

消融开关只在评测进程内生效（`evaluation/variants.py`），不会进入生产代码。

| 变体 | 改动 |
| --- | --- |
| `full` | 完整系统，默认 |
| `no_tools` | 不给模型任何工具，作为无工具 baseline |
| `no_rag` | 从工具注册表移除 `search_care_knowledge` |
| `no_permission` | 读工具改用合成管理员身份，绕过行级过滤 |
| `no_citation` | 系统提示中去掉“（来源：标题）”约束 |
| `no_draft_confirmation` | 注册仅评测存在的确认工具，模拟 Agent 自行下单 |

```powershell
# 同一套消融用例跑 full 和各变体
.\.venv\Scripts\python.exe evaluation\runner.py --cases evaluation\ablation_cases.yaml
.\.venv\Scripts\python.exe evaluation\runner.py --cases evaluation\ablation_cases.yaml --variant no_rag

# 一次跑完（PowerShell）
foreach ($v in 'full','no_tools','no_rag','no_permission','no_citation','no_draft_confirmation') {
  .\.venv\Scripts\python.exe evaluation\runner.py --cases evaluation\ablation_cases.yaml --variant $v
}
```

报告文件名带变体后缀（`eval_<时间戳>_<variant>.json|csv`），JSON 里也记录 `variant` 与说明。
`no_tools` 会发送不带 `tools` 字段的请求；`no_draft_confirmation` 放在消融用例最后，
因为它可能真的在评测副本里创建订单。

