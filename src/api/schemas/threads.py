from pydantic import BaseModel, ConfigDict
from datetime import datetime

from src.domain.enums import ThreadType, ThreadStatus


class ThreadOut(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: int
    chat_session_id: int
    parent_thread_id: int | None
    thread_type: ThreadType
    status: ThreadStatus
    title: str | None
    fork_from_message_id: int | None
    created_at: datetime

class ForkThreadRequest(BaseModel):
    chat_session_id: int
    parent_thread_id: int
    title: str | None = None
    # 只能从parent最新的消息切出分支

class ForkThreadResponse(BaseModel):
    thread: ThreadOut