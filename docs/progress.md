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

- `73e6b66` feat: 扩充 91 条评测集并加入 baseline 与消融实验

### 下一步

1. 网络与 Docker 可用时执行 `docker compose up -d --build`，验证迁移、pgvector 检索和前端链路。
2. 通知中心（可选）。
3. 多轮澄清评测：把单轮 `clarify` 用例扩展成两轮（追问后补全信息）。
4. 论文阶段补充引用忠实度与拒答准确率的细粒度统计。

## 2026-10-20 · 第 9 天

### 完成

- 保留显式循环作为生产主实现，新增轻量 LangGraph 对照适配层：
  - `app/agent/langgraph_runtime.py`：`StateGraph` 三个节点 `agent` / `tools` / `finish`，
    条件边在“继续调工具”和“结束”之间选择。
  - 复用现有 `OpenAICompatibleClient`、8 个工具、权限校验、RAG、持久化与 SSE 事件，
    没有复制业务逻辑；不引入 checkpointer，数据库仍是会话历史的唯一事实源。
  - 适配层在调用时读取 `runtime` 模块属性，因此 6 个评测变体对两种引擎都生效。
- 引擎切换：
  - `app/config.py` 增加 `AGENT_ENGINE`，默认 `explicit`。
  - `app/agent/engine.py` 懒加载 LangGraph；未安装时记录日志并回退到显式循环。
  - `agent_service` 改为调用引擎分发器，接口与流式行为不变。
- 评测支持 `--engine {explicit,langgraph}`；报告名和 JSON 记录引擎，避免报告互相覆盖。
- 清理 `requirements-agent.txt`：只保留 `langgraph==1.2.13`，删除未使用的
  LangChain-OpenAI / sentence-transformers 等陈旧依赖，并注明生产链路不需要它。
- 测试新增 `tests/test_agent_langgraph.py`：工具循环、超轮次停止、模型失败兜底。
- README、架构文档、评测 README 补充引擎选型、差异数据与运行方式。

### 验证

- `pytest`：67 passed（新增 3 条 LangGraph 行为对齐测试）。
- 同一套 5 条用例（`pets-001`、`draft-001`、`knowledge-001`、`perm-001`、`refusal-001`）：
  - 显式循环 5/5，平均 4.0s，P95 5.5s，25,766 tokens；
  - LangGraph 5/5，平均 4.5s，P95 7.8s，29,879 tokens；
  - 差异主要来自模型工具路径不同（2 条用例多调用工具），不是适配层开销。
- 隔离模型延迟的微基准（脚本化 `FakeLLM`，固定两步工具循环，各 25 次）：
  - 显式循环平均 4.50ms，P95 4.99ms；
  - LangGraph 平均 12.04ms，P95 10.91ms；
  - 编排开销约 +7.5ms/轮，相对真实模型 3–5s 可忽略。

### 结论

- 生产继续用显式循环：代码量更小、失败定位直接、无额外依赖。
- LangGraph 适配层验证了“调度可替换”，并为论文提供同业务能力下的框架对照；
  后续若需要 checkpoint、复杂分支或可视化编排，再以它为起点引入。

### 提交

- `b282fff` feat: 增加 LangGraph 对照适配层与引擎切换

### 下一步

1. 前端 UI 改版：降低模板化观感，先调研 2–3 个成熟开源后台 / 宠物管理项目，
   再调整布局、配色、字号层级和组件密度；不改动 Agent / 评测主链路。
2. 网络与 Docker 可用时执行 `docker compose up -d --build`，验证迁移、pgvector 检索和前端链路。
3. 通知中心（可选）。

## 2026-10-20 · 第 10 天

### 目标

- 前端整体改造为“临床工作台”风格：暖白底、松绿主色、1px 描边、8px 圆角，
  去掉渐变、玻璃拟态、超大圆角和 emoji，让界面更像宠物医院的工作系统。
- 不改动 Agent 交互、SSE 事件、寄养草稿确认和任何后端接口。

