from pydantic import BaseModel, Field
from datetime import datetime


class ChatSessionListRequest(BaseModel):
    """会话列表请求（游标分页）"""
    cursor: str | None = Field(None, description="上一页返回的 next_cursor，第一页不传")
    limit: int = Field(20, ge=1, le=100, description="每页数量")


class ChatSessionItem(BaseModel):
    """会话列表项"""
    id: int
    title: str | None
    goal: str | None
    status: int
    active_thread_id: int | None
    created_at: datetime
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    """会话列表响应（游标分页）"""
    items: list[ChatSessionItem]
    next_cursor: str | None = Field(None, description="下一页游标，为 None 表示没有更多数据")
    has_more: bool = Field(..., description="是否还有更多数据")
