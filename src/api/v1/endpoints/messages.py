from fastapi import APIRouter, Depends

from src.api.deps import get_current_user_id
from src.api.deps import get_db_session
from src.api.schemas.base import BaseResponse
from src.api.schemas.messages import MessageOut, MessageRequest, MessageResponse
from src.app.services.message_service import MessageService
from src.domain.enums import MessageRole, MessageType

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
                MessageOut(
                    id=message.id,
                    content=message.content if isinstance(message.content, str) else str(message.content),
                    created_at=message.created_at, # type: ignore
                    thread_id=message.thread_id,
                    role=MessageRole(message.role),
                    type=MessageType(message.type)
                ) for message in messages if message is not None    
            ],
        )
    )
    
