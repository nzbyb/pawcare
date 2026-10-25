<p align="center">
  <img src="frontend/public/logo.svg" width="72" height="72" alt="PawCare 标志" />
</p>

<h1 align="center">PawCare</h1>

<p align="center">面向宠物寄养与健康管理场景的领域智能体系统</p>

## 1. 项目简介

PawCare 是一套面向宠物寄养与健康管理场景的全栈系统，由业务平台与领域智能体两部分组成。业务平台承载宠物档案、健康记录、寄养预约、在线支付与运营管理；智能体通过显式工具调用连接上述业务能力，在权限边界内完成查询、推荐与草稿生成。

项目重点验证四个问题：

1. 工具调用如何与真实业务数据结合，而不是停留在演示脚本；
2. 写操作如何始终处于用户确认之下，避免模型直接产生业务副作用；
3. 权限与数据边界如何在工具层落实，而非依赖提示词约束；
4. 智能体效果如何量化评测，并支持消融实验。

- 在线体验：<http://121.196.150.159>
- 部署形态：阿里云 ECS（2C4G），Docker Compose 四容器 + Nginx
- 质量保障：后端 pytest 156 条用例；Agent 评测 101 条用例；MCP 专项评测 10 条检查

## 2. 功能概览

### 2.1 业务流程

```text
宠物建档 → 录入疫苗 / 驱虫 → 到期提醒 → 预约寄养 → 选择笼舍
        → 在线支付 → 入住 → 每日报告 → 退房 → 健康时间线更新
```

### 2.2 功能模块

| 模块 | 说明 |
|---|---|
| 宠物档案与健康管理 | 档案、体重、疫苗 / 驱虫记录、健康时间线、到期提醒同步 |
| 寄养预约 | 笼舍管理、空档查询、草稿确认、订单状态流转、每日报告 |
| 在线支付 | 模拟收银台与支付宝沙箱电脑网站支付，异步通知与主动查单双通道核销 |
| 通知中心 | 站内通知、偏好开关、提醒完成 / 延后、每日 08:00 定时补发 |
| 智能助手 | 多轮对话、工具轨迹、草稿卡片、历史会话、逐字流式输出 |
| 能力开放 | 7 个只读工具通过 MCP Server 暴露，支持 stdio 与 Streamable HTTP |
| 运营管理 | 运营概览、账号启停、笼舍占用、审计日志、MCP 调用审计 |

### 2.3 智能体典型场景

> “我家豆豆下个月要寄养 5 天，它疫苗快到期了吗？帮我看看有没有合适的笼舍。”

智能体可查询疫苗记录、检索笼舍空档、生成预约草稿；**订单仅在用户于前端确认后才落库**。

## 3. 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.12+、FastAPI、SQLAlchemy 2.0、Pydantic v2、Alembic |
| 数据库 | MySQL 8+（PyMySQL）+ Alembic |
| 缓存 / 限流 | Redis 7（可选，未启动时退回进程内存） |
| 鉴权 | JWT + bcrypt，三角色：宠物主 / 寄养员 / 管理员 |
| Agent | 显式工具调用循环 + 步骤 / 逐字 SSE（httpx + OpenAI 兼容接口）；附 LangGraph 对照适配层 |
| 能力开放 | MCP 1.30：只读 Server（stdio / Streamable HTTP）+ 站内 Agent 的只读 MCP Client |
| RAG | fastembed + bge-small-zh-v1.5（512 维），向量以 JSON 文本存库，应用层余弦 + 词法混合检索 |
| 定时任务 | APScheduler（单进程） |
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Vue Router |
| UI | Naive UI + ECharts，临床工作台主题（暖白底 + 松绿主色） |
| 部署 | Docker Compose + Nginx |

## 4. 系统架构

```text
浏览器（Vue 3）
    │ HTTP
Nginx ── /api、/uploads 反向代理
    │
FastAPI
    ├─ MySQL 8：业务数据、Agent 会话与工具轨迹、MCP 审计
    ├─ Redis 7：限流计数（故障时退回进程内存）
    ├─ DeepSeek（OpenAI 兼容接口）：对话与工具调用
    └─ 支付宝网关 / 外部 MCP Server
```

### 4.1 目录结构

