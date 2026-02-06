from typing import Optional
from pydantic import BaseModel
from datetime import datetime

class ChatRequest(BaseModel):
    chat_session_id: int
    thread_id: int
    content: str
    temp_id: Optional[str] = None

class ChatMessage(BaseModel):
    id: int
    content: str
    create_at: datetime
    temp_id: Optional[str] = None
    
class ChatResponse(BaseModel):
    chat_session_id: int
    thread_id: int
    human_message: ChatMessage
    ai_message: ChatMessage