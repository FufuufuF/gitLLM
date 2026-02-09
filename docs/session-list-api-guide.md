# 会话列表接口实现指南（游标分页版）

本文档描述 `GET /api/v1/chat_sessions` 接口的技术实现，用于获取用户的历史会话列表。

> **变更说明**：为了更好地支持前端无限滚动（Infinite Scroll）交互，本接口采用**游标分页（Cursor Pagination）**方案，以解决 Offset 分页在数据动态变化时可能出现的重复或遗漏问题。

---

## 1. 接口定义

### 1.1 基本信息

| 项目 | 值                                    |
| ---- | ------------------------------------- |
| 路由 | `GET /api/v1/chat_sessions`           |
| 认证 | Bearer Token（`get_current_user_id`） |
| 分页 | **Cursor 分页**                       |

### 1.2 请求参数

| 参数     | 类型 | 必填 | 默认值 | 说明                                   |
| -------- | ---- | ---- | ------ | -------------------------------------- |
| `cursor` | str  | 否   | None   | 上一页返回的 `next_cursor`，第一页不传 |
| `limit`  | int  | 否   | 20     | 每页数量（最大 100）                   |

### 1.3 响应体

```python
# src/api/schemas/chat_sessions.py

class ChatSessionItem(BaseModel):
    """会话列表项"""
    id: int
    title: str | None
    goal: str | None
    status: int
    active_thread_id: int
    created_at: datetime
    updated_at: datetime

class ChatSessionListResponse(BaseModel):
    """会话列表响应（游标分页）"""
    items: list[ChatSessionItem]
    next_cursor: str | None     # 下一页游标，为 None 表示没有更多数据
    has_more: bool              # 是否还有更多数据
```

---

## 2. API 层

**路径**: `src/api/v1/endpoints/chat_sessions.py`

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.chat_sessions import ChatSessionListResponse
from src.api.deps import get_current_user_id, get_db
from src.app.services.chat_session_service import SessionService

router = APIRouter()


@router.get("", response_model=ChatSessionListResponse)
async def list_sessions(
    cursor: str | None = Query(None, description="游标（上一页的 next_cursor）"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionListResponse:
    """
    获取当前用户的会话列表（游标分页）。
    适用于无限滚动场景。
    """
    service = SessionService(db)
    result = await service.list_sessions(user_id, cursor, limit)

    return ChatSessionListResponse(
        items=result["items"],
        next_cursor=result["next_cursor"],
        has_more=result["has_more"],
    )
```

---

## 3. Service 层

**路径**: `src/app/services/chat_session_service.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from src.infra.db.repositories.chat_sessions import SessionRepository
from src.domain.models import ChatSession

class SessionService:
    """会话服务"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.session_repo = SessionRepository(db_session)

    async def list_sessions(
        self,
        user_id: int,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """
        获取用户的会话列表（游标分页）。

        返回:
        {
            "items": [ChatSession, ...],
            "next_cursor": "...",
            "has_more": True/False
        }
        """
        # 调用 Repository 获取数据
        items, next_cursor, has_more = await self.session_repo.list_sessions_cursor(
            user_id, cursor, limit
        )

        return {
            "items": items,
            "next_cursor": next_cursor,
            "has_more": has_more
        }
```

---

## 4. Repository 层

**路径**: `src/infra/db/repositories/chat_sessions.py`

```python
from sqlalchemy import select, desc, or_, and_
from src.infra.db.repositories.base import BaseRepository
from src.infra.db.models.chat_sessions import ChatSession as ChatSessionModel
from src.domain.models import ChatSession
import base64

class SessionRepository(BaseRepository[ChatSessionModel, ChatSession]):
    """会话仓储"""
    model = ChatSessionModel
    schema_class = ChatSession

    async def list_sessions_cursor(
        self,
        user_id: int,
        cursor: str | None,
        limit: int = 20
    ) -> tuple[list[ChatSession], str | None, bool]:
        """
        游标分页查询。

        排序规则：updated_at DESC, id DESC
        游标构成：base64(timestamp|id)
        """
        query = select(ChatSessionModel).where(
            ChatSessionModel.user_id == user_id,
            ChatSessionModel.deleted_at.is_(None)
        )

        # 1. 解析游标
        if cursor:
            try:
                decoded = base64.urlsafe_b64decode(cursor).decode('utf-8')
                timestamp_str, id_str = decoded.split('|')
                timestamp_val = float(timestamp_str)  # 假设 timestamp 转为 float 存储
                id_val = int(id_str)

                # 构建游标过滤条件 (updated_at < ts OR (updated_at == ts AND id < id_val))
                # 注意：SQLAlchemy 中使用 tuple 比较通常更简洁，但考虑到兼容性，展开写
                query = query.where(
                    or_(
                        ChatSessionModel.updated_at < timestamp_val,  # 这里的类型转换需注意，DB 中是 DateTime
                        and_(
                            ChatSessionModel.updated_at == timestamp_val,
                            ChatSessionModel.id < id_val
                        )
                    )
                )
            except Exception:
                # 游标无效时，可以选择忽略或报错，这里做忽略处理，从头开始
                pass

        # 2. 排序与限制
        query = query.order_by(
            ChatSessionModel.updated_at.desc(),
            ChatSessionModel.id.desc()
        ).limit(limit + 1)  # 多查一条用于判断 has_more

        # 3. 执行查询
        result = await self.session.execute(query)
        rows = result.scalars().all()

        # 4. 处理分页结果
        has_more = len(rows) > limit
        items = rows[:limit]

        next_cursor = None
        if has_more and items:
            last_item = items[-1]
            # 生成新游标: base64(timestamp|id)
            # 注意：实际 timestamp 转 str 需要处理时区和精度
            ts = last_item.updated_at.timestamp()
            cursor_str = f"{ts}|{last_item.id}"
            next_cursor = base64.urlsafe_b64encode(cursor_str.encode('utf-8')).decode('utf-8')

        return [self.to_entity(row) for row in items], next_cursor, has_more
```

> **注意**：实际实现中，`updated_at` 的比较可能需要根据数据库类型做适配。如果 `updated_at` 不是唯一的，必须配合 `id` 使用（Tie-breaker）以保证排序确定性。

---

## 5. 文件修改清单

| 文件路径                                     | 修改内容                                            |
| -------------------------------------------- | --------------------------------------------------- |
| `src/api/schemas/chat_sessions.py`           | 重构为 `ChatSessionListResponse` (cursor, has_more) |
| `src/api/v1/endpoints/chat_sessions.py`      | 更新接口参数为 cursor/limit                         |
| `src/app/services/chat_session_service.py`   | 更新逻辑适配 cursor 分页                            |
| `src/infra/db/repositories/chat_sessions.py` | 实现 `list_sessions_cursor`                         |

---

## 6. 前端对接指南

1. **初始请求**: 不传 `cursor` 参数。
   `GET /api/v1/chat_sessions?limit=20`
2. **接收响应**:
   ```json
   {
       "items": [...],
       "next_cursor": "Base64String...",
       "has_more": true
   }
   ```
3. **加载更多**: 当用户滚动到底部（且 `has_more=true`）时，取上一次的 `next_cursor` 发起请求。
   `GET /api/v1/chat_sessions?limit=20&cursor=Base64String...`

4. **数据合并**: 将新返回的 `items` 追加到当前列表尾部。
