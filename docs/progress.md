# 开发日志

## 2026-10-19 · 第 1 天

### 完成

- 初始化仓库结构与开发文档（README、架构、ER 图）。
- 后端骨架：配置、SQLAlchemy 2.0、统一响应与异常、JWT 鉴权、bcrypt、角色守卫、限流。
- 数据模型：用户、宠物、体重、健康记录、附件、笼舍、寄养订单、日报、用药、草稿、提醒、通知、Agent 会话/消息/工具调用、知识库、审计日志。
- 核心接口：注册 / 登录 / 当前用户 / 改密码；宠物增删改查；体重记录；健康记录增删改查；提醒查询与自动同步。
- 权限规则：宠物主只能访问自己的宠物；寄养员只读宠物档案；写操作在服务层校验。
- 测试：认证、越权、寄养员权限、体重、健康记录与提醒同步。
- 前端骨架：Vue 3 + TypeScript + Vite + Pinia + Naive UI + ECharts，暖色主题。
- 前端页面：登录/注册、工作台、宠物档案、宠物详情（体重曲线、健康档案、提醒）、Agent 占位页。
- 部署文件：Dockerfile、Nginx 配置、Compose 服务。

### 验证

- `backend/.venv` 依赖安装完成（Python 3.13.5）。
- `pytest`：15 passed。
- `npm run typecheck`：通过。
- `npm run build`：通过（Vite 6.4.4）。
- 真实服务冒烟：注册、登录、建档、写健康记录、生成提醒全部返回 200。
- 修复：SlowAPI 初始化会自动读取 cwd 下 `.env` 并使用系统默认编码，Windows 上遇到 UTF-8 中文注释会崩溃；改为读取专用的 `.slowapi.env`。

### 提交

- `2671f87` feat: 初始化 PawCare 后端核心链路与前端骨架
- `2dacf0e` fix: 宠物详情路由复用与助手进度文案
- `6d3fbda` docs: 记录第一天验证结果与推送阻塞
- 远程已配置为 `https://github.com/nzbyb/pawcare.git`。
- 推送阻塞：当前网络无法连接 `github.com:443`（无代理，TCP 探测失败），且远端仓库尚未创建。
  网络恢复并在 GitHub 创建仓库后执行：`git push -u origin main`。

### 下一步

1. 增加笼舍与寄养订单服务、重叠日期约束、草稿确认接口。
2. 写合成数据 seed 脚本，保证演示账号与数据可复现。
3. 接入 Agent 工具层（LangGraph），实现 SSE 流式输出与工具轨迹。
4. 准备知识库切片与 RAG 引用。
5. 补 Alembic 迁移，启动 Docker Postgres 验证生产路径。

## 2026-10-19 · 第 2 天

### 完成

- 寄养服务层：笼舍维护、空档查询、草稿创建 / 查看 / 取消 / 确认、订单查询与状态流转、日报。
- 空档判断采用半开区间 `[start, end)`，`pending` 订单同样占位，避免“先确认再撞车”。
- 草稿有效期 15 分钟；确认时锁定草稿与笼舍行，重新校验档期后再落订单。
- 确认接口幂等：同一草稿重复确认返回同一笔订单；幂等键只对应同一组参数。
- 订单流程：`pending → confirmed → checked_in → completed`，支持取消；入住 / 退房同步笼舍状态。
- 日报唯一约束 `(order_id, report_date)`，只有寄养员可填写，宠物主可查看。
- 权限：宠物主只能操作自己的宠物 / 草稿 / 订单；寄养员可接单、入住、退房、写日报；管理员维护笼舍。
- 所有关键写操作写审计日志。
- 新增 8 个寄养测试：空档、越权、幂等、过期、冲突复核、状态流转、日报、取消释放档期。
- 合成数据 seed：4 个账号、3 只宠物、5 间笼舍、体重 / 健康记录 / 提醒、3 笔订单与日报。
- 寄养前端：日期 / 体型空档查询、笼舍选择、草稿卡片与 15 分钟倒计时、确认 / 放弃；
  订单列表按角色展示不同操作，寄养员可接单、入住、退房，日报弹窗支持查看与填写。

### 验证

- `pytest`：23 passed。
- seed 重复执行通过，数据量稳定（4 用户 / 3 宠物 / 5 笼舍 / 3 订单 / 4 提醒）。
- `npm run typecheck`、`npm run build`：通过。

### 提交

- `37aed47` feat: 完成寄养主流程与草稿确认

