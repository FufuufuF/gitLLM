# 记忆分支（Memory Branch）功能技术实现指南

更新时间：2026-02-09

> 本文档采用自顶向下的组织结构，描述"记忆分支"功能的完整实现方案。从 API 层开始逐层展开至领域模型和基础设施层。

---

## 1. 功能概述

### 1.1 核心能力

| 功能                 | 描述                                                       |
| -------------------- | ---------------------------------------------------------- |
| **切出分支 (Fork)**  | 从当前线程（主线或分支）的某个节点切出一个新的子线程       |
| **合并分支 (Merge)** | 将子线程的对话内容总结为"学习简报"，注入父线程后归档子线程 |

### 1.2 设计原则

1. **checkpoint 与业务库分离**
   - LangGraph checkpoint 表：驱动 AI 引擎的运行态快照
   - 业务数据库（`threads`/`messages`/`merges`）：事实源，用于前端展示和历史查看

2. **一致性保障**
   - 切分支前强制刷新 checkpoint
   - 合并失败时整体回滚
   - 设计补偿机制处理跨库操作

3. **约束规则**
   - 分支只能合并到其直接父分支（逐级合并）
   - 所有约束在应用层校验

---

## 2. API 层设计

### 2.1 需要提供的接口清单

| 接口                                    | 方法  | 说明                         | 优先级 |
| --------------------------------------- | ----- | ---------------------------- | ------ |
| `/api/v1/threads/fork`                  | POST  | 切出分支                     | P0     |
| `/api/v1/threads/{id}/merge`            | POST  | 合并分支到父线程             | P0     |
| `/api/v1/threads/{id}/context-messages` | GET   | 获取线程上下文消息（带分页） | P0     |
| `/api/v1/sessions/{id}`                 | PATCH | 切换活跃线程                 | P0     |
| `/api/v1/threads/{id}/breadcrumb`       | GET   | 获取面包屑导航               | P1     |
| `/api/v1/sessions/{id}/thread-tree`     | GET   | 获取线程树结构               | P1     |

---

### 2.2 切出分支接口

**路由**: `POST /api/v1/threads/fork`

**请求体 Schema**:

```python
# src/api/schemas/thread.py

class ForkThreadRequest(BaseModel):
    """切出分支请求 从当前线程的最新一条消息中切出"""
    chat_session_id: int              # 所属会话 ID
    parent_thread_id: int             # 父线程 ID（从哪个线程切出）
    title: str | None = None          # 分支标题（可选，系统可自动生成）
```

**响应体 Schema**:

```python
class ForkThreadResponse(BaseModel):
    """切出分支响应"""
    thread_id: int                    # 新创建的分支线程 ID
    parent_thread_id: int             # 父线程 ID
    title: str                        # 分支标题
    fork_from_message_id: int | None  # 切出点
```

**业务流程**:

```
1. 校验权限：user_id 是否有权访问 chat_session_id
2. 校验父线程：parent_thread_id 是否属于该会话且状态为 active
3. 强制刷新父线程的 checkpoint（确保持久化）
4. 读取父线程的 LangGraph State
5. 创建新 Thread 记录（业务库）
6. 用父线程 State 为新 thread_id 创建初始 checkpoint
7. 记录 fork 操作到 merges 表（op_type=1）
8. 返回新线程信息
```

---

### 2.3 合并分支接口

**路由**: `POST /api/v1/threads/{thread_id}/merge`

**请求体 Schema**:

```python
class MergeThreadRequest(BaseModel):
    """合并分支请求"""
    # thread_id 从 path 获取，无需在 body 中传递
    pass  # 目前无需额外参数，后续可扩展支持自定义简报模板
```

**响应体 Schema**:

```python
class MergeThreadResponse(BaseModel):
    """合并分支响应"""
    merged_thread_id: int             # 被合并的分支 ID
    target_thread_id: int             # 目标父线程 ID
    brief_message_id: int             # 生成的学习简报消息 ID
    brief_content: str                # 简报内容摘要
```

**业务流程**:

