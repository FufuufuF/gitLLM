from pydantic import BaseModel

class ChatRequest(BaseModel):
    chat_session_id: int
    thread_id: int
    content: str

class ChatResponse(BaseModel):
    human_message_id: int
    ai_message_id: int
    chat_session_id: int
    thread_id: int
    human_message: str
    ai_message: str