### 完成内容

- 设计系统：
  - `styles/main.css` 重写颜色、圆角、阴影变量，统一表格数字与紧凑排版。
  - `App.vue` 的 Naive UI 主题同步为主色 `#2F5D50`、8px / 6px 圆角、14px 字号。
  - 新增 `AppIcon.vue`，用内联 SVG 图标替代界面里的 emoji。
- 布局：`MainLayout.vue` 改为 232px 固定侧边栏 + 54px 顶栏，带面包屑和当前日期。
- 页面：
  - 工作台、登录页、宠物卡片、宠物详情、寄养预约、智能助手全部重做视觉层。
  - 寄养订单列表改为带分隔线的紧凑列表；笼舍选择用描边卡片和松绿选中态。
  - 助手页保留工具调用轨迹、草稿卡片和 trace，侧栏改为“能力 / 使用边界”。
- 清理：删除不再使用的 `speciesEmoji` 及 emoji 映射。

### 验证

- `npm run typecheck`：通过。
- `npm run build`：通过，产物正常分包。

### 提交

- `2099d4c` feat: 前端改造为临床工作台风格

### 下一步

1. 在浏览器里过一遍桌面和移动端页面，检查间距、选中态和长文本换行。
2. 网络与 Docker 可用时执行 `docker compose up -d --build`，验证迁移、pgvector 检索和前端链路。
3. 通知中心（可选）。

### 统一 Logo

- 新增 `frontend/src/components/AppLogo.vue` 与 `frontend/public/logo.svg`：
  松绿圆角方块 + 白色几何爪印，爪印由四个倾斜胶囊和一块圆角脚垫组成。
- 侧边栏、移动端顶栏、登录页、favicon 和 README 统一使用同一标识；
  深色背景使用白底松绿爪印的反色版本。

## 2026-10-20 · 第 11 天

### 目标

- 数据库从 PostgreSQL / pgvector 切回 MySQL：本机与部署统一 MySQL，SQLite 只保留给 pytest。
- 不改变业务接口、Agent 工具和评测指标，只替换存储实现。

### 完成内容

- 连接层：
  - `config.py` 默认 `mysql+pymysql://…/pawcare?charset=utf8mb4`。
  - `database.py` 按 URL 判断方言，MySQL 加 `pool_pre_ping` + `pool_recycle=3600`，
    避免 `MySQL server has gone away`；SQLite 仅测试时保留 `check_same_thread=False`。
- 模型：`models/types.py` 去掉 pgvector，`EmbeddingType` 以 JSON 文本存 MySQL `TEXT`；
  `JsonType` 统一用 `sa.JSON()`（MySQL 原生 JSON 列）。
- 检索：`rag/retriever.py` 删除 PostgreSQL 分支和 HNSW 查询，
  统一“取候选切片 + 应用层 0.75 余弦 / 0.25 词法”评分。
- 迁移：初始迁移移除 `CREATE EXTENSION`、`JSONB` → `JSON`、HNSW 索引与
  `EXCLUDE` 排他约束；档期冲突改由确认事务里的笼舍行锁保证。
- 依赖：`psycopg[binary]` / `pgvector` → `PyMySQL` + `cryptography`（caching_sha2_password）。
- 部署：`docker-compose.yml` 新增 `mysql:8.4`（宿主机 3307，避开本机 3306），
  backend 等 MySQL healthy 后启动。
- 评测：`evaluation/runner.py` 不再复制 `pawcare_dev.db`，
  改为在 MySQL 同实例 `DROP/CREATE pawcare_eval` 后建表 + seed，结束后删除。
- 启动：`main.py` 只在 SQLite（测试）下 `create_all`；MySQL 一律走 Alembic。
- 文档：README、architecture、ER 同步为 MySQL + 应用层余弦检索。

### 验证

