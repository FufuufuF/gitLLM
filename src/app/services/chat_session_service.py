from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.db.repositories.chat_sessions import ChatSessionRepository
from src.infra.db.repositories.threads import ThreadRepository
from src.domain.models import ChatSession, ChatSessionListResult


class ChatSessionService:
    """会话服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_repo = ChatSessionRepository(db)
        self.thread_repo = ThreadRepository(db)

    async def create_session(
        self,
        user_id: int,
        title: str | None = None,
        goal: str | None = None,
    ) -> ChatSession:
        """
        创建新会话，同时自动创建主线线程并关联。

        流程：
        1. 创建 ChatSession 行
        2. 创建对应的主线 Thread 行
        3. 将 Thread.id 回写到 ChatSession.active_thread_id

        Returns:
            ChatSession: 已关联主线线程的会话实体
        """
        # 1. 创建会话
        session_entity = ChatSession(
            user_id=user_id,
            title=title,
            goal=goal,
            status=1,
        )
        created_session = await self.session_repo.add(session_entity)

        # 2. 创建主线线程
        mainline_thread = await self.thread_repo.create_mainline_thread(
            user_id=user_id,
            chat_session_id=created_session.id,  # type: ignore
            title=title,
        )

        # 3. 回写 active_thread_id
        await self.session_repo.update_active_thread(
            session_id=created_session.id,  # type: ignore
            thread_id=mainline_thread.id,   # type: ignore
        )
        created_session.active_thread_id = mainline_thread.id

        return created_session

    async def list_sessions(
        self,
        user_id: int,
        cursor: str | None = None,
        limit: int = 20,
    ) -> ChatSessionListResult:
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

        return ChatSessionListResult(
            items=items,
            next_cursor=next_cursor,
            has_more=has_more,
        )