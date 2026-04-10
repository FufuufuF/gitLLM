import asyncio
import logging
from typing import AsyncGenerator
from langchain.messages import AIMessage, HumanMessage
from langgraph.graph.state import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from src.api.schemas.messages import MessageOut
from src.infra.db.repositories.messages import MessageRepository
from src.infra.db.repositories.model_config import ModelConfigRepository
from src.infra.db.repositories.chat_sessions import ChatSessionRepository
from src.infra.db.repositories.threads import ThreadRepository
from src.infra.checkpoint.postgres import get_postgres_saver
from src.infra.db.session import SessionFactory
from src.domain.models import Message, ModelConfig, ChatSession, Thread
from src.domain.enums import MessageRole, MessageStatus, MessageType, ThreadStatus
from src.graph.graphs.chat_graph import create_chat_graph
from src.app.services.session_title_service import SessionTitleService
from src.core.exceptions import AppException, ExternalServiceException, InternalServerException, BadRequestException
from src.core.config.model_config import model_setting
from src.api.schemas.chat import (
    StreamEventType,
    StreamToken,
    StreamHumanMessageCreated,
    StreamChatSessionUpdated,
    StreamAIMessageCreated,
)

logger = logging.getLogger(__name__)


def _classify_llm_error(e: Exception) -> tuple[str, str]:
    """根据 LLM 提供商异常推断错误类型和用户友好消息。

    Returns:
        (error_type, user_message)
    """
    # 优先通过 openai SDK 异常类型判断
    try:
        from openai import RateLimitError, AuthenticationError, APITimeoutError, APIConnectionError
        if isinstance(e, RateLimitError):
            return "quota_exceeded", "API 额度已耗尽或请求频率过高，请稍后再试"
        if isinstance(e, AuthenticationError):
            return "auth_error", "API Key 无效或已过期，请检查模型配置"
        if isinstance(e, APITimeoutError):
            return "timeout", "LLM 服务响应超时，请稍后再试"
        if isinstance(e, APIConnectionError):
            return "connection_error", "无法连接 LLM 服务，请检查网络或服务地址"
    except ImportError:
        pass

    # 兜底：基于错误信息关键词匹配
    msg = str(e).lower()
    if any(kw in msg for kw in ("rate limit", "quota", "429", "insufficient_quota")):
        return "quota_exceeded", "API 额度已耗尽或请求频率过高，请稍后再试"
    if any(kw in msg for kw in ("authentication", "api key", "401", "unauthorized")):
        return "auth_error", "API Key 无效或已过期，请检查模型配置"
    if "timeout" in msg:
        return "timeout", "LLM 服务响应超时，请稍后再试"
    if any(kw in msg for kw in ("connection", "connect")):
        return "connection_error", "无法连接 LLM 服务，请检查网络或服务地址"

    return "llm_error", "LLM 服务异常，请稍后再试"


