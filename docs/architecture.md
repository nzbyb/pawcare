# PawCare 架构说明

## 1. 分层

```text
Vue3 + TS + Naive UI
        │ HTTP / SSE
        ▼
FastAPI + JWT + RBAC
        │
        ├── 业务服务：Pet / Health / Boarding / Reminder / Knowledge
        │
        └── Agent Runtime（显式工具调用循环为默认；LangGraph 为可选适配层）
              ├── Tool Registry
              ├── Permission Guard
              ├── Draft Manager
              ├── RAG Retriever
              └── Trace Logger

数据：MySQL 8+（PyMySQL）、Redis、本地 uploads/
运维：Docker Compose + Nginx + APScheduler
```

## 2. 角色与权限

| 角色 | 权限 |
|---|---|
| `pet_owner` | 自己的宠物、健康档案、体重、预约、日报、Agent |
| `boarding_staff` | 今日入住/退房、笼舍看板、日报、用药记录、寄养中宠物健康摘要 |
| `admin` | 用户、笼舍、知识库、统计、审计日志 |

权限原则：

1. 用户身份只来自 JWT，不接受 Agent 传入的 `user_id`。
2. 工具只做参数校验；归属校验、行级过滤、状态校验都在服务层。
3. 写操作必须先经过草稿和用户确认。

## 3. 写操作：草稿 + 确认

```text
用户提出预约
      │
      ▼
Agent 调用 create_boarding_draft
      │
      ▼
服务层校验归属 / 档期 / 价格
      │
      ▼
boarding_drafts(status=pending, expires_at=+15min)
      │
      ▼
前端渲染确认卡片
      │
      ▼
用户点击确认
      │
      ▼
POST /api/boarding/drafts/{id}/confirm
      │
      ├── 校验草稿归属与状态
      ├── 幂等键去重
      ├── 事务内锁定笼舍并重新校验档期
      ├── 创建 boarding_orders
      ├── 草稿置为 confirmed
      └── 写审计日志
```

**Agent 没有 confirm 工具。** 这是本项目的核心安全边界。

## 4. 工具清单（9 个）

| 工具 | 类型 | 权限 | 说明 |
|---|---|---|---|
| `list_my_pets` | 读 | 宠物主本人 / 寄养员与管理员只读全部 | 当前用户可访问的宠物 |
| `get_pet_health_records` | 读 | 宠物主本人 / 寄养员与管理员只读 | 按宠物名、类型、日期查健康记录 |
| `get_boarding_health_check` | 读 | 宠物主本人 / 寄养员与管理员 | 指定寄养日期的健康资料核对，不代表诊断或入住许可 |
| `get_upcoming_reminders` | 读 | 宠物主本人 / 寄养员与管理员只读 | 待处理提醒 |
| `check_kennel_availability` | 读 | 登录用户 | 日期 + 体型查空闲笼舍与预估价格 |
| `create_boarding_draft` | 写草稿 | 宠物主本人 | 只建草稿，15 分钟过期 |
| `list_boarding_orders` | 读 | 宠物主本人 / 寄养员与管理员只读全部 | 订单与状态 |
| `get_boarding_daily_reports` | 读 | 订单所有者 / 寄养员与管理员 | 寄养日报 |
| `search_care_knowledge` | 读 | 登录用户 | 混合检索护理知识；返回不可信片段与来源 |

`search_care_knowledge` 只读、不涉及用户数据；检索结果里带有 `trust: untrusted` 标记，
模型必须把片段当作资料而不是指令。

## 5. 安全与可观测

- Prompt 注入：知识库、宠物备注按不可信数据分隔；工具层不接受模型传入的身份；写操作有白名单和确认。
- 限制：单轮最多 6 次工具调用，请求 30 秒超时，限制最大输出 token。
- Trace：记录 `trace_id`、工具名、参数、结果摘要、耗时、token、错误码。
- 审计：健康档案修改、草稿确认、入住/退房等关键操作写 `audit_logs`。

### 5.1 流式输出

`POST /api/agent/chat/stream` 返回 `text/event-stream`，事件顺序如下：