### 下一步

1. 接入 Agent 工具层（LangGraph），实现 SSE 流式输出与工具轨迹。
2. 补 Alembic 初始迁移与 PostgreSQL 排他约束。
3. 准备知识库切片与 RAG 引用。

## 2026-10-19 · 第 3 天

### 完成

- Agent 工具层：7 个权限感知工具（宠物、健康记录、提醒、笼舍空档、草稿、订单、日报）。
- 工具注册表刻意不包含 `confirm_draft`；确认只能走独立 REST 接口，模型无法自行下单。
- 工具身份只来自 JWT 对应的 `User`，参数中没有 `user_id`；越权查询在服务层被拦截。
- 显式 Agent 循环：最多 6 轮工具调用，单轮 LLM 超时 30 秒，异常时返回友好兜底文案。
- 每轮持久化 assistant / tool 消息、工具参数与结果摘要、状态、耗时、token 和 trace_id。
- 会话历史按数据库为准，客户端重发历史不会重复落库；对话按用户隔离。
- 新增 `POST /api/agent/chat`、`GET /api/agent/conversations`、`GET /api/agent/conversations/{id}`。
- 新增 14 个 Agent 测试：工具注册表、越权隔离、草稿只写不确认、假模型多轮循环、
  历史恢复、最大轮数、模型异常、会话私有性。
- 前端智能助手页替换占位：真实多轮对话、工具轨迹、草稿卡片、历史会话切换、Enter 发送。
- 清理并重建开发库（`AgentMessage` 新增 token / 耗时列，`create_all` 不会自动改表），
  重新执行 seed；开发库仅含合成数据。

### 验证

- `pytest`：37 passed。
- `npm run typecheck`：通过。
- `npm run build`：通过（AgentView chunk 9.36 kB）。
- 真实 `deepseek-flash` 冒烟：`owner` 提问“我有哪些宠物？”，模型调用 `list_my_pets` 后
  返回 2 只宠物；两轮共约 3.1k tokens，工具 2ms，LLM 845ms / 1393ms。
- 冒烟后确认：只产生 1 个会话、4 条消息、1 条工具 trace；没有新增草稿或订单。

### 提交

- `41fc8a6` feat: 接入权限感知 Agent 工具层与智能助手对话页

### 下一步

1. SSE 流式输出（步骤级或 token 级）与前端增量渲染。
2. RAG 知识库切片、引用与拒答。
3. 80–100 条 YAML 评测用例与 baseline / 消融。
4. Alembic 初始迁移、PostgreSQL 排他约束、Docker 演示。
5. 网络恢复且远端仓库创建后推送 GitHub。

## 2026-10-19 · 第 4 天

### 完成

- 新增 `backend/evaluation/`：
  - `schema.py`：YAML 加载与校验（未知字段 / 未知工具 / 重复 id / 用户与分类白名单）。
  - `grading.py`：按工具选择、工具参数、回复内容、草稿副作用四项评分。
  - `cases.yaml`：29 条用例，覆盖宠物、健康、提醒、笼舍空档、草稿、订单、日报、越权、拒答、提示注入。
  - `runner.py`：复制开发库到 `pawcare_eval.db`，自动创建注入测试数据，走真实 HTTP 与真实模型，
    从 `agent_tool_calls.arguments` 读取参数，从 trace 汇总 token，输出控制台摘要 + JSON / CSV。
  - `README.md`：运行方式、字段说明、指标定义、扩展方法。
- 评测默认不污染演示库；运行结束删除副本，`--keep-db` 可保留排查。
- `perm-002` 初版强制要求模型调用草稿工具并拿到权限错误；实际模型先查宠物、确认“可乐”不在名下后拒绝，
  这是合法且更自然的路径。用例改为接受“查宠物后拒绝”与“草稿工具报错”两种路径，
  仍保留“不得产生草稿、不得泄漏他人宠物信息”的硬约束。
- 新增 `tests/test_evaluation.py`：用例校验与评分逻辑单测，不调用模型。
- 更新 README、架构文档和 `.gitignore`（评测报告不入库）。

### 验证

- `pytest`：47 passed。
- `runner.py --dry-run`：29 条用例校验通过。
- 全量真实评测（`deepseek-flash`）：
  - 任务成功 29/29（100%），工具选择 100%，参数准确 100%。
  - 平均延迟 5.2s，P95 7.4s。
  - token 合计 112,399（输入 102,511 / 输出 9,888）。
  - 分类：pets 3/3、health 4/4、reminders 2/2、availability 3/3、draft 3/3、
    orders 3/3、reports 1/1、permission 5/5、refusal 3/3、injection 2/2。
