from typing import Optional
from pydantic import BaseModel
from enum import StrEnum

from src.api.schemas.messages import MessageOut

class ChatRequest(BaseModel):
    chat_session_id: int
    thread_id: int
    content: str
    temp_id: Optional[str] = None
    
class ChatResponse(BaseModel):
    chat_session_id: int
    thread_id: int
    human_message: MessageOut
    ai_message: MessageOut

class StreamEventType(StrEnum):
    HUMAN_MESSAGE_CREATED = "human_message_created"
    CHAT_SESSION_UPDATED = "chat_session_updated"
    TOKEN = "token"
    AI_MESSAGE_CREATED = "ai_message_created"
    ERROR = "error"


class StreamHumanMessageCreated(BaseModel):
    chat_session_id: int
    thread_id: int
    message: MessageOut


class StreamChatSessionUpdated(BaseModel):
    chat_session_id: int
    title: Optional[str] = None
    reason: str = "title_updated"


class StreamAIMessageCreated(BaseModel):
    chat_session_id: int
    thread_id: int
    message: MessageOut
    
class StreamToken(BaseModel):
    content: str
    
class StreamError(BaseModel):
    code: int
    message: str
    error_type: str = "internal_error"  # quota_exceeded, rate_limited, auth_error, llm_error, internal_error
