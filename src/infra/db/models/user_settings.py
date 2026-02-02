from __future__ import annotations

import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.db.models.base import MyORMBase


class UserSetting(MyORMBase):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    auto_suggest_branch: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("1"),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
