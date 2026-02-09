# 游标分页（Cursor-based Pagination）技术指南

更新时间：2026-02-09

> 本文档解释游标分页的原理及其在"递归消息拼接"场景中的应用。

---

## 0. 背景：什么是"递归消息拼接"场景？

### 0.1 产品背景

在"记忆分支"功能中，用户可以从主线对话中**切出分支**进行深入探究，分支还可以继续切出子分支。这形成了一个树状结构：

```
主线（Thread 1）
├── 消息 1: "帮我部署一个 Docker 应用"
├── 消息 2: "好的，我来帮你..."
├── 消息 3: "Docker 是什么？"          ← 用户在此处切出分支
│
└── 分支A（Thread 5，fork_from_message_id=3）
    ├── 消息 4: "Docker 是一个容器化平台..."
    ├── 消息 5: "我该怎么安装？"
    │
    └── 分支A-1（Thread 8，fork_from_message_id=5）
        ├── 消息 7: "在 Ubuntu 上..."
        └── 消息 8: "安装成功了！"
```

### 0.2 核心需求

**当用户处于分支 A-1 时，前端需要展示完整的上下文**：

```
完整上下文 = 主线消息(1-3) + 分支A消息(4-5) + 分支A-1消息(7-8)
```

这就是"递归消息拼接"——需要递归遍历祖先链，将每个层级的消息拼接起来。

### 0.3 为什么需要分页？

| 场景     | 问题                                   |
| -------- | -------------------------------------- |
| 长对话   | 主线可能有 100+ 条消息，一次性加载太慢 |
| 深层分支 | 多层嵌套的分支累计可能有几百条消息     |
| 移动端   | 内存受限，需要按需加载                 |

### 0.4 为什么传统分页不适用？

**传统 OFFSET 分页**：`LIMIT 20 OFFSET 40`

```
问题 1：跨线程查询时 OFFSET 语义不清晰
  - "第 3 页"是指全局第 40-60 条，还是当前线程的？

问题 2：插入新消息时 OFFSET 会错位
  - 用户在看第 2 页时，第 1 页插入了新消息
  - 刷新后会看到重复的消息

问题 3：祖先链消息分布不均匀
  - 主线 100 条，分支 A 只有 5 条，分支 A-1 有 20 条
  - OFFSET 无法优雅处理这种分布
```

**因此需要游标分页**：用消息 ID 作为锚点，而不是偏移量。

### 0.5 额外的复杂性：用户可能切换线程

根据产品设计，用户可以在分支活跃时切回主线继续对话：

```
时间线：
10:00 主线消息1
10:01 主线消息2
10:02 主线消息3  ← 切出分支A
10:03 分支A消息4
10:04 分支A消息5
10:05 主线消息6  ← ⚠️ 用户切回主线发的消息
10:06 分支A消息7  ← 用户又切回分支
10:07 分支A-1消息8
```

**问题**：当用户在分支 A-1 时，应该看到 `消息6`（主线消息）吗？

**答案**：不应该。分支 A 的上下文应该"冻结"在 fork 点（消息3），之后主线的新消息不属于分支 A 的上下文。

这就是为什么需要 **Fork 点过滤**——每个线程只取它"有权看到"的消息范围。

---

## 1. 你的问题解答

### Q1: `LIMIT` 是否需要先取出所有符合条件的数据？

**答案：不需要。**

数据库查询优化器会利用 `ORDER BY + LIMIT` 的组合进行优化：

```sql
SELECT * FROM messages
WHERE thread_id IN (1, 5, 8)
  AND created_at < '2026-02-09 14:00:00'
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

**执行过程**：

1. 数据库使用索引 `ix_messages_thread_id_created_at` 定位符合条件的行
2. 按 `created_at DESC, id DESC` 顺序扫描
3. **扫描到 20 条就停止**，不会继续扫描剩余数据

这就像图书馆按时间排列的书架：你想找"2024年之前出版的最新20本书"，不需要把2024年之前的所有书都搬出来，只需要从最近的位置开始往前数20本。

**验证方法**：使用 `EXPLAIN ANALYZE` 查看执行计划：

```sql
EXPLAIN ANALYZE
SELECT * FROM messages
WHERE thread_id IN (1, 5, 8)
ORDER BY created_at DESC
LIMIT 20;

-- 你会看到类似这样的输出：
-- Limit  (actual rows=20 loops=1)
--   -> Index Scan Backward using ix_messages_thread_id_created_at
--      (actual rows=20 loops=1)  ← 只扫描了20行
```

---

### Q2: 如何保证取到的消息是连续的，而不是离散的？

**答案：`ORDER BY` 保证了连续性。**

关键理解：**"符合条件"和"离散"不矛盾**。

让我用具体例子解释：

```
假设 messages 表数据（已按 created_at 排序）：