- `pytest`：全量通过（测试仍走临时 SQLite）。
- 迁移在全新 SQLite 上 `upgrade head` → 重复执行 → `downgrade base` 通过。
- 本机 MySQL 9.7：`alembic upgrade head` 建表成功，`scripts/seed.py` 写入
  3 只宠物 / 5 间笼舍 / 3 笔订单 / 14 篇知识；登录、宠物列表、订单列表接口均返回 200。
- 检索：14 篇知识全部生成 512 维向量并以 JSON 存入 MySQL，混合检索命中正常。
- 评测：单条 `pets-001` 端到端通过（2.6s、3,850 tokens），评测库 `pawcare_eval` 自动创建并删除。
- 修复评审时发现的问题：`str(URL)` 会把密码替换成 `***`，评测库连接报 1045；
  改为 `render_as_string(hide_password=False)`，并以空库名连接实例执行 `CREATE/DROP DATABASE`。

### 下一步

1. 本机建 `pawcare` 库和账号，`alembic upgrade head` + `scripts/seed.py`，启动后端冒烟。
2. 网络与 Docker 可用时执行 `docker compose up -d --build` 验证容器链路。
3. 通知中心（可选）。

## 2026-10-20 · 第 11 天（续）· 注册验证与登录安全

### 目标

- 让登录页接近可上线产品：注册需要邮箱或手机号验证，支持找回密码和协议勾选。
- 不引入付费短信依赖：手机走可插拔发送器，本地用日志输出验证码。

### 完成内容

- 模型：新增 `verification_codes`（channel / target / scene / code_hash /
  expires_at / attempts / consumed_at / request_ip）；`users` 增加 `email`、
  `email_verified_at`、`phone_verified_at`、`failed_login_count`、`locked_until`，
  邮箱与手机号加唯一索引。迁移 `8521a822ba0b` 已在 MySQL 执行。
- 验证码服务：6 位数字、HMAC-SHA256 存摘要、5 分钟有效、60 秒重发冷却、
  每小时 5 条、最多试错 5 次、一次核销、签发新码即作废旧码。
- 发信：`services/mailer.py` 用标准库 `smtplib` + `EmailMessage`，支持 SSL / STARTTLS；
  `services/sms.py` 提供 `console` 发送器；未配置且非调试模式时返回 503。
- 接口：`POST /api/auth/verification-code`、`POST /api/auth/password/reset`；
  注册请求改为“邮箱或手机号二选一 + 验证码”。
- 登录保护：连续 5 次密码错误锁定 15 分钟；登录成功清零；重置密码递增
  `token_version` 并解除锁定。
- 登录页：注册页增加验证方式切换、验证码倒计时、密码强度、协议勾选与协议弹窗；
  登录页增加“忘记密码”弹窗和锁定提示；调试模式自动回填验证码。
- 配置：`backend/.env.example` 增加 SMTP / 验证码策略说明；
  `VERIFY_CODE_DEBUG=true` 只在本地 `.env` 开启。

### 验证

- `pytest`：76 条全部通过（新增 10 条验证码 / 锁定 / 找回密码用例）。
- `npm run typecheck` 与 `npm run build` 通过。
- 本机 MySQL 冒烟：邮箱验证码 → 注册 → 登录 → 找回密码 → 新密码登录全部返回 200；
  手机号验证码经 `console` 发送器返回 `debug_code`。冒烟数据已清理。

### 下一步

1. 拿到 QQ / 163 授权码后填入 `.env`，关闭 `VERIFY_CODE_DEBUG` 验证真实发信。
2. 需要真实短信时接入阿里云 / 腾讯云，并补充签名与模板配置。
3. 网络与 Docker 可用时执行 `docker compose up -d --build` 验证容器链路。

## 2026-10-20 · 第 11 天（续 2）· 模拟支付收银台

### 目标

- 给寄养订单补上「待支付 / 已支付」状态和扫码支付流程。
- 不申请商户资质、不接真实资金，但把回调、幂等、超时和状态机做完整。

### 完成内容

