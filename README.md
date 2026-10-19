# PawCare

面向宠物寄养与健康管理场景的领域智能体。业务系统是底座，Agent 是主线，核心关注 **工具调用、写操作确认、权限隔离和可评测性**。

> 当前阶段：实战项目开发（论文材料后补）。每天完成的内容提交并推送 GitHub。

## 1. 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.12+、FastAPI、SQLAlchemy 2.0、Pydantic v2、Alembic |
| 数据库 | PostgreSQL 16 + pgvector |
| 缓存/限流 | Redis 7（可选，未启动时退回进程内存） |
| 鉴权 | JWT + bcrypt，三角色：宠物主 / 寄养员 / 管理员 |
| Agent | LangGraph + langchain-openai，DeepSeek OpenAI 兼容接口 |
| RAG | pgvector + bge-small-zh-v1.5，回答带引用 |
| 定时 | APScheduler（单进程） |
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Vue Router |
| UI | Naive UI + ECharts，自定义暖色主题 |
| 部署 | Docker Compose + Nginx |

## 2. 核心闭环

```text
宠物建档 → 录入疫苗/驱虫 → 到期提醒 → 预约寄养 → 选择笼舍
        → 入住 → 每日报告 → 退房 → 健康时间线更新
```

Agent 的典型场景：

> “我家豆豆下个月要寄养 5 天，它疫苗快到期了吗？帮我看看有没有合适的笼舍。”

Agent 可以查疫苗、推荐笼舍、生成预约草稿；**用户在前端确认后，订单才真正落库**。

## 3. 关键设计

- **草稿 + 人工确认**：`create_boarding_draft` 只写草稿；`confirm` 不是 Agent 工具，只能由用户点击触发。
- **权限感知工具**：用户身份来自 JWT，工具不接受 LLM 传入的 `user_id`；权限和行级过滤在服务层。
- **不可信上下文**：知识库、宠物备注都按不可信数据处理，配合注入测试。
- **可观测**：每轮对话记录 trace、工具参数、耗时、token 和错误码。
- **可评测**：80–100 条 YAML 用例，baseline + 消融，输出 CSV / 图表。

## 4. 目录结构

```text
backend/
  app/
    api/          # FastAPI 路由
    models/       # SQLAlchemy 模型
    schemas/      # Pydantic 模型
    services/     # 业务逻辑（权限、事务、Agent 工具的服务层）
    dependencies/ # 鉴权依赖
    common/       # 统一响应与异常
    utils/        # JWT、密码
  tests/
  migrations/     # Alembic
frontend/
  src/
    api/          # axios 封装
    stores/       # Pinia
    router/
    layouts/
    views/
    styles/
docs/
  ER.md
  architecture.md
  progress.md     # 每日开发日志
```

## 5. 本地启动

### 5.1 后端

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # 填入真实值
uvicorn app.main:app --reload --port 8000
```

本地第一天先用 SQLite 跑通链路（`DATABASE_URL=sqlite:///./pawcare_dev.db`）；
Docker Compose 启动 Postgres 后，把 `DATABASE_URL` 换成 `postgresql+psycopg://...` 即可。
生产路径仍以 PostgreSQL + pgvector 为准。

### 5.2 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认 `http://localhost:5173`，Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

### 5.3 Docker Compose

```bash
copy .env.example .env
docker compose up -d --build
```

## 6. 环境变量

真实密钥只放在 `.env`，不进仓库。模板见 `backend/.env.example` 和根目录 `.env.example`。

| 变量 | 说明 |
|---|---|
| `DATABASE_URL` | 本地：`postgresql+psycopg://...@127.0.0.1:5432/pawcare` |
| `JWT_SECRET_KEY` | 至少 32 位随机值，每个项目独立 |
| `LLM_API_KEY` | DeepSeek / OpenAI 兼容接口密钥 |
| `LLM_MODEL` | 当前使用 `deepseek-flash` |
| `LLM_BASE_URL` | `https://api.deepseek.com` |
| `REDIS_URL` | 留空时使用进程内限流 |

## 7. 当前进度

- [x] 项目骨架、统一响应、异常处理
- [x] 用户 / 宠物 / 健康档案模型
- [x] 注册登录、JWT 鉴权、角色守卫
- [x] 宠物档案、体重、健康记录、提醒同步接口
- [x] 后端 pytest 用例（认证 / 权限 / 档案 / 提醒）
- [x] 前端骨架：登录、工作台、宠物列表、详情、Agent 占位页
- [ ] 寄养主流程（笼舍、订单、日报）
- [ ] 通知中心
- [ ] Agent 工具层 + SSE
- [ ] RAG + 引用
- [ ] 评测 harness
- [ ] Alembic 迁移、Docker 演示
- [ ] 推送 GitHub（等待仓库地址）

## 8. 说明

- 演示数据全部为合成数据，不使用真实用户或真实病例。
- 本项目与 `lab-agent` 是两个独立项目，不复用其数据库、JWT 密钥或前端代码。
