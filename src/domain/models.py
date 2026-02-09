# MVP
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class Message(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    role: int
    content: str | list[str | dict]
    chat_session_id: int
    thread_id: int
    user_id: int
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
    status: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None