```
1. 校验权限：user_id 是否有权访问该线程
2. 校验线程状态：status 必须为 active
3. 校验逐级合并约束：
   a. 该线程必须有 parent_thread_id（不能是主线）
   b. 该线程不能有 status=active 的子线程（需先处理子线程）
4. 获取分支对话历史：
   a. 从 messages 表获取该线程从 fork 点之后的所有消息
   b. 遵循 K 轮对话和摘要原则控制上下文长度
5. 调用 LLM 生成学习简报
6. 事务性操作：
   a. 在父线程创建 brief 类型的消息
   b. 更新子线程状态为 merged
   c. 记录 merge 操作到 merges 表（op_type=2）
   d. 更新 chat_session.active_thread_id 为父线程 ID
   e. 归档子线程的 checkpoint（可选：直接标记或延迟清理）
7. 返回合并结果
```

---

### 2.4 获取线程上下文消息接口

**路由**: `GET /api/v1/threads/{thread_id}/context-messages`

**查询参数**:

| 参数        | 类型   | 必填 | 说明                                       |
| ----------- | ------ | ---- | ------------------------------------------ |
| `direction` | string | 是   | `before`（向前翻页）或 `after`（向后翻页） |
| `cursor`    | string | 否   | 游标（消息 ID），不传表示从最新/最旧开始   |
| `limit`     | int    | 否   | 每页数量，默认 20，最大 100                |

**响应体 Schema**:

```python
class ContextMessagesResponse(BaseModel):
    """线程上下文消息响应"""
    messages: list[MessageOut]          # 消息列表
    next_cursor: str | None             # 下一页游标
    has_more: bool                      # 是否还有更多

class MessageOut(BaseModel):
    """消息输出"""
    id: int
    role: int                           # 1=user, 2=assistant, 3=system
    type: int                           # 1=normal, 2=suggestion, 3=brief
    content: str
    thread_id: int                      # 消息所属线程
    created_at: datetime
    metadata: dict | None = None
```

**业务流程**:

```
1. 校验权限：user_id 是否有权访问该线程
2. 构建祖先链：从当前线程递归向上找到主线
3. 确定每个祖先线程的有效消息范围（基于 fork_from_message_id）
4. 使用 UNION ALL 合并多个线程的查询
5. 应用游标和分页限制
6. 返回消息列表和分页信息
```

> 详细实现逻辑参见 [游标分页技术指南](./cursor-pagination-guide.md)

---

### 2.5 切换活跃线程接口

**路由**: `GET /api/v1/sessions/{session_id}`

**请求体 Schema**:

```python
class UpdateSessionRequest(BaseModel):
    """更新会话请求"""
    active_thread_id: int | None = None  # 要切换到的线程 ID
    title: str | None = None             # 更新会话标题（可选）
```

**响应体 Schema**:

```python
class UpdateSessionResponse(BaseModel):
    """更新会话响应"""
    session_id: int
    active_thread_id: int
    updated_at: datetime
```

**业务流程**:

```
1. 校验权限：user_id 是否拥有该会话
2. 校验目标线程：active_thread_id 是否属于该会话
3. 更新 chat_sessions.active_thread_id
4. 返回更新后的会话信息
```

---

### 2.6 获取面包屑导航接口（P1）

**路由**: `GET /api/v1/threads/{thread_id}/breadcrumb`

**响应体 Schema**:

```python
class BreadcrumbItem(BaseModel):
    """面包屑项"""
    thread_id: int
    title: str
    thread_type: int                    # 1=mainline, 2=branch
    status: int                         # 1=active, 2=merged, 3=closed

class BreadcrumbResponse(BaseModel):
    """面包屑响应"""
    breadcrumb: list[BreadcrumbItem]    # 从主线到当前线程的路径
```

**业务流程**:

```
1. 校验权限
2. 从当前线程递归向上遍历 parent_thread_id
3. 返回从主线到当前线程的路径列表
```

---

## 3. Service 层设计

### 3.1 需要提供的 Service 清单

| Service                 | 职责                                           |
| ----------------------- | ---------------------------------------------- |
| `ThreadService`         | 线程的 CRUD 和状态管理                         |
| `BranchService`         | **新增**，封装切出分支和合并分支的核心逻辑     |
| `CheckpointService`     | **新增**，封装 LangGraph checkpoint 的读写操作 |
| `BriefGeneratorService` | **新增**，调用 LLM 生成学习简报                |
| `MessageService`        | **新增**，封装消息上下文查询逻辑               |
| `SessionService`        | **扩展**，增加 `active_thread_id` 切换方法     |