- 模型：新增 `payment_orders`（支付单号 / 订单 / 金额 / 状态 / 二维码 token /
  有效期 / 交易号 / 回调原文）；`boarding_orders` 增加冗余字段
  `payment_status`、`paid_amount`。迁移 `6974e27e2fdc` 已在 MySQL 执行。
- 服务：`payment_service` 实现 `created → paying → paid / closed` 状态机；
  未过期支付单复用，过期惰性关单，重复回调幂等，已支付订单拒绝再次发起。
- 接口：`POST /api/payments`、`GET /api/payments/{payment_no}`、
  公开的扫码页查询与模拟回调 `GET/POST /api/payments/mock/...`。
- 安全：二维码内容是前端支付页地址 + 一次性 token，回调用 `compare_digest`
  校验；公开查询不返回 owner_id 和交易号。
- 前端：订单卡片增加支付标签与「去支付」；收银台弹窗展示金额、二维码、
  倒计时和轮询；新增公开支付页 `/pay/:paymentNo`，支持模拟支付。
- 演示数据：seed 把历史已完成订单标记为已支付并写入一条支付单，
  新库里同时能看到「已支付」和「待支付」两种状态。
- 文档：README、architecture 增加支付说明与配置项。

### 验证

- `pytest`：82 条全部通过（新增 6 条支付用例：复用、权限、扫码回调、
  重复回调、过期关单、取消订单不可支付）。
- 本机 MySQL 冒烟：登录 → 创建支付单 → 扫码页查询（`paying`）→ 回调
  （`paid`）→ 订单 `payment_status=paid`、`paid_amount=204`。
- `npm run typecheck`、`npm run build` 通过。
- seed 在临时 SQLite 上完整跑通，可重复执行。

### 下一步

1. 需要真实收款时申请支付宝沙箱，新增 provider 并补验签、金额比对与退款。
2. 拿到 QQ / 163 授权码后关闭 `VERIFY_CODE_DEBUG` 验证真实发信。
3. 网络与 Docker 可用时执行 `docker compose up -d --build` 验证容器链路。



## 2026-10-20 · 第 11 天（续 3）· 收银台轮询泄漏修复

### 问题

工作台上每隔 2.5 秒弹出「无权查看该支付单」，关掉收银台后也停不下来。

### 原因

`PaymentModal.loadPayment()` 里 `createPayment` 尚未返回时关闭弹窗或离开页面，
`stopTimers()` 先执行（此时还没有定时器），请求返回后又把 `setInterval` 装上，
组件已卸载、无人清理。切换账号后残留的轮询带着新账号的 token 查询旧账号的支付单，
后端返回业务码 403，全局拦截器每次都提示一次。

### 修复

- `PaymentModal` 增加 `disposed` 与 `loadSeq`：关闭 / 卸载 / 切换订单时作废在途请求，
  迟到的结果不再启动轮询；`poll()` 发现弹窗已关闭或组件已卸载时自行停表。
- 轮询请求改为 `silent`，失败不弹全局提示；遇到 403 / 404 直接停止轮询。
- `http.ts` 统一把业务错误码挂到 `Error.code`，并在拦截器支持 `silent` 配置，
  便于后台轮询区分「网络抖动可重试」和「重试无意义的权限错误」。

### 验证

- `npm run typecheck`、`npm run build` 通过。
- 定时器只在 `props.show` 为真且组件存活时运行；关闭、切路由、切换账号后
  不再产生后台请求，403 / 404 只提示一次。

## 2026-10-20 · 第 11 天（续 4）· 工作台细节打磨

### 目标

降低工作台的模板感，让统计、提醒和宠物卡片更像真实商用后台，不改布局和功能。

### 完成内容

- 统计卡片：四张卡片分别配业务图标（宠物 / 健康记录 / 提醒 / 逾期），
  健康记录用松绿、提醒用琥珀、逾期用砖红，悬停时轻微上浮并加一层淡阴影。