```text
backend/
  app/
    api/          # FastAPI 路由
    models/       # SQLAlchemy 模型
    schemas/      # Pydantic 模型
    services/     # 业务逻辑（权限、事务、Agent 工具的服务层）
    agent/        # 系统提示词、工具定义、LLM 客户端与 Agent 循环
    payments/     # 支付渠道客户端（支付宝 RSA2 签名与验签）
    mcp/          # MCP Server 与客户端
    dependencies/ # 鉴权依赖
    common/       # 统一响应与异常
    utils/        # JWT、密码
  tests/
  migrations/     # Alembic
  evaluation/     # Agent 评测与 MCP 专项评测
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
  alipay-sandbox.md
  progress.md     # 开发日志
```

## 5. 核心设计

### 5.1 智能体与权限边界

- **草稿 + 人工确认**：`create_boarding_draft` 只写草稿；确认接口不注册为 Agent 工具，只能由用户在前端点击触发。
- **权限感知工具**：用户身份只取自 JWT，工具不接受模型传入的 `user_id`；权限判断与行级过滤在服务层完成。
- **不可信上下文**：知识库片段、宠物备注与外部 MCP 结果均按不可信数据处理，并配套提示注入测试用例。
- **可观测**：每轮对话记录 trace、工具参数、耗时、token 与错误码。

### 5.2 流式输出

助手通过 SSE 返回两类事件：工具步骤（`llm_start`、`tool_start`、`tool_end` 等）与正文增量（`delta`）。后端以 `stream: true` 调用模型，逐段回调正文；工具调用的分片参数按 index 拼装。前端累加增量渲染，并在收到完整 `assistant` 事件后以其为准校正。Nginx 对 `/api` 关闭 `proxy_buffering`，避免事件被合并成一整块。

### 5.3 RAG 与可信回答

14 篇护理知识，本地 bge-small-zh（512 维）向量 + 中文词法混合检索；低于阈值拒答，知识片段标记为不可信资料并强制标注来源。

### 5.4 MCP 能力开放

7 个只读工具通过 MCP Server 暴露，复用 `app/agent/tools.py` 的服务层，身份只来自 token；写操作与确认接口均不在 MCP 工具表中。站内 Agent 同时作为 MCP Client 接入外部只读工具，本地工具与外部工具合并为同一份 function schema，外部工具使用 `mcp__server__tool` 命名空间，并做描述过滤、结果限长与故障降级。HTTP 入口按用户限流，每次调用写入审计表。

### 5.5 支付与交易闭环

- 支持模拟收银台与支付宝沙箱电脑网站支付（`alipay.trade.page.pay`）。
- 请求使用应用私钥做 RSA2 签名（签名串包含 `sign_type`）；异步通知验签剔除 `sign` 与 `sign_type`。
- 沙箱查单响应为 GBK 编码，验签针对原始字节而非重新编码后的文本。
- 异步通知与主动查单双通道核销，校验 `app_id`、金额与订单号；重复通知幂等；订单已由其他支付单付清时，当前支付单关闭而不重复入账。
- 支付单过期关单后 24 小时内仍允许主动查单，覆盖“到期后才完成付款”的情况。
- 并发创建由订单行锁串行化，重复点击不会生成多张支付单。

### 5.6 评测与消融

101 条 YAML 用例（91 条 Agent + 10 条 MCP），使用真实 `deepseek-flash` 走完整 HTTP 链路；baseline 与 5 个消融变体（`no_tools`、`no_rag`、`no_permission`、`no_citation`、`no_draft_confirmation`）输出任务成功率、工具与参数准确率、P95 延迟与 token 成本。

## 6. 本地开发

### 6.1 环境要求

- Python 3.12+
- Node.js 18+
- MySQL 8.x / 9.x
- Redis 7（可选）
- Docker 与 Docker Compose（容器化运行）

