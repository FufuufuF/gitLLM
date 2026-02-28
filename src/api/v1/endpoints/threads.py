from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user_id
from src.api.schemas.base import BaseResponse
from src.api.schemas.messages import MessageOut
from src.api.schemas.threads import (
    BreadcrumbItem,
    BreadcrumbResponse,
    ContextMessagesResponse,
    ForkThreadRequest,
    ForkThreadResponse,
    MergeConfirmRequest,
    MergeConfirmResponse,
    MergePreviewResponse,
    ThreadOut,
    ThreadsListResponse,
)
from src.app.services.chat_session_service import ChatSessionService
from src.app.services.merge_service import MergeService
from src.app.services.message_service import MessageService
from src.app.services.thread_service import ThreadService
from src.infra.db.session import get_db_session

router = APIRouter()


@router.get("")
def list_threads() -> list[dict]:
    return []


# ── Fork ──


@router.post("/fork", response_model=BaseResponse[ForkThreadResponse])
async def fork_thread(
    request: ForkThreadRequest,
    user_id: int = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
) -> BaseResponse[ForkThreadResponse]:
    service = ThreadService(db_session)
    thread = await service.fork_thread(
        user_id=user_id,
        chat_session_id=request.chat_session_id,
        parent_thread_id=request.parent_thread_id,
        title=request.title,
    )

    return BaseResponse(
        code=0,
        message="success",
        data=ForkThreadResponse(
            thread=ThreadOut(
                id=thread.id,  # type: ignore[arg-type]
                chat_session_id=thread.chat_session_id,
                parent_thread_id=thread.parent_thread_id,
                thread_type=thread.thread_type,
                status=thread.status,
                title=thread.title,
                fork_from_message_id=thread.fork_from_message_id,
                created_at=thread.created_at,  # type: ignore[arg-type]
            )
        ),
    )


# ── Merge ──


@router.post("/{thread_id}/merge/preview", response_model=BaseResponse[MergePreviewResponse])
async def merge_preview(
    thread_id: int,
    user_id: int = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
) -> BaseResponse[MergePreviewResponse]:
    """生成合并简报预览（不修改任何状态）"""
    service = MergeService(db_session)
    tid, target_tid, brief_content = await service.preview(user_id, thread_id)

    return BaseResponse(
        code=0,
        message="success",
        data=MergePreviewResponse(
            thread_id=tid,
            target_thread_id=target_tid,
            brief_content=brief_content,
        ),
    )


@router.post("/{thread_id}/merge/confirm", response_model=BaseResponse[MergeConfirmResponse])
async def merge_confirm(
    thread_id: int,
    request: MergeConfirmRequest,
    user_id: int = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
) -> BaseResponse[MergeConfirmResponse]:
    """确认合并（事务性操作）"""
    service = MergeService(db_session)
    merged_thread, target_thread, brief_message = await service.confirm(
        user_id, thread_id, request.brief_content
    )

    return BaseResponse(
        code=0,
        message="success",
        data=MergeConfirmResponse(
            merged_thread=ThreadOut(
                id=merged_thread.id,  # type: ignore
                chat_session_id=merged_thread.chat_session_id,
                parent_thread_id=merged_thread.parent_thread_id,
                thread_type=merged_thread.thread_type,
                status=merged_thread.status,
                title=merged_thread.title,
                fork_from_message_id=merged_thread.fork_from_message_id,
                created_at=merged_thread.created_at,  # type: ignore
            ),
            target_thread=ThreadOut(
                id=target_thread.id,  # type: ignore
                chat_session_id=target_thread.chat_session_id,
                parent_thread_id=target_thread.parent_thread_id,
                thread_type=target_thread.thread_type,
                status=target_thread.status,
                title=target_thread.title,
                fork_from_message_id=target_thread.fork_from_message_id,
                created_at=target_thread.created_at,  # type: ignore
            ),
            brief_message=MessageOut(
                id=brief_message.id,  # type: ignore
                role=brief_message.role,  # type: ignore[arg-type]
                type=brief_message.type,  # type: ignore[arg-type]
                content=brief_message.content if isinstance(brief_message.content, str) else str(brief_message.content),
                thread_id=brief_message.thread_id,
                created_at=brief_message.created_at,  # type: ignore
            ),
        ),
    )


# ── Context Messages ──


@router.get("/{thread_id}/context-messages", response_model=BaseResponse[ContextMessagesResponse])
async def get_context_messages(
    thread_id: int,
    direction: str = Query("before", pattern="^(before|after)$"),
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db_session: AsyncSession = Depends(get_db_session),
) -> BaseResponse[ContextMessagesResponse]:
    """获取跨线程的上下文消息（游标分页）"""
    service = MessageService(db_session)
    messages, next_cursor, has_more = await service.get_context_messages(
        thread_id=thread_id,
        direction=direction,
        cursor=cursor,
        limit=limit,
    )

    return BaseResponse(
        code=0,
        message="success",
        data=ContextMessagesResponse(
            messages=[
                MessageOut(
                    id=m.id,  # type: ignore
                    role=m.role,  # type: ignore[arg-type]
                    type=m.type,  # type: ignore[arg-type]
                    content=m.content if isinstance(m.content, str) else str(m.content),
                    thread_id=m.thread_id,
                    created_at=m.created_at,  # type: ignore
                    status=m.status,
                )
                for m in messages
            ],
            next_cursor=next_cursor,
            has_more=has_more,
        ),
    )


# ── Threads ──


@router.get("/{chat_session_id}/list", response_model=BaseResponse[ThreadsListResponse])
async def get_threads(
    chat_session_id: int,
    user_id: int = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
) -> BaseResponse[ThreadsListResponse]:
    """获取会话下的线程列表"""
    service = ThreadService(db_session)
    threads = await service.get_threads(user_id, chat_session_id)

    return BaseResponse(
        code=0,
        message="success",
        data=ThreadsListResponse(
            threads=[
                ThreadOut(
                    id=t.id,  # type: ignore
                    chat_session_id=t.chat_session_id,
                    parent_thread_id=t.parent_thread_id,
                    thread_type=t.thread_type,
                    status=t.status,
                    title=t.title,
                    fork_from_message_id=t.fork_from_message_id,
                    created_at=t.created_at,  # type: ignore
                )
                for t in threads
            ],
        ),
    )


# ── Breadcrumb ──


@router.get("/{thread_id}/breadcrumb", response_model=BaseResponse[BreadcrumbResponse])
async def get_breadcrumb(
    thread_id: int,
    user_id: int = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
) -> BaseResponse[BreadcrumbResponse]:
    """获取面包屑导航"""
    service = ChatSessionService(db_session)
    chain = await service.get_breadcrumb(user_id, thread_id)

    return BaseResponse(
        code=0,
        message="success",
        data=BreadcrumbResponse(
            breadcrumb=[
                BreadcrumbItem(
                    thread_id=t.id,  # type: ignore
                    title=t.title,
                    thread_type=t.thread_type,
                    status=t.status,
                    fork_from_message_id=t.fork_from_message_id,
                )
                for t in chain
            ],
            current_thread_id=thread_id,
        ),
    )