| 事件 | 时机 | 数据 |
|---|---|---|
| `start` | 用户消息落库后 | `conversation_id`、`trace_id` |
| `llm_start` / `llm_end` | 每轮模型调用前后 | 轮次、耗时、是否产生工具调用 |
| `tool_start` / `tool_end` | 每个工具执行前后 | 工具名、参数、状态、摘要、耗时 |
| `delta` | 最终回答生成过程中 | 一小段正文增量，前端累加渲染 |
| `assistant` | 最终回复落库后 | 完整回复文本（以它为准覆盖增量） |
| `done` | 本轮结束 | 与 `/agent/chat` 相同的完整响应 |
| `error` | 流内异常 | 友好错误文案 |

- 校验、会话归属和模型配置检查在返回流之前完成，失败仍是普通 JSON 错误。
- 模型调用开启 `stream: true`，正文增量通过 `delta` 实时下发；工具调用的
  分片参数在流结束时拼装。客户端不支持流式时自动退回一次性 `complete`。
- 流式与非流式共用 `prepare_turn` / `run_agent` / `finalize_turn`，持久化和 trace 行为一致。
- 客户端断开时取消后台 Agent 任务；已落库的消息保留，未完成轮次不产生最终回复。
- 非流式 `/agent/chat` 保留，供评测和脚本调用。

### 5.2 RAG 知识库

- 数据：`knowledge_chunks` 存切片、标题、来源和 512 维向量；seed 写入 14 篇合成护理知识。
- 向量：fastembed `BAAI/bge-small-zh-v1.5`，首次检索时按需加载并缓存到 `backend/.fastembed_cache`
  （第一次会下载模型，之后离线可用）。
- 检索：向量以 JSON 文本存库（MySQL `TEXT`），不依赖数据库扩展。先取候选切片，再按
  `0.75 × 向量余弦 + 0.25 × 中文词法覆盖率` 排序；模型不可用时自动退回纯词法检索。
  分类过滤在 Python 中完成，候选数取 `top_k × 4`（12–50）。
- 阈值：混合检索默认 `0.45`，词法回退默认 `0.25`，低于阈值不返回片段。
- 引用：工具返回 `title / content / source / score / trust`，系统提示要求用“（来源：标题）”标注。
- 拒答：没有检索结果时明确说没有查到，不凭常识编造，不推荐具体商品或购买链接。
- 注入：知识片段与宠物备注一样按不可信数据处理；即使片段包含“忽略之前的指令”，也只提醒用户。
- 迁移：[migrations/versions/39bc51a83f0d_initial_schema.py](../backend/migrations/versions/39bc51a83f0d_initial_schema.py)
  建全量表结构；MySQL 无 PostgreSQL 的 `EXCLUDE` 约束，档期冲突由应用层在确认事务中校验。
- 启动：MySQL 表结构由 Alembic 管理，开发机执行 `alembic upgrade head`，
  容器由 entrypoint 先迁移再启动服务；SQLite 只在 pytest 里由 `create_all` 建临时库。

### 5.3 数据库约束

| 约束 | 作用 |
|---|---|
| `uq_knowledge_doc_chunk` | 同一文档的切片序号唯一，seed 可重复执行 |
| `uq_daily_report_order_date` | 每笔订单每天只有一份日报 |
| `ix_boarding_orders_draft_id`（唯一） | 一张草稿最多确认出一笔订单，支撑确认接口幂等 |

档期冲突由应用层档期校验 + 确认事务里的笼舍行锁兜住（`SELECT … FOR UPDATE`），
MySQL 没有 PostgreSQL 的排他约束，因此不再建库级约束。

### 5.4 账号与验证码

- 注册与找回密码都要求先验证邮箱或手机号。验证码为 6 位数字，5 分钟有效；
  签发新码时旧的未用码立即作废，核销一次即失效。
- 数据库只存 HMAC-SHA256 摘要（密钥由 `JWT_SECRET_KEY` 派生），不存明文；
  校验用 `hmac.compare_digest`，避免时序侧信道。
- 限流：同一联系方式 60 秒重发冷却、每小时最多 5 条、每条最多试错 5 次；
  接口层另有 `6/minute` 的 IP 限流。
