# MVP
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

from src.domain.enums import MessageType, MessageRole, ThreadType, ThreadStatus

class Message(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: Optional[int] = None
    role: MessageRole
    content: str | list[str | dict]
    chat_session_id: int
    thread_id: int
    user_id: int
    type: MessageType
    created_at: Optional[datetime] = None # Datetime object

class ModelConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    provider: str
    api_key: str
    base_url: Optional[str] = None
    model_name: str
    created_at: Optional[datetime] = None
    user_id: int

class ChatSession(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    user_id: int
    title: Optional[str] = None
    goal: Optional[str] = None
    status: int = 1
    active_thread_id: Optional[int] = None  # Nullable for initial creation
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class ChatSessionListResult(BaseModel):
    """会话列表结果（游标分页）"""
    model_config = ConfigDict(from_attributes=True)

    items: list[ChatSession]
    next_cursor: Optional[str] = None
    has_more: bool


class Thread(BaseModel):
    """线程领域模型"""
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: Optional[int] = None
    user_id: int
    chat_session_id: int
    parent_thread_id: Optional[int] = None
    thread_type: ThreadType = ThreadType.MAIN_LINE
    status: ThreadStatus = ThreadStatus.NORNAL
    title: Optional[str] = None
    fork_from_message_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None