### 6.2 后端

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # 填入真实配置
uvicorn app.main:app --reload --port 8000
```

本地开发与部署统一使用 MySQL，表结构由 Alembic 管理。首次启动前需建库与账号：

```sql
CREATE DATABASE pawcare CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'pawcare'@'localhost' IDENTIFIED BY 'pawcare_dev_password';
GRANT ALL PRIVILEGES ON pawcare.* TO 'pawcare'@'localhost';
-- Agent 评测会在同实例上创建 / 删除独立评测库 pawcare_eval
GRANT ALL PRIVILEGES ON `pawcare_eval`.* TO 'pawcare'@'localhost';
FLUSH PRIVILEGES;
```

随后将 `backend/.env` 中的 `DATABASE_URL` 改为对应密码，执行迁移：

```bash
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
```

迁移文件位于 [backend/migrations/](backend/migrations/)。MySQL 不支持 PostgreSQL 的 `EXCLUDE` 排他约束，同一笼舍的档期冲突由应用层在确认事务中校验。SQLite 仅用于 pytest（`tests/conftest.py` 自动创建临时库），不参与日常开发。

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

登录页提供演示账号面板，点击即可填入表单。对外部署时可在根目录 `.env` 设置 `VITE_DEMO_ACCOUNTS=false` 后重新构建前端以隐藏该面板。

### 6.3 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行于 `http://localhost:5173`，Vite 将 `/api` 代理到 `http://127.0.0.1:8000`。

### 6.4 Docker Compose

```bash
copy .env.example .env      # Windows
cp .env.example .env        # Linux / macOS
docker compose up -d --build
docker compose ps
```

- 后端容器启动时先执行 `alembic upgrade head`，再启动 uvicorn；`.env` 不进入镜像。
- 前端默认 `http://localhost:8080`，`/api` 与 `/uploads` 由容器内 Nginx 反向代理至后端；MySQL、Redis 与后端仅绑定 `127.0.0.1`。
- 服务器部署时将根目录 `.env` 的 `FRONTEND_PORT` 设为 `80`，即可通过公网 IP 访问。
- 国内网络构建较慢时，可在根目录 `.env` 启用 `APT_MIRROR`、`PIP_INDEX_URL`、`NPM_REGISTRY`；拉取 Docker Hub 镜像失败时，为 `/etc/docker/daemon.json` 配置 `registry-mirrors` 后重启 Docker。
- 知识库模型缓存在 `backend/.fastembed_cache`，首次检索会下载 BGE 模型；挂载后可避免重建镜像时重复下载。

常用运维命令：

```bash
docker compose exec backend python scripts/seed.py
docker compose logs -f backend
docker compose exec backend python -m alembic current
```

## 7. MCP Server

PawCare 将 7 个只读领域工具通过 MCP 开放给外部 Agent：

`list_my_pets`、`get_pet_health_records`、`get_upcoming_reminders`、`check_kennel_availability`、`list_boarding_orders`、`get_boarding_daily_reports`、`search_care_knowledge`。

### 7.1 stdio（本地 Claude Desktop / Cursor）

```bash
# 先登录获取 JWT
curl -s http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"owner","password":"Owner12345"}'

# 将 data.token 注入环境变量后启动
set PAWCARE_MCP_TOKEN=<token>
python -m app.mcp.server --transport stdio
```

Claude Desktop 配置示例（Windows，路径按实际项目位置替换）：

```json
{
  "mcpServers": {
    "pawcare": {
      "command": "<项目路径>\\backend\\.venv\\Scripts\\python.exe",
      "args": ["-m", "app.mcp.server", "--transport", "stdio"],
      "env": {
        "PAWCARE_MCP_TOKEN": "<token>",
        "PYTHONPATH": "<项目路径>\\backend"
      }
    }
  }
}
```

### 7.2 Streamable HTTP（远程 / 多用户）

```bash
python -m app.mcp.server --transport streamable-http --host 127.0.0.1 --port 8765

# POST /mcp，Authorization: Bearer <JWT>
# GET  /health 无需认证
```

可使用 MCP Inspector 验证工具列表与调用：

```bash
npx @modelcontextprotocol/inspector
```

### 7.3 站内 Agent 接入外部 MCP

在 `backend/.env` 中配置 `MCP_CLIENT_SERVERS`（JSON 数组），仅接受 `readOnlyHint=True` 的工具：

```bash
# stdio：每次发现 / 调用单独拉起进程，token 通过 ${VAR} 从环境变量读取
MCP_CLIENT_SERVERS=[{"name":"pawcare","transport":"stdio","command":"python","args":["-m","app.mcp.server","--transport","stdio"],"env":{"PAWCARE_MCP_TOKEN":"${PAWCARE_MCP_TOKEN}"}}]

# 远程：Streamable HTTP
MCP_CLIENT_SERVERS=[{"name":"remote","transport":"streamable-http","url":"https://example.com/mcp","headers":{"Authorization":"Bearer ${REMOTE_MCP_TOKEN}"}}]
```

