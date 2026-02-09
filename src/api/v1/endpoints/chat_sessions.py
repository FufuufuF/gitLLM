from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.chat_sessions import ChatSessionListRequest, ChatSessionListResponse, ChatSessionItem
from src.api.deps import get_current_user_id, db_session

router = APIRouter()


@router.get("/")
def list_sessions(
    request: Annotated[ChatSessionListRequest, Depends()],
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session)
) -> ChatSessionListResponse:
    pass
