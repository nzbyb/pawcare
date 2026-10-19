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
        └── Agent Runtime（LangGraph）
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

## 4. 工具清单（7 个）

| 工具 | 类型 | 权限 | 说明 |
|---|---|---|---|
| `get_my_pets` | 读 | 本人 | 当前用户宠物列表 |
| `get_pet_health_summary` | 读 | 宠物主 | 健康摘要、疫苗到期、体重趋势 |
| `get_upcoming_reminders` | 读 | 宠物主 | 近期提醒 |
| `check_kennel_availability` | 读 | 登录用户 | 日期 + 尺寸查空闲笼舍 |
| `create_boarding_draft` | 写草稿 | 宠物主 | 只建草稿，15 分钟过期 |
| `get_boarding_reports` | 读 | 宠物主/寄养员 | 寄养日报 |
| `search_care_knowledge` | 读 | 登录用户 | RAG 检索，返回引用 |

## 5. 安全与可观测

- Prompt 注入：知识库、宠物备注按不可信数据分隔；工具层不接受模型传入的身份；写操作有白名单和确认。
- 限制：单轮最多 6 次工具调用，请求 30 秒超时，限制最大输出 token。
- Trace：记录 `trace_id`、工具名、参数、结果摘要、耗时、token、错误码。
- 审计：健康档案修改、草稿确认、入住/退房等关键操作写 `audit_logs`。

## 6. 评测（论文阶段）

- 80–100 条 YAML 用例，覆盖健康查询、提醒、笼舍、草稿、日报、RAG、拒答、注入。
- 基线：prompt-only function calling vs LangGraph vs 完整系统。
- 消融：去 RAG、去权限过滤、去草稿确认、去引用约束。
- 指标：工具选择准确率、参数准确率、端到端成功率、引用忠实度、拒答准确率、注入抵抗率、P95 延迟、token 成本。
