from __future__ import annotations

import datetime
from sqlalchemy import DateTime, ForeignKey, Index, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.db.models.base import MyORMBase


class ChatSession(MyORMBase):
    __tablename__ = "chat_sessions"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    goal: Mapped[str | None] = mapped_column(Text)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_chat_sessions_user_id_created_at", "user_id", "created_at"),
    )
