from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.chat_sessions import (
    ChatSessionListRequest,
    ChatSessionListResponse,
    ChatSessionItem,
)
from src.api.schemas.base import BaseResponse
from src.api.schemas.threads import (
    ThreadOut,
    UpdateSessionRequest,
    UpdateSessionResponse,
)
from src.api.deps import get_current_user_id, db_session
from src.app.services.chat_session_service import ChatSessionService

router = APIRouter()


@router.get("/", response_model=BaseResponse[ChatSessionListResponse])
async def list_sessions(
    request: Annotated[ChatSessionListRequest, Depends()],
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session),
) -> BaseResponse[ChatSessionListResponse]:
    """获取当前用户的会话列表（游标分页）"""
    service = ChatSessionService(db)
    result = await service.list_sessions(
        user_id=user_id,
        cursor=request.cursor,
        limit=request.limit,
    )

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


@router.patch("/{chat_session_id}", response_model=BaseResponse[UpdateSessionResponse])
async def update_session(
    chat_session_id: int,
    request: UpdateSessionRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session),
) -> BaseResponse[UpdateSessionResponse]:
    """更新会话（切换活跃线程 / 更新标题）"""
    service = ChatSessionService(db)
    active_thread = await service.update_session(
        user_id=user_id,
        chat_session_id=chat_session_id,
        active_thread_id=request.active_thread_id,
        title=request.title,
    )

    return BaseResponse(
        code=0,
        message="success",
        data=UpdateSessionResponse(
            active_thread=ThreadOut(
                id=active_thread.id,  # type: ignore
                chat_session_id=active_thread.chat_session_id,
                parent_thread_id=active_thread.parent_thread_id,
                thread_type=active_thread.thread_type,
                status=active_thread.status,
                title=active_thread.title,
                fork_from_message_id=active_thread.fork_from_message_id,
                created_at=active_thread.created_at,  # type: ignore
            ),
        ),
    )