- 外部工具以 `mcp__<server>__<tool>` 暴露给模型，不会覆盖本地同名工具。
- 工具描述中的“忽略之前指令 / 系统提示词 / API Key”等字样会被整段替换；返回值超过 32KB 直接拒绝，调用超时（默认 8 秒）返回结构化错误。
- 单个 Server 发现失败仅影响自身，站内对话退化为仅使用本地工具。
- 外部工具返回的内容在系统提示中标记为不可信资料，不能据此触发写操作。

### 7.4 限流与审计

- HTTP 入口按用户限流：默认 60 次 / 分钟（`MCP_RATE_LIMIT_PER_MINUTE`），超限返回 429 与 `Retry-After`；部署时配合 `REDIS_URL` 使用 Redis 计数。
- 每次调用（含被拒绝的调用）写入 `mcp_audit_logs`：用户、传输方式、工具、参数摘要、状态（ok / error / denied / timeout）、耗时、IP、trace_id。
- 管理端查询：`GET /api/admin/mcp-audit?user_id=&tool=&status=&page=`。

### 7.5 边界说明

- stdio 为单用户模式，token 在进程启动时固定；HTTP 每次请求校验 JWT，支持多用户。
- MCP 仅提供只读能力，写操作仍遵循“生成草稿 → 用户确认”。
- Streamable HTTP 使用 `json_response=True`，与站内 Agent 的 SSE 是两条独立链路。
- 单次工具调用超时 5 秒（`MCP_TOOL_TIMEOUT_SECONDS`），结果超过 32KB 直接拒绝。
- 公网部署建议仅监听 `127.0.0.1`，由 Nginx 增加 `/mcp` 反向代理并关闭缓冲；当前 ECS 部署未对外暴露 MCP 端口。

## 8. 评测

```powershell
cd backend
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\python.exe evaluation\runner.py --dry-run
.\.venv\Scripts\python.exe evaluation\runner.py
```

评测会复制开发库、自动创建注入测试数据，并使用真实模型走完整 HTTP 链路，输出任务成功率、工具选择准确率、参数准确率、P95 延迟与 token 成本；JSON / CSV 报告写入 `backend/evaluation/reports/`（不提交仓库）。

baseline 与消融实验使用同一套用例切换变体：

```powershell
.\.venv\Scripts\python.exe evaluation\runner.py --cases evaluation\ablation_cases.yaml --variant no_rag
```

字段说明与扩展示例见 [backend/evaluation/README.md](backend/evaluation/README.md)。

调度引擎默认为显式循环；LangGraph 适配层用于对照实验（需安装 `requirements-agent.txt`）：

```powershell
.\.venv\Scripts\python.exe evaluation\runner.py --engine langgraph --case pets-001 --case knowledge-001
```

