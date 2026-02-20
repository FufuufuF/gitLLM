from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional

from src.domain.enums import MessageRole, MessageType

class MessageOut(BaseModel):
    """消息通用输出模型"""
    model_config = ConfigDict(use_enum_values=True)

    id: Optional[int] = None
    role: MessageRole
    type: MessageType
    content: str
    thread_id: int
    created_at: datetime
    temp_id: Optional[str] = None

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
