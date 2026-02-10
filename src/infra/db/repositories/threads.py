from sqlalchemy import select, update

from src.infra.db.repositories.base import BaseRepository
from src.infra.db.models.threads import Thread as ThreadModel
from src.domain.models import Thread


class ThreadRepository(BaseRepository[ThreadModel, Thread]):
    """线程仓储"""
    model = ThreadModel
    schema_class = Thread

    async def create_mainline_thread(
        self,
        user_id: int,
        chat_session_id: int,
        title: str | None = None,
    ) -> Thread:
        """
        创建主线线程。

        Args:
            user_id: 用户ID
            chat_session_id: 会话ID
            title: 线程标题（可选）

        Returns:
            Thread: 创建的线程实体
        """
        thread = Thread(
            user_id=user_id,
            chat_session_id=chat_session_id,
            thread_type=1,  # MAINLINE
            status=1,       # ACTIVE
            title=title,
        )
        return await self.add(thread)

    async def get_mainline_by_session(self, chat_session_id: int) -> Thread | None:
        """获取会话的主线线程"""
        stmt = select(ThreadModel).where(
            ThreadModel.chat_session_id == chat_session_id,
            ThreadModel.thread_type == 1,  # MAINLINE
        )
        result = await self.session.execute(stmt)
        return self.to_entity(result.scalar_one_or_none())