---

### 3.2 BranchService（核心服务）

**路径**: `src/app/services/branch_service.py`

```python
class BranchService:
    """分支管理服务：切出分支与合并分支"""

    def __init__(
        self,
        db_session: AsyncSession,
        checkpoint_service: CheckpointService,
        brief_generator: BriefGeneratorService,
    ):
        self.db_session = db_session
        self.thread_repo = ThreadRepository(db_session)
        self.message_repo = MessageRepository(db_session)
        self.merge_repo = MergeRepository(db_session)
        self.checkpoint_service = checkpoint_service
        self.brief_generator = brief_generator

    async def fork_branch(
        self,
        user_id: int,
        chat_session_id: int,
        parent_thread_id: int,
        fork_from_message_id: int | None,
        title: str | None,
    ) -> Thread:
        """
        切出分支的核心逻辑。

        步骤：
        1. 校验父线程存在且属于当前会话和用户
        2. 确定 fork 点（message_id）
        3. 强制刷新父线程 checkpoint
        4. 读取父线程的 LangGraph State
        5. 创建新 Thread 记录
        6. 为新 thread_id 创建初始 checkpoint（基于父线程 State）
        7. 记录 fork 操作
        """
        ...

    async def merge_branch(
        self,
        user_id: int,
        thread_id: int,
    ) -> MergeResult:
        """
        合并分支的核心逻辑。

        步骤：
        1. 校验线程状态和权限
        2. 校验逐级合并约束
        3. 获取分支消息历史
        4. 调用 LLM 生成简报
        5. 事务性写入（简报消息 + 状态更新 + 操作记录）
        6. 归档 checkpoint
        """
        ...

    async def _validate_fork_prerequisites(
        self,
        user_id: int,
        chat_session_id: int,
        parent_thread_id: int,
    ) -> Thread:
        """校验切分支的前置条件"""
        ...

    async def _validate_merge_prerequisites(
        self,
        user_id: int,
        thread_id: int,
    ) -> tuple[Thread, Thread]:
        """校验合并的前置条件，返回 (source_thread, target_thread)"""
        ...
```

---

### 3.3 CheckpointService

**路径**: `src/app/services/checkpoint_service.py`

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.base import Checkpoint

class CheckpointService:
    """LangGraph Checkpoint 操作封装"""

    async def get_latest_state(self, thread_id: int) -> dict | None:
        """
        获取指定线程的最新 State。

        返回：
        - State 字典（包含 messages、configurable 等）
        - None 如果不存在
        """
        ...

    async def create_checkpoint_from_state(
        self,
        new_thread_id: int,
        source_state: dict,
    ) -> None:
        """
        基于已有 State 为新线程创建初始 checkpoint。

        注意：
        - 不是简单复制 checkpoint 记录
        - 而是读取 State 后以新 thread_id 创建新的 checkpoint
        """
        ...

    async def flush_checkpoint(self, thread_id: int) -> None:
        """
        强制刷新指定线程的 checkpoint。

        用途：确保切分支前 checkpoint 已持久化。
        """
        ...

    async def archive_checkpoint(self, thread_id: int) -> None:
        """
        归档指定线程的 checkpoint。

        策略：
        - MVP 阶段可以只做标记
        - 后续可配合定期清理任务处理
        """
        ...
```

---

### 3.4 BriefGeneratorService

**路径**: `src/app/services/brief_generator_service.py`

```python
class BriefGeneratorService:
    """学习简报生成服务"""

    async def generate_brief(
        self,
        messages: list[Message],
        fork_context: str | None = None,
    ) -> Brief:
        """
        调用 LLM 将分支消息总结为学习简报。

        输入：
        - messages: 分支中从 fork 点之后的所有消息
        - fork_context: 可选的上下文说明（如父线程的主题）

        输出：
        - Brief 对象，包含结构化的简报内容

        异常处理：
        - LLM 调用失败时抛出 ExternalServiceException
        - 调用方负责回滚事务
        """
        ...

    def _build_summary_prompt(self, messages: list[Message]) -> str:
        """构建总结 prompt"""
        ...
