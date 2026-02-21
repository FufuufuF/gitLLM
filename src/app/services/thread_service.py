from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from src.domain.enums import ThreadStatus, ThreadType
from src.domain.models import BranchOp, Thread
from src.app.services.checkpoint_service import CheckpointService
from src.infra.db.repositories.chat_sessions import ChatSessionRepository
from src.infra.db.repositories.branch_ops import BranchOpRepository
from src.infra.db.repositories.messages import MessageRepository
from src.infra.db.repositories.threads import ThreadRepository


class ThreadService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.session_repo = ChatSessionRepository(db)
        self.thread_repo = ThreadRepository(db)
        self.message_repo = MessageRepository(db)
        self.branch_op_repo = BranchOpRepository(db)
        self.checkpoint_service = CheckpointService()

    async def get_threads(self, user_id: int, chat_session_id: int) -> list[Thread]:
        session = await self.session_repo.get(chat_session_id)
        if session is None:
            raise NotFoundException("Chat session not found")
        if session.user_id != user_id:
            raise ForbiddenException("No permission to access this session")
        return await self.thread_repo.get_threads_by_session(chat_session_id)

    async def fork_thread(
        self,
        user_id: int,
        chat_session_id: int,
        parent_thread_id: int,
        title: str | None = None,
    ) -> Thread:
        session = await self.session_repo.get(chat_session_id)
        if session is None:
            raise NotFoundException("Chat session not found")
        if session.user_id != user_id:
            raise ForbiddenException("No permission to access this session")

        parent_thread = await self.thread_repo.get(parent_thread_id)
        if parent_thread is None:
            raise NotFoundException("Parent thread not found")
        if parent_thread.user_id != user_id or parent_thread.chat_session_id != chat_session_id:
            raise ForbiddenException("Parent thread does not belong to this session")
        if parent_thread.status != ThreadStatus.NORMAL:
            raise BadRequestException("Parent thread is not active")

        fork_from_message_id = await self.message_repo.get_latest_message_id(
            user_id=user_id,
            chat_session_id=chat_session_id,
            thread_id=parent_thread_id,
        )
        if fork_from_message_id is None:
            raise BadRequestException("Parent thread has no messages to fork from")

        await self.checkpoint_service.flush_checkpoint(parent_thread_id)
        parent_state = await self.checkpoint_service.get_latest_state(parent_thread_id)

        new_thread = await self.thread_repo.create_fork_thread(
            user_id=user_id,
            chat_session_id=chat_session_id,
            parent_thread_id=parent_thread_id,
            title=title,
            fork_from_message_id=fork_from_message_id,
            thread_type=ThreadType.SUB_LINE,
            status=ThreadStatus.NORMAL,
        )

        await self.checkpoint_service.create_checkpoint_from_state(
            new_thread_id=new_thread.id,  # type: ignore[arg-type]
            source_state=parent_state,
        )

        await self.branch_op_repo.add(
            BranchOp(
                user_id=user_id,
                chat_session_id=chat_session_id,
                op_type=1,
                thread_id=new_thread.id,  # type: ignore[arg-type]
                related_thread_id=parent_thread_id,
                message_id=fork_from_message_id,
                metadata_=None,
            )
        )

        await self.session_repo.update_active_thread(
            chat_session_id=chat_session_id,
            thread_id=new_thread.id,  # type: ignore[arg-type]
        )

        return new_thread
