from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundException
from src.domain.models import Message
from src.infra.db.repositories.messages import MessageRepository
from src.infra.db.repositories.threads import ThreadRepository


class MessageService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.message_repo = MessageRepository(db_session)
        self.thread_repo = ThreadRepository(db_session)

    async def get_messages(
        self,
        user_id: int,
        chat_session_id: int,
        thread_id: int,
    ) -> list[Message | None]:
        messages = await self.message_repo.get_messages(
            user_id,
            chat_session_id,
            thread_id,
        )
        return messages

    async def get_context_messages(
        self,
        thread_id: int,
        direction: str = "before",
        cursor: str | None = None,
        limit: int = 20,
    ) -> tuple[list[Message], str | None, bool]:
        """
        获取跨线程的上下文消息。

        按祖先链聚合：当前线程的全部消息 + 父线程 fork 点之前的消息 + ...
        一直追溯到主线。

        Returns:
            (messages, next_cursor, has_more)
        """
        # 1. 沿祖先链收集线程及其上界
        ancestor_chain = await self.thread_repo.get_ancestor_chain(thread_id)
        if not ancestor_chain:
            raise NotFoundException("Thread not found")

        # 构建 (thread_id, upper_bound_message_id) 列表
        # 当前线程：无上界（取全部）
        # 父线程：上界 = 子线程的 fork_from_message_id
        # 祖父线程：上界 = 父线程的 fork_from_message_id
        # ...
        thread_ids_with_bounds: list[tuple[int, int | None]] = []

        for i, t in enumerate(ancestor_chain):
            if i == 0:
                # 当前线程：无上界
                thread_ids_with_bounds.append((t.id, None))  # type: ignore
            else:
                # 父/祖先线程：上界 = 子线程的 fork_from_message_id
                child = ancestor_chain[i - 1]
                thread_ids_with_bounds.append(
                    (t.id, child.fork_from_message_id)  # type: ignore
                )

        # 2. 查询
        cursor_int = int(cursor) if cursor else None
        messages, next_cursor, has_more = await self.message_repo.get_context_messages(
            thread_ids_with_bounds=thread_ids_with_bounds,
            direction=direction,
            cursor=cursor_int,
            limit=limit,
        )

        return messages, next_cursor, has_more
        
        
