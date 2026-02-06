from typing import Optional
from pydantic import BaseModel

from src.api.schemas.messages import ChatMessage

class ChatRequest(BaseModel):
    chat_session_id: int
    thread_id: int
    content: str
    temp_id: Optional[str] = None
    
class ChatResponse(BaseModel):
    chat_session_id: int
    thread_id: int
    human_message: ChatMessage
    ai_message: ChatMessage