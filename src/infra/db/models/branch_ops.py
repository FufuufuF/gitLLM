from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, JSON, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.db.models.base import MyORMBase


class BranchOp(MyORMBase):
    __tablename__ = "branch_ops"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    chat_session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    op_type: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"), nullable=False)
    related_thread_id: Mapped[int | None] = mapped_column(ForeignKey("threads.id"))
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON)

    __table_args__ = (
        CheckConstraint("related_thread_id IS NULL OR thread_id <> related_thread_id"),
        Index("ix_branch_ops_chat_session_id_created_at", "chat_session_id", "created_at"),
        Index("ix_branch_ops_thread_id_created_at", "thread_id", "created_at"),
        Index("ix_branch_ops_related_thread_id_created_at", "related_thread_id", "created_at"),
        Index("ix_branch_ops_user_id_created_at", "user_id", "created_at"),
    )
