# gitLLM 数据库设计：全量 ERD（概念模型）+ MVP 建表清单（物理模型）

更新时间：2026-02-02

本文档目标：
- 给出 **全量 ERD（概念模型）**：把产品域的核心实体、关系、状态/约束一次性想清楚。
- 给出 **MVP 建表清单（物理模型）**：只把 P0（主线/分支/逐级合并/学习简报）+ 登录/注册 必需的表落地，其余作为后续迭代表。

> 说明：本文以“关系型数据库（推荐 PostgreSQL）”为基准描述字段与索引。若你最终用 MySQL/SQLite，字段类型可按等价映射调整。

---

## 1. 设计原则（强约束）

1) **所有业务数据都必须可归属到用户**
- 会话（Session）、分支（Thread）、消息（Message）、合并记录（Merge）都要能追溯到 `user_id`。
- 最小权限模型：默认只允许资源所有者访问（后续协作/共享再扩展）。

2) **逐级合并是“业务不变量”，数据库只做底线约束**
- “子分支不能越级合并到主线”与“父分支存在未处理子分支时不允许合并”属于业务规则，推荐在应用层校验。
- 数据库层建议做：外键、唯一性、必要的 CHECK（能表达的就表达），避免脏数据。

3) **演进优先：简报内容与参数抽取结果必须可版本化**
- 学习简报字段建议保留 `brief_version` 与 `metadata JSON` 以支持后续格式升级。

4) **软删除（可选但推荐）**
- 为满足“用户删除会话/隐私清理”，建议至少对顶层资源支持 `deleted_at`。

---

## 2. 全量 ERD（概念模型）

### 2.1 概念实体清单

**身份与账号域（Auth）**
- User（用户）
- Credential（凭证：密码哈希/强度/升级策略）
- SessionToken / RefreshToken（登录态：JWT 场景下通常用于 refresh token 轮换/退出登录）

> 当前阶段约束：只做“用户名 + 密码”注册/登录；暂不考虑邮箱验证、找回密码、第三方登录（后续可扩展）。

**对话与分支域（Conversation）**
- ChatSession（会话：一个任务目标的容器）
- Thread（对话线：主线或探究分支，可嵌套）
- Message（消息：用户/助手/系统/简报等）
- Merge / ThreadOp（分支操作事件：记录切分支、合并分支等关键操作）

**策略与配置域（Settings/Model）**
- UserSetting（用户设置：自动建议开关等）
- ModelConfig（模型配置：provider/model/温度/系统提示词版本等，后续）

**可观测与治理（Ops）**
- AuditLog（审计日志：谁在什么时候做了什么，后续）
- ExportJob（导出任务，后续）

**向量检索（Vector Store / Memory，后续）**
- VectorDocument（向量索引条目：简报/知识片段的 embedding 元信息）

### 2.2 关系总览（ASCII ERD）

```text
User (1) ──────────── (N) ChatSession
  │                        │
  │                        └──────── (N) Thread
  │                                     │
  │                                     ├──────── (N) Message
  │                                     │
  │                                     └──────── (N) Merge (source)
  │
  ├──────── (1) UserSetting
  ├──────── (N) RefreshToken
  ├──────── (N) EmailVerification
  └──────── (N) PasswordReset

Thread (self) : parent_thread_id 形成树
Thread -> Message : fork_from_message_id 表示“从哪个节点切出”
Merge/ThreadOp : 记录 fork/merge 等操作，并可关联 fork 点或简报消息
```

### 2.3 核心不变量（概念约束）

**会话与线程**
- 一个会话必须且仅有一个主线线程（main thread）。
- 线程形成树：`parent_thread_id` 指向父线程；主线 `parent_thread_id = NULL`。
- 线程的 `root_session_id` 固定，不允许跨 session 移动。

**消息**
- 消息归属到线程；线程归属到会话；三者归属到同一个用户。
- 学习简报在概念上是一种“系统生成的消息”，可用 `message.type = brief` 表达。

