from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.db.session import get_db_session


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session

async def get_current_user_id() -> int:
    return 1
