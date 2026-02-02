from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.core.config import db_setting as settings


def get_database_url() -> str:
    url = settings.database_url.strip()
    return url


engine: AsyncEngine = create_async_engine(
    get_database_url(),
    pool_pre_ping=True,
)
