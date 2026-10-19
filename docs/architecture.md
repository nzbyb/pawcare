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
        └── Agent Runtime（显式工具调用循环，后续可替换为 LangGraph）
              ├── Tool Registry
              ├── Permission Guard
              ├── Draft Manager
              ├── RAG Retriever
              └── Trace Logger

数据：PostgreSQL 16 + pgvector、Redis、本地 uploads/
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

## 4. 工具清单（8 个）

| 工具 | 类型 | 权限 | 说明 |
|---|---|---|---|
| `list_my_pets` | 读 | 宠物主本人 / 寄养员与管理员只读全部 | 当前用户可访问的宠物 |
| `get_pet_health_records` | 读 | 宠物主本人 / 寄养员与管理员只读 | 按宠物名、类型、日期查健康记录 |
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
| `assistant` | 最终回复落库后 | 完整回复文本 |
| `done` | 本轮结束 | 与 `/agent/chat` 相同的完整响应 |
| `error` | 流内异常 | 友好错误文案 |

- 校验、会话归属和模型配置检查在返回流之前完成，失败仍是普通 JSON 错误。
- 流式与非流式共用 `prepare_turn` / `run_agent` / `finalize_turn`，持久化和 trace 行为一致。
- 客户端断开时取消后台 Agent 任务；已落库的消息保留，未完成轮次不产生最终回复。
- 非流式 `/agent/chat` 保留，供评测和脚本调用。

### 5.2 RAG 知识库

- 数据：`knowledge_chunks` 存切片、标题、来源和 512 维向量；seed 写入 14 篇合成护理知识。
- 向量：fastembed `BAAI/bge-small-zh-v1.5`，首次检索时按需加载并缓存到 `backend/.fastembed_cache`
  （第一次会下载模型，之后离线可用）。
- 检索：SQLite 开发库没有 pgvector，先取候选切片，再按
  `0.75 × 向量余弦 + 0.25 × 中文词法覆盖率` 排序；模型不可用时自动退回纯词法检索。
- 阈值：混合检索默认 `0.45`，词法回退默认 `0.25`，低于阈值不返回片段。
- 引用：工具返回 `title / content / source / score / trust`，系统提示要求用“（来源：标题）”标注。
- 拒答：没有检索结果时明确说没有查到，不凭常识编造，不推荐具体商品或购买链接。
- 注入：知识片段与宠物备注一样按不可信数据处理；即使片段包含“忽略之前的指令”，也只提醒用户。
- 生产路径：PostgreSQL 上先用 `ORDER BY embedding <=> CAST(:q AS vector(512))`
  取候选（HNSW 余弦索引），再在 Python 里叠加词法分，保证两种数据库的评分口径一致；
  分类过滤走 JSONB `meta->>'category'`。
- 迁移：[migrations/versions/39bc51a83f0d_initial_schema.py](../backend/migrations/versions/39bc51a83f0d_initial_schema.py)
  在 PostgreSQL 上创建 `vector` / `btree_gist` 扩展、`vector(512)` 列、HNSW 索引，
  并为活跃寄养订单添加日期区间排他约束。
- 启动：SQLite 开发库仍由 `create_all` 建表；PostgreSQL 由 Alembic 管理，
  容器 entrypoint 先执行 `alembic upgrade head` 再启动服务。

### 5.3 数据库约束

| 约束 | 作用 |
|---|---|
| `uq_knowledge_doc_chunk` | 同一文档的切片序号唯一，seed 可重复执行 |
| `uq_daily_report_order_date` | 每笔订单每天只有一份日报 |
| `ex_boarding_orders_active_period` | PostgreSQL 排他约束：同一笼舍的 `[start, end)` 活跃订单不得重叠 |
| `ix_boarding_orders_draft_id`（唯一） | 一张草稿最多确认出一笔订单，支撑确认接口幂等 |

排他约束与应用层档期校验形成双层保护：应用层负责友好报错，数据库层兜住并发确认。

## 6. 评测（论文阶段）

- 当前 harness：`backend/evaluation/`，YAML 用例 + 独立 SQLite 副本 + 真实模型 + JSON / CSV 报告。
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
