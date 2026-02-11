from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.chat_sessions import (
    ChatSessionListRequest,
    ChatSessionListResponse,
    ChatSessionItem,
)
from src.api.schemas.base import BaseResponse
from src.api.deps import get_current_user_id, db_session
from src.app.services.chat_session_service import ChatSessionService

router = APIRouter()


@router.get("/", response_model=BaseResponse[ChatSessionListResponse])
async def list_sessions(
    request: Annotated[ChatSessionListRequest, Depends()],
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session),
) -> BaseResponse[ChatSessionListResponse]:
    """
    获取当前用户的会话列表（游标分页）。
    适用于无限滚动场景。
    """
    service = ChatSessionService(db)
    result = await service.list_sessions(
        user_id=user_id,
        cursor=request.cursor,
        limit=request.limit,
    )

    # 将 domain entity 转换为 API schema
    items = [
        ChatSessionItem(
            id=item.id, # type: ignore
            title=item.title,
            goal=item.goal,
            status=item.status,
            active_thread_id=item.active_thread_id,
            created_at=item.created_at, # type: ignore
            updated_at=item.updated_at, # type: ignore
        )
        for item in result.items
    ]

    return BaseResponse(
        code=0,
        message="success",
        data=ChatSessionListResponse(
            items=items,
            next_cursor=result.next_cursor,
            has_more=result.has_more,
        )
    )
