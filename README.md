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
| 数据库 | MySQL 8+（PyMySQL）+ Alembic |
| 缓存/限流 | Redis 7（可选，未启动时退回进程内存） |
| 鉴权 | JWT + bcrypt，三角色：宠物主 / 寄养员 / 管理员 |
| Agent | 显式工具调用循环 + 步骤/逐字 SSE（httpx + OpenAI 兼容接口）；附 LangGraph 对照适配层 |
| 能力开放 | MCP 1.30：只读 Server（stdio / Streamable HTTP）+ 站内 Agent 的只读 MCP Client |
| RAG | fastembed + bge-small-zh-v1.5（512 维），向量以 JSON 文本存库，应用层余弦 + 词法混合检索 |
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
- **能力开放**：7 个只读工具通过 MCP Server 暴露，写操作仍留在站内确认流程。
- **统一工具入口**：本地工具与外部 MCP 只读工具合并成同一份 function schema；
  外部工具使用 `mcp__server__tool` 命名空间，描述过滤、结果限长、故障降级。
- **入口治理**：MCP HTTP 按用户限流，每次调用写审计表，管理端可按用户 / 工具 / 状态查询。

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

本地开发和部署统一使用 MySQL（8.x / 9.x 均可），表结构由 Alembic 管理。
首次启动前先建库和账号（用你有权限的 MySQL 账号执行一次）：

```sql
CREATE DATABASE pawcare CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'pawcare'@'localhost' IDENTIFIED BY 'pawcare_dev_password';
GRANT ALL PRIVILEGES ON pawcare.* TO 'pawcare'@'localhost';
-- Agent 评测会在同实例上建/删独立评测库 pawcare_eval
GRANT ALL PRIVILEGES ON `pawcare_eval`.* TO 'pawcare'@'localhost';
FLUSH PRIVILEGES;
```

然后把 `backend/.env` 里的 `DATABASE_URL` 改成对应密码，执行迁移：

```bash
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
```

迁移文件在 [backend/migrations/](backend/migrations/)。MySQL 不支持 PostgreSQL 的
`EXCLUDE` 排他约束，同一笼舍的档期冲突由应用层在确认事务中校验。

SQLite 只用于 pytest（`tests/conftest.py` 自动建临时库），不参与日常开发。

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

登录页的“演示账号”面板会列出宠物主 / 寄养员 / 管理员三个账号，点一下就填入表单，答辩时不用手打。
如不需要（例如正式对外），在根 `.env` 设 `VITE_DEMO_ACCOUNTS=false` 后重新构建前端即可隐藏。

### 5.2 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认 `http://localhost:5173`，Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

### 5.3 Docker Compose

```bash
copy .env.example .env      # Windows
cp .env.example .env        # Linux / macOS
docker compose up -d --build
docker compose ps
```

- 后端容器启动时先执行 `alembic upgrade head`，再启动 uvicorn；`.env` 不进入镜像。
- 前端默认 `http://localhost:8080`，`/api` 与 `/uploads` 由容器内 Nginx 反代到
  backend；MySQL / Redis / 后端只绑定 `127.0.0.1`，不会暴露到局域网或公网。
- 服务器上把根目录 `.env` 的 `FRONTEND_PORT` 改成 `80`，即可直接用公网 IP 访问。
- 国内网络构建慢时，在根目录 `.env` 打开 `APT_MIRROR` / `PIP_INDEX_URL` /
  `NPM_REGISTRY` 三行（模板里给了阿里云和 npmmirror 地址）；拉不到 Docker Hub
  镜像时给 `/etc/docker/daemon.json` 配 `registry-mirrors` 后重启 Docker。
- `frontend/nginx.conf` 对 `/api` 关闭了 `proxy_buffering`，否则助手 SSE 会被
  缓冲成一整块，步骤轨迹无法逐条显示。
