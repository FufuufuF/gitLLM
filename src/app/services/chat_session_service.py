from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.db.repositories.chat_sessions import SessionRepository
from src.domain.models import ChatSession


class SessionService:
    """会话服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_repo = SessionRepository(db)

    async def list_sessions(
        self,
        user_id: int,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """
        获取用户的会话列表（游标分页）。

        Returns:
            dict: {
                "items": list[ChatSession],
                "next_cursor": str | None,
                "has_more": bool
            }
        """
        items, next_cursor, has_more = await self.session_repo.list_sessions_cursor(
            user_id, cursor, limit
        )

        return {
            "items": items,
            "next_cursor": next_cursor,
            "has_more": has_more
        }