id | thread_id | created_at          | content
---|-----------|---------------------|----------
1  | 1         | 2026-02-09 10:00:00 | 主线消息1
2  | 1         | 2026-02-09 10:01:00 | 主线消息2
3  | 1         | 2026-02-09 10:02:00 | 主线消息3  ← fork 点
4  | 5         | 2026-02-09 10:03:00 | 分支A消息1
5  | 5         | 2026-02-09 10:04:00 | 分支A消息2
6  | 1         | 2026-02-09 10:05:00 | 主线消息4 (用户切回主线后发的)
7  | 5         | 2026-02-09 10:06:00 | 分支A消息3 (用户又切回分支)
8  | 8         | 2026-02-09 10:07:00 | 分支A-1消息1
```

**用户当前在分支 A-1，祖先链 = [1, 5, 8]**

**问题**：`WHERE thread_id IN (1, 5, 8)` 会不会取到 `id=6`（主线消息4）？

**答案**：会取到，但这正是你想要的！

```
查询结果（按时间排序）：
id=1, id=2, id=3, id=4, id=5, id=6, id=7, id=8
```

**等等，这不对！** 用户在分支 A-1，不应该看到 `id=6`（主线消息4）。

---

## 2. 关键修正：需要考虑 Fork 点

上面的例子暴露了一个问题：**简单的 `thread_id IN (...)` 不够，还需要过滤 fork 点。**

### 正确的查询逻辑

对于祖先链上的每个线程，需要设定**有效消息范围**：

| 线程           | 类型 | 有效范围                               |
| -------------- | ---- | -------------------------------------- |
| 主线 (id=1)    | 根   | 从开始 → 到 fork 点 (msg_id=3)         |
| 分支A (id=5)   | 中间 | 从 fork_from=3 → 到 fork 点 (msg_id=7) |
| 分支A-1 (id=8) | 当前 | 从 fork_from=7 → 到最新                |

### 修正后的 SQL

```sql
-- 方案：使用 UNION ALL 为每个线程设定不同的范围
(
  -- 主线：从开始到第一个 fork 点
  SELECT * FROM messages
  WHERE thread_id = 1
    AND id <= 3  -- fork_from_message_id of 分支A
)
UNION ALL
(
  -- 分支A：从它的 fork 点到下一个 fork 点
  SELECT * FROM messages
  WHERE thread_id = 5
    AND id > 3   -- 在分支A的起始 fork 点之后
    AND id <= 7  -- 到分支A-1的 fork 点
)
UNION ALL
(
  -- 分支A-1：从它的 fork 点到最新
  SELECT * FROM messages
  WHERE thread_id = 8
    AND id > 7
)
ORDER BY created_at ASC, id ASC
LIMIT 20;
```

现在结果是：

```
id=1, id=2, id=3, id=4, id=5, id=7, id=8
```

`id=6`（主线消息4）被正确排除了！

---

## 3. 完整的游标分页实现

### 3.1 数据结构

```python
from dataclasses import dataclass

@dataclass
class ThreadRange:
    """线程的有效消息范围"""
    thread_id: int
    start_after_msg_id: int | None  # 该线程消息的起始点（不包含）
    end_at_msg_id: int | None       # 该线程消息的结束点（包含）
```

### 3.2 构建祖先链范围

```python
async def _build_ancestor_ranges(
    self,
    current_thread_id: int,
) -> list[ThreadRange]:
    """
    构建从主线到当前线程的祖先链，并确定每个线程的有效消息范围。
    """
    ranges = []
    stack = []  # 临时存储，从当前线程向上遍历

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

    # 反转：从主线开始处理
    stack.reverse()

    for i, item in enumerate(stack):
        if i == len(stack) - 1:
            # 当前线程：从 fork 点到最新
            ranges.append(ThreadRange(
                thread_id=item['thread_id'],
                start_after_msg_id=item['fork_from'],
                end_at_msg_id=None,  # 无上限
            ))
        else:
            # 祖先线程：从 fork 点到下一个 fork 点
            next_fork = stack[i + 1]['fork_from']
            ranges.append(ThreadRange(
                thread_id=item['thread_id'],
                start_after_msg_id=item['fork_from'],
                end_at_msg_id=next_fork,
            ))

    return ranges
