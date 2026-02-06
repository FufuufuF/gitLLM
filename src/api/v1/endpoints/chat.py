from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.chat import ChatRequest, ChatResponse, ChatMessage
from src.api.deps import get_current_user_id
from src.api.schemas.base import BaseResponse
from src.app.services.chat_service import ChatService
from src.infra.db.session import get_db_session
from src.core.exceptions import InternalServerException

router = APIRouter()

@router.post("/")
async def chat(
    chat_request: ChatRequest, 
    user_id: int = Depends(get_current_user_id), 
    db_session: AsyncSession = Depends(get_db_session)
    ) -> BaseResponse[ChatResponse]:
    chat_service = ChatService(db_session)
    human_message, ai_message = await chat_service.chat(
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
            chat_session_id=chat_request.chat_session_id,
            thread_id=chat_request.thread_id,
            human_message=ChatMessage(
                id=human_message.id,
                content=human_message.content if isinstance(human_message.content, str) else str(human_message.content),
                create_at=human_message.created_at,
                temp_id=chat_request.temp_id,
                role=0
            ),
            ai_message=ChatMessage(
                id=ai_message.id,
                content=ai_message.content if isinstance(ai_message.content, str) else str(ai_message.content),
                create_at=ai_message.created_at,
                role=1
            )
        )
    )

    
    
