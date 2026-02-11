from __future__ import annotations

from sqlalchemy import ForeignKey, Index, JSON, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.db.models.base import MyORMBase


class Message(MyORMBase):
    __tablename__ = "messages"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    chat_session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"), nullable=False)
    role: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")

    __table_args__ = (
        Index("ix_messages_thread_id_created_at", "thread_id", "created_at"),
        Index("ix_messages_chat_session_id_created_at", "chat_session_id", "created_at"),
        Index("ix_messages_user_id_created_at", "user_id", "created_at"),
    )
