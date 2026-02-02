from __future__ import annotations

import datetime
from sqlalchemy import DateTime, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.db.models.base import MyORMBase


class User(MyORMBase):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
