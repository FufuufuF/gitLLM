# 记忆分支 API 接口文档

> 本文档描述记忆分支功能涉及的所有 REST API 接口，包括请求/响应格式、调用方式和前端编排模式。  
> 所有接口均以 `/api/v1` 为前缀，响应统一使用 `BaseResponse` 包装。

---

## 目录

- [0. 通用约定](#0-通用约定)
- [1. POST /threads/fork — 创建分支](#1-post-threadsfork--创建分支)
- [2. POST /threads/{id}/merge/preview — 合并预览](#2-post-threadsidmergepreview--合并预览)
- [3. POST /threads/{id}/merge/confirm — 确认合并](#3-post-threadsidmergeconfirm--确认合并)
- [4. GET /threads/{id}/context-messages — 上下文消息](#4-get-threadsidcontext-messages--上下文消息)
- [5. PATCH /chat_sessions/{id} — 更新会话/切换线程](#5-patch-chat_sessionsid--更新会话切换线程)
- [6. GET /threads/{id}/breadcrumb — 面包屑导航](#6-get-threadsidbreadcrumb--面包屑导航)
- [7. GET /chat_sessions/{id}/thread-tree — 线程树](#7-get-chat_sessionsidthread-tree--线程树)
- [8. 前端编排模式](#8-前端编排模式)
- [9. 枚举值参考](#9-枚举值参考)

---

## 0. 通用约定

### 统一响应格式

所有接口响应均遵循以下结构：

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

- `code = 0` 表示成功，非零表示错误
- `data` 为各接口特定的响应数据

### 错误码

| HTTP 状态码 | 含义 |
|---|---|
| 400 | 请求参数错误 / 业务约束不满足（如逐级合并约束） |
| 403 | 无权限访问该资源 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 1. POST /threads/fork — 创建分支

从指定线程的最新消息处切出一个新的子分支。

### 请求

```
POST /api/v1/threads/fork
Content-Type: application/json
Authorization: Bearer <token>
```

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chat_session_id` | int | 是 | 所属会话 ID |
| `parent_thread_id` | int | 是 | 从哪个线程切出 |
| `title` | string \| null | 否 | 分支标题 |

```json
{
  "chat_session_id": 1,
  "parent_thread_id": 1,
  "title": "Docker 部署探究"
}
```

### 响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "thread": {
      "id": 5,
      "chat_session_id": 1,
      "parent_thread_id": 1,
      "thread_type": 2,
      "status": 1,
      "title": "Docker 部署探究",
      "fork_from_message_id": 42,
      "created_at": "2025-01-15T10:30:00Z"
    }
  }
}
```

### 说明

- Fork 操作**内部同时完成**：创建 thread + 更新 `session.active_thread_id` + 创建初始 checkpoint
- 响应中不冗余返回 `active_thread_id`，前端从 `thread.id` 推断
- Fork 完成后，前端需**串行调用** `GET /threads/{new_id}/context-messages` 加载消息

---

## 2. POST /threads/{id}/merge/preview — 合并预览

生成合并简报预览。此接口为**只读操作**，不修改任何数据库状态。

### 请求

```
POST /api/v1/threads/{thread_id}/merge/preview
Authorization: Bearer <token>
```

无请求体。`thread_id` 为待合并的分支 ID。

### 响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "thread_id": 5,
    "target_thread_id": 1,
    "brief_content": "## 关键结论\n\n- Docker 使用..."
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `thread_id` | int | 待合并的分支 ID |
| `target_thread_id` | int | 合并目标（父线程）ID |
| `brief_content` | string | LLM 生成的学习简报（Markdown 格式），用户可编辑 |

### 校验规则

- 线程必须存在且属于当前用户
- 线程类型不能是主线（主线不可被合并）
- 线程状态必须为 `NORMAL`(1)
- 父线程必须存在且状态为 `NORMAL`(1)
- **逐级合并约束**：该线程下不能有未合并的子分支

---

## 3. POST /threads/{id}/merge/confirm — 确认合并

确认执行合并操作。这是一个事务性操作。

### 请求

```
POST /api/v1/threads/{thread_id}/merge/confirm
Content-Type: application/json
Authorization: Bearer <token>
```

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `brief_content` | string | 是 | 用户确认/编辑后的学习简报文本 |

```json
{
  "brief_content": "## 关键结论\n\n- Docker 使用 cgroup + namespace 实现隔离..."
}
```

### 响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "merged_thread": {
      "id": 5,
      "chat_session_id": 1,
      "parent_thread_id": 1,
      "thread_type": 2,
      "status": 2,
      "title": "Docker 部署探究",
      "fork_from_message_id": 42,
      "created_at": "2025-01-15T10:30:00Z"
    },
    "target_thread": {
      "id": 1,
      "chat_session_id": 1,
      "parent_thread_id": null,
      "thread_type": 1,
      "status": 1,
      "title": "后端部署",
      "fork_from_message_id": null,
      "created_at": "2025-01-15T09:00:00Z"
    },
    "brief_message": {
      "id": 100,
      "role": 3,
      "type": 2,
      "content": "## 关键结论\n\n- Docker 使用 cgroup + namespace 实现隔离...",
      "thread_id": 1,
      "created_at": "2025-01-15T11:00:00Z"
    }
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `merged_thread` | ThreadOut | 被合并的分支（`status` 已变为 `MERGED`(2)） |
| `target_thread` | ThreadOut | 目标父线程 |
| `brief_message` | MessageOut | 已写入父线程的学习简报消息（`role=3/system`, `type=2/BRIEF`） |

### 内部执行步骤

1. 重新校验权限、线程状态（防止 preview 与 confirm 之间状态变更）
2. 在父线程创建 BRIEF 类型消息
3. 更新子线程状态 → `MERGED`
4. 记录 merge 操作到 branch_ops 表
5. 更新 `session.active_thread_id` → 父线程
6. 向父线程的 LangGraph checkpoint 注入 SystemMessage（事务外，失败不阻塞）

### 后续操作

Confirm 成功后，前端**串行调用** `GET /threads/{target_thread.id}/context-messages` 加载父线程消息。

---

## 4. GET /threads/{id}/context-messages — 上下文消息

获取跨线程的上下文消息，支持游标分页。这是一个**独立的复用接口**，在创建分支、切换分支、合并分支、进入会话、滚动加载等场景均可使用。

### 请求

```
GET /api/v1/threads/{thread_id}/context-messages?direction=before&limit=20
Authorization: Bearer <token>
```

**查询参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `direction` | string | 否 | `"before"` | `before`（最新→旧）或 `after`（旧→最新） |
| `cursor` | string | 否 | null | 游标（消息 ID），不传表示从最新/最旧开始 |
| `limit` | int | 否 | 20 | 每页数量，范围 `[1, 100]` |

### 响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "messages": [
      {
        "id": 1,
        "role": 1,
        "type": 1,
        "content": "帮我部署后端项目到服务器上",
        "thread_id": 1,
        "created_at": "2025-01-15T09:00:00Z"
      },
      {
        "id": 2,
        "role": 2,
        "type": 1,
        "content": "好的，首先我们需要确认服务器环境...",
        "thread_id": 1,
        "created_at": "2025-01-15T09:01:00Z"
      },
      {
        "id": 43,
        "role": 1,
        "type": 1,
        "content": "Docker 是怎么工作的？",
        "thread_id": 5,
        "created_at": "2025-01-15T10:31:00Z"
      }
    ],
    "next_cursor": "43",
    "has_more": true
  }
}
```

### 消息聚合逻辑

此接口会沿**祖先链**聚合消息：

```
当前线程（全部消息） → 父线程（fork 点及之前的消息） → 祖父线程（...） → 主线
```

每条消息的 `thread_id` 标注了它来自哪个线程，前端可据此做视觉分区（如淡色显示继承自父线程的消息）。

消息始终按 `id` 升序返回，方便前端按时间顺序渲染。

---

## 5. PATCH /chat_sessions/{id} — 更新会话/切换线程

更新会话属性（切换活跃线程和/或更新标题）。

### 请求

```
PATCH /api/v1/chat_sessions/{session_id}
Content-Type: application/json
Authorization: Bearer <token>
```

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `active_thread_id` | int \| null | 否 | 要切换到的线程 ID |
| `title` | string \| null | 否 | 更新会话标题 |

至少提供一个字段。

```json
{
  "active_thread_id": 5
}
```

### 响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "session_id": 1,
    "title": "后端部署",
    "active_thread_id": 5,
    "active_thread": {
      "id": 5,
      "chat_session_id": 1,
      "parent_thread_id": 1,
      "thread_type": 2,
      "status": 1,
      "title": "Docker 部署探究",
      "fork_from_message_id": 42,
      "created_at": "2025-01-15T10:30:00Z"
    },
    "updated_at": "2025-01-15T11:30:00Z"
  }
}
```

### 校验规则

- 会话必须存在且属于当前用户
- 如果提供 `active_thread_id`，目标线程必须属于该会话

---

## 6. GET /threads/{id}/breadcrumb — 面包屑导航

获取从主线到当前线程的祖先链路径。

### 请求

```
GET /api/v1/threads/{thread_id}/breadcrumb
Authorization: Bearer <token>
```

### 响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "breadcrumb": [
      {
        "thread_id": 1,
        "title": "后端部署",
        "thread_type": 1,
        "status": 1,
        "fork_from_message_id": null
      },
      {
        "thread_id": 5,
        "title": "Docker 部署探究",
        "thread_type": 2,
        "status": 1,
        "fork_from_message_id": 42
      }
    ],
    "current_thread_id": 5
  }
}
```

面包屑顺序：`[主线, ..., 父线程, 当前线程]`，由远及近排列。

---

## 7. GET /chat_sessions/{id}/thread-tree — 线程树

获取会话下的完整线程树结构。

### 请求

```
GET /api/v1/chat_sessions/{session_id}/thread-tree
Authorization: Bearer <token>
```

### 响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "session_id": 1,
    "active_thread_id": 1,
    "threads": [
      {
        "thread_id": 1,
        "parent_thread_id": null,
        "title": "后端部署",
        "thread_type": 1,
        "status": 1,
        "fork_from_message_id": null,
        "created_at": "2025-01-15T09:00:00Z",
        "closed_at": null,
        "message_count": 10,
        "children_count": 2
      },
      {
        "thread_id": 5,
        "parent_thread_id": 1,
        "title": "Docker 部署探究",
        "thread_type": 2,
        "status": 2,
        "fork_from_message_id": 42,
        "created_at": "2025-01-15T10:30:00Z",
        "closed_at": null,
        "message_count": 6,
        "children_count": 0
      }
    ]
  }
}
```

- 返回**扁平列表**，前端用 `parent_thread_id` 自行构建树形结构
- `message_count`：该线程自身的消息数量
- `children_count`：直接子线程数量

---

## 8. 前端编排模式

### 8.1 创建分支

```
fork 有数据依赖（需要 new_thread_id），不能并行。
```

```typescript
// 串行调用
const forkRes = await api.post('/threads/fork', {
  chat_session_id: sessionId,
  parent_thread_id: currentThreadId,
  title: '探究 Docker',
});
const newThreadId = forkRes.data.thread.id;

// fork 完成后再加载消息
const messagesRes = await api.get(
  `/threads/${newThreadId}/context-messages?direction=before&limit=20`
);
renderMessages(messagesRes.data.messages);
```

### 8.2 切换分支

```
target_id 前端已知，PATCH 和 GET 无数据依赖，可以并行。
```

```typescript
// 并行调用 — 唯一支持 Promise.all 的场景
const [sessionRes, messagesRes] = await Promise.all([
  api.patch(`/chat_sessions/${sessionId}`, {
    active_thread_id: targetThreadId,
  }),
  api.get(
    `/threads/${targetThreadId}/context-messages?direction=before&limit=20`
  ),
]);

updateSessionUI(sessionRes.data);
renderMessages(messagesRes.data.messages);
```

### 8.3 合并分支

```
两步操作：preview → 用户编辑 → confirm → 加载消息。全程串行。
```

```typescript
// Step 1: 预览简报
const previewRes = await api.post(`/threads/${branchId}/merge/preview`);
showBriefEditor(previewRes.data.brief_content);

// Step 2: 用户编辑后确认
const editedBrief = getBriefFromEditor();
const confirmRes = await api.post(`/threads/${branchId}/merge/confirm`, {
  brief_content: editedBrief,
});

// Step 3: 加载父线程消息
const parentId = confirmRes.data.target_thread.id;
const messagesRes = await api.get(
  `/threads/${parentId}/context-messages?direction=before&limit=20`
);
renderMessages(messagesRes.data.messages);
```

### 8.4 滚动加载历史

```typescript
// 利用 context-messages 的游标分页
const res = await api.get(
  `/threads/${threadId}/context-messages?direction=before&cursor=${lastCursor}&limit=20`
);
prependMessages(res.data.messages);

if (res.data.has_more) {
  updateCursor(res.data.next_cursor);
} else {
  hideLoadMoreButton();
}
```

---

## 9. 枚举值参考

### ThreadType

| 值 | 枚举名 | 说明 |
|---|---|---|
| 1 | `MAIN_LINE` | 主线线程 |
| 2 | `SUB_LINE` | 子线程（分支） |

### ThreadStatus

| 值 | 枚举名 | 说明 |
|---|---|---|
| 1 | `NORMAL` | 活跃 |
| 2 | `MERGED` | 已合并 |

### MessageRole

| 值 | 枚举名 | 说明 |
|---|---|---|
| 1 | `USER` | 用户消息 |
| 2 | `ASSISTANT` | AI 回复 |
| 3 | `SYSTEM` | 系统消息（含简报） |

### MessageType

| 值 | 枚举名 | 说明 |
|---|---|---|
| 1 | `CHAT` / `NORMAL` | 普通聊天消息 |
| 2 | `BRIEF` | 学习简报（合并时生成） |

---

## 接口总览

| 接口 | 方法 | 路径 | 核心用途 |
|---|---|---|---|
| 创建分支 | POST | `/api/v1/threads/fork` | 从指定线程切出子分支 |
| 合并预览 | POST | `/api/v1/threads/{id}/merge/preview` | 生成学习简报预览（只读） |
| 确认合并 | POST | `/api/v1/threads/{id}/merge/confirm` | 执行合并（事务性写操作） |
| 上下文消息 | GET | `/api/v1/threads/{id}/context-messages` | 跨线程消息聚合（游标分页） |
| 更新会话 | PATCH | `/api/v1/chat_sessions/{id}` | 切换活跃线程 / 更新标题 |
| 面包屑 | GET | `/api/v1/threads/{id}/breadcrumb` | 主线→当前线程的路径导航 |
| 线程树 | GET | `/api/v1/chat_sessions/{id}/thread-tree` | 会话下的完整线程结构 |