- 邮件走 SMTP 授权码（QQ / 163 均可），短信发送器可插拔；当前 `console`
  只把验证码写入日志，接入阿里云 / 腾讯云短信后替换实现即可。
- 登录保护：连续 5 次密码错误锁定 15 分钟；失败提示统一为“账号或密码错误”，
  不暴露账号是否存在；重置密码递增 `token_version`，此前签发的令牌立即失效。
- `VERIFY_CODE_DEBUG` 会从接口返回 `debug_code`，只允许本地开启（启动时打警告），
  部署环境必须为 `false`。

### 5.5 支付状态机

支付渠道由 `PAYMENT_PROVIDER` 切换：`mock` 用于本地演示，`alipay` 走支付宝
电脑网站支付（沙箱和正式环境只换网关与密钥）。两种渠道共用同一套状态机、
订单联动和幂等规则。

| 状态 | 含义 | 进入方式 |
|---|---|---|
| `created` | 支付单已生成，等待支付 | 用户点「去支付」 |
| `paying` | 支付页已打开 / 扫码页已读取 | 支付页读取支付单 |
| `paid` | 支付成功 | 渠道回调或主动查单核销 |
| `closed` | 已过期 / 订单已支付 | 超时或重复支付保护 |

- 订单表冗余 `payment_status` / `paid_amount`，列表页不关联支付单；回调在同一事务里
  更新支付单与订单，并写 `audit_logs`。
- 模拟渠道：二维码内容是 `支付页地址 + 一次性 token`；回调必须带正确 token
  （`compare_digest`），仅凭支付单号不能入账。
- 支付宝渠道：后端用应用私钥对 `alipay.trade.page.pay` 参数做 RSA2 签名，
  生成收银台 URL 存进 `pay_url`（签名 URL 较长，用 `Text` 单独存）；同步跳转
  回到 `/pay/<支付单号>?token=...`，异步通知打到 `/api/payments/alipay/notify`。
- 通知处理顺序：RSA2 验签 → `app_id` → 可选 `seller_id` → 支付单渠道 → 金额；
  失败返回 `failure` 让支付宝重试，成功返回纯文本 `success`。
- 主动对账：`refresh` 调用 `alipay.trade.query`，对响应中的原始 JSON 节点验签，
  覆盖异步通知丢失；页面轮询、「我已完成支付」和回跳都会触发。支付单过期关单后
  24 小时内仍会查单（`CLOSED_QUERY_WINDOW`），覆盖「刚过期就付完款」的情况。
- 幂等：重复回调直接返回成功；同一订单已支付时，后续支付单关闭而不重复入账；
  未过期支付单复用，过期后重新生成。并发创建靠订单行锁串行化，拿到锁后再用
  锁读查未过期支付单，连点不会生成重复单据。
- 渠道切换保护：服务端发现未支付单属于旧渠道时先关闭再新建；`alipay` 模式下
  模拟回调接口直接 403，避免本地按钮白拿订单。
- 超时：默认 15 分钟（`PAYMENT_TTL_MINUTES`），查询时惰性关单，`paid` 状态不可逆。
- 退款与对账文件尚未实现；`closed` 的已付款订单目前只记审计日志，真实环境应接退款。

### 5.6 管理端边界

管理端只做“看”和一个安全操作，避免出现第二套绕过状态机的写入口：

| 接口 | 用途 |
|---|---|
| `GET /api/admin/overview` | 运营概览：账号 / 宠物 / 订单 / 今日入住退房 / 实收金额 / 待处理提醒 / 知识库切片 |
| `GET /api/admin/users` | 账号检索、角色 / 状态筛选、分页；附带宠物与订单数 |
| `PUT /api/admin/users/{id}/status` | 启用 / 停用账号 |
| `GET /api/admin/kennels/occupancy` | 指定日期的笼舍占用与在住宠物 |
| `GET /api/admin/audit-logs` | 只读审计日志，按操作前缀筛选 |
| `GET /api/admin/knowledge` | 只读知识库切片，按标题 / 内容 / 文档 ID 检索；不暴露向量 |

- 概览与知识库都是聚合读，不新增写路径；统计口径直接来自业务表，不做缓存，
  避免管理端数字与实际订单状态不一致。