- 即将到期列表：7 天内到期整行文字标橙并显示「即将到期」，已过期标红并显示
  「已过期」，正常条目保持墨黑；右侧新增「查看详情」按钮，行本身仍可点击。
- 我的宠物：每条增加「编辑」「查看档案」两个文字按钮，编辑复用 `PetFormModal`，
  保存后原地更新列表与提醒中的宠物名；名称旁增加犬 / 猫类型小标识。
- 底部说明：删除 AI 口播式文案，替换为健康档案自动跟踪的业务描述，
  按钮改为「查看宠物档案」。
- 顶部简介同步去掉「交给助手」的说法，改为统一的档案与预约状态查看。

### 验证

- `npm run typecheck`、`npm run build` 通过。
- 数据绑定沿用原有接口：提醒按到期日排序、逾期统计、宠物列表均未改动逻辑。

## 2026-10-21 · 第 11 天（续 5）· 开题答辩 PPT

### 目标

按开题报告和项目构思生成一份可直接参加开题答辩的 PPTX，统一采用工作台的
暖白 + 松绿视觉，不使用模板化渐变和大色块。

### 完成内容

- `docs/PawCare-开题答辩.pptx`：19 页、16:9，含封面、提纲、选题背景、
  国内外现状、研究目标、角色边界、总体架构、业务闭环、四个关键机制、
  评测结果、前期进展、研究方法、进度安排、预期成果、风险应对、参考文献和结束页。
- 关键数据沿用项目和评测事实：8 个工具、91 条用例、6 个消融变体、82 条后端测试、
  首轮 87/91（95.6%）、P95 17.4 s、约 42 万 token；消融图用真实通过数绘制。
- 每页写有讲稿备注，答辩时可在 PowerPoint 演讲者视图直接查看。
- `docs/ppt/build_opening_deck.py`：用 python-pptx 生成整份 PPT，改文案后可重新运行；
  内置暖白 / 松绿 / 砖红主题、无边框表格、分层架构图和消融柱状图。

### 验证

- 脚本运行成功，输出 19 页。
- 用 PowerPoint COM 将全部页面导出为 1600×900 PNG 逐页检查，
  修复了表格默认黑边框、工具名断行压字、评测页文字重叠等问题。
- 进度安排、指导教师、学号与班级均与开题报告一致。

### 待处理

- 开题报告 docx 仍写 SQLite / PostgreSQL / pgvector，实际实现为 MySQL 8+、
  向量以 JSON 存储。答辩前需要把文档中的数据库方案改成与系统一致。

## 2026-10-21 · 第 11 天（续 6）· 站内通知中心

### 目标

在不引入常驻调度器的前提下，把订单状态、寄养日报和健康提醒汇到一个
顶栏铃铛里，用户在任意页面都能看到发生了什么。

### 完成内容

- 后端新增 `notifications` 元数据：`category`、`link`、`dedupe_key`，
  迁移 `9f3c1a7d2b6e`；唯一索引 `(user_id, dedupe_key)` 保证同一业务事件只通知一次。
- `notification_service`：幂等写入、按角色群发、列表 / 未读数 / 单条已读 / 全部已读；
  健康提醒采用「读时补齐」——打开通知列表时把 7 天内到期或已逾期的待处理提醒
  生成站内通知，不需要定时任务。
- 业务钩子：创建订单通知宠物主与寄养员、寄养员确认订单、入住、退房、取消订单、
  填写日报、模拟支付成功，均写入通知并与业务数据同一事务提交。
- API：`GET /api/notifications`、`GET /api/notifications/unread-count`、
  `POST /api/notifications/{id}/read`、`POST /api/notifications/read-all`。
- 前端 `NotificationBell`：铃铛 + 未读数徽标 + 下拉面板，60 秒静默轮询，
  页面隐藏时跳过；分类图标、相对时间、未读底色与红点，点击跳转并标记已读；
  顶部工作栏和移动端导航栏各放一个，共享 Pinia store。