```

---

### 3.5 ThreadService（扩展）

**路径**: `src/app/services/thread_service.py`

需要在现有基础上扩展以下方法：

```python
class ThreadService:
    """线程 CRUD 服务"""

    async def get_thread(self, thread_id: int) -> Thread | None:
        """获取线程详情"""
        ...

    async def get_thread_with_validation(
        self,
        thread_id: int,
        user_id: int,
        chat_session_id: int | None = None,
    ) -> Thread:
        """获取线程并校验权限，不存在或无权限时抛异常"""
        ...

    async def create_thread(self, thread: Thread) -> Thread:
        """创建线程"""
        ...

    async def update_thread_status(
        self,
        thread_id: int,
        status: ThreadStatus,
        closed_at: datetime | None = None,
    ) -> Thread:
        """更新线程状态"""
        ...

    async def has_active_children(self, thread_id: int) -> bool:
        """检查是否有活跃的子线程"""
        ...

    async def get_breadcrumb(self, thread_id: int) -> list[Thread]:
        """获取从主线到当前线程的路径"""
        ...
```

---

### 3.6 MessageService（新增）

**路径**: `src/app/services/message_service.py`

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class ThreadRange:
    """线程的有效消息范围"""
    thread_id: int
    start_after_msg_id: int | None  # 该线程消息的起始点（不包含）
    end_at_msg_id: int | None       # 该线程消息的结束点（包含）


class MessageService:
    """消息查询服务"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.message_repo = MessageRepository(db_session)
        self.thread_repo = ThreadRepository(db_session)

    async def get_context_messages(
        self,
        thread_id: int,
        cursor: str | None,
        direction: Literal["before", "after"],
        limit: int = 20,
    ) -> dict:
        """
        获取线程上下文消息（带分页）。

        核心算法：
        1. 构建祖先链 ThreadRange 列表
        2. 使用 UNION ALL 合并各线程的消息查询
        3. 应用 Fork 点过滤，确保消息连续性
        4. 应用游标分页

        返回:
        {
            "messages": [...],
            "next_cursor": "123" | None,
            "has_more": True | False
        }
        """
        # Step 1: 构建祖先链范围
        ranges = await self._build_ancestor_ranges(thread_id)

        # Step 2-5: 调用 repository 方法执行查询
        return await self.message_repo.get_context_messages_paginated(
            ranges=ranges,
            cursor=cursor,
            direction=direction,
            limit=limit,
        )

    async def _build_ancestor_ranges(
        self,
        current_thread_id: int,
    ) -> list[ThreadRange]:
        """
        构建从主线到当前线程的祖先链，并确定每个线程的有效消息范围。

        示例：
        主线(1) -> 分支A(5, fork_from=3) -> 分支A-1(8, fork_from=7)

        返回:
        [
            ThreadRange(1, None, 3),      # 主线：从头到 msg_id=3
            ThreadRange(5, 3, 7),         # 分支A：msg_id=3 之后到 msg_id=7
            ThreadRange(8, 7, None),      # 分支A-1：msg_id=7 之后到最新
        ]
        """
        ranges = []
        stack = []

        current = await self.thread_repo.get(current_thread_id)
        while current:
            stack.append({
                'thread_id': current.id,
                'fork_from': current.fork_from_message_id,
            })
            if current.parent_thread_id:
                current = await self.thread_repo.get(current.parent_thread_id)
            else:
                break

        stack.reverse()

        for i, item in enumerate(stack):
            if i == len(stack) - 1:
                ranges.append(ThreadRange(
                    thread_id=item['thread_id'],
                    start_after_msg_id=item['fork_from'],
                    end_at_msg_id=None,
                ))
            else:
                next_fork = stack[i + 1]['fork_from']
                ranges.append(ThreadRange(
                    thread_id=item['thread_id'],
                    start_after_msg_id=item['fork_from'],
                    end_at_msg_id=next_fork,
                ))

        return ranges
```

---

### 3.7 SessionService（扩展）

**路径**: `src/app/services/session_service.py`

需要在现有基础上扩展以下方法：