```

### 3.3 分页查询

```python
async def get_context_messages_paginated(
    self,
    thread_id: int,
    cursor: str | None,  # 格式: "msg_id" 或 None
    direction: Literal["before", "after"],
    limit: int = 20,
) -> dict:
    """
    获取线程上下文消息（带分页）。

    Args:
        thread_id: 当前线程 ID
        cursor: 游标（消息 ID），None 表示从最新/最旧开始
        direction: "before" 向前翻（更早的消息），"after" 向后翻（更新的消息）
        limit: 每页数量

    Returns:
        {
            "messages": [...],
            "next_cursor": "123" | None,
            "has_more": True | False
        }
    """
    # Step 1: 构建祖先链范围
    ranges = await self._build_ancestor_ranges(thread_id)

    # Step 2: 构建查询
    #   这里使用 UNION ALL 合并多个线程的查询
    #   每个子查询都应用各自的范围过滤

    subqueries = []
    for r in ranges:
        q = select(MessageModel).where(MessageModel.thread_id == r.thread_id)

        if r.start_after_msg_id is not None:
            q = q.where(MessageModel.id > r.start_after_msg_id)
        if r.end_at_msg_id is not None:
            q = q.where(MessageModel.id <= r.end_at_msg_id)

        subqueries.append(q)

    # UNION ALL
    combined = union_all(*subqueries).subquery()

    # Step 3: 应用游标和方向
    query = select(MessageModel).from_statement(
        select(combined)
    )

    if cursor:
        cursor_id = int(cursor)
        if direction == "before":
            query = query.where(combined.c.id < cursor_id)
        else:  # after
            query = query.where(combined.c.id > cursor_id)

    # Step 4: 排序和限制
    if direction == "before":
        query = query.order_by(combined.c.id.desc())
    else:
        query = query.order_by(combined.c.id.asc())

    query = query.limit(limit + 1)  # 多取一条判断 has_more

    # Step 5: 执行
    result = await self.session.execute(query)
    messages = [self.to_entity(m) for m in result.scalars().all()]

    # Step 6: 处理结果
    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    # 如果是 before 方向，需要反转回正序
    if direction == "before":
        messages.reverse()

    next_cursor = None
    if has_more and messages:
        if direction == "before":
            next_cursor = str(messages[0].id)  # 最早的那条
        else:
            next_cursor = str(messages[-1].id)  # 最新的那条

    return {
        "messages": messages,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }
```

---

## 4. 前端调用流程

### 4.1 初始加载

```javascript
// 用户打开会话，加载最新的 20 条消息
const response = await fetch(
  `/api/v1/threads/${threadId}/context-messages?direction=before&limit=20`,
);
// cursor 不传，表示从最新开始
```

### 4.2 向上滚动加载更多（更早的消息）

```javascript
// 用户滚动到顶部，加载更早的消息
const oldestMsgId = messages[0].id;
const response = await fetch(
  `/api/v1/threads/${threadId}/context-messages?direction=before&cursor=${oldestMsgId}&limit=20`,
);
```

### 4.3 实时更新（有新消息时）

```javascript
// 轮询或 WebSocket 收到新消息通知
const newestMsgId = messages[messages.length - 1].id;
const response = await fetch(
  `/api/v1/threads/${threadId}/context-messages?direction=after&cursor=${newestMsgId}&limit=20`,
);
```

---

## 5. 性能保障

### 5.1 必要的索引

确保 `messages` 表有以下索引：

```sql
-- 已有的索引（满足需求）
CREATE INDEX ix_messages_thread_id_created_at ON messages(thread_id, created_at);

-- 可选：如果按 id 分页更频繁，可以加这个
CREATE INDEX ix_messages_thread_id_id ON messages(thread_id, id);
```

### 5.2 查询性能分析

| 操作           | 复杂度          | 说明                               |
| -------------- | --------------- | ---------------------------------- |
| 构建祖先链     | O(深度)         | 通常 ≤ 5 层，极快                  |
| UNION ALL 查询 | O(limit)        | 每个子查询各扫描 limit 行          |
| 总体           | O(深度 × limit) | 即使 5 层 × 20 条 = 100 行，毫秒级 |

---

## 6. 总结

| 问题                     | 答案                                               |
| ------------------------ | -------------------------------------------------- |
| LIMIT 是否需要全量扫描？ | 否，数据库利用索引 + ORDER BY 只扫描需要的行       |
| 如何保证连续性？         | ORDER BY + Fork 点范围过滤，确保只取有效的连续消息 |
| 分页方案的核心？         | 游标分页 + 祖先链范围限定                          |
