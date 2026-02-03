# Chat & Memory Branching 功能实现逻辑

本文档记录了与 AI 助手达成一致的核心功能实现逻辑。所有代码实现应严格遵循此设计的时序与分层原则。

## 1. Chat 功能 (Chat Flow)

### 1.1 核心原则

1.  **分层解耦 (Layer Separation)**: API Layer 负责 `Schema <-> Domain` 的转换，Service Layer 仅接收纯净的参数（如 `user_id`, `thread_id`, `content`），不依赖 HTTP 层的 Schema 定义。
2.  **双写存储 (Dual Write)**:
    - **业务数据库 (MySQL)**: 实时存储完整的对话记录 (`messages` 表)，用于前端历史列表展示、搜索、管理。
    - **Agent 系统 (Postgres)**: 通过 LangGraph Checkpointer 自动维护运行状态，作为 Agent 的“大脑记忆”。
3.  **职责划分**: Service 负责编排“权限校验 -> 业务落库 -> Agent 调用 -> 结果处理”的全流程。

### 1.2 详细时序 (Sequence)

#### Step 1: API Layer (`src/api/v1/messages.py`)

- **输入**: 接收 HTTP POST 请求，校验 `ChatRequest` Schema。
- **操作**: 解析 Current User，调用 `chat_service.chat_stream(user_id, thread_id, content)`。

#### Step 2: Service Layer (`src/app/services/chat_service.py`)

- **2.1 业务校验**:
  - 从 MySQL 查询 `Thread`。
  - 验证 `thread.user_id == user_id`。
  - 验证 `thread.status != CLOSED`。
- **2.2 用户消息落库 (MySQL)**:
  - 立即在 MySQL `messages` 表创建一条记录 (Role=`user`, Status=`completed`)。
  - _目的: 保证前端能立即获取到“刚发送的消息”。_
- **2.3 调用 Agent (LangGraph)**:
  - 构建 LangGraph Input: `{"messages": [HumanMessage(content=...)]}`。
  - 配置 Config: `{"configurable": {"thread_id": str(thread_id)}}`。
  - 调用 `graph_runner.astream(input, config)`。
  - _注意: 无需手动 Load Checkpoint，LangGraph 会自动根据 thread_id 加载。_
- **2.4 流式处理与 AI 落库**:
  - 遍历 Stream Event，实时 yield token 给前端。
  - 聚合完整的 AI 回复内容。
  - 流结束后，在 MySQL `messages` 表创建一条记录 (Role=`assistant`, Status=`completed`)。

---

## 2. 记忆分支功能 (Memory Branching Flow)

### 2.1 核心原则

1.  **API 驱动复制**: 使用 `langgraph.checkpoint.postgres` 提供的原生 API (`aget_tuple`, `aput`) 进行状态复制，严禁使用 Raw SQL 操作底层表，以规避 Schema 变更风险。
2.  **ID 策略**: 直接复用 MySQL 的 Thread ID (转换为字符串) 作为 LangGraph 的 Thread ID。
3.  **原子性**: 虽然跨了两个数据库，但需确保“创建业务 Thread”与“复制 Checkpoint”在逻辑上作为一个整体执行（若复制失败，应回滚或标记业务 Thread 无效）。

### 2.2 详细时序 (Sequence)

#### Step 1: API Layer (`src/api/v1/threads.py`)

- **输入**: 接收 HTTP POST `/threads/{thread_id}/branch`。
- **操作**: 调用 `thread_service.create_branch(source_thread_id, user_id)`。

#### Step 2: Service Layer (`src/app/services/thread_service.py`)

- **2.1 校验源上下文**:
  - 查询 `source_thread`，确认用户权限。
- **2.2 创建新分支记录 (MySQL)**:
  - 开启 MySQL 事务。
  - INSERT `threads` 表: `parent_thread_id = source_thread.id`, `title = "Branch from..."`。
  - Flush Session 以获取 `new_thread.id`。
  - 提交 MySQL 事务。
- **2.3 复制记忆状态 (Postgres - LangGraph)**:
  - 获取 `AsyncPostgresSaver` 实例。
  - **Read**: `checkpoint = await saver.aget_tuple({"thread_id": str(source_thread.id)})`。
  - **Write**:
    ```python
    await saver.aput(
        config={"configurable": {"thread_id": str(new_thread.id)}},
        checkpoint=checkpoint.checkpoint,
        metadata=checkpoint.metadata,
        new_versions={}
    )
    ```
- **2.4 返回结果**:
  - 返回新创建的 `new_thread` 实体。
