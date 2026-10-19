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

- `a10c9cd` feat: 初始化 PawCare 后端核心链路与前端骨架
- `7fe4ac3` fix: 宠物详情路由复用与助手进度文案
- 远程已配置为 `https://github.com/nzbyb/pawcare.git`。
- 推送阻塞：当前网络无法连接 `github.com:443`（无代理，TCP 探测失败），且远端仓库尚未创建。
  网络恢复并在 GitHub 创建仓库后执行：`git push -u origin main`。

### 下一步

1. 增加笼舍与寄养订单服务、重叠日期约束、草稿确认接口。
2. 写合成数据 seed 脚本，保证演示账号与数据可复现。
3. 接入 Agent 工具层（LangGraph），实现 SSE 流式输出与工具轨迹。
4. 准备知识库切片与 RAG 引用。
5. 补 Alembic 迁移，启动 Docker Postgres 验证生产路径。