```python
class SessionService:
    """会话服务"""

    async def update_active_thread(
        self,
        user_id: int,
        session_id: int,
        thread_id: int,
    ) -> ChatSession:
        """
        切换会话的活跃线程。

        校验:
        1. 用户有权访问该会话
        2. 目标线程属于该会话

        返回:
        更新后的 ChatSession
        """
        ...

    async def get_session_with_active_thread(
        self,
        user_id: int,
        session_id: int,
    ) -> ChatSession:
        """
        获取会话详情，包含 active_thread_id。
        """
        ...
```

---

## 4. Domain 层设计

### 4.1 领域模型扩展

**路径**: `src/domain/models.py`

```python
from enum import IntEnum
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class ThreadType(IntEnum):
    """线程类型"""
    MAINLINE = 1   # 主线
    BRANCH = 2     # 分支


class ThreadStatus(IntEnum):
    """线程状态"""
    ACTIVE = 1           # 进行中
    MERGED = 2           # 已合并
    CLOSED_UNMERGED = 3  # 已结束（未合并）


class MessageType(IntEnum):
    """消息类型"""
    NORMAL = 1               # 普通消息
    BRANCH_SUGGESTION = 2    # 分支建议卡片
    BRIEF = 3                # 学习简报
    ERROR = 4                # 错误消息


class MergeOpType(IntEnum):
    """分支操作类型"""
    FORK = 1           # 切出分支
    MERGE = 2          # 合并分支
    CLOSE_UNMERGED = 3 # 结束分支（不合并）


class Thread(BaseModel):
    """线程领域模型"""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    user_id: int
    chat_session_id: int
    parent_thread_id: Optional[int] = None
    thread_type: ThreadType
    status: ThreadStatus
    title: Optional[str] = None
    fork_from_message_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None


class Merge(BaseModel):
    """分支操作记录领域模型"""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    user_id: int
    chat_session_id: int
    op_type: MergeOpType
    thread_id: int              # fork: 新线程 | merge: 被合并的线程
    related_thread_id: Optional[int] = None  # fork: 父线程 | merge: 目标线程
    message_id: Optional[int] = None         # merge: 简报消息 ID
    metadata_: Optional[dict] = None
    created_at: Optional[datetime] = None


class Brief(BaseModel):
    """学习简报领域模型"""
    title: str                           # 简报标题
    key_conclusions: list[str]           # 关键结论
    action_items: list[str]              # 可执行步骤
    key_parameters: dict[str, str] | None = None  # 关键参数
    pending_items: list[str] | None = None        # 待确认事项


# 扩展 Message 模型
class Message(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    role: int                             # 1=user, 2=assistant, 3=system
    type: int = MessageType.NORMAL        # 消息类型
    content: str | list[str | dict]
    chat_session_id: int
    thread_id: int
    user_id: int
    metadata_: Optional[dict] = None      # 元数据（简报结构化数据等）
    created_at: Optional[datetime] = None
```

---

## 5. Repository 层设计（Infra）

### 5.1 需要提供的 Repository 方法

#### ThreadRepository

**路径**: `src/infra/db/repositories/threads.py`

```python
class ThreadRepository(BaseRepository[ThreadModel, Thread]):
    """线程仓储"""

    async def get_by_session_and_user(
        self,
        chat_session_id: int,
        user_id: int,
        thread_id: int,
    ) -> Thread | None:
        """获取指定会话和用户下的线程"""
        ...

    async def get_children_by_status(
        self,
        parent_thread_id: int,
        status: ThreadStatus,
    ) -> list[Thread]:
        """获取指定父线程下特定状态的子线程"""
        ...

    async def has_active_children(self, thread_id: int) -> bool:
        """检查是否存在活跃的子线程"""
        ...

    async def update_status(
        self,
        thread_id: int,
        status: ThreadStatus,
        closed_at: datetime | None = None,
    ) -> Thread | None:
        """更新线程状态"""
        ...

    async def get_mainline_thread(
        self,
        chat_session_id: int,
    ) -> Thread | None:
        """获取会话的主线线程"""
        ...
```

#### MergeRepository

**路径**: `src/infra/db/repositories/merges.py`

