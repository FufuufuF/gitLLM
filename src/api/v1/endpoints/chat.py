import logging
import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.chat import ChatRequest, ChatResponse, StreamError, StreamEventType
from src.api.schemas.messages import MessageOut
from src.api.deps import get_current_user_id
from src.api.schemas.base import BaseResponse
from src.api.utils import format_sse
from src.app.services.chat_service import ChatService
from src.infra.db.session import get_db_session, get_session_factory, SessionFactory
from src.core.exceptions import InternalServerException
from src.domain.enums import MessageRole, MessageType

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/")
async def chat(
    chat_request: ChatRequest, 
    user_id: int = Depends(get_current_user_id), 
    db_session: AsyncSession = Depends(get_db_session)
    ) -> BaseResponse[ChatResponse]:
    chat_service = ChatService(db_session)
    human_message, ai_message, chat_session_id, thread_id = await chat_service.chat(
        user_id, 
        chat_request.chat_session_id, 
        chat_request.thread_id, 
        chat_request.content
    )
    
    # Validate message IDs and created_at (should never be None after save)
    if human_message.id is None or ai_message.id is None:
        raise InternalServerException("Message ID should not be None after saving")
    if human_message.created_at is None or ai_message.created_at is None:
        raise InternalServerException("Message created_at should not be None after saving")

    return BaseResponse[ChatResponse](
        code=0,
        message='success',
        data=ChatResponse(
            chat_session_id=chat_session_id,  # 使用实际创建的 ID
            thread_id=thread_id,              # 使用实际创建的 ID
            human_message=MessageOut(
                id=human_message.id,
                content=human_message.content if isinstance(human_message.content, str) else str(human_message.content),
                created_at=human_message.created_at,
                thread_id=thread_id,
                temp_id=chat_request.temp_id,
                role=MessageRole.USER,
                type=MessageType.CHAT,
                status=human_message.status
            ),
            ai_message=MessageOut(
                id=ai_message.id,
                content=ai_message.content if isinstance(ai_message.content, str) else str(ai_message.content),
                created_at=ai_message.created_at,
                thread_id=thread_id,
                role=MessageRole.ASSISTANT,
                type=MessageType.CHAT,
                status=ai_message.status
            )
        )
    )

@router.post("/stream")
async def chat_stream(
    chat_request: ChatRequest, 
    user_id: int = Depends(get_current_user_id), 
    db_session: AsyncSession = Depends(get_db_session),
    session_factory: SessionFactory = Depends(get_session_factory),
    ) -> StreamingResponse:
    async def event_generator():
        service = ChatService(db_session, session_factory)
        try:
            async for event_type, payload in service.chat_stream(
                user_id, 
                chat_request.chat_session_id, 
                chat_request.thread_id, 
                chat_request.content
            ):
                yield format_sse(event_type, payload.model_dump(mode="json"))
        except asyncio.CancelledError:
            logger.info("Chat stream cancelled by client")
            return  # 静默结束生成器，不再 re-raise 避免框架层打印异常堆栈
        except Exception as e:
            logger.exception("chat stream failed")
            error = StreamError(code=500, message="stream failed")
            yield format_sse(StreamEventType.ERROR, error.model_dump())

    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # For Nginx to disable response buffering
        }
    )