class ChatService:
    # 持有后台任务的强引用，防止 GC 在任务完成前将其回收
    _background_tasks: set[asyncio.Task] = set()

    def __init__(
        self,
        db_session: AsyncSession,
        session_factory: SessionFactory | None = None,
    ):
        self.db_session = db_session
        self.session_factory = session_factory
        self.message_repo = MessageRepository(db_session)
        self.model_config_repo = ModelConfigRepository(db_session)
        self.session_repo = ChatSessionRepository(db_session)
        self.thread_repo = ThreadRepository(db_session)

    @classmethod
    def _fire_and_forget(cls, coro) -> None:
        """创建后台任务并持有强引用，任务完成后自动从 set 中移除。"""
        task = asyncio.create_task(coro)
        cls._background_tasks.add(task)
        task.add_done_callback(cls._background_tasks.discard)

    async def get_model_config(self, model_config_id: int) -> ModelConfig:
        # MOCK
        model_config = ModelConfig(
            id=1,
            model_name=model_setting.QWEN_MODEL_NAME,
            api_key=model_setting.QWEN_MODEL_API_KEY,
            provider=model_setting.QWEN_MODEL_PROVIDER if model_setting.QWEN_MODEL_PROVIDER else "Tongyi",
            base_url=model_setting.QWEN_MODEL_BASE_URL,
            user_id=1
        )
        return model_config
        model_config = await self.model_config_repo.get(model_config_id)
        if not model_config:
            raise InternalServerException(f"Model config with id {model_config_id} not found")
        return model_config


    async def _save_message(self, message: Message) -> Message:
        """Save message to DB."""
        saved = await self.message_repo.add(message)
        if saved is None:
            raise InternalServerException("Failed to save message to database")
        return saved


    async def _commit_session(self) -> None:
        """Commit current transaction; rollback on failure to keep session clean."""
        try:
            await self.db_session.commit()
        except BaseException:
            await self.db_session.rollback()
            raise

    async def _save_and_commit(self, message: Message) -> Message:
        """Save message and commit in one operation (suitable for asyncio.shield)."""
        saved = await self._save_message(message)
        await self._commit_session()
        return saved

    async def _save_message_detached(self, message: Message) -> None:
        """使用独立 session 保存消息，不受请求级 session 生命周期影响。

        用于取消/错误场景，此时请求级 session 可能已被破坏。
        """
        if self.session_factory is None:
            logger.warning("session_factory not provided, cannot save detached message")
            return
        async with self.session_factory() as session:
            repo = MessageRepository(session)
            await repo.add(message)
            await session.commit()

    async def _invoke_llm(self, content: str, thread_id: int, model_config: ModelConfig) -> str:
        """Invoke LLM."""
        
        # Prepare input and config
        graph_input = {
            "messages": [HumanMessage(content=content)],
        }
        run_config = RunnableConfig({
            "configurable": {
                "thread_id": str(thread_id),
                "model_name": model_config.model_name,
                "api_key": model_config.api_key,
                "provider": model_config.provider,
                "base_url": model_config.base_url,
            }
        })

        try:
            async with get_postgres_saver() as saver:
                agent = create_chat_graph(postgres_saver=saver)
                
                result = await agent.ainvoke(graph_input, run_config)
            
            response_message: AIMessage = result["messages"][-1]
            return str(response_message.content)
        
        except AppException:
            raise
        except Exception as e:
            error_type, user_msg = _classify_llm_error(e)
            logger.error("LLM invocation failed [%s]: %s", error_type, e, exc_info=True)
            raise ExternalServiceException(
                message=user_msg,
                code=5001,
                details={"error_type": error_type},
            ) from None
            
    
    async def _invoke_llm_stream(self, content: str, thread_id: int, model_config: ModelConfig) -> AsyncGenerator[str, None]:
        """Invoke LLM with streaming output."""
        # Prepare input and config
        graph_input = {
            "messages": [HumanMessage(content=content)],
        }
        run_config = RunnableConfig({
            "configurable": {
                "thread_id": str(thread_id),
                "model_name": model_config.model_name,
                "api_key": model_config.api_key,
                "provider": model_config.provider,
                "base_url": model_config.base_url,
            }
        })

        try:
            async with get_postgres_saver() as saver:
                agent = create_chat_graph(postgres_saver=saver)

                async for event in agent.astream_events(
                    graph_input, 
                    run_config, 
                    version="v2",
                    include_types=["chat_model"]
                ):
                    if event.get("event") != "on_chat_model_stream":
                        continue

                    chunk = event.get("data", {}).get("chunk")
                    chunk_content = getattr(chunk, "content", None)
                    if not chunk_content:
                        continue

                    if isinstance(chunk_content, str):
                        yield chunk_content
                    elif isinstance(chunk_content, list):
                        for item in chunk_content:
                            text = getattr(item, "text", None)
                            if text:
                                yield str(text)
                    else:
                        yield str(chunk_content)
        
        except AppException:
            raise
        except Exception as e:
            error_type, user_msg = _classify_llm_error(e)
            logger.error("LLM stream failed [%s]: %s", error_type, e, exc_info=True)
            raise ExternalServiceException(
                message=user_msg,
                code=5001,
                details={"error_type": error_type},
            ) from None

    async def _create_new_session_and_thread(
        self,
        user_id: int,
        title: str | None = None,
    ) -> tuple[int, int]:
        """
        创建新的会话和主线线程。

        Args:
            user_id: 用户ID
            title: 会话标题（可选）

        Returns:
            tuple[int, int]: (chat_session_id, thread_id)
        """
        # 1. 创建 ChatSession（active_thread_id 暂为 None）
        new_session = ChatSession(
            user_id=user_id,
            title=title,
            status=1,
        )
        created_session = await self.session_repo.add(new_session)
        if created_session is None or created_session.id is None:
            raise InternalServerException("Failed to create chat session")
        
        chat_session_id = created_session.id

        # 2. 创建主线 Thread
        new_thread = await self.thread_repo.create_mainline_thread(
            user_id=user_id,
            chat_session_id=chat_session_id,
            title=title,
        )
        if new_thread is None or new_thread.id is None:
            raise InternalServerException("Failed to create thread")
        
        thread_id = new_thread.id

        # 3. 更新 session 的 active_thread_id
        await self.session_repo.update_active_thread(chat_session_id, thread_id)

        return chat_session_id, thread_id

    async def _generate_new_session_title(self, first_user_message: str) -> str | None:
        """为新会话生成标题（失败时返回兜底标题）。"""
        session_title_service = SessionTitleService()
        try:
            model_config = await self.get_model_config(1)
            return await session_title_service.generate_title(
                first_user_message=first_user_message,
                model_config=model_config,
            )
        except Exception as e:
            logger.warning("Failed to generate title for new session: %s", e)
            return None

    
    async def chat_stream(
        self,
        user_id: int,
        chat_session_id: int,
        thread_id: int,
        content: str,
    ) -> AsyncGenerator[tuple[StreamEventType, BaseModel], None]:
        # 0. 校验请求参数一致性
        if (chat_session_id == -1) != (thread_id == -1):
            raise BadRequestException(
                message="chat_session_id 和 thread_id 必须同时为 -1 或同时为有效值"
            )

        # 1. 如果是新会话，创建 session 和 thread
        created_new_session = False
        if chat_session_id == -1:
            created_new_session = True
            generated_title = await self._generate_new_session_title(content)
            chat_session_id, thread_id = await self._create_new_session_and_thread(
                user_id=user_id,
                title=generated_title,
            )
            
        # 检查thread状态是否合法
        thread = await self.thread_repo.get(thread_id)
        if thread is None or thread.status != 1:
            raise BadRequestException(
                message=f"Thread with id {thread_id} is not active or does not exist"
            )
            
        # 2. 用户消息先入库并返回元数据
        human_message = Message(
            role=MessageRole.USER,
            content=content,
            chat_session_id=chat_session_id,
            thread_id=thread_id,
            user_id=user_id,
            type=MessageType.CHAT,
        )
        
        human_message = await self._save_message(human_message)
        if human_message.id is None or human_message.created_at is None:
            raise InternalServerException("Saved human message missing id or created_at")
        await self._commit_session()

        yield (
            StreamEventType.HUMAN_MESSAGE_CREATED,
            StreamHumanMessageCreated(
                chat_session_id=chat_session_id,
                thread_id=thread_id,
                message=MessageOut(
                    id=human_message.id,
                    role=MessageRole.USER,
                    type=MessageType.CHAT,
                    content=human_message.content if isinstance(human_message.content, str) else str(human_message.content),
                    thread_id=thread_id,
                    created_at=human_message.created_at,
                    status=human_message.status,
                ),
            )
        )

        if created_new_session:
            current_session = await self.session_repo.get(chat_session_id)
            yield (
                StreamEventType.CHAT_SESSION_UPDATED,
                StreamChatSessionUpdated(
                    chat_session_id=chat_session_id,
                    title=current_session.title if current_session else None,
                    reason="chat_session_created",
                ),
            )
        
        model_config = await self.get_model_config(1)
        full_ai_content = ""

        try:
            async for token in self._invoke_llm_stream(content, thread_id, model_config):
                full_ai_content += token
                yield (
                    StreamEventType.TOKEN,
                    StreamToken(content=token)
                )
        except asyncio.CancelledError:
            # 用户主动取消：用独立 session 保存部分内容，标记 STOP_GENERATION
            logger.info("LLM stream cancelled by client, saving partial content")
            if full_ai_content:
                partial_msg = Message(
                    role=MessageRole.ASSISTANT,
                    content=full_ai_content,
                    status=MessageStatus.STOP_GENERATION,
                    chat_session_id=chat_session_id,
                    thread_id=thread_id,
                    user_id=user_id,
                    type=MessageType.CHAT,
                )
                self._fire_and_forget(self._save_message_detached(partial_msg))
        except Exception:
            # LLM/系统错误：用独立 session 保存部分内容，标记 ERROR
            if full_ai_content:
                error_msg = Message(
                    role=MessageRole.ASSISTANT,
                    content=full_ai_content,
                    status=MessageStatus.ERROR,
                    chat_session_id=chat_session_id,
                    thread_id=thread_id,
                    user_id=user_id,
                    type=MessageType.CHAT,
                )
                self._fire_and_forget(self._save_message_detached(error_msg))
            raise  # 向上抛出，由 endpoint 层 except Exception 捕获并发送 StreamError

        # 正常完成：保存完整 AI 消息
        ai_message = Message(
            role=MessageRole.ASSISTANT,
            content=full_ai_content,
            chat_session_id=chat_session_id,
            thread_id=thread_id,
            user_id=user_id,
            type=MessageType.CHAT,
        )
        ai_message = await self._save_message(ai_message)
        if ai_message.id is None or ai_message.created_at is None:
            raise InternalServerException("Saved ai message missing id or created_at")
        await self._commit_session()
        yield (
            StreamEventType.AI_MESSAGE_CREATED,
            StreamAIMessageCreated(
                chat_session_id=chat_session_id,
                thread_id=thread_id,
                message=MessageOut(
                    id=ai_message.id,
                    role=MessageRole.ASSISTANT,
                    type=MessageType.CHAT,
                    content=ai_message.content if isinstance(ai_message.content, str) else str(ai_message.content),
                    thread_id=thread_id,
                    created_at=ai_message.created_at,
                    status=ai_message.status,
                ),
            )
        )

    async def chat(
        self, 
        user_id: int,
        chat_session_id: int,
        thread_id: int,
        content: str,
    ) -> tuple[Message, Message, int, int]:
        """
        处理聊天请求。

        Args:
            user_id: 用户ID
            chat_session_id: 会话ID（-1 表示新会话）
            thread_id: 线程ID（-1 表示新线程）
            content: 消息内容

        Returns:
            tuple: (human_message, ai_message, chat_session_id, thread_id)
        """
        # 0. 校验请求参数一致性
        if (chat_session_id == -1) != (thread_id == -1):
            raise BadRequestException(
                message="chat_session_id 和 thread_id 必须同时为 -1 或同时为有效值"
            )

        # 1. 如果是新会话，创建 session 和 thread
        if chat_session_id == -1:
            generated_title = await self._generate_new_session_title(content)
            chat_session_id, thread_id = await self._create_new_session_and_thread(
                user_id=user_id,
                title=generated_title,
            )
            
        # 检查thread状态是否合法
        thread = await self.thread_repo.get(thread_id)
        if thread is None or thread.status != 1:
            raise BadRequestException(
                message=f"Thread with id {thread_id} is not active or does not exist"
            )

        # 2. Save human message
        human_message = Message(
            role=MessageRole.USER,
            content=content,
            chat_session_id=chat_session_id,
            thread_id=thread_id,
            user_id=user_id,
            type=MessageType.CHAT,
        )
        human_message = await self._save_message(human_message)

        # 3. Get model config
        model_config = await self.get_model_config(1)

        # 4. Invoke LLM
        try:
            ai_content = await self._invoke_llm(content, thread_id, model_config)
        except Exception as e:
            # LLM/系统错误：用独立 session 保存部分内容，标记 ERROR
            await self.thread_repo.update_status(thread_id, ThreadStatus.ERROR)  # 标记线程异常
            raise e  # 向上抛出，由 endpoint 层 except Exception 捕获并返回错误响应
        # 5. Save AI message
        ai_message = Message(
            role=MessageRole.ASSISTANT,
            content=ai_content,
            chat_session_id=chat_session_id,
            thread_id=thread_id,
            user_id=user_id,
            type=MessageType.CHAT,
        )
        ai_message = await self._save_message(ai_message)

        return human_message, ai_message, chat_session_id, thread_id