- 知识库只读：切片由 seed 与离线导入脚本写入，管理端不提供增删改，防止在演示中
  把未审核的内容写进检索集合。

- `audit_logs` 由寄养、支付服务在业务事务内写入，管理端不补写、不修改。
- 停用账号会递增 `token_version`，已登录会话立即失效；不能停用自己，也不能停用
  最后一个可用的管理员。
- 占用按订单反推：已入住（`checked_in` / `boarding`）的宠物即使档期与当前日期有偏差
  也计入占用；`kennels.status=occupied` 但没有在住订单时按空闲展示，避免残留脏状态
  造成“占用中但没有客人”。
- 订单确认、入住、退房、支付仍然只走业务服务，管理端不提供直接改状态的接口。

### 5.7 提醒处理

`PATCH /api/pets/{pet_id}/reminders/{reminder_id}` 支持两种动作，二选一：

| 动作 | 行为 |
|---|---|
| `{"status": "done"}` | 提醒置为 `done`，不再出现在待处理列表，也不会再触发通知 |
| `{"snooze_days": 7}` | 到期日顺延 1–90 天，清空 `notified_at`，同步 `dedupe_key`，新日期可以重新通知 |

- 提醒属于健康档案：宠物主可操作，寄养员只读，管理员沿用档案写权限。
- 已处理的提醒不能重复操作；延后后的提醒仍可再次完成或延后。
- 两种动作都写 `audit_logs`（`reminder.done` / `reminder.snooze`），保留处理前状态和日期。

### 5.8 图片上传

`POST /api/uploads`（需登录，`multipart/form-data`）用于宠物头像和寄养日报照片：

- 类型判定只读文件头魔数（JPEG / PNG / GIF / WEBP），不信任客户端的 `Content-Type`
  和文件名扩展名；伪装成图片的脚本会被拒绝。
- 上限 10MB；超出直接返回 400，不落盘。
- 文件名用 `uuid4().hex` 重新生成，按用途分目录（`uploads/pet/`、`uploads/report/`），
  客户端无法决定存放路径。
- 返回 `{"url": "/uploads/{purpose}/{filename}", "size": …}`；静态目录由 FastAPI
  `StaticFiles` 挂载在 `/uploads`。
- 业务侧再校验一次：日报最多 6 张、地址必须以 `/uploads/` 开头，避免把外部链接
  写进日报（例如带追踪参数的图片）。

### 5.9 定时任务

`app/scheduler.py` 用 APScheduler 的 `BackgroundScheduler` 在进程内跑一个任务：

- 每天 08:00（`Asia/Shanghai`）扫描全部正常宠物主，调用
  `notification_service.sync_all_reminders` 补站内通知；逐用户提交，单用户失败不影响其他人。
- 通知本身带 `dedupe_key`，重复扫描不会产生重复消息；因此多进程部署时每个进程都跑
  也是安全的（代价只是多次查询）。
- 与“读通知时惰性同步”互补：惰性同步保证用户一进站就看到最新提醒，定时任务保证
  用户当天不打开页面也能在通知中心看到。
- `SCHEDULER_ENABLED=false` 可关闭；pytest 在 `conftest.py` 里关闭，避免线程在临时
  SQLite 上并发写。

### 5.10 MCP 能力开放

`app/mcp/` 把领域能力开放给外部 Agent，而不是复制一套业务逻辑：

```text
Claude Desktop / Cursor ──stdio──┐
远程 MCP Client ──Streamable HTTP┴─→ MCPAuthMiddleware（JWT + 按用户限流）
                                      → current_user_id（来自 token）
                                      → execute_read_tool（只读白名单 + 审计）
                                      → app.agent.tools.execute_tool
                                      → 服务层（权限 / 行级过滤）
```

- **只读**：白名单只有 7 个查询工具；`create_boarding_draft` 不在白名单，
  确认接口也没有注册。外部客户端无法创建、确认或取消订单。
- **身份**：与 REST 接口同一套校验（签名、过期、`users.status`、`token_version`）；
  工具参数里没有 `user_id`。stdio 在启动时解析一次 token，HTTP 每请求校验 Bearer。