**合并**
- 合并一定是“子 -> 父”：source_thread 的 parent_thread 必须等于 target_thread（或 target 为主线）。
- 合并成功后：source_thread 状态变为 merged；父线程新增一条 brief 消息。

**权限**
- 默认：User 只能访问自己的会话/线程/消息/合并记录。
- 未来协作：通过 Share/Workspace 增加授权关系（不属于 MVP）。

---

## 3. MVP 建表清单（物理模型）

MVP 必建表（P0 + 登录/注册）：
- `users`
- `user_settings`
- `refresh_tokens`（或 `sessions`/`auth_tokens`，用于登录态）
- `chat_sessions`
- `threads`
- `messages`
- `merges`（建议更准确叫 `thread_ops`，但物理表名可先沿用 `merges`）

> 命名说明：为避免与“会话 Session（产品概念）”混淆，这里把产品会话命名为 `chat_sessions`；登录态使用 `refresh_tokens`。

### 3.1 `users`（用户）

用途：登录/注册、资源归属。

字段建议：
- `id` SERIAL PK
- `username` VARCHAR(64) UNIQUE NOT NULL（MVP：用户名 + 密码注册/登录）
- `password_hash` TEXT NOT NULL
- `display_name` VARCHAR(64) NULL
- `status` SMALLINT NOT NULL DEFAULT 1  （1=active, 2=disabled, 3=pending_verification）
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL
- `last_login_at` TIMESTAMPTZ NULL

索引/约束：
- UNIQUE(`username`)
- 可选：`status` 普通索引（后台筛选）

### 3.2 `user_settings`（用户设置）

用途：自动建议开关等。

字段建议：
- `user_id` INT PK, FK -> users(id)
- `auto_suggest_branch` BOOLEAN NOT NULL DEFAULT TRUE
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL

索引/约束：
- PK(`user_id`)（一人一份设置）

### 3.3 `refresh_tokens`（登录态 / 刷新令牌）

用途：实现登录持久化、退出登录、踢下线。

