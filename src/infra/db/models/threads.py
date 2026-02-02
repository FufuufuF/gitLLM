from __future__ import annotations

import datetime
from sqlalchemy import DateTime, ForeignKey, Index, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.db.models.base import MyORMBase


class Thread(MyORMBase):
    __tablename__ = "threads"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    chat_session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    parent_thread_id: Mapped[int | None] = mapped_column(ForeignKey("threads.id"))
    thread_type: Mapped[int] = mapped_column("type", SmallInteger, nullable=False)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    fork_from_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"))
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    closed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_threads_chat_session_id_created_at", "chat_session_id", "created_at"),
        Index("ix_threads_parent_thread_id_status", "parent_thread_id", "status"),
        Index("ix_threads_user_id_created_at", "user_id", "created_at"),
    )
