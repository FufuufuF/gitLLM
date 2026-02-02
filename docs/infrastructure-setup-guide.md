# gitLLM 基础建设清单（2026-02-02）

本文档用于今天的实施指导，覆盖数据库、跨域、配置、运行时依赖与可观测基础。面向当前仓库与 MVP 范围（主线/分支/逐级合并/学习简报）。

## 0. 今日交付目标（建议）

- 业务数据库可用（本地/开发环境），完成基础连接与迁移方案。
- FastAPI 具备 CORS、配置加载、日志输出与错误处理的最小基建。
- 关键环境变量与示例配置完善（.env.example）。
- 本地开发流程可一键启动（脚本/命令）。

---

## 1. 数据库（必做）

### 1.1 选择与落地
- 选型：MySQL 8.x
- 部署位置：WSL 中的 Docker
- 目标：Windows 侧（FastAPI）能通过 `127.0.0.1:3306` 连上 MySQL（端口映射到宿主机）。

建议的容器启动命令（在 WSL 内执行）：

```bash
docker volume create gitllm_mysql
docker run --name gitllm-mysql \
  -e MYSQL_ROOT_PASSWORD=fufu \
  -e MYSQL_DATABASE=gitllm \
  -e MYSQL_USER=fufu \
  -e MYSQL_PASSWORD=fufu \
  -p 3306:3306 \
  -v gitllm_mysql:/var/lib/mysql \
  -d mysql:8.4 \
  --character-set-server=utf8mb4 \
  --collation-server=utf8mb4_0900_ai_ci
```

连通性自检（任选其一）：
- WSL 内：`docker exec -it gitllm-mysql mysql -u gitllm -pdev_pw -D gitllm -e "SELECT 1"`
- Windows 内：用你熟悉的 MySQL 客户端连 `127.0.0.1:3306`

### 1.2 MVP 建表清单
必须先落地的表（对应 docs/database-design.md 的 MVP 物理模型）：
- users
- user_settings
- refresh_tokens（若暂不做 refresh，可延后）
- chat_sessions
- threads
- messages
- thread_ops（或 merges，建议统一命名）

> 建议：先明确“表名最终采用 thread_ops 还是 merges”，避免后续迁移成本。

### 1.3 迁移工具
- 建议：SQLAlchemy 2.x + Alembic
- MVP 允许先手工建表，但强烈建议今天就把迁移跑通（后续表结构会变，没迁移会很痛）。

### 1.4 连接池与会话
- 建议优先选“同步 SQLAlchemy”（落地成本最低、Windows 兼容最好），后续真需要再迁移 async。
- FastAPI 依赖注入 DB session（在 `src/api/deps.py`）。
- 每请求一个 session，结束后关闭。

推荐连接串（示例）：
- `DATABASE_URL=mysql+pymysql://gitllm:dev_pw@127.0.0.1:3306/gitllm?charset=utf8mb4`

### 1.5 约束与索引（最低限度）
- users.username UNIQUE
- chat_sessions(user_id, created_at DESC)
- threads(chat_session_id, created_at)
- messages(thread_id, created_at)
- thread_ops(chat_session_id, created_at DESC)

### 1.6 数据一致性（应用层）
- 资源归属校验：user_id 一致。
- 逐级合并校验：子 -> 父，且子线程无 active 子线程。
- 一会话内唯一主线线程。

---

## 2. 跨域（CORS）

### 2.1 目标
- 本地前端（单独仓库）能访问后端 API。

### 2.2 建议配置
- 允许来源列表（当前阶段：本地开发）：
  - `http://localhost:3000`
  - `http://127.0.0.1:3000`
- 允许方法：GET/POST/PUT/PATCH/DELETE/OPTIONS
- 允许请求头：Authorization, Content-Type
- 允许携带凭证（如果使用 cookie 或 refresh token）

> 生产环境必须改为白名单，不允许 *。

---

## 3. 环境变量与配置（必做）