字段建议：
- `id` SERIAL PK
- `user_id` INT NOT NULL FK -> users(id)
- `token_hash` TEXT NOT NULL UNIQUE（只存 hash，不存明文）
- `expires_at` TIMESTAMPTZ NOT NULL
- `revoked_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ NOT NULL
- `last_used_at` TIMESTAMPTZ NULL
- `user_agent` TEXT NULL
- `ip` INET NULL（PostgreSQL）/ VARCHAR(45)（MySQL）

索引/约束：
- UNIQUE(`token_hash`)
- INDEX(`user_id`, `expires_at`)

> 备注：如果你使用 JWT 且不需要 refresh token，也建议保留一张“token 黑名单/会话表”支撑主动退出与封禁。

### 3.4 `chat_sessions`（产品会话：一个任务目标容器）

用途：主线 + 分支的顶层容器，对齐 PRD 的 Session。

字段建议：
- `id` SERIAL PK
- `user_id` INT NOT NULL FK -> users(id)
- `title` VARCHAR(200) NULL
- `goal` TEXT NULL（可选：显式保存“主线目标”，便于 UI 顶部展示）
- `status` SMALLINT NOT NULL DEFAULT 1（1=active, 2=archived）
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL
- `deleted_at` TIMESTAMPTZ NULL

索引/约束：
- INDEX(`user_id`, `created_at` DESC)
- 可选：全文索引（title/goal）后续再做

### 3.5 `threads`（对话线：主线/分支）

用途：承载主线与探究分支，支持嵌套与逐级合并。

字段建议：
- `id` SERIAL PK
- `user_id` INT NOT NULL FK -> users(id)
- `chat_session_id` INT NOT NULL FK -> chat_sessions(id)
- `parent_thread_id` INT NULL FK -> threads(id)
- `type` SMALLINT NOT NULL（1=mainline, 2=branch）
- `status` SMALLINT NOT NULL（1=active, 2=merged, 3=closed_unmerged）
- `title` VARCHAR(200) NULL（例如“探究：Docker”）
- `fork_from_message_id` INT NULL FK -> messages(id)（表示从哪个“节点/消息之后”切出）
- `created_at` TIMESTAMPTZ NOT NULL
- `updated_at` TIMESTAMPTZ NOT NULL
- `closed_at` TIMESTAMPTZ NULL

关键约束建议：
- 一个 `chat_session_id` 下只能有一个主线线程：UNIQUE(`chat_session_id`) WHERE `type` = mainline（PostgreSQL 可用 partial unique index）
- 线程与父线程必须在同一会话下：数据库难以用纯 FK 表达，建议应用层校验

索引建议：
- INDEX(`chat_session_id`, `created_at`)
- INDEX(`parent_thread_id`, `status`)
- INDEX(`user_id`, `created_at`)

> 备注：`fork_from_message_id` 依赖 `messages` 表，会形成循环引用。落地时可先允许 NULL，或分两次迁移添加 FK。

### 3.6 `messages`（消息）

用途：对话内容、系统卡片、学习简报都统一当做消息存。

字段建议：
- `id` SERIAL PK
- `user_id` INT NOT NULL FK -> users(id)
- `chat_session_id` INT NOT NULL FK -> chat_sessions(id)
- `thread_id` INT NOT NULL FK -> threads(id)
- `role` SMALLINT NOT NULL（1=user, 2=assistant, 3=system）
- `type` SMALLINT NOT NULL（1=normal, 2=branch_suggestion, 3=brief, 4=error）
- `content` TEXT NOT NULL
- `content_format` SMALLINT NOT NULL DEFAULT 1（1=plain, 2=markdown, 3=json）
- `metadata` JSONB NULL（存：模型信息、token 使用、候选建议理由、brief_version、冲突项等）
- `created_at` TIMESTAMPTZ NOT NULL

关键约束建议：
- `messages.user_id` 必须等于其 `threads.user_id` 且等于 `chat_sessions.user_id`：建议应用层校验

索引建议：
- INDEX(`thread_id`, `created_at`)
- INDEX(`chat_session_id`, `created_at`)
- INDEX(`user_id`, `created_at`)
- 可选：GIN(`metadata`)（PostgreSQL）后续再加

### 3.7 `threads_ops`（分支操作事件：fork/merge/…）

用途：记录“切出分支、合并分支”等关键操作事件。

字段建议（事件建模，推荐）：
- `id` SERIAL PK
- `user_id` INT NOT NULL FK -> users(id)
- `chat_session_id` INT NOT NULL FK -> chat_sessions(id)
- `op_type` SMALLINT NOT NULL
  - 1=fork（切出分支）
  - 2=merge（合并分支，生成简报）
  - （可选）3=close_unmerged（结束分支不合并）
- `thread_id` INT NOT NULL FK -> threads(id)
  - fork：新创建的子线程 id
  - merge：被合并的 source_thread_id
  - close：被关闭的 thread_id
- `related_thread_id` INT NULL FK -> threads(id)
  - fork：parent_thread_id
  - merge：target_thread_id
  - close：通常为空
- `message_id` INT NULL FK -> messages(id)
  - fork：fork_from_message_id（从哪条消息节点切出）
  - merge：brief_message_id（合并产出的简报消息）
- `metadata` JSONB NULL（可选：原因、参数、冲突提示、客户端信息等）
- `created_at` TIMESTAMPTZ NOT NULL

可选字段（未来如果要做失败重试/回退再加）：
- `status`
- `error_message`

关键约束建议：
- 对 merge 操作防重复：建议在数据库加“部分唯一”（PostgreSQL）
  - UNIQUE(`thread_id`) WHERE `op_type` = 2
  - 若数据库不支持 partial index，则在应用层做幂等校验
- `thread_id != related_thread_id`（当 related_thread_id 非空时）

索引建议：
- INDEX(`chat_session_id`, `created_at` DESC)
- INDEX(`thread_id`, `created_at`)
- INDEX(`related_thread_id`, `created_at`)
- INDEX(`user_id`, `created_at`)

---

## 4. MVP 之外但建议现在纳入“概念设计”的表（后续迭代落地）

这些表先在 ERD 里占位，等对应功能进入迭代再建：

### 4.1 账号安全与合规（后续）

当前阶段明确不做：
- 邮箱验证
- 找回密码
- 第三方登录

后续可扩展表：
- `audit_logs`：关键操作审计（删除会话、合并、导出等）
- `password_reset_tokens`：找回密码
- `email_verifications`：注册后验证邮箱
- `oauth_accounts`：第三方登录（GitHub/Google 等）

### 4.2 配置与实验
- `model_configs`：用户级/会话级模型配置
- `prompt_versions`：简报模板/建议模板版本化
- `feature_flags`：灰度开关、A/B 实验

### 4.3 导出与分享（非 MVP）
- `export_jobs`：会话导出异步任务
- `shares` / `workspaces`：协作与共享

### 4.4 向量检索（如后续要把简报进 Chroma 并做可追溯）
- `vector_documents`：保存 collection、doc_id、source（brief/message）、embedding_model、hash、写入时间等

---

## 5. 数据一致性与权限校验建议（实现要点）

即使数据库有 FK，也建议在应用层统一做以下校验：

- 任意对 `chat_sessions/threads/messages/merges` 的读写：必须校验 `resource.user_id == current_user.id`。
- 创建分支：`parent_thread.chat_session_id == current_session.id`。
- 逐级合并：
  - `source_thread.parent_thread_id == target_thread.id`
  - source_thread 没有 `status=active` 的子线程（用 `threads.parent_thread_id = source_id AND status=active` 判断）
- 结束分支（不合并）：同上，先处理子线程。

---

## 6. LangGraph checkpoint 与 `messages` 表协作策略（避免冗余且可重启恢复）

你提到的点非常关键：LangGraph/LangChain 的 state 里经常会维护一个 `messages` 列表；如果把它原封不动写入 checkpoint，会导致两类问题：
- **数据重复**：同一段历史既在业务库 `messages` 表里，又在 checkpoint 里再存一遍。
- **一致性难题**：到底以哪份为准（特别是你将来要支持删除会话/脱敏/撤销合并）。

推荐的“工程上稳”的分层是：
- **业务数据库 `messages` 是事实源（source of truth）**：永久保存用户/助手/系统/简报等消息。
- **checkpoint 只保存“运行态快照 + 指针”，不保存消息全文**：例如 `last_message_id/last_seq`、当前图节点、已执行的工具调用标记、简报版本号等。

### 6.1 你是否必须“每切出一个 thread 就保存一次 checkpoint”？

不必须。

想要“能回到每个交叉节点”的能力，MVP 里用数据库锚点就够了：
- 分支创建时写入 `threads.fork_from_message_id`（或未来改成 `fork_from_message_seq`）。
- 需要回放上下文时：从父线程取到 fork 点（A），再拼接当前线程消息（B），得到 A+B。

checkpoint 的职责更偏向“让一次对话执行在重启后能续跑”，因此通常只需要：
- **每个 thread 保留最新 1 份 checkpoint**（可选保留最近 K 份用于调试/回滚）。
- 在“完成一轮（用户消息 -> 助手回复）”后更新 latest checkpoint。

### 6.2 你能否控制 checkpoint 不保存 `messages` 列表？

能做到，关键在于：**checkpointer 通常会序列化并持久化整个 state**，所以你要控制的是“state 里到底放什么”。你有两种常见做法：

**做法 A（推荐）：把 state 设计成“只存引用”，运行时再加载消息**
- 不把 `messages: list[...]` 当作持久化字段，而是把它当作“运行时派生字段”。
- state 里只放：`thread_id`、`last_message_id/last_seq`、`context_window`、`fork_from_message_id` 等轻量字段。
- 在图的第一个节点（你在架构里已有 `load_context.py` 的位置）中：从业务库按需查询消息并注入到运行时变量/局部 state，再交给后续节点生成回复。

优点：checkpoint 小、无重复、重启恢复时可“先取 checkpoint 指针，再从 DB 增量补齐消息”。

**做法 B：state 仍含 `messages`，但持久化前“裁剪/剔除”**
- 如果你强依赖某些现成封装（例如某些 graph helper 默认把 `messages` 放进 state），可以在写 checkpoint 前把 `messages` 裁剪成“最近 N 条”或直接置空。
- 这通常需要你：
  - 自己实现/包装 checkpointer（或其序列化逻辑），在 `put`/`save` 时对 state 做一次清洗；或
  - 统一用一个“可持久化子 state”（例如 `persisted_state`）写入 checkpoint。

优点：改动现有 graph 代码较少；缺点：实现复杂度略高，且更容易踩一致性坑。

### 6.3 推荐的最小字段（供你定义 state / checkpoint schema）

每个 thread 的 checkpoint 建议至少包含：
- `thread_id`
- `checkpoint_version`（方便后续 state 结构升级）
- `last_message_id` 或 `last_seq`
- `graph_node` / `graph_step`（可选，便于续跑）
- `summary` / `brief_cache`（可选：摘要、已合并简报的缓存，用于加速）
- `updated_at`

### 6.4（可选）如果你要把 checkpoint 也落到业务库

可以加一张后续迭代表（或直接使用 LangGraph 提供的持久化实现）：
- `thread_checkpoints(thread_id, version, state_json, last_message_id, created_at)`

MVP 阶段你可以先不建这张表：只要你使用的 checkpointer 是持久化的（例如落到 Postgres/SQLite），就能达到重启恢复目的。

### 6.5 决策建议（当前结论）

结合当前架构思路（“记忆分支/会话管理在业务层；AI 层只负责对话与工具调用”），建议先按以下结论推进：

```
MVP：不必上 checkpoint DB，把“记忆”定义为业务库可重建的上下文（messages + fork 点 + 简报/摘要），AI 层每次运行时装载。
预留接口：把“是否启用持久化 checkpointer”做成可切换；等你们出现“长流程/异步/中断恢复”需求再引入 checkpoint 表或 LangGraph 的持久化实现。
```

落地含义：
- 业务库 `messages/threads/merges` 是事实源；分支的分叉点用 `fork_from_message_id` 固化。
- AI 执行前统一走“加载上下文”步骤（按 thread 拼接祖先链 + 当前 thread 的消息），必要时叠加简报/摘要以控制上下文长度。
- 后续如引入异步/可暂停流程，再把 checkpoint 持久化作为增强能力补上。

---

## 7. 最小可用的 ERD 输出物（你可以直接照此画图）

如果你要把它画成图（draw.io / Mermaid / dbdiagram.io），MVP 版本只需要这几条线：
- users 1--N chat_sessions
- chat_sessions 1--N threads
- threads 1--N messages
- threads 1--N threads (parent_thread_id)
- threads 1--N merges (source_thread_id)
- merges N--1 threads (target_thread_id)
- merges 1--1 messages (brief_message_id)

---

## 8. 下一步（我建议你现在做的）

1) 确认你选用的数据库（PostgreSQL / MySQL / SQLite）。
2) 我可以基于本表设计输出一份“迁移顺序建议”（避免 threads/messages 循环 FK 的落地问题）。
3) 如果你们要支持邮箱验证/找回密码，我也可以把对应表的 MVP 版本补齐到物理清单里。
