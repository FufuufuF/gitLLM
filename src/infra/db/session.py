from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infra.db.engine import engine

logger = logging.getLogger(__name__)


SessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)

# session_factory 的类型别名
SessionFactory = Callable[[], AsyncSession]


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: provides an AsyncSession.

    Notes:
    - Auto-commit on success to ensure data persistence.
    - Rollback on exceptions to keep connections clean.
    """

    async with SessionLocal() as session:
        try:
            yield session
            if session.is_active:
                await session.commit()
        except BaseException:
            try:
                if session.is_active or session.in_transaction():
                    await session.rollback()
            except Exception:
                logger.debug("Session cleanup failed (likely due to cancellation), ignoring")
            raise


def get_session_factory() -> SessionFactory:
    """FastAPI dependency: provides a session factory for creating independent sessions.

    Used in scenarios where a new session is needed outside the request lifecycle,
    e.g., saving partial messages on stream cancellation.
    """
    return SessionLocal