```python
class MergeRepository(BaseRepository[MergeModel, Merge]):
    """分支操作记录仓储"""

    async def get_by_thread(self, thread_id: int) -> list[Merge]:
        """获取指定线程的所有操作记录"""
        ...

    async def get_merge_record(self, thread_id: int) -> Merge | None:
        """获取指定线程的合并记录（如果有）"""
        ...

    async def record_fork(
        self,
        user_id: int,
        chat_session_id: int,
        new_thread_id: int,
        parent_thread_id: int,
        fork_from_message_id: int | None,
    ) -> Merge:
        """记录 fork 操作"""
        ...

    async def record_merge(
        self,
        user_id: int,
        chat_session_id: int,
        source_thread_id: int,
        target_thread_id: int,
        brief_message_id: int,
    ) -> Merge:
        """记录 merge 操作"""
        ...
```

#### MessageRepository（扩展）

**路径**: `src/infra/db/repositories/messages.py`

```python
from typing import Literal
from sqlalchemy import union_all

class MessageRepository(BaseRepository[MessageModel, Message]):
    """消息仓储"""

    # 已有方法
    async def get_messages(self, ...) -> list[Message]:
        ...

    # 新增方法
    async def get_last_message(self, thread_id: int) -> Message | None:
        """获取指定线程的最后一条消息"""
        stmt = (
            select(MessageModel)
            .where(MessageModel.thread_id == thread_id)
            .order_by(MessageModel.created_at.desc(), MessageModel.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return self.to_entity(result.scalar_one_or_none())

    async def get_messages_after(
        self,
        thread_id: int,
        after_message_id: int | None,
        limit: int | None = None,
    ) -> list[Message]:
        """
        获取指定线程中某消息之后的所有消息。

        用途：获取分支从 fork 点之后的消息用于生成简报。

        参数：
        - after_message_id: 起始消息 ID（不包含），None 表示从头开始
        - limit: 限制返回数量（用于 K 轮对话控制）
        """
        stmt = select(MessageModel).where(MessageModel.thread_id == thread_id)

        if after_message_id is not None:
            stmt = stmt.where(MessageModel.id > after_message_id)

        stmt = stmt.order_by(MessageModel.created_at.asc(), MessageModel.id.asc())

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return [self.to_entity(m) for m in result.scalars().all()]

    async def get_context_messages_paginated(
        self,
        ranges: list[ThreadRange],
        cursor: str | None,
        direction: Literal["before", "after"],
        limit: int = 20,
    ) -> dict:
        """
        获取跨线程的上下文消息（带分页）。

        参数：
        - ranges: 祖先链线程范围列表
        - cursor: 游标（消息 ID）
        - direction: 翻页方向
        - limit: 每页数量

        返回：
        {
            "messages": [...],
            "next_cursor": "123" | None,
            "has_more": True | False
        }

        详细算法参见: docs/cursor-pagination-guide.md
        """
        # 构建 UNION ALL 子查询
        subqueries = []
        for r in ranges:
            q = select(MessageModel).where(MessageModel.thread_id == r.thread_id)
            if r.start_after_msg_id is not None:
                q = q.where(MessageModel.id > r.start_after_msg_id)
            if r.end_at_msg_id is not None:
                q = q.where(MessageModel.id <= r.end_at_msg_id)
            subqueries.append(q)

        combined = union_all(*subqueries).subquery()

        # 应用游标
        query = select(MessageModel).from_statement(select(combined))
        if cursor:
            cursor_id = int(cursor)
            if direction == "before":
                query = query.where(combined.c.id < cursor_id)
            else:
                query = query.where(combined.c.id > cursor_id)

        # 排序和限制
        if direction == "before":
            query = query.order_by(combined.c.id.desc())
        else:
            query = query.order_by(combined.c.id.asc())

        query = query.limit(limit + 1)

        # 执行查询
        result = await self.session.execute(query)
        messages = [self.to_entity(m) for m in result.scalars().all()]

        # 处理结果
        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        if direction == "before":
            messages.reverse()

        next_cursor = None
        if has_more and messages:
            if direction == "before":
                next_cursor = str(messages[0].id)
            else:
                next_cursor = str(messages[-1].id)

        return {
            "messages": messages,
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

    async def create_brief_message(
        self,
        user_id: int,
        chat_session_id: int,
        thread_id: int,
        brief: Brief,
    ) -> Message:
        """
        创建学习简报消息。

        特殊处理：
        - role = 3 (system)
        - type = 3 (brief)
        - metadata 存储结构化的 Brief 数据
        """
        ...
```

