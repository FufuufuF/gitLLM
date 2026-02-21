from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from src.infra.db.repositories.chat_sessions import ChatSessionRepository
from src.infra.db.repositories.threads import ThreadRepository
from src.domain.models import ChatSession, ChatSessionListResult, Thread


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
            chat_session_id=created_session.id,  # type: ignore
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

    async def update_session(
        self,
        user_id: int,
        chat_session_id: int,
        active_thread_id: int | None = None,
        title: str | None = None,
    ) -> tuple[ChatSession, Thread]:
        """
        更新会话（切换活跃线程 / 更新标题）。

        Returns:
            (updated_session, active_thread)
        """
        session = await self.session_repo.get(chat_session_id)
        if session is None:
            raise NotFoundException("Chat session not found")
        if session.user_id != user_id:
            raise ForbiddenException("No permission to access this session")

        # 如果要切换线程，校验目标线程属于该会话
        if active_thread_id is not None:
            target_thread = await self.thread_repo.get(active_thread_id)
            if target_thread is None:
                raise NotFoundException("Target thread not found")
            if target_thread.chat_session_id != chat_session_id:
                raise BadRequestException("Thread does not belong to this session")

        updated = await self.session_repo.update_session(
            chat_session_id=chat_session_id,
            active_thread_id=active_thread_id,
            title=title,
        )
        if updated is None:
            raise NotFoundException("Session not found after update")

        # 查询活跃线程信息
        thread = await self.thread_repo.get(updated.active_thread_id)  # type: ignore
        if thread is None:
            raise NotFoundException("Active thread not found")

        return updated, thread

    async def get_thread_tree(
        self,
        user_id: int,
        chat_session_id: int,
    ) -> tuple[int, int, list[dict]]:
        """
        获取会话的线程树结构。

        Returns:
            (chat_session_id, active_thread_id, thread_nodes)
        """
        session = await self.session_repo.get(chat_session_id)
        if session is None:
            raise NotFoundException("Chat session not found")
        if session.user_id != user_id:
            raise ForbiddenException("No permission to access this session")

        threads = await self.thread_repo.get_threads_by_session(chat_session_id)
        msg_counts = await self.thread_repo.get_thread_message_counts(chat_session_id)
        children_counts = await self.thread_repo.get_thread_children_counts(chat_session_id)

        nodes = []
        for t in threads:
            nodes.append({
                "thread_id": t.id,
                "parent_thread_id": t.parent_thread_id,
                "title": t.title,
                "thread_type": t.thread_type,
                "status": t.status,
                "fork_from_message_id": t.fork_from_message_id,
                "created_at": t.created_at,
                "closed_at": t.closed_at,
                "message_count": msg_counts.get(t.id, 0),  # type: ignore
                "children_count": children_counts.get(t.id, 0),  # type: ignore
            })

        return chat_session_id, session.active_thread_id, nodes  # type: ignore

    async def get_breadcrumb(
        self,
        user_id: int,
        thread_id: int,
    ) -> list[Thread]:
        """
        获取面包屑导航（从当前线程到主线的祖先链）。

        Returns:
            list[Thread] — 顺序: [主线, ..., 父线程, 当前线程]
        """
        chain = await self.thread_repo.get_ancestor_chain(thread_id)
        if not chain:
            raise NotFoundException("Thread not found")

        # 校验权限
        if chain[0].user_id != user_id:
            raise ForbiddenException("No permission to access this thread")

        # 反转：从主线到当前线程
        chain.reverse()
        return chain