- 知识库模型缓存在 `backend/.fastembed_cache`，首次检索会下载 BGE 模型；
  挂载后重建镜像不必重复下载。

演示数据与排查：

```bash
docker compose exec backend python scripts/seed.py
docker compose logs -f backend
docker compose exec backend python -m alembic current
```

### 5.4 MCP Server

PawCare 把 7 个只读领域工具通过 MCP 开放给外部 Agent。工具复用
`app/agent/tools.py` 的服务层，身份只来自 token；`create_boarding_draft`
和确认接口都不在 MCP 工具表中。

工具：`list_my_pets`、`get_pet_health_records`、`get_upcoming_reminders`、
`check_kennel_availability`、`list_boarding_orders`、
`get_boarding_daily_reports`、`search_care_knowledge`。

stdio（本地 Claude Desktop / Cursor）：

```bash
# 先登录拿 JWT
curl -s http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"owner","password":"Owner12345"}'

# 把 data.token 注入环境变量后启动
set PAWCARE_MCP_TOKEN=<token>
python -m app.mcp.server --transport stdio
```

Claude Desktop 配置示例（Windows）：

```json
{
  "mcpServers": {
    "pawcare": {
      "command": "E:\\毕设\\backend\\.venv\\Scripts\\python.exe",
      "args": ["-m", "app.mcp.server", "--transport", "stdio"],
      "env": {
        "PAWCARE_MCP_TOKEN": "<token>",
        "PYTHONPATH": "E:\\毕设\\backend"
      }
    }
  }
}
```

Streamable HTTP（远程 / 多用户）：

```bash
python -m app.mcp.server --transport streamable-http --host 127.0.0.1 --port 8765

# POST /mcp，Authorization: Bearer <JWT>
# GET  /health 不需要认证
```

可以用 MCP Inspector 验证工具列表和调用：

```bash
npx @modelcontextprotocol/inspector
```

#### 接入外部 MCP（站内 Agent 作为 Client）

Agent 也能反向消费别的 MCP Server。在 `backend/.env` 里配置
`MCP_CLIENT_SERVERS`（JSON 数组），**只接受 `readOnlyHint=True` 的工具**：

```bash
# stdio：每次发现 / 调用单独拉起进程，token 用 ${VAR} 从环境变量取
MCP_CLIENT_SERVERS=[{"name":"pawcare","transport":"stdio","command":"python","args":["-m","app.mcp.server","--transport","stdio"],"env":{"PAWCARE_MCP_TOKEN":"${PAWCARE_MCP_TOKEN}"}}]

# 远程：Streamable HTTP
MCP_CLIENT_SERVERS=[{"name":"remote","transport":"streamable-http","url":"https://example.com/mcp","headers":{"Authorization":"Bearer ${REMOTE_MCP_TOKEN}"}}]
```

- 外部工具以 `mcp__<server>__<tool>` 暴露给模型，不会覆盖本地同名工具。
- 工具描述中的“忽略之前指令 / 系统提示词 / API key”等字样会被整段替换；
  返回值超过 32KB 拒绝，调用超时（默认 8 秒）返回结构化错误。
- 单个 Server 发现失败只影响它自己，站内对话退化为只用本地工具。
- 外部工具返回的内容在系统提示里标记为不可信资料，不能据此触发写操作。

#### 限流与审计

- HTTP 入口按用户限流：默认 60 次/分钟（`MCP_RATE_LIMIT_PER_MINUTE`），
  超限返回 429 + `Retry-After`；部署时配合 `REDIS_URL` 使用 Redis 计数。
- 每次调用（含被拒绝的调用）写入 `mcp_audit_logs`：用户、传输方式、工具、
  参数摘要、状态（ok / error / denied / timeout）、耗时、IP、trace_id。
- 管理端查询：`GET /api/admin/mcp-audit?user_id=&tool=&status=&page=`。

边界：

