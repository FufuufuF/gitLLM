from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user_id
from src.api.schemas.base import BaseResponse
from src.api.schemas.threads import ForkThreadRequest, ForkThreadResponse, ThreadOut
from src.app.services.thread_service import ThreadService
from src.infra.db.session import get_db_session

router = APIRouter()


@router.get("")
def list_threads() -> list[dict]:
    return []

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