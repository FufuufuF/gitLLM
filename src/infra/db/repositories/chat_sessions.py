import base64
from datetime import datetime
from sqlalchemy import select, or_, and_

from src.infra.db.repositories.base import BaseRepository
from src.infra.db.models.chat_sessions import ChatSession as ChatSessionModel
from src.domain.models import ChatSession


class SessionRepository(BaseRepository[ChatSessionModel, ChatSession]):
    """会话仓储"""
    model = ChatSessionModel
    schema_class = ChatSession

    async def list_sessions_cursor(
        self,
        user_id: int,
        cursor: str | None,
        limit: int = 20
    ) -> tuple[list[ChatSession], str | None, bool]:
        """
        游标分页查询。

        排序规则：updated_at DESC, id DESC
        游标构成：base64(timestamp|id)

        Returns:
            tuple: (items, next_cursor, has_more)
        """
        query = select(ChatSessionModel).where(
            ChatSessionModel.user_id == user_id,
            ChatSessionModel.deleted_at.is_(None)
        )

        # 1. 解析游标
        if cursor:
            try:
                decoded = base64.urlsafe_b64decode(cursor).decode('utf-8')
                timestamp_str, id_str = decoded.split('|')
                cursor_ts = datetime.fromisoformat(timestamp_str)
                cursor_id = int(id_str)

                # 构建游标过滤条件: (updated_at < ts) OR (updated_at == ts AND id < id)
                query = query.where(
                    or_(
                        ChatSessionModel.updated_at < cursor_ts,
                        and_(
                            ChatSessionModel.updated_at == cursor_ts,
                            ChatSessionModel.id < cursor_id
                        )
                    )
                )
            except Exception:
                # 游标无效时忽略，从头开始
                pass

        # 2. 排序与限制
        query = query.order_by(
            ChatSessionModel.updated_at.desc(),
            ChatSessionModel.id.desc()
        ).limit(limit + 1)  # 多查一条用于判断 has_more

        # 3. 执行查询
        result = await self.session.execute(query)
        rows = list(result.scalars().all())

        # 4. 处理分页结果
        has_more = len(rows) > limit
        items = rows[:limit]

        next_cursor = None
        if has_more and items:
            last_item = items[-1]
            # 生成新游标: base64(timestamp|id)
            ts_str = last_item.updated_at.isoformat()
            cursor_str = f"{ts_str}|{last_item.id}"
            next_cursor = base64.urlsafe_b64encode(cursor_str.encode('utf-8')).decode('utf-8')

        return [self.to_entity(row) for row in items], next_cursor, has_more # type: ignore