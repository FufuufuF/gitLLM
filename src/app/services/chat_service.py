
from langchain.messages import AIMessage, HumanMessage
from langgraph.graph.state import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from src.graph.state import GraphState
from src.infra.db.repositories.messages import MessageRepository
from src.infra.db.repositories.model_config import ModelConfigRepository
from src.infra.db.repositories.chat_sessions import ChatSessionRepository
from src.infra.db.repositories.threads import ThreadRepository
from src.infra.checkpoint.postgres import get_postgres_saver
from src.domain.models import Message, ModelConfig, ChatSession, Thread
from src.graph.graphs.chat_graph import create_chat_graph
from src.core.exceptions import ExternalServiceException, InternalServerException, BadRequestException
from src.core.config.model_config import model_setting

class ChatService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.message_repo = MessageRepository(db_session)
        self.model_config_repo = ModelConfigRepository(db_session)
        self.session_repo = ChatSessionRepository(db_session)
        self.thread_repo = ThreadRepository(db_session)


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


    async def _invoke_llm(self, content: str, thread_id: int, model_config: ModelConfig) -> str:
        """Invoke LLM."""
        
        # Prepare input and config
        graph_input = GraphState(
            messages=[
                HumanMessage(content=content),
            ]
        )
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
        
        except Exception as e:
            raise ExternalServiceException(
                message=f"LLM service failed: {str(e)}",
                code=5001
            )


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
            chat_session_id, thread_id = await self._create_new_session_and_thread(
                user_id=user_id,
                title=None,  # 可后续用 LLM 生成标题
            )

        # 2. Save human message
        human_message = Message(
            role=1,
            content=content,
            chat_session_id=chat_session_id,
            thread_id=thread_id,
            user_id=user_id,
        )
        human_message = await self._save_message(human_message)

        # 3. Get model config
        model_config = await self.get_model_config(1)

        # 4. Invoke LLM
        ai_content = await self._invoke_llm(content, thread_id, model_config)

        # 5. Save AI message
        ai_message = Message(
            role=2,
            content=ai_content,
            chat_session_id=chat_session_id,
            thread_id=thread_id,
            user_id=user_id,
        )
        ai_message = await self._save_message(ai_message)

        return human_message, ai_message, chat_session_id, thread_id