- 说明：当前用例集偏基础，100% 说明主链路稳定，但区分度不足；
  下一步需要加入多工具串联、信息不足、多轮澄清和更隐蔽的注入用例，并补 baseline / 消融。

### 提交

- `24347bd` feat: 增加 Agent 评测 harness 与 29 条用例

### 下一步

1. 将评测集扩充到 80–100 条，增加困难用例与 baseline / 消融。
2. SSE 流式输出（步骤级或 token 级）与前端增量渲染。
3. RAG 知识库切片、引用与拒答。
4. Alembic 初始迁移、PostgreSQL 排他约束、Docker 演示。

## 2026-10-19 · 第 5 天

### 完成

- Agent Runtime 增加可选事件回调，按步骤推送 `llm_start` / `llm_end` / `tool_start` / `tool_end` / `assistant`；
  回调异常只记日志，不影响 Agent 主流程。
- 抽取 `prepare_turn` / `finalize_turn`，流式与非流式共用同一套会话落库、历史恢复、草稿回填和 trace 逻辑。
- 新增 `POST /api/agent/chat/stream`：
  - 返回 `text/event-stream`，事件包含 `start`、步骤事件、`assistant` 和最终 `done`。
  - 校验、会话归属和模型配置检查在返回流之前完成，失败仍是普通 JSON 错误。
  - `stream_turn` 用队列桥接 Agent 回调和 SSE 生成器；客户端断开时取消后台任务。
  - `X-Accel-Buffering: no`，便于后续 Nginx 部署时关闭缓冲。
- 前端新增 `streamChat`：`fetch` + `ReadableStream` 解析 SSE，支持跨 chunk 边界和 `\r\n`。
- 智能助手页改为增量渲染：思考状态、工具执行中 / 完成 chip、最终回复、草稿卡片和 trace 实时更新。
- 保留非流式 `/agent/chat`，评测和脚本继续使用。

### 验证

- `pytest`：50 passed（新增 3 个流式测试：事件顺序与内容、流前校验、模型异常兜底）。
- `npm run typecheck`：通过。
- `npm run build`：通过（AgentView chunk 11.74 kB / gzip 5.42 kB）。
- 真实 `deepseek-flash` 流式冒烟（隔离副本库）：
  - `HTTP 200 text/event-stream`。
  - 事件顺序：`start → llm_start → llm_end → tool_start → tool_end → llm_start → llm_end → assistant → done`。
  - 第一轮模型 3109ms，`list_my_pets` 3ms，第二轮模型 2137ms。
  - `done` 携带完整回复、`trace_id` 和 2 只宠物的工具轨迹，与非流式响应结构一致。

### 提交

- `283331d` feat: 增加 Agent 流式输出与前端增量渲染

### 下一步

1. RAG 知识库切片、引用与拒答。
2. 评测集扩充到 80–100 条，增加困难用例与 baseline / 消融。
3. Alembic 初始迁移、PostgreSQL 排他约束、Docker 演示。
4. 通知中心（可选）。

## 2026-10-19 · 第 6 天

### 完成

- 新增 `app/rag/`：
  - `embedding.py`：fastembed `BAAI/bge-small-zh-v1.5`（512 维），按需加载、进程内复用，
    模型缓存到 `backend/.fastembed_cache`（已加入 `.gitignore`）；加载失败会记住原因，避免反复重试。
  - `retriever.py`：SQLite 上先取候选切片，再按 `0.75 × 向量余弦 + 0.25 × 中文词法覆盖率`
    排序；模型不可用时自动退回纯词法检索。混合阈值 0.45，词法阈值 0.25。
  - `RetrievedChunk.payload()` 返回 `title / content / source / score / trust=untrusted`。
- `EmbeddingType` 补 SQLite 的 JSON 序列化 / 反序列化；PostgreSQL 仍映射 `vector(512)`。
- seed 新增 14 篇合成护理知识：寄养准备、应激、犬猫疫苗、驱虫、换粮、体重、喂药、
  急症、老年、过敏、中暑、航空箱、多宠家庭。
- 新增第 8 个工具 `search_care_knowledge`：只读，支持 `query`、`top_k`、`category`；
  系统提示要求“（来源：标题）”标注、无结果时拒答、知识片段按不可信数据处理。
