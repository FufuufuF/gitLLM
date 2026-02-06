from pydantic import BaseModel
from datetime import datetime

class ChatRequest(BaseModel):
    chat_session_id: int
    thread_id: int
    content: str

class ChatMessage(BaseModel):
    id: int
    content: str
    create_time: datetime
    
class ChatResponse(BaseModel):
    chat_session_id: int
    thread_id: int
    human_message: ChatMessage
    ai_message: ChatMessage