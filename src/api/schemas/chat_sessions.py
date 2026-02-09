from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ChatSessionListRequest(BaseModel):
    """会话列表请求"""
    page: Optional[int] = 1
    page_size: Optional[int] = 20

class ChatSessionItem(BaseModel):
    """会话列表项"""
    id: int
    title: str | None
    goal: str | None
    status: int
    created_at: datetime
    updated_at: datetime

class ChatSessionListResponse(BaseModel):
    """会话列表响应"""
    items: list[ChatSessionItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    