- **复用**：MCP 调用 `execute_tool`，和站内 Agent 共用服务层权限与行级过滤，
  避免出现“站内拦住了、MCP 没拦住”的第二套规则。
- **不可信输入输出**：知识片段继续按不可信资料处理并要求标注来源；工具结果限制
  32KB，单次调用 5 秒超时，失败返回结构化错误而不是抛出协议异常。
- **协议**：`mcp==1.30.0` + FastMCP；HTTP 使用 Streamable HTTP 的 stateless +
  JSON 响应模式，方便反向代理和 curl 调试。2.x 重命名 FastMCP 并要求
  starlette>=1，与 FastAPI 0.115 冲突，因此固定在 1.30。
- **入口治理**：HTTP 在认证之后按 user_id 限流（默认 60 次/分钟，Redis 或进程
  内存），超限返回 429；每次调用（含拒绝）写 `mcp_audit_logs`，记录参数摘要、
  状态、耗时、IP 和 trace_id，管理端只读查询。

### 5.11 MCP Client 与统一工具注册表

站内 Agent 既用本地工具，也能接入其他 MCP Server。两条路径在调用模型之前
合并成同一份 function schema：

```text
                    ┌─ 本地 9 个工具（TOOL_DEFINITIONS / execute_tool）
Agent runtime ──────┤
                    └─ 外部 MCP 只读工具（mcp__server__tool）
                            ↑ ToolRegistry 发现 + 缓存
                            │
                 stdio / Streamable HTTP → 外部 MCP Server
```

- **只读是硬门槛**：只注册 `annotations.readOnlyHint is True` 的工具，没有
  “允许外部写工具”的开关；写操作仍只有本地 `create_boarding_draft`。
- **命名空间**：外部工具统一加 `mcp__<server>__<tool>` 前缀，超过 64 字符时
  截断并附哈希，避免覆盖本地工具或超出模型函数名限制。
- **不可信描述**：外部工具描述先压缩空白、截断，命中“忽略之前指令 / 系统提示词 /
  API key”等模式时整段替换，不让工具描述成为注入入口。
- **不可信返回值**：结果统一转成站内 `{ok, data, error, code}`；超过 32KB 拒绝，
  调用超时返回 504，协议错误返回 502。系统提示额外声明外部内容不得当作指令。
- **故障降级**：单个 Server 发现失败只影响它自己，注册表继续提供本地工具和
  其他 Server 的工具；发现结果缓存 300 秒，避免每轮对话拉起子进程。
- **配置与密钥**：`MCP_CLIENT_SERVERS` 是 JSON 数组，`env` / `headers` 支持
  `${VAR}` 展开，token 只放环境变量，不写进仓库。

两种调度引擎共用这套注册表：显式循环在 `runtime.run_agent` 里合并 schema，
LangGraph 适配层通过参数拿到同一个注册表，评测变体对 `TOOL_DEFINITIONS` 的
monkeypatch 仍然生效。

## 6. 调度引擎选型

### 6.1 主实现：显式工具调用循环

生产与所有演示路径都走 `app/agent/runtime.py` 的显式循环：

```text
messages = system + history
loop:
    LLM.complete(messages, TOOLS)
    if tool_calls and 未超过轮次上限:
        持久化 assistant(tool_calls)
        for call in tool_calls:
            registry.execute(...) 或 execute_tool(...)
                → 持久化 tool message + trace
    else:
        持久化最终回复，返回
```

选择它的原因：

- **可控**：轮次上限、30 秒超时、失败兜底、SSE 事件顺序都在一个函数里，安全边界不依赖框架默认行为。
- **可调试**：一次请求就是一条 Python 调用栈，异常直接定位到循环或工具行；trace 表和 SSE 事件与代码一一对应。
- **依赖少**：生产镜像只装 `requirements.txt`，不需要 LangChain 生态；模型接口就是一个 OpenAI 兼容的 `httpx` 请求。
- **可测试**：测试用脚本化 `FakeLLM` 直接驱动循环，不需要构造图状态或 checkpoint。

### 6.2 对照适配层：LangGraph

`app/agent/langgraph_runtime.py` 保留同一套工具、提示词、持久化和事件，只把调度换成 `StateGraph`：

```text
START → agent ──(有 tool_calls)──→ tools ──→ agent
           └──(无 tool_calls / 出错 / 超轮次)──→ finish → END
```

- `agent`：调用模型、发 `llm_start/llm_end`、持久化 tool-call 消息。
- `tools`：逐个执行工具、写 `agent_messages` 与 `agent_tool_calls`、发 `tool_start/tool_end`、记录草稿 ID。
- `finish`：持久化最终回复、发 `assistant` 事件。
- 通过 `AGENT_ENGINE=langgraph` 切换；`app/agent/engine.py` 懒加载，未安装 LangGraph 时自动回退，生产路径不受影响。
- 不引入 checkpointer：会话历史仍以数据库为唯一事实源，避免两套状态。
- 评测的 6 个变体对两种引擎都生效，因为适配层在调用时读取 `runtime` 模块属性，
  而不是复制 `TOOL_DEFINITIONS` / `execute_tool` / `build_system_prompt`。

### 6.3 实测差异

同一套 5 条用例（`pets-001` / `draft-001` / `knowledge-001` / `perm-001` / `refusal-001`），
`deepseek-flash`，两个引擎都是 5/5 通过：

| 维度 | 显式循环 | LangGraph 适配层 |
| --- | --- | --- |
| 端到端平均延迟 | 4.0s | 4.5s |
| P95 延迟 | 5.5s | 7.8s |
| tokens（5 条合计） | 25,766 | 29,879 |
| 工具路径 | — | 其中 2 条多调用了工具 |

这组差异主要来自模型每次选择不同（`refusal-001`、`knowledge-001` 多了一轮工具），
不能直接归因于适配层。为隔离调度开销，另用脚本化 `FakeLLM` 跑固定两步工具循环，
每边 25 次（脚本化 FakeLLM、无网络）：

| 实现 | 平均 | 中位数 | P95 |
| --- | --- | --- | --- |
| 显式循环 | 4.50ms | 4.47ms | 4.99ms |
| LangGraph | 12.04ms | 10.37ms | 10.91ms |

即适配层每次多约 **7.5ms** 编排开销，相对 3–5 秒的模型延迟可以忽略。

### 6.4 结论

- 生产继续使用显式循环：代码量更小、失败定位更直接、没有额外运行时依赖。
- LangGraph 适配层用于验证“调度可替换”，并在论文里提供同一业务能力下的框架对照，
  而不是为了关键词把主链路重写。
- 如果后续需要 checkpoint 恢复、复杂分支或可视化编排，再以适配层为起点引入 LangGraph。

适配层与显式循环的行为对齐由 `backend/tests/test_agent_langgraph.py` 覆盖
（工具循环、超轮次停止、模型失败兜底）。

## 7. 评测（论文阶段）

- 当前 harness：`backend/evaluation/`，YAML 用例 + 独立评测库（`pawcare_eval`，与演示库隔离）+ 真实模型 + JSON / CSV 报告。
- 主评测集 91 条，覆盖宠物、健康、提醒、笼舍空档、草稿、订单、日报、知识检索、
  越权、拒答、提示注入、多工具串联和多轮澄清。
- baseline / 消融在 `evaluation/variants.py` 中实现，仅在评测进程内替换注册表或提示词：
  - `no_tools`：无工具直答，作为 baseline；
  - `no_rag`：移除 `search_care_knowledge`；
  - `no_permission`：读工具改用合成管理员身份，测量行级泄漏；
  - `no_citation`：移除“（来源：标题）”约束；
  - `no_draft_confirmation`：注册仅评测存在的 `confirm_boarding_draft`，模拟 Agent 自行下单。
- 消融专用用例在 `evaluation/ablation_cases.yaml`，报告名带变体后缀，便于横向对比。
- 指标：工具选择准确率、参数准确率、端到端成功率、引用忠实度、拒答准确率、注入抵抗率、P95 延迟、token 成本。
- 参数评分读取 `agent_tool_calls.arguments`，不依赖模型自述；越权用例同时检查草稿副作用。
