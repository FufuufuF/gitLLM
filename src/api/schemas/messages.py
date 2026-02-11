from datetime import datetime
from pydantic import BaseModel
from typing import Optional

from src.domain.enums import MessageRole

class MessageOut(BaseModel):
    id: Optional[int] = None
    content: str
    create_at: datetime
    temp_id: Optional[str] = None
    role: MessageRole

class MessageRequest(BaseModel):
    chat_session_id: int
    thread_id: int
    page: Optional[int] = 1
    page_size: Optional[int] = 10

class MessageResponse(BaseModel):
    messages: list[MessageOut]
    total: Optional[int] = None
    page: Optional[int] = None
    page_size: Optional[int] = None
    total_pages: Optional[int] = None