- 演示数据：`seed.py` 里豆豆的体内驱虫改为 3 天后到期，新环境打开通知中心即可
  看到一条健康提醒，不会出现空白面板；已有开发库同步更新了这条记录。

### 验证

- 新增 5 条通知测试，全量 `pytest` 87 条通过。
- `npm run typecheck`、`npm run build` 通过。
- 用 Edge 无头模式登录演示账号，检查桌面 1440×900 与手机 390×844 两档：
  面板、未读徽标、全部已读、移动端定位均正常；检查后已删除临时演示数据。

## 2026-10-21 · 第 11 天（续 7）· 寄养交接单

### 目标

把入住、退房时需要核对的信息汇总成一页可打印的交接单，让前台不必在
宠物档案、订单和健康记录之间来回切换。

### 完成内容

- 后端新增 `GET /api/boarding/orders/{id}/handover`：一次返回订单、宠物档案、
  主人联系方式、最近 12 条健康记录、待处理提醒和最近一次体重；宠物主只能看
  自己的订单，寄养员和管理员可以查看任意订单。
- 前端新增独立页面 `/boarding/orders/:id/handover`，不套工作台布局；
  顶部只保留「返回」「打印 / 导出 PDF」，正文按 A4 排版。
- 交接单分区：宠物信息、寄养安排、健康与注意事项（过敏史单独标红）、
  健康记录表、待处理提醒、主人联系、随行物品勾选、双方签字栏。
- 寄养订单卡片新增「交接单」入口，宠物主和寄养员都能打开。
- 打印样式：隐藏工具栏、去掉页面底色与卡片边框、`@page` 设为 A4 13mm
  边距，表格与分区避免跨页断开。

### 验证

- 新增交接单测试（数据聚合、寄养员可看、他人 403），全量 `pytest` 88 条通过。
- `npm run typecheck`、`npm run build` 通过。
- 用无头 Edge 检查 1440px 桌面视图和打印媒体视图，并导出 PDF 确认可生成；
  桌面与打印版式均无溢出，工具栏在打印时正确隐藏。

## 2026-10-21 · 第 11 天（续 8）· 个人中心与账号安全

### 目标

把侧边栏只有「退出登录」的账户菜单补成可用的个人中心：维护资料、修改密码、
控制接收哪些站内通知。

### 完成内容

- 模型与迁移：`users` 增加 `notify_health`、`notify_order`、`notify_system`
  三个布尔字段（默认开启），迁移 `c4e8b1f6a2d9` 已在 MySQL 执行。
- 资料修改 `PUT /api/auth/me`：昵称必填；邮箱或手机号至少保留一个；
  校验格式与唯一性；改绑联系方式后清空对应的 `*_verified_at`，提醒用户重新验证。
- 通知偏好 `PUT /api/auth/notification-prefs`：`create_notification` 写入前先看
  用户偏好，关闭的类别不再产生新通知，历史记录保留。
- 修改密码沿用 `PUT /api/auth/password`：校验原密码，`token_version` 递增让旧令牌
  全部失效，响应返回新令牌，前端立即替换，当前设备无需重新登录。
- 前端新增 `/profile`：左侧「基本资料」「账号安全」，右侧「通知偏好」「账号信息」；
  已验证 / 未验证状态随联系方式展示，保存资料或偏好后同步 Pinia 与 localStorage。
- 侧边栏新增「账户 · 个人中心」入口，账户下拉菜单增加「个人中心」；移动端
  顶栏把单独的「退出」换成用户图标下拉，同样可进入个人中心。

### 验证

- 新增 6 条测试（资料更新与验证状态重置、联系方式占用、必填校验、改密换令牌、
  关闭订单 / 健康通知后不再写入），全量 `pytest` 94 条通过。
- `npm run typecheck`、`npm run build` 通过。
- 无头 Edge 检查 1440px 桌面与 400px 手机两档：两栏在窄屏正确堆叠，
  表单、开关、验证状态徽标显示正常。