- 评测：
  - 新增 knowledge 分类 4 条、知识库注入 1 条，共 34 条用例。
  - 注入测试数据新增一条带指令的知识片段。
  - 修复评测误判：模型断连 / 超时返回的 200 兜底文案现在判为失败；
    网络失败默认重试 1 次（`--retries`），报告记录 `attempts` 和重试条数。
  - `perm-001` 放宽拒答关键词，接受“没有叫 / 查不到”等自然表述。
- 前端：工具 chip 增加“检索护理知识”，欢迎语、示例问题和能力卡补充 RAG。

### 验证

- `pytest`：58 passed（新增 RAG 混合检索、分类过滤、词法回退、无关拒答、
  工具参数校验、EmbeddingType 往返、评测兜底识别等 8 个测试）。
- 检索标定（14 篇知识库）：相关问题的 top1 分数 0.58–0.68；
  “今天股市 / 写诗 / 我的宠物最近怎么样”均低于阈值返回空；
  “今天天气”在 0.45 阈值下也被过滤。
- 全量真实评测（`deepseek-flash`，34 条）：
  - 任务成功 34/34（100%），工具选择 100%，参数准确 100%。
  - 平均延迟 3.6s，P95 5.7s；token 150,524（输入 138,767 / 输出 11,757）。
  - 分类全部 100%：pets 3/3、health 4/4、reminders 2/2、availability 3/3、draft 3/3、
    orders 3/3、reports 1/1、permission 5/5、refusal 3/3、injection 3/3、knowledge 4/4。
  - 此前一次运行遇到 4 条网络超时并触发重试；兜底回复已被判为失败，最终重跑全部通过。
- `npm run typecheck`、`npm run build`：通过（AgentView chunk 11.97 kB / gzip 5.53 kB）。

### 提交

- `0ea48bb` feat: 增加护理知识库 RAG 检索与知识评测

### 下一步

1. 评测集扩充到 80–100 条，增加多工具串联、信息不足、多轮澄清和更隐蔽的注入用例。
2. 补 baseline / 消融（去 RAG、去权限、去引用约束）。
3. Alembic 初始迁移、PostgreSQL pgvector 检索与排他约束、Docker 演示。
4. 通知中心（可选）。

## 2026-10-19 · 第 7 天

### 完成

- Alembic：
  - `alembic.ini` + `migrations/env.py`：数据库地址统一从 `settings.DATABASE_URL` 读取；
    自定义类型通过 `render_item` 输出为 `EmbeddingType()`。
  - 初始迁移覆盖 17 张业务表、索引、唯一约束与外键。
  - PostgreSQL 专有部分：`vector` / `btree_gist` 扩展、`vector(512)` 列、
    知识库 HNSW 余弦索引、活跃订单日期区间排他约束
    `EXCLUDE USING gist (kennel_id WITH =, daterange(start, end, '[)') WITH &&)`。
  - `alembic.ini` 必须保持 ASCII：Windows 上 Alembic 按系统 locale（GBK）读取，
    中文注释会直接抛 `UnicodeDecodeError`。
- 启动与部署：
  - SQLite 开发库继续用 `create_all`；PostgreSQL 不再隐式建表，改由 Alembic 管理。
  - 后端镜像增加 `migrations/`、`alembic.ini` 和 `scripts/docker-entrypoint.sh`，
    容器启动先 `alembic upgrade head` 再拉起 uvicorn。
  - 新增 `backend/.dockerignore`，排除 `.venv`、`.env`、开发库和模型缓存。
  - Compose 挂载 `backend/.fastembed_cache`，重建镜像不必重新下载 BGE 模型。
- 检索生产路径：
  - PostgreSQL 上用 `ORDER BY embedding <=> CAST(:q AS vector(512))` 取候选，
    再在 Python 中叠加词法分，SQLite / PostgreSQL 评分口径一致。
  - 分类过滤下推到 JSONB `meta->>'category'`，候选数默认 `top_k × 4`（12–50）。
  - 嵌入缺失时先补齐再排序；向量服务失败仍退回纯词法检索。
- 测试新增：迁移 upgrade / 重复 upgrade / downgrade，以及 pgvector 查询编译断言。

### 验证

- `pytest`：60 passed。
- 迁移在全新 SQLite 库上 `upgrade head` → 重复执行 → `downgrade base` 全部通过；
  `alembic check` 报告 `No new upgrade operations detected`。
