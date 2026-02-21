from pydantic import BaseModel, ConfigDict
from datetime import datetime

from src.domain.enums import ThreadType, ThreadStatus
from src.api.schemas.messages import MessageOut


class ThreadOut(BaseModel):
    """线程通用输出模型 — 所有涉及线程的接口复用此 Schema"""
    model_config = ConfigDict(use_enum_values=True)

    id: int
    chat_session_id: int
    parent_thread_id: int | None
    thread_type: ThreadType
    status: ThreadStatus
    title: str | None
    fork_from_message_id: int | None
    created_at: datetime


# ── Fork ──

class ForkThreadRequest(BaseModel):
    chat_session_id: int
    parent_thread_id: int
    title: str | None = None

class ForkThreadResponse(BaseModel):
    thread: ThreadOut


# ── Merge ──

class MergePreviewResponse(BaseModel):
    thread_id: int
    target_thread_id: int
    brief_content: str

class MergeConfirmRequest(BaseModel):
    brief_content: str

class MergeConfirmResponse(BaseModel):
    merged_thread: ThreadOut
    target_thread: ThreadOut
    brief_message: MessageOut


# ── Context Messages ──


class ContextMessagesResponse(BaseModel):
    messages: list[MessageOut]
    next_cursor: str | None
    has_more: bool


# ── Update Session ──

class UpdateSessionRequest(BaseModel):
    active_thread_id: int | None = None
    title: str | None = None

class UpdateSessionResponse(BaseModel):
    session_id: int
    title: str | None
    active_thread_id: int
    active_thread: ThreadOut
    updated_at: datetime


# ── Breadcrumb (P1) ──

class BreadcrumbItem(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    thread_id: int
    title: str | None
    thread_type: ThreadType
    status: ThreadStatus
    fork_from_message_id: int | None

class BreadcrumbResponse(BaseModel):
    breadcrumb: list[BreadcrumbItem]
    current_thread_id: int


# ── Thread List (P1) ──

class ThreadsListResponse(BaseModel):
    threads: list[ThreadOut]