---

## 6. 跨库一致性与补偿机制

### 6.1 问题描述

切出分支和合并分支都涉及两个存储的操作：

- **业务库**（PostgreSQL via SQLAlchemy）：`threads`、`messages`、`merges` 表
- **Checkpoint 库**（PostgreSQL via LangGraph）：checkpoint 相关表

这两者使用不同的连接，无法在同一个数据库事务中完成。

### 6.2 补偿策略

#### Fork 操作

```
成功路径:
1. [业务库] 创建 Thread 记录 → 获得 new_thread_id
2. [业务库] 创建 Merge 记录（op_type=FORK）
3. [Checkpoint] 为 new_thread_id 创建初始 checkpoint
4. [业务库] COMMIT

失败补偿:
- 步骤 3 失败：在业务库回滚 Thread 和 Merge 记录
- 步骤 4 失败：checkpoint 已创建但业务记录未提交
  → 孤儿 checkpoint 由定期清理任务处理（checkpoint 中无对应业务记录的可删除）
```

#### Merge 操作

```
成功路径:
1. [业务库 - 事务开始]
   a. 创建 Brief Message
   b. 更新 Thread 状态为 MERGED
   c. 创建 Merge 记录（op_type=MERGE）
2. [Checkpoint] 归档/清理被合并线程的 checkpoint
3. [业务库] COMMIT

失败补偿:
- 步骤 1 任意失败：业务库自动回滚
- 步骤 2 失败：业务库回滚，合并操作整体失败
- 步骤 3 失败：checkpoint 已归档但业务记录未提交
  → MVP 可接受此状态，checkpoint 归档不影响业务
```

### 6.3 实现建议

```python
# src/app/services/branch_service.py

async def fork_branch(self, ...):
    # 1. 业务库操作（带回滚点）
    async with self.db_session.begin_nested() as savepoint:
        try:
            new_thread = await self.thread_repo.create_thread(...)
            await self.merge_repo.record_fork(...)

            # 2. Checkpoint 操作
            parent_state = await self.checkpoint_service.get_latest_state(parent_thread_id)
            await self.checkpoint_service.create_checkpoint_from_state(
                new_thread.id,
                parent_state,
            )

        except Exception as e:
            # Checkpoint 操作失败，回滚业务库
            await savepoint.rollback()
            raise

    # 3. 全部成功，提交事务
    await self.db_session.commit()
    return new_thread
```

---

## 7. 文件新增/修改清单

### 7.1 新增文件

| 文件路径                                      | 说明                      |
| --------------------------------------------- | ------------------------- |
| `src/api/schemas/thread.py`                   | 线程相关 API Schema       |
| `src/api/v1/endpoints/threads.py`             | 线程相关 API 端点（扩展） |
| `src/app/services/branch_service.py`          | 分支管理核心服务          |
| `src/app/services/checkpoint_service.py`      | Checkpoint 操作封装       |
| `src/app/services/brief_generator_service.py` | 简报生成服务              |
| `src/app/services/message_service.py`         | 消息上下文查询服务        |

### 7.2 修改文件

| 文件路径                                | 修改内容                                                                                                |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `src/domain/models.py`                  | 添加 `Thread`、`Merge`、`Brief`、`ThreadRange` 模型和枚举                                               |
| `src/infra/db/models/chat_sessions.py`  | 添加 `active_thread_id` 字段                                                                            |
| `src/infra/db/repositories/threads.py`  | 实现 `ThreadRepository`                                                                                 |
| `src/infra/db/repositories/merges.py`   | 实现 `MergeRepository`                                                                                  |
| `src/infra/db/repositories/messages.py` | 添加 `get_last_message`、`get_messages_after`、`get_context_messages_paginated`、`create_brief_message` |
| `src/app/services/thread_service.py`    | 扩展线程服务方法，添加 `get_breadcrumb`                                                                 |
| `src/app/services/session_service.py`   | 添加 `update_active_thread`、`get_session_with_active_thread`                                           |
| `src/api/v1/endpoints/sessions.py`      | 添加 `PATCH` 端点用于切换活跃线程                                                                       |
| `src/api/v1/router.py`                  | 注册新的路由                                                                                            |

