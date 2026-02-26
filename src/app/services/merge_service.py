from __future__ import annotations

from pathlib import Path

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config.model_config import model_setting
from src.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from src.domain.enums import MessageRole, MessageType, ThreadStatus, ThreadType
from src.domain.models import BranchOp, Message, Thread
from src.app.services.checkpoint_service import CheckpointService
from src.infra.db.repositories.branch_ops import BranchOpRepository
from src.infra.db.repositories.chat_sessions import ChatSessionRepository
from src.infra.db.repositories.messages import MessageRepository
from src.infra.db.repositories.threads import ThreadRepository
from src.infra.checkpoint.postgres import get_postgres_saver
from src.graph.graphs.chat_graph import create_chat_graph
from src.llm.factory import get_model


# 简报生成 prompt
_BRIEF_PROMPT_PATH = Path(__file__).resolve().parents[2] / "llm" / "prompts" / "brief.md"


def _load_brief_prompt() -> str:
    try:
        return _BRIEF_PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError("Brief prompt not found")


class MergeService:
    """分支合并服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.session_repo = ChatSessionRepository(db)
        self.thread_repo = ThreadRepository(db)
        self.message_repo = MessageRepository(db)
        self.branch_op_repo = BranchOpRepository(db)
        self.checkpoint_service = CheckpointService()

    # ── 公共校验 ──

    async def _validate_merge_preconditions(
        self, user_id: int, thread_id: int
    ) -> tuple[Thread, Thread]:
        """
        校验合并前置条件，返回 (子线程, 父线程)。

        校验项：
        1. 线程存在
        2. 权限
        3. 非主线线程（主线不可被合并）
        4. 线程状态为 NORMAL（未被合并过）
        5. 父线程存在且状态正常
        6. 逐级合并约束：子线程下面不能有未合并的子线程
        """
        thread = await self.thread_repo.get(thread_id)
        if thread is None:
            raise NotFoundException("Thread not found")
        if thread.user_id != user_id:
            raise ForbiddenException("No permission to access this thread")
        if thread.thread_type == ThreadType.MAIN_LINE:
            raise BadRequestException("Cannot merge the mainline thread")
        if thread.status != ThreadStatus.NORMAL:
            raise BadRequestException("Thread is already merged or closed")
        if thread.parent_thread_id is None:
            raise BadRequestException("Thread has no parent to merge into")

        parent_thread = await self.thread_repo.get(thread.parent_thread_id)
        if parent_thread is None:
            raise NotFoundException("Parent thread not found")
        if parent_thread.status != ThreadStatus.NORMAL:
            raise BadRequestException("Parent thread is not active")

        # 逐级合并约束：检查子线程下是否有未合并的子分支
        all_threads = await self.thread_repo.get_threads_by_session(thread.chat_session_id)
        for t in all_threads:
            if (
                t.parent_thread_id == thread_id
                and t.status == ThreadStatus.NORMAL
            ):
                raise BadRequestException(
                    f"Thread has unmerged sub-branch '{t.title or t.id}'. "
                    "Please merge all sub-branches first (逐级合并约束)."
                )

        return thread, parent_thread

    # ── Preview ──

    async def preview(self, user_id: int, thread_id: int) -> tuple[int, int, str]:
        """
        生成合并简报预览（不修改任何状态）。

        Returns:
            (thread_id, target_thread_id, brief_content)
        """
        thread, parent_thread = await self._validate_merge_preconditions(user_id, thread_id)

        # 获取分支 fork 点之后的消息
        branch_messages = await self.message_repo.get_messages_after_fork(
            thread_id=thread_id,
            fork_from_message_id=thread.fork_from_message_id,
        )

        if not branch_messages:
            brief_content = "该分支没有新的对话内容。"
        else:
            brief_content = await self._generate_brief(branch_messages)

        return (
            thread.id,  # type: ignore
            parent_thread.id,  # type: ignore
            brief_content,
        )

    # ── Confirm ──

    async def confirm(
        self, user_id: int, thread_id: int, brief_content: str
    ) -> tuple[Thread, Thread, Message]:
        """
        确认合并（事务性操作）。

        步骤：
        1. 重新校验线程状态
        2. 在父线程创建 BRIEF 消息
        3. 更新子线程状态 → MERGED
        4. 记录 merge 操作
        5. 更新 session.active_thread_id → 父线程
        6. 向父线程 checkpoint 注入简报
        7. 归档子线程 checkpoint（可选，暂跳过）

        Returns:
            (merged_thread, target_thread, brief_message)
        """
        thread, parent_thread = await self._validate_merge_preconditions(user_id, thread_id)

        # Step 2: 在父线程创建 BRIEF 类型消息
        brief_message = Message(
            user_id=user_id,
            chat_session_id=thread.chat_session_id,
            thread_id=parent_thread.id,  # type: ignore
            role=MessageRole.SYSTEM,
            type=MessageType.BRIEF,
            content=brief_content,
        )
        saved_brief = await self.message_repo.create_message(brief_message)

        # Step 3: 更新子线程状态 → MERGED
        await self.thread_repo.update_status(thread_id, ThreadStatus.MERGED)

        # Step 4: 记录 merge 操作
        await self.branch_op_repo.add(
            BranchOp(
                user_id=user_id,
                chat_session_id=thread.chat_session_id,
                op_type=2,  # MERGE
                thread_id=thread_id,
                related_thread_id=parent_thread.id,  # type: ignore
                message_id=saved_brief.id,  # type: ignore
                metadata_=None,
            )
        )

        # Step 5: 更新 session.active_thread_id → 父线程
        await self.session_repo.update_active_thread(
            chat_session_id=thread.chat_session_id,
            thread_id=parent_thread.id,  # type: ignore
        )

        await self.db.flush()

        # Step 6: 向父线程 checkpoint 注入简报（事务外）
        try:
            await self._inject_brief_to_checkpoint(
                parent_thread_id=parent_thread.id,  # type: ignore
                brief_content=brief_content,
            )
        except Exception:
            # checkpoint 注入失败不阻塞业务，由补偿机制处理
            pass

        # 重新查询最新状态
        merged_thread = await self.thread_repo.get(thread_id)
        target_thread = await self.thread_repo.get(parent_thread.id)  # type: ignore

        return merged_thread, target_thread, saved_brief  # type: ignore

    # ── 内部方法 ──

    async def _generate_brief(self, messages: list[Message]) -> str:
        """调用 LLM 生成学习简报"""

        system_prompt = _load_brief_prompt()

        # 拼接对话历史
        conversation = "\n".join(
            f"{'User' if m.role == MessageRole.USER else 'Assistant'}: {m.content}"
            for m in messages
            if m.role in (MessageRole.USER, MessageRole.ASSISTANT)
        )

        prompt = f"{system_prompt}\n\n---\n\n{conversation}\n\n---\n\nPlease generate the brief:"

        try:
            model = get_model({
                "provider": model_setting.QWEN_MODEL_PROVIDER or "tongyi",
                "api_key": model_setting.QWEN_MODEL_API_KEY,
                "model_name": model_setting.QWEN_MODEL_NAME,
                "base_url": model_setting.QWEN_MODEL_BASE_URL,
            })
            result = await model.ainvoke(prompt)
            return str(result.content)
        except Exception as e:
            # 如果 LLM 调用失败，返回一个基础简报
            return f"（简报生成失败：{str(e)}）\n\n对话包含 {len(messages)} 条消息。"

    async def _inject_brief_to_checkpoint(
        self, parent_thread_id: int, brief_content: str
    ) -> None:
        """向父线程的 checkpoint 注入简报 SystemMessage"""
        async with get_postgres_saver() as saver:
            graph = create_chat_graph(postgres_saver=saver)
            config = RunnableConfig(
                {"configurable": {"thread_id": str(parent_thread_id)}}
            )
            await graph.aupdate_state(
                config,
                {"messages": [SystemMessage(content=brief_content)]},
            )