- stdio 是单用户，token 在进程启动时固定；HTTP 每个请求校验 JWT，支持多用户。
- MCP 只读；写操作仍然只能走“生成草稿 → 用户在前端确认”。
- MCP 的 Streamable HTTP 使用 `json_response=True` 关闭了 SSE；这和站内 Agent
  的步骤级 SSE 是两条独立的链路。
- 单次工具调用超时 5 秒（`MCP_TOOL_TIMEOUT_SECONDS`），结果超过 32KB 直接拒绝。
- 公网部署时建议只监听 `127.0.0.1`，由 Nginx 增加 `/mcp` 反代并关闭缓冲；
  当前 ECS 部署没有对外暴露 MCP 端口。

### 5.5 Agent 评测

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

MCP 专项评测不调用模型，直接验证工具发现、只读边界、身份隔离、描述注入、
超时、结果上限和故障降级：

```powershell
.\.venv\Scripts\python.exe evaluation\mcp_runner.py --list
.\.venv\Scripts\python.exe evaluation\mcp_runner.py
.\.venv\Scripts\python.exe evaluation\mcp_runner.py --only mcp-timeout --strict
```

10 条检查覆盖 PawCare Server 与 5 种假 Server（恶意描述、写工具、慢响应、
超大结果、同名工具）。输出 `evaluation/reports/mcp_eval_*.json/.csv`；演示库
缺少 owner / owner2 账号时，依赖真实数据的三条用例标记为 skipped。

## 6. 环境变量

真实密钥只放在 `.env`，不进仓库。模板见 `backend/.env.example` 和根目录 `.env.example`。

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
| `MCP_RATE_LIMIT_PER_MINUTE` | MCP HTTP 每用户每分钟请求上限，0 关闭 |
| `MCP_AUDIT_ENABLED` | 是否写 `mcp_audit_logs`，默认 `true` |
| `MCP_CLIENT_SERVERS` | 站内 Agent 接入的外部 MCP Server（JSON 数组） |
| `MCP_CLIENT_CALL_TIMEOUT_SECONDS` | 外部工具单次调用超时，默认 8 秒 |
| `RAG_ENABLED` | 是否启用知识库检索，默认 `true` |
| `RAG_EMBEDDING_MODEL` | 默认 `BAAI/bge-small-zh-v1.5` |
| `RAG_TOP_K` / `RAG_MIN_SCORE` | 返回片段数与混合检索阈值 |
| `SMTP_HOST` / `SMTP_PORT` | 邮箱验证码 SMTP，QQ 为 `smtp.qq.com:465`，163 为 `smtp.163.com:465` |
| `SMTP_USER` / `SMTP_PASSWORD` | 发信邮箱与客户端授权码（不是登录密码） |
| `SMS_PROVIDER` | 手机验证码发送器，`console` 只写日志；接入短信服务后再扩展 |
| `VERIFY_CODE_DEBUG` | `true` 时接口直接返回 `debug_code`，仅限本地；部署必须为 `false` |
| `LOGIN_MAX_FAILURES` / `LOGIN_LOCK_MINUTES` | 连续密码错误锁定阈值，默认 5 次 / 15 分钟 |
| `PAYMENT_PROVIDER` | `mock`（本地演示）/ `alipay`（支付宝沙箱或正式网关） |
| `PAYMENT_TTL_MINUTES` | 支付单有效期，默认 15 分钟 |
| `PAYMENT_MOCK_BASE_URL` | 前端地址，模拟支付页与支付宝同步跳转都回到这里 |
| `PUBLIC_BASE_URL` | 后端公网地址，用于生成支付宝异步通知地址 |
| `ALIPAY_APP_ID` | 支付宝开放平台应用的 APPID |
| `ALIPAY_PRIVATE_KEY` | 应用私钥，填 PEM 内容或文件路径（推荐 `secrets/alipay_app_private.pem`） |
| `ALIPAY_PUBLIC_KEY` | 支付宝公钥，填 PEM 内容或文件路径（推荐 `secrets/alipay_public.pem`） |
| `ALIPAY_GATEWAY` | 沙箱网关，正式环境改为 `https://openapi.alipay.com/gateway.do` |
| `ALIPAY_NOTIFY_URL` | 异步通知地址；留空时用 `PUBLIC_BASE_URL` 拼出 |
| `ALIPAY_SELLER_ID` | 可选，校验通知中的收款账号 |
| `UPLOAD_DIR` / `MAX_FILE_SIZE_MB` | 图片存放目录与单图上限，默认 `uploads` / 10MB |
| `SCHEDULER_ENABLED` | 每日 08:00 提醒同步任务；测试环境设为 `false` |

