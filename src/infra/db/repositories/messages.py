from sqlalchemy import select, and_, or_

from src.infra.db.repositories.base import BaseRepository
from src.domain.models import Message
from src.infra.db.models.messages import Message as MessageModel
from src.domain.models import Message

class MessageRepository(BaseRepository[MessageModel, Message]):
    model = MessageModel
    schema_class = Message

    async def get_messages(
        self,
        user_id: int,
        chat_session_id: int,
        thread_id: int,
    ) -> list[Message | None]:
        stmt = self.list_stmt().where(
            MessageModel.user_id == user_id,
            MessageModel.chat_session_id == chat_session_id,
            MessageModel.thread_id == thread_id,
        ).order_by(MessageModel.created_at.asc())
        result = await self.session.execute(stmt)
        return [self.to_entity(obj) for obj in result.scalars().all()]

    async def get_latest_message_id(
        self,
        user_id: int,
        chat_session_id: int,
        thread_id: int,
    ) -> int | None:
        stmt = (
            select(MessageModel.id)
            .where(
                MessageModel.user_id == user_id,
                MessageModel.chat_session_id == chat_session_id,
                MessageModel.thread_id == thread_id,
            )
            .order_by(MessageModel.created_at.desc(), MessageModel.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_context_messages(
        self,
        thread_ids_with_bounds: list[tuple[int, int | None]],
        direction: str = "before",
        cursor: int | None = None,
        limit: int = 20,
    ) -> tuple[list[Message], str | None, bool]:
        """
        聚合上下文消息：跨祖先链的多个线程。

        Args:
            thread_ids_with_bounds: [(thread_id, fork_from_message_id), ...]
                按 [当前线程, 父线程, 祖父线程, ...] 排列。
                fork_from_message_id 表示该线程在父线程中的分叉点消息 ID，
                当前线程自身传 None（无上界约束）。
            direction: "before" 向前（最新→旧），"after" 向后（旧→最新）
            cursor: 游标消息 ID
            limit: 每页数量

        Returns:
            (messages, next_cursor, has_more)
        """
        if not thread_ids_with_bounds:
            return [], None, False

        # 构建 OR 条件：对每个线程，取 <= fork_from_message_id 的消息
        conditions = []
        for thread_id, upper_bound_msg_id in thread_ids_with_bounds:
            thread_cond = MessageModel.thread_id == thread_id
            if upper_bound_msg_id is not None:
                # 父/祖先线程：只取 fork 点及之前的消息
                thread_cond = and_(thread_cond, MessageModel.id <= upper_bound_msg_id)
            conditions.append(thread_cond)

        stmt = select(MessageModel).where(or_(*conditions))

        # 游标过滤
        if cursor is not None:
            if direction == "before":
                stmt = stmt.where(MessageModel.id < cursor)
            else:
                stmt = stmt.where(MessageModel.id > cursor)

        # 排序
        if direction == "before":
            stmt = stmt.order_by(MessageModel.id.desc())
        else:
            stmt = stmt.order_by(MessageModel.id.asc())

        stmt = stmt.limit(limit + 1)

        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        items = rows[:limit]

        # 统一按 id 升序返回，方便前端渲染
        items.sort(key=lambda m: m.id)

        messages = [self.to_entity(obj) for obj in items]  # type: ignore

        next_cursor: str | None = None
        if has_more and rows:
            # 游标指向本页最后一条（按原始排序方向）
            last_item = rows[limit - 1]
            next_cursor = str(last_item.id)

        return messages, next_cursor, has_more

    async def get_messages_after_fork(
        self,
        thread_id: int,
        fork_from_message_id: int | None,
    ) -> list[Message]:
        """
        获取某个线程在 fork 点之后的所有消息（用于生成合并简报）。
        如果 fork_from_message_id 为 None，返回该线程的所有消息。
        """
        stmt = select(MessageModel).where(
            MessageModel.thread_id == thread_id,
        )
        if fork_from_message_id is not None:
            stmt = stmt.where(MessageModel.id > fork_from_message_id)
        stmt = stmt.order_by(MessageModel.created_at.asc())

        result = await self.session.execute(stmt)
        return [self.to_entity(obj) for obj in result.scalars().all()]  # type: ignore

    async def create_message(self, message: Message) -> Message:
        """创建消息"""
        return await self.add(message)

    