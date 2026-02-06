from fastapi import APIRouter, Depends

from src.api.deps import get_current_user_id
from src.api.deps import get_db_session
from src.api.schemas.base import BaseResponse
from src.api.schemas.messages import ChatMessage, MessageRequest, MessageResponse
from src.app.services.message_service import MessageService

router = APIRouter()

@router.post("/")
async def list_messages(
    request: MessageRequest,
    user_id: int = Depends(get_current_user_id),
    db_session = Depends(get_db_session)
) -> BaseResponse[MessageResponse]:
    message_service = MessageService(db_session)
    messages = await message_service.get_messages(
        user_id,
        request.chat_session_id,
        request.thread_id,
    )
    return BaseResponse[MessageResponse](
        code=0,
        message='success',
        data=MessageResponse(
            messages=[
                ChatMessage(
                    id=message.id,
                    content=message.content, # type: ignore
                    create_at=message.created_at, # type: ignore
                    role=message.role
                ) for message in messages if message is not None    
            ],
        )
    )
    