### 3.1 基础配置项
建议在 core/config.py 中统一读取：
- APP_ENV (local/dev/prod)
- APP_HOST / APP_PORT
- DATABASE_URL
- LOG_LEVEL
- JWT_SECRET / JWT_ALG / ACCESS_TOKEN_EXPIRE_MINUTES
- REFRESH_TOKEN_EXPIRE_DAYS
- CORS_ORIGINS（逗号分隔）
- LLM_PROVIDER / LLM_MODEL（先占位）
- CHROMA_PERSIST_DIR（先占位）

### 3.2 .env.example
- 仅提供示例值，不放真实密钥。
- 与 README 保持一致。

---

## 4. 认证与安全（MVP 最小集）

### 4.1 是否在 MVP 启用 JWT：成本评估

结论：你可以暂时不启用鉴权，后续补 JWT 的成本可以做到“很小”，但前提是你今天就把“鉴权边界”预留出来。

不预留边界的风险（会显著抬高后续成本）：
- 现在所有表/接口都不带 `user_id` 概念；后续启用登录后需要做数据迁移 + 接口重构。

低成本做法（推荐）：MVP 不做登录/注册，不发 JWT，但把依赖接口先定好：
- 统一使用 `get_current_user()` 依赖（或等价命名），当前实现为“开发模式固定用户”（例如读取 `DEV_USER_ID` 或自动创建一个 dev user）。
- Repository / Service 的入参里始终传 `user_id`，避免后续大规模改签名。
- 当你准备启用 JWT 时，只需要替换 `get_current_user()` 的实现即可。

### 4.2 JWT（后续启用时的建议）
- Access token（JWT）用于 API 鉴权。
- Refresh token 是否需要：
  - 不需要“主动退出/踢下线/多端管理”时，MVP2 也可以先不做 refresh。
  - 一旦需要上述能力，再引入 refresh_tokens（存 hash，不存明文）。

### 4.3 安全中间件
- 统一异常处理（api/error_handlers.py）。
- 速率限制（可后续加入，当前不强制）。

---

## 5. 日志与可观测（MVP 最小集）

你希望“落地成本小、又利于扩展”，这里给出一个偏工程化但不复杂的选择：

- MVP：继续用 Python 标准库 logging（你现在已有基础实现），输出统一文本格式。
- 预留扩展：增加 `LOG_FORMAT=text|json` 配置位；当你要接入日志平台时，再切到 JSON（可以用 `python-json-logger` 这种低成本依赖）。
- 建议补一层 HTTP middleware，记录：方法、路径、状态码、耗时；并在日志里带 `request_id`（可用 UUID）。

---

## 6. 本地开发脚本（必做）

- scripts/dev.ps1 与 scripts/dev.sh 应支持：
  - 安装依赖
  - 启动服务
  - 可选：初始化数据库

---

## 7. 目录与模块就绪度检查

确保以下文件存在且可被导入：
- src/main.py（应用入口）
- src/core/config.py（配置）
- src/core/logging.py（日志）
- src/api/deps.py（依赖注入）
- src/api/error_handlers.py（异常映射）
- src/infra/db/engine.py（数据库引擎）
- src/infra/db/session.py（Session 管理）
- src/infra/db/models.py（ORM 模型）

---

## 8. 今日优先级建议（实施顺序）

1) 确认数据库选型与连接串 → 启动本地 DB
2) 落地 ORM 模型 + 迁移方案（至少 MVP 表）
3) FastAPI：CORS + 配置加载 + DB 依赖注入
4) 最小认证（注册/登录）
5) 日志与错误处理
6) 本地启动脚本完善

---

## 9. 已确认的决策（用于避免反复改动）

1) 数据库：MySQL，运行在 WSL 的 Docker 中
2) 鉴权：MVP 暂不启用（但必须预留 `get_current_user()` 依赖边界）
3) LLM/向量：先占位
4) CORS：仅本地 `localhost:3000` 白名单，等前端代理确定后再扩展
5) 日志：先标准 logging 文本格式，预留切 JSON 的开关

---

## 10. 可选但建议尽早确定的约定

- 表命名：thread_ops vs merges（尽快统一）
- ID 生成：UUID v4（推荐）
- 时区：统一 UTC
- 软删除策略：chat_sessions/threads 是否需要 deleted_at