注册与找回密码支持邮箱或手机号验证码：6 位数字、5 分钟有效、60 秒重发冷却、
每小时最多 5 次、最多试错 5 次、一次核销，旧码在签发新码时立即作废。
数据库只保存 HMAC-SHA256 摘要。本地未配置 SMTP 时，验证码打印到后端日志
并从接口返回，方便联调；上线前关闭 `VERIFY_CODE_DEBUG` 并填写 SMTP 授权码。

寄养订单支持在线支付，默认 `PAYMENT_PROVIDER=mock` 使用本地模拟收银台；
填好支付宝沙箱参数后改为 `alipay`，即走**电脑网站支付**（`alipay.trade.page.pay`）：

- 后端用应用私钥做 RSA2 签名，生成收银台跳转地址；前端点「前往支付宝支付」打开，
  付款完成后支付宝同步跳回 `/pay/<支付单号>`，页面主动查单。
- 异步通知 `POST /api/payments/alipay/notify` 会校验签名、`app_id`、可选
  `seller_id` 和订单金额，核销成功才把订单标记为已支付；重复通知幂等。
- 异步通知丢失时，「我已完成支付」会调用 `alipay.trade.query` 主动对账，
  查单响应同样验签。
- 切到 `alipay` 后模拟回调接口直接返回 403，不能靠本地按钮白拿订单。

支付宝沙箱对个人开放：在 [支付宝开放平台](https://open.alipay.com/) 创建沙箱应用，
用密钥工具生成应用私钥，把应用公钥上传后复制「支付宝公钥」，两个 PEM 放进
`backend/secrets/`（已加入 `.gitignore`），再填 `ALIPAY_APP_ID`。本地联调异步
通知需要内网穿透地址填到 `PUBLIC_BASE_URL`；没有公网回调时仍可用主动查单完成支付。
完整步骤见 [docs/alipay-sandbox.md](docs/alipay-sandbox.md)。

## 7. 当前进度

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
- [x] Agent 工具层：8 个权限感知工具，工具注册表中没有确认工具
- [x] 多轮工具调用循环、会话历史持久化、token / 耗时 / 错误码 trace
- [x] `POST /api/agent/chat` 与历史会话接口，deepseek-flash 真实冒烟通过
- [x] 前端智能助手页：多轮对话、工具轨迹、草稿卡片、历史会话切换
- [x] SSE 流式输出：步骤事件 + 正文逐字增量 + 前端增量渲染
- [x] RAG：14 篇护理知识、混合检索、来源标注、拒答与注入防护
- [x] 评测 harness：91 条 YAML 用例、隔离评测库、JSON / CSV 报告
- [x] Alembic 初始迁移（MySQL）、向量存库 + 应用层余弦检索、订单档期冲突校验
- [x] Docker Compose 部署验证（ECS 上四容器 healthy；公网访问需在安全组放行 TCP 80）
- [x] 支付收银台：模拟渠道 + 支付宝沙箱电脑网站支付、RSA2 验签、主动查单、回调幂等
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

## 8. 说明

- 演示数据全部为合成数据，不使用真实用户或真实病例。
- 本项目与 `lab-agent` 是两个独立项目，不复用其数据库、JWT 密钥或前端代码。
