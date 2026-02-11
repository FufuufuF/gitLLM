from pydantic import BaseModel
from datetime import datetime

from src.domain.enums import ThreadType, ThreadStatus


class ThreadOut(BaseModel):
    id: int
    chat_session_id: int
    parent_thread_id: int | None
    thread_type: ThreadType
    status: ThreadStatus
    title: str
    fork_from_message_id: int | None
    created_at: datetime
