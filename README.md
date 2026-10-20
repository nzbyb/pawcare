<p align="center">
  <img src="frontend/public/logo.svg" width="72" height="72" alt="PawCare logo" />
</p>

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
| Agent | 显式工具调用循环 + 步骤级 SSE（httpx + OpenAI 兼容接口）；附 LangGraph 对照适配层 |
| RAG | fastembed + bge-small-zh-v1.5（512 维），向量 + 词法混合检索；生产保留 pgvector 路径 |
| 定时 | APScheduler（单进程） |
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Vue Router |
| UI | Naive UI + ECharts，临床工作台主题（暖白底 + 松绿主色） |
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
    agent/        # 系统提示词、工具定义、LLM 客户端与 Agent 循环
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

本地开发默认用 SQLite 跑通链路（`DATABASE_URL=sqlite:///./pawcare_dev.db`），
启动时自动 `create_all`；切换到 PostgreSQL 后，表结构由 Alembic 管理：

```bash
cd backend
# 新库：建表 + 扩展 + 索引 + 排他约束
.venv\Scripts\python.exe -m alembic upgrade head
# 已有旧库（曾由 create_all 建表）：只登记版本，不重复建表
.venv\Scripts\python.exe -m alembic stamp head
```

迁移文件在 [backend/migrations/](backend/migrations/)。PostgreSQL 路径会创建
`vector` / `btree_gist` 扩展、知识库 HNSW 索引，以及订单日期区间的排他约束。

生成可重复执行的演示数据：

```bash
cd backend
.venv\Scripts\python.exe scripts\seed.py
```

演示账号（全部为合成数据）：

| 角色 | 账号 | 密码 |
|---|---|---|
| 宠物主 | `owner` | `Owner12345` |
| 宠物主 | `owner2` | `Owner12345` |
| 寄养员 | `staff` | `Staff12345` |
| 管理员 | `admin` | `Admin12345` |

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

后端容器启动时先执行 `alembic upgrade head`，再启动 uvicorn；`.env` 不进入镜像。
知识库模型缓存在 `backend/.fastembed_cache`，首次检索会下载 BGE 模型。

### 5.4 Agent 评测

```powershell
cd backend
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\python.exe evaluation\runner.py --dry-run
.\.venv\Scripts\python.exe evaluation\runner.py
```

评测会复制开发库、自动创建注入测试数据，并用真实模型走完整 HTTP 链路。
输出任务成功率、工具选择准确率、参数准确率、P95 延迟和 token 成本，
JSON / CSV 报告写入 `backend/evaluation/reports/`（不入库）。

baseline / 消融用同一套用例切换变体（`full` / `no_tools` / `no_rag` /
`no_permission` / `no_citation` / `no_draft_confirmation`）：

```powershell
.\.venv\Scripts\python.exe evaluation\runner.py --cases evaluation\ablation_cases.yaml --variant no_rag
```

字段说明和扩展示例见 [backend/evaluation/README.md](backend/evaluation/README.md)。

调度引擎默认是显式循环；LangGraph 适配层用于对照实验（先装 `requirements-agent.txt`）：

```powershell
.\.venv\Scripts\python.exe evaluation\runner.py --engine langgraph --case pets-001 --case knowledge-001
```

报告文件名和 JSON 会带引擎标识。主链路为什么选显式循环、两种实现的差异，
见 [docs/architecture.md](docs/architecture.md#6-调度引擎选型)。

## 6. 环境变量

真实密钥只放在 `.env`，不进仓库。模板见 `backend/.env.example` 和根目录 `.env.example`。

| 变量 | 说明 |
|---|---|
| `DATABASE_URL` | 本地：`postgresql+psycopg://...@127.0.0.1:5432/pawcare` |
| `JWT_SECRET_KEY` | 至少 32 位随机值，每个项目独立 |
| `LLM_API_KEY` | DeepSeek / OpenAI 兼容接口密钥 |
| `LLM_MODEL` | 当前使用 `deepseek-flash` |
| `LLM_BASE_URL` | `https://api.deepseek.com` |
| `AGENT_ENGINE` | `explicit`（默认）/ `langgraph`（对照实验） |
| `REDIS_URL` | 留空时使用进程内限流 |
| `RAG_ENABLED` | 是否启用知识库检索，默认 `true` |
| `RAG_EMBEDDING_MODEL` | 默认 `BAAI/bge-small-zh-v1.5` |
| `RAG_TOP_K` / `RAG_MIN_SCORE` | 返回片段数与混合检索阈值 |

## 7. 当前进度

- [x] 项目骨架、统一响应、异常处理
- [x] 用户 / 宠物 / 健康档案模型
- [x] 注册登录、JWT 鉴权、角色守卫
- [x] 宠物档案、体重、健康记录、提醒同步接口
- [x] 后端 pytest 用例（认证 / 权限 / 档案 / 提醒）
- [x] 前端骨架：登录、工作台、宠物列表、详情、Agent 占位页
- [x] 寄养主流程：笼舍、空档查询、草稿确认、订单状态流转、日报
- [x] 演示数据 seed 脚本（账号 / 宠物 / 健康记录 / 笼舍 / 订单）
- [x] 寄养前端页面：空档查询、草稿倒计时确认、订单流转、日报
- [x] Agent 工具层：8 个权限感知工具，工具注册表中没有确认工具
- [x] 多轮工具调用循环、会话历史持久化、token / 耗时 / 错误码 trace
- [x] `POST /api/agent/chat` 与历史会话接口，deepseek-flash 真实冒烟通过
- [x] 前端智能助手页：多轮对话、工具轨迹、草稿卡片、历史会话切换
- [x] SSE 流式输出：步骤事件 + 前端增量渲染
- [x] RAG：14 篇护理知识、混合检索、来源标注、拒答与注入防护
- [x] 评测 harness：91 条 YAML 用例、隔离评测库、JSON / CSV 报告
- [x] Alembic 初始迁移、pgvector 余弦检索与订单排他约束
- [ ] Docker Compose 启动验证（本机 Docker daemon 未运行）
- [ ] 通知中心
- [x] baseline / 消融实验（无工具、去 RAG、去权限、去引用、去确认边界）
- [x] LangGraph 对照适配层（`AGENT_ENGINE` / 评测 `--engine`，生产默认显式循环）

## 8. 说明

- 演示数据全部为合成数据，不使用真实用户或真实病例。
- 本项目与 `lab-agent` 是两个独立项目，不复用其数据库、JWT 密钥或前端代码。
