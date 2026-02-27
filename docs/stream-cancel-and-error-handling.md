# 流式生成取消与错误处理设计

> 讨论日期: 2026-02-27

## 1. MessageStatus 枚举语义

```python
class MessageStatus(IntEnum):
    NORMAL = 1           # 消息完整生成并保存
    ERROR = 2            # LLM/系统错误导致生成中断，内容不完整
    STOP_GENERATION = 3  # 用户主动停止生成，内容不完整
```

### 各状态的适用场景

| 状态 | 触发方 | 场景 | 消息内容 |
|---|---|---|---|
| `NORMAL` | 正常流程 | AI 完整生成并入库 | 完整 |
| `ERROR` | 系统 | LLM 网络超时、服务异常等导致流式中断 | 部分（可能为空） |
| `STOP_GENERATION` | 用户 | 用户点击"停止生成"按钮 | 部分（可能为空） |

### 关于"消息入库失败"

消息入库失败时，数据库中不存在该消息记录，因此**无法**通过 `MessageStatus` 字段表示。入库失败应通过 SSE 的 `error` 事件通知前端，属于流级别的错误处理，而非消息级别。

---

## 2. 用户停止生成的触发机制

**方案：关闭 EventSource 连接**

前端点击"停止生成"按钮时：

1. 前端调用 `eventSource.close()` 关闭 SSE 连接
2. TCP 连接断开，服务端（uvicorn/Starlette）检测到客户端断开
3. asyncio 取消当前 Task，在最内层 `await` 处抛出 `CancelledError`
4. 异常通过 async generator 的清理协议逐层向上传播

不需要额外的 `POST /chat/stop` API 或取消令牌机制。

---

## 3. 取消后保存部分消息的实现

### 3.1 调用链与取消传播路径

```
event_generator()                    ← endpoint 层
  └─ service.chat_stream()           ← service 层 (async generator)
       └─ self._invoke_llm_stream()  ← service 层 (async generator)
            └─ agent.astream_events() ← LangGraph (async generator → HTTP 调用)
```

`CancelledError` 从最内层的 `agent.astream_events()` 中的 `await` 处被抛出，逐层向上传播。每层 async generator 在退出时，Python 自动调用 `aclose()`，触发底层 HTTP 连接关闭，**LLM 调用自然终止**。

### 3.2 service 层 — `chat_stream()` 中的处理

在 token 循环处捕获 `CancelledError` 和 `Exception`：

```python
model_config = await self.get_model_config(1)
full_ai_content = ""

try:
    async for token in self._invoke_llm_stream(content, thread_id, model_config):
        full_ai_content += token
        yield (StreamEventType.TOKEN, StreamToken(content=token))
except asyncio.CancelledError:
    # 用户主动取消：保存部分内容，标记 STOP_GENERATION
    if full_ai_content:
        partial_msg = Message(
            role=MessageRole.ASSISTANT,
            content=full_ai_content,
            status=MessageStatus.STOP_GENERATION,
            chat_session_id=chat_session_id,
            thread_id=thread_id,
            user_id=user_id,
            type=MessageType.CHAT,
        )
        try:
            await self._save_message(partial_msg)
        except Exception:
            logger.warning("Failed to save partial message on cancellation")
    raise  # 必须重新抛出，让框架正确关闭连接
except Exception:
    # LLM/系统错误：保存部分内容，标记 ERROR
    if full_ai_content:
        error_msg = Message(
            role=MessageRole.ASSISTANT,
            content=full_ai_content,
            status=MessageStatus.ERROR,
            chat_session_id=chat_session_id,
            thread_id=thread_id,
            user_id=user_id,
            type=MessageType.CHAT,
        )
        try:
            await self._save_message(error_msg)
        except Exception:
            logger.warning("Failed to save partial message on LLM error")
    raise  # 向上抛出，由后续 except Exception 处理并发送 StreamError
```

### 3.3 endpoint 层 — `event_generator()` 中的处理

```python
async def event_generator():
    service = ChatService(db_session)
    try:
        async for event_type, payload in service.chat_stream(
            user_id,
            chat_request.chat_session_id,
            chat_request.thread_id,
            chat_request.content,
        ):
            yield format_sse(event_type, payload.model_dump(mode="json"))
    except asyncio.CancelledError:
        logger.info("Chat stream cancelled by client")
        raise  # 让 Starlette 正确关闭连接
    except Exception:
        logger.exception("chat stream failed")
        error = StreamError(code=500, message="stream failed")
        yield format_sse(StreamEventType.ERROR, error.model_dump())
```

### 3.4 关键设计决策

1. **不在 `CancelledError` 处理中 yield 事件**：客户端已经断开连接，发送事件无意义且可能导致写入异常。

2. **保存操作必须用 `try/except Exception` 包裹**：确保无论保存成功与否，`CancelledError` 都能被重新抛出。

3. **`CancelledError` 必须重新抛出**：它是 asyncio 的协作取消信号（`BaseException` 子类），吞掉它会导致：
   - Task 状态不正确（认为自己仍在运行）
   - Starlette 无法正确关闭连接
   - 可能导致资源泄漏

4. **`CancelledError` 放在 `Exception` 之前**：`CancelledError` 继承自 `BaseException`（Python 3.9+），不会被 `except Exception` 捕获，但显式分开写更清晰、更安全。

5. **`_invoke_llm_stream()` 的 `except Exception` 不捕获 `CancelledError`**：因为 `CancelledError` 是 `BaseException` 的子类，会直接穿透 `except Exception`，无需修改 `_invoke_llm_stream()`。

---

## 4. 前端配合

### 停止生成后的 UI 流程

```
用户点击"停止生成"
  → eventSource.close()
  → 等待连接关闭（极短）
  → 调用消息列表 API 获取最新消息
  → 渲染带 STOP_GENERATION 状态的 AI 消息
  → 显示提示："用户已停止该消息的生成"
```

### LLM 错误后的 UI 流程

```
收到 SSE error 事件
  → 关闭 eventSource
  → 显示错误提示
  → 消息列表中渲染带 ERROR 状态的 AI 消息（如有内容）
  → 可选：提供"重新生成"按钮
```

### 前端区分消息状态的 UI 参考

| 状态 | UI 表现 |
|---|---|
| `NORMAL` | 正常展示消息内容 |
| `ERROR` | 消息内容 + 错误标记，如"生成过程中出错" |
| `STOP_GENERATION` | 消息内容 + 提示，如"用户已停止该消息的生成" |

---

## 5. 完整事件流对比

### 正常流程

```
human_message_created → [chat_session_updated] → token* → ai_message_created
```

### 用户取消

```
human_message_created → [chat_session_updated] → token* → (连接断开，部分消息静默入库)
```

### LLM 错误

```
human_message_created → [chat_session_updated] → token* → error (部分消息静默入库)
```
