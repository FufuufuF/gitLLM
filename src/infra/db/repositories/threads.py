from sqlalchemy import select, update, func

from src.infra.db.repositories.base import BaseRepository
from src.infra.db.models.threads import Thread as ThreadModel
from src.infra.db.models.messages import Message as MessageModel
from src.domain.enums import ThreadStatus, ThreadType
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
        """创建主线线程。"""
        thread = Thread(
            user_id=user_id,
            chat_session_id=chat_session_id,
            thread_type=ThreadType.MAIN_LINE,
            status=ThreadStatus.NORMAL,
            title=title,
        )
        return await self.add(thread)

    async def create_fork_thread(
        self,
        user_id: int,
        chat_session_id: int,
        parent_thread_id: int,
        title: str | None = None,
        fork_from_message_id: int | None = None,
        thread_type: ThreadType = ThreadType.SUB_LINE,
        status: ThreadStatus = ThreadStatus.NORMAL,
    ) -> Thread:
        thread = Thread(
            user_id=user_id,
            chat_session_id=chat_session_id,
            parent_thread_id=parent_thread_id,
            thread_type=thread_type,
            status=status,
            title=title,
            fork_from_message_id=fork_from_message_id,
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

    async def update_status(self, thread_id: int, status: ThreadStatus) -> None:
        """更新线程状态"""
        stmt = (
            update(ThreadModel)
            .where(ThreadModel.id == thread_id)
            .values(status=status.value)
        )
        await self.session.execute(stmt)

    async def get_ancestor_chain(self, thread_id: int) -> list[Thread]:
        """
        获取从当前线程到主线的祖先链（含自身）。
        返回顺序：[当前线程, 父线程, 祖父线程, ..., 主线]
        """
        chain: list[Thread] = []
        current_id: int | None = thread_id
        visited: set[int] = set()

        while current_id is not None:
            if current_id in visited:
                break  # 防止循环引用
            visited.add(current_id)

            thread = await self.get(current_id)
            if thread is None:
                break
            chain.append(thread)
            current_id = thread.parent_thread_id

        return chain

    async def get_threads_by_session(self, chat_session_id: int) -> list[Thread]:
        """获取会话下的所有线程"""
        stmt = (
            select(ThreadModel)
            .where(ThreadModel.chat_session_id == chat_session_id)
            .order_by(ThreadModel.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return [self.to_entity(obj) for obj in result.scalars().all()]  # type: ignore

    async def get_thread_message_counts(
        self, chat_session_id: int
    ) -> dict[int, int]:
        """获取会话下每个线程的消息数量"""
        stmt = (
            select(
                MessageModel.thread_id,
                func.count(MessageModel.id).label("cnt"),
            )
            .where(MessageModel.chat_session_id == chat_session_id)
            .group_by(MessageModel.thread_id)
        )
        result = await self.session.execute(stmt)
        return {row.thread_id: row.cnt for row in result.all()}

    async def get_thread_children_counts(
        self, chat_session_id: int
    ) -> dict[int, int]:
        """获取会话下每个线程的直接子线程数量"""
        stmt = (
            select(
                ThreadModel.parent_thread_id,
                func.count(ThreadModel.id).label("cnt"),
            )
            .where(
                ThreadModel.chat_session_id == chat_session_id,
                ThreadModel.parent_thread_id.isnot(None),
            )
            .group_by(ThreadModel.parent_thread_id)
        )
        result = await self.session.execute(stmt)
        return {row.parent_thread_id: row.cnt for row in result.all()}