---

## 8. 依赖关系图

```
┌─────────────────────────────────────────────────────────────────────┐
│                           API Layer                                  │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  POST /api/v1/threads/fork                                   │    │
│  │  POST /api/v1/threads/{id}/merge                            │    │
│  └─────────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Service Layer                                │
│  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────────┐  │
│  │   BranchService   │──│ CheckpointService │  │ BriefGenerator  │  │
│  │   (核心编排)       │  │  (Checkpoint 操作)│  │ (LLM 调用)      │  │
│  └─────────┬─────────┘  └───────────────────┘  └─────────────────┘  │
│            │                                                         │
│  ┌─────────┴─────────┐                                               │
│  │   ThreadService   │                                               │
│  │   (线程 CRUD)     │                                               │
│  └───────────────────┘                                               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Domain Layer                                 │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐     │
│  │   Thread   │  │   Merge    │  │   Brief    │  │  Message   │     │
│  │  (领域模型) │  │  (领域模型) │  │ (值对象)   │  │ (领域模型)  │     │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Infrastructure Layer                             │
│  ┌────────────────────────┐  ┌────────────────────────────────────┐ │
│  │     Repositories       │  │     Checkpoint Infra               │ │
│  │  ┌─────────────────┐   │  │  ┌──────────────────────────────┐  │ │
│  │  │ ThreadRepository│   │  │  │ AsyncPostgresSaver (LangGraph)│  │ │
│  │  │ MergeRepository │   │  │  └──────────────────────────────┘  │ │
│  │  │ MessageRepository│  │  │                                    │ │
│  │  └─────────────────┘   │  │                                    │ │
│  └────────────────────────┘  └────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                      ORM Models (SQLAlchemy)                    │ │
│  │  threads.py  |  merges.py  |  messages.py                       │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 9. 后续工作

本文档聚焦于"切出分支"和"合并分支"两个核心功能的技术实现。以下能力作为后续迭代：

1. **自动建议分支 (P0-7)**：在 `ChatService` 中集成"跑题检测"逻辑
2. **结束分支不合并 (P0-8)**：`BranchService.close_branch()` 方法
3. **简报可编辑 (P1-2)**：合并前允许用户修改简报内容
4. **合并撤销 (P1-5)**：从已归档分支恢复并撤销父线程的简报消息

---

---

## 附录 A：Checkpoint 操作技术细节

### A.1 读取 State

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async def get_latest_state(thread_id: int) -> dict | None:
    async with AsyncPostgresSaver.from_conn_string(conn_str) as saver:
        config = {"configurable": {"thread_id": str(thread_id)}}
        checkpoint = await saver.aget(config)
        if checkpoint is None:
            return None
        return checkpoint.channel_values  # State 数据
```

### A.2 创建新 Checkpoint

```python
async def create_checkpoint_from_state(
    new_thread_id: int,
    source_state: dict,
) -> None:
    """
    注意：这不是简单的"复制 checkpoint"。
    而是读取 source_state 后，用 LangGraph 的机制为新 thread 创建 checkpoint。

    实现方式：
    1. 构造一个最小的 Graph
    2. 用 source_state 作为输入 invoke
    3. LangGraph 会自动为新 thread_id 创建 checkpoint
    """
    # 具体实现取决于你的 Graph 结构
    # 核心思路：用一个"透传"节点把 State 原样写入新 thread
    ...
```

---

## 附录 B：学习简报 Prompt 模板

```text
你是一个专业的技术助手。请将以下对话内容总结为一份简洁的"学习简报"。

对话内容：
{conversation_history}

请按以下格式输出：

## 本次探究主题
{简要描述讨论的主题}

## 关键结论
- {结论1}
- {结论2}
- ...

## 可执行步骤
1. {步骤1}
2. {步骤2}
...

## 关键参数与约束
| 参数名 | 值 | 说明 |
|--------|-----|------|
| ... | ... | ... |

## 待确认事项
- {如有需要进一步确认的问题，列在这里}

注意：
- 只提取事实和结论，不做主观判断
- 如果对话中出现与之前信息冲突的参数，请在"待确认事项"中标注
```