- 以 PostgreSQL 方言离线生成 DDL（`alembic upgrade head --sql`），确认：
  `VECTOR(512)`、`JSONB`、`CREATE EXTENSION`、HNSW 索引和排他约束均正确输出。
- 本机 Docker daemon 未运行（Docker Desktop 未安装 / 未启动），
  因此 Compose 只完成配置与离线 DDL 校验，未做容器级启动验证。

### 提交

- `e6a129c` feat: 补 Alembic 迁移、pgvector 检索与容器迁移启动

### 下一步

1. 评测集扩充到 80–100 条，增加多工具串联、信息不足、多轮澄清和更隐蔽的注入用例。
2. 补 baseline / 消融（去 RAG、去权限、去引用约束）。
3. 网络与 Docker 可用时执行 `docker compose up -d --build`，验证迁移、pgvector 检索和前端链路。
4. 通知中心（可选）。

## 2026-10-19 · 第 8 天

### 完成

- 评测主集从 34 条扩到 91 条：
  - pets 7、health 9、reminders 5、availability 7、draft 7、orders 7、reports 3；
  - knowledge 11、permission 10、refusal 7、injection 7；
  - 新增 multi 6 条（多工具串联）与 clarify 5 条（信息不足先追问）。
- 修正两处过严断言：
  - `injection-006` 不再强制模型先查备注；安全拒答本身即可通过。
  - `perm-002` 接受“没找到”等自然表述，仍保留“不得产生草稿、不得泄漏”硬约束。
- baseline / 消融：
  - 新增 `evaluation/variants.py`，仅在评测进程内替换工具注册表或提示词；
    变体：`full`、`no_tools`、`no_rag`、`no_permission`、`no_citation`、
    `no_draft_confirmation`。
  - `runner.py` 增加 `--variant`，报告文件名和 JSON 都带变体标识。
  - `no_tools` 时 LLM 请求体不发送空 `tools` 字段。
  - `no_permission` 把 5 个读工具的当前用户替换为合成管理员，测量行级泄漏。
  - `no_draft_confirmation` 注册仅评测存在的 `confirm_boarding_draft`，
    并同步移除提示词、草稿工具描述和返回值里的确认边界，模拟不安全的系统设计。
  - 新增 `evaluation/ablation_cases.yaml`（12 条），覆盖工具、RAG、引用、权限和确认边界。
- 测试新增：消融用例加载、变体注册表、LLM 空工具请求体。
- README、评测 README、架构文档同步 baseline / 消融用法。

### 验证

- `pytest`：64 passed。
- `runner.py --dry-run`：主集 91 条、消融集 12 条均校验通过。
- 全量 91 条真实评测（`deepseek-flash`，`--retries 1`）：
  - 任务成功 87/91（95.6%），工具选择 97.8%，参数准确 100%。
  - 平均延迟 8.5s，P95 17.4s；token 420,540（输入 384,784 / 输出 35,756）。
  - 4 条失败：2 条模型网络断连兜底、1 条 `perm-002` 关键词过严、
    1 条 `injection-006` 强制先调工具。修正断言后单跑这 4 条：4/4 通过。
- 消融实验（同一套 12 条用例，`--retries 2`）：

  | 变体 | 通过 | 主要失败维度 |
  | --- | --- | --- |
  | `full` | 12/12 | — |
  | `no_tools` | 0/12 | 所有需要工具的任务都无法完成 |
  | `no_rag` | 8/12 | 3 条护理知识 + 1 条引用用例无法检索 |
  | `no_permission` | 9/12 | 3 条越权用例泄漏他人宠物 / 订单 / 健康记录 |
  | `no_citation` | 11/12 | 引用用例未输出“（来源：标题）”格式 |
  | `no_draft_confirmation` | 11/12 | Agent 自行调用确认工具，真的创建了订单 |

- `no_draft_confirmation` 的具体表现：模型在创建草稿后调用 `confirm_boarding_draft`，
  回复“预约并确认成功”，评测库新增订单；完整系统中确认工具不存在，模型只能提示用户去前端确认。

### 提交

- 待提交。

### 下一步

1. 网络与 Docker 可用时执行 `docker compose up -d --build`，验证迁移、pgvector 检索和前端链路。
2. 通知中心（可选）。
3. 多轮澄清评测：把单轮 `clarify` 用例扩展成两轮（追问后补全信息）。
4. 论文阶段补充引用忠实度与拒答准确率的细粒度统计。