报告文件名与 JSON 中会带引擎标识。主链路选择显式循环的原因与两种实现的差异见 [docs/architecture.md](docs/architecture.md#6-调度引擎选型)。

MCP 专项评测不调用模型，直接验证工具发现、只读边界、身份隔离、描述注入、超时、结果上限与故障降级：

```powershell
.\.venv\Scripts\python.exe evaluation\mcp_runner.py --list
.\.venv\Scripts\python.exe evaluation\mcp_runner.py
.\.venv\Scripts\python.exe evaluation\mcp_runner.py --only mcp-timeout --strict
```

10 条检查覆盖 PawCare Server 与 5 种模拟 Server（恶意描述、写工具、慢响应、超大结果、同名工具）。输出 `evaluation/reports/mcp_eval_*.json/.csv`；演示库缺少 `owner` / `owner2` 账号时，依赖真实数据的三条用例标记为 skipped。

## 9. 支付接入

默认 `PAYMENT_PROVIDER=mock` 使用本地模拟收银台；填写支付宝沙箱参数后改为 `alipay`，即启用电脑网站支付：

- 后端使用应用私钥做 RSA2 签名，生成收银台跳转地址；付款完成后支付宝同步跳回 `/pay/<支付单号>`，页面主动查单。
- 异步通知 `POST /api/payments/alipay/notify` 校验签名、`app_id`、可选 `seller_id` 与订单金额，核销成功后才会将订单标记为已支付；重复通知幂等。
- 异步通知丢失时，“我已完成支付”会调用 `alipay.trade.query` 主动对账，查单响应同样验签。
- 切换为支付宝渠道后，模拟回调接口统一返回 403，避免绕过真实支付。

支付宝沙箱对个人开发者开放：在 [支付宝开放平台](https://open.alipay.com/) 创建沙箱应用，使用密钥工具生成应用私钥，上传应用公钥后复制“支付宝公钥”，将两个 PEM 文件放入 `backend/secrets/`（已加入 `.gitignore`），并填写 `ALIPAY_APP_ID`。本地联调异步通知需要内网穿透地址并配置到 `PUBLIC_BASE_URL`；无公网回调时仍可通过主动查单完成支付。完整步骤见 [docs/alipay-sandbox.md](docs/alipay-sandbox.md)。

## 10. 环境变量

真实密钥仅存放于 `.env`，不进入仓库。模板见 `backend/.env.example` 与根目录 `.env.example`。

| 变量 | 说明 |
|---|---|
| `DATABASE_URL` | 本地：`mysql+pymysql://pawcare:密码@127.0.0.1:3306/pawcare?charset=utf8mb4` |
| `JWT_SECRET_KEY` | 至少 32 位随机值，每个项目独立 |
| `LLM_API_KEY` | DeepSeek / OpenAI 兼容接口密钥 |
| `LLM_MODEL` | 当前使用 `deepseek-flash` |
| `LLM_BASE_URL` | `https://api.deepseek.com` |
| `AGENT_ENGINE` | `explicit`（默认）/ `langgraph`（对照实验） |
| `REDIS_URL` | 留空时使用进程内限流 |
| `MCP_TOOL_TIMEOUT_SECONDS` | MCP Server 单次工具调用超时，默认 5 秒 |
| `MCP_RATE_LIMIT_PER_MINUTE` | MCP HTTP 每用户每分钟请求上限，0 表示关闭 |
| `MCP_AUDIT_ENABLED` | 是否写入 `mcp_audit_logs`，默认 `true` |
| `MCP_CLIENT_SERVERS` | 站内 Agent 接入的外部 MCP Server（JSON 数组） |
| `MCP_CLIENT_CALL_TIMEOUT_SECONDS` | 外部工具单次调用超时，默认 8 秒 |
| `RAG_ENABLED` | 是否启用知识库检索，默认 `true` |
| `RAG_EMBEDDING_MODEL` | 默认 `BAAI/bge-small-zh-v1.5` |
| `RAG_TOP_K` / `RAG_MIN_SCORE` | 返回片段数与混合检索阈值 |
| `SMTP_HOST` / `SMTP_PORT` | 邮箱验证码 SMTP，QQ 为 `smtp.qq.com:465`，163 为 `smtp.163.com:465` |
| `SMTP_USER` / `SMTP_PASSWORD` | 发信邮箱与客户端授权码（非登录密码） |
| `SMS_PROVIDER` | 手机验证码发送器，`console` 仅写日志；接入短信服务后扩展 |
| `VERIFY_CODE_DEBUG` | `true` 时接口直接返回 `debug_code`，仅限本地；部署必须为 `false` |
| `LOGIN_MAX_FAILURES` / `LOGIN_LOCK_MINUTES` | 连续密码错误锁定阈值，默认 5 次 / 15 分钟 |
| `PAYMENT_PROVIDER` | `mock`（本地演示）/ `alipay`（支付宝沙箱或正式网关） |
| `PAYMENT_TTL_MINUTES` | 支付单有效期，默认 15 分钟 |
| `PAYMENT_MOCK_BASE_URL` | 前端地址，模拟支付页与支付宝同步跳转均回到此处 |
| `PUBLIC_BASE_URL` | 后端公网地址，用于生成支付宝异步通知地址 |
| `ALIPAY_APP_ID` | 支付宝开放平台应用 APPID |
| `ALIPAY_PRIVATE_KEY` | 应用私钥，填写 PEM 内容或文件路径（推荐 `secrets/alipay_app_private.pem`） |
| `ALIPAY_PUBLIC_KEY` | 支付宝公钥，填写 PEM 内容或文件路径（推荐 `secrets/alipay_public.pem`） |
| `ALIPAY_GATEWAY` | 沙箱网关，正式环境改为 `https://openapi.alipay.com/gateway.do` |
| `ALIPAY_NOTIFY_URL` | 异步通知地址；留空时由 `PUBLIC_BASE_URL` 拼接 |
| `ALIPAY_SELLER_ID` | 可选，用于校验通知中的收款账号 |
| `UPLOAD_DIR` / `MAX_FILE_SIZE_MB` | 图片存放目录与单图上限，默认 `uploads` / 10MB |
| `SCHEDULER_ENABLED` | 每日 08:00 提醒同步任务；测试环境设为 `false` |

注册与找回密码支持邮箱或手机号验证码：6 位数字、5 分钟有效、60 秒重发冷却、每小时最多 5 次、最多试错 5 次、一次核销，旧码在签发新码时立即作废。数据库仅保存 HMAC-SHA256 摘要。本地未配置 SMTP 时，验证码打印到后端日志并从接口返回，便于联调；上线前需关闭 `VERIFY_CODE_DEBUG` 并配置 SMTP 授权码。

## 11. 开发进度

- [x] 项目骨架、统一响应、异常处理
- [x] 用户 / 宠物 / 健康档案模型
- [x] 注册登录、JWT 鉴权、角色守卫
- [x] 邮箱 / 手机验证码注册、找回密码、连续失败锁定
- [x] 宠物档案、体重、健康记录、提醒同步接口
- [x] 后端 pytest 用例（认证 / 权限 / 档案 / 提醒）
- [x] 前端骨架：登录、工作台、宠物列表、详情、Agent 占位页
- [x] 寄养主流程：笼舍、空档查询、草稿确认、订单状态流转、日报
- [x] 演示数据 seed 脚本（账号 / 宠物 / 健康记录 / 笼舍 / 订单）
- [x] 寄养前端页面：空档查询、草稿倒计时确认、订单流转、日报
- [x] Agent 工具层：8 个权限感知工具，工具注册表中不含确认工具
- [x] 多轮工具调用循环、会话历史持久化、token / 耗时 / 错误码 trace
- [x] `POST /api/agent/chat` 与历史会话接口，deepseek-flash 真实冒烟通过
- [x] 前端智能助手页：多轮对话、工具轨迹、草稿卡片、历史会话切换
- [x] SSE 流式输出：步骤事件 + 正文逐字增量 + 前端增量渲染
- [x] RAG：14 篇护理知识、混合检索、来源标注、拒答与注入防护
- [x] 评测 harness：101 条 YAML 用例、隔离评测库、JSON / CSV 报告
- [x] Alembic 初始迁移（MySQL）、向量存库 + 应用层余弦检索、订单档期冲突校验
- [x] Docker Compose 部署验证（ECS 四容器 healthy；公网访问需在安全组放行 TCP 80）
- [x] 支付收银台：模拟渠道 + 支付宝沙箱电脑网站支付、RSA2 验签、主动查单、回调幂等
- [x] 支付可靠性：并发核销修复、关单后 24 小时查单兜底、创建幂等，公网异步通知实测通过
- [x] 通知中心：站内通知、偏好开关、健康提醒完成 / 延后、每日 08:00 定时补发
- [x] 图片上传：宠物头像、日报照片（魔数识别、10MB 上限、UUID 文件名）
- [x] 管理控制台：运营概览、账号启停、笼舍占用、审计日志、只读知识库
- [x] 寄养订单时间轴：预约 → 确认 → 入住 → 退房
- [x] MCP Server：7 个只读工具、stdio / Streamable HTTP、JWT 校验、工具白名单
- [x] 统一工具注册表：本地 8 个 + 外部 MCP 只读工具（命名空间、注入过滤、故障降级）
- [x] MCP HTTP 按用户限流 + `mcp_audit_logs` 调用审计 + 管理端查询
- [x] MCP 专项评测：10 条检查（发现 / 隔离 / 注入 / 超时 / 结果上限 / 降级）
- [x] 后端 pytest 156 条用例全部通过
- [x] baseline / 消融实验（无工具、去 RAG、去权限、去引用、去确认边界）
- [x] LangGraph 对照适配层（`AGENT_ENGINE` / 评测 `--engine`，生产默认显式循环）

## 12. 说明

- 演示数据全部为合成数据，不包含真实用户或真实病例。
- 仓库仅包含 `.env.example` 与密钥占位文件，真实 `.env`、应用私钥与支付宝公钥不进入版本库。
- 本项目为独立实现，未复用其他项目的数据库、JWT 密钥或前端代码。
- 支付功能当前运行于支付宝沙箱环境，不产生真实资金流转；切换正式网关需完成商户签约并替换 APPID 与密钥。
