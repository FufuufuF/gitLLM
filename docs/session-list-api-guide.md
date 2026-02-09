# 会话列表接口实现指南

本文档描述 `GET /api/v1/sessions` 接口的技术实现，用于获取用户的历史会话列表。

---

## 1. 接口定义

### 1.1 基本信息

| 项目 | 值                                    |
| ---- | ------------------------------------- |
| 路由 | `GET /api/v1/sessions`                |
| 认证 | Bearer Token（`get_current_user_id`） |
| 分页 | Offset 分页                           |

### 1.2 请求参数

| 参数        | 类型 | 必填 | 默认值 | 说明                 |
| ----------- | ---- | ---- | ------ | -------------------- |
| `page`      | int  | 否   | 1      | 页码（从 1 开始）    |
| `page_size` | int  | 否   | 20     | 每页数量（最大 100） |

### 1.3 响应体

```python
# src/api/schemas/sessions.py

class SessionItem(BaseModel):
    """会话列表项"""
    id: int
    title: str | None
    goal: str | None
    status: int
    created_at: datetime
    updated_at: datetime

class SessionListResponse(BaseModel):
    """会话列表响应"""
    items: list[SessionItem]
    total: int
    page: int
    page_size: int
    total_pages: int
```

---

## 2. API 层

**路径**: `src/api/v1/endpoints/sessions.py`

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.sessions import SessionListResponse
from src.api.deps import get_current_user_id, get_db
from src.app.services.session_service import SessionService

router = APIRouter()


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SessionListResponse:
    """获取当前用户的会话列表"""
    service = SessionService(db)
    result = await service.list_sessions(user_id, page, page_size)
    return SessionListResponse(
        items=result.items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )
```

---

## 3. Service 层

**路径**: `src/app/services/session_service.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.db.repositories.sessions import SessionRepository
from src.infra.db.repositories.base import PaginatedResult
from src.domain.models import ChatSession


class SessionService:
    """会话服务"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.session_repo = SessionRepository(db_session)

    async def list_sessions(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult[ChatSession]:
        """
        获取用户的会话列表（分页）。

        参数:
        - user_id: 用户 ID
        - page: 页码（从 1 开始）
        - page_size: 每页数量

        返回:
        PaginatedResult 包含 items, total, page, page_size, total_pages
        """
        return await self.session_repo.list_by_user(user_id, page, page_size)
```

---

## 4. Domain 层

**路径**: `src/domain/models.py`

```python
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class ChatSession(BaseModel):
    """会话领域模型"""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    user_id: int
    title: str | None = None
    goal: str | None = None
    status: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

---

## 5. Repository 层

**路径**: `src/infra/db/repositories/sessions.py`

```python
from sqlalchemy import func, select

from src.infra.db.repositories.base import BaseRepository, PaginatedResult
from src.infra.db.models.chat_sessions import ChatSession as ChatSessionModel
from src.domain.models import ChatSession


class SessionRepository(BaseRepository[ChatSessionModel, ChatSession]):
    """会话仓储"""
    model = ChatSessionModel
    schema_class = ChatSession

    async def list_by_user(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult[ChatSession]:
        """
        分页获取用户的会话列表。

        排序: 按 updated_at 降序（最近更新的在前）
        过滤: 排除已删除的会话（deleted_at IS NULL）
        """
        # 1. 构建基础查询条件
        base_filter = (
            (ChatSessionModel.user_id == user_id) &
            (ChatSessionModel.deleted_at.is_(None))
        )

        # 2. 统计总数
        count_stmt = select(func.count()).select_from(ChatSessionModel).where(base_filter)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # 3. 计算分页信息
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        offset = (page - 1) * page_size

        # 4. 查询数据
        stmt = (
            select(ChatSessionModel)
            .where(base_filter)
            .order_by(ChatSessionModel.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        items = [self.to_entity(row) for row in result.scalars().all()]

        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
```

---

## 6. 文件修改清单

### 6.1 修改文件

| 文件路径                                | 修改内容                                          |
| --------------------------------------- | ------------------------------------------------- |
| `src/api/schemas/sessions.py`           | 更新 Schema：`SessionItem`, `SessionListResponse` |
| `src/api/v1/endpoints/sessions.py`      | 实现 `list_sessions` 端点                         |
| `src/app/services/session_service.py`   | 实现 `list_sessions` 方法                         |
| `src/domain/models.py`                  | 添加 `ChatSession` 领域模型                       |
| `src/infra/db/repositories/sessions.py` | 实现 `SessionRepository.list_by_user`             |

---

## 7. 数据流

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   API 层     │────▶│  Service 层  │────▶│ Repository   │────▶│   Database   │
│  sessions.py │     │ SessionService│    │ SessionRepo  │     │ chat_sessions│
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │                    │
       │  page, page_size   │                    │                    │
       │  user_id           │                    │                    │
       │───────────────────▶│                    │                    │
       │                    │  list_by_user()    │                    │
       │                    │───────────────────▶│                    │
       │                    │                    │  SELECT + COUNT    │
       │                    │                    │───────────────────▶│
       │                    │                    │◀───────────────────│
       │                    │  PaginatedResult   │                    │
       │                    │◀───────────────────│                    │
       │ SessionListResponse│                    │                    │
       │◀───────────────────│                    │                    │
```
