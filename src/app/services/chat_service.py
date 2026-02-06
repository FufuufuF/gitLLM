import os

from langchain.messages import AIMessage, HumanMessage
from langgraph.graph.state import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from src.graph.state import GraphState
from src.infra.db.repositories.messages import MessageRepository
from src.infra.db.repositories.model_config import ModelConfigRepository
from src.infra.checkpoint.postgres import get_postgres_saver
from src.domain.models import Message, ModelConfig
from src.graph.graphs.chat_graph import create_chat_graph
from src.core.config.model_config import model_setting
from src.core.exceptions import ExternalServiceException, InternalServerException

# MOCK mode: set MOCK_DB=1 to skip real DB and LLM calls
MOCK_DB = "1"


class ChatService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.message_repo = MessageRepository(db_session)
        self.model_config_repo = ModelConfigRepository(db_session)


    async def get_model_config(self, model_config_id: int) -> ModelConfig:
        # MOCK
        return ModelConfig(
            id=1,
            provider=model_setting.QWEN_MODEL_PROVIDER if model_setting.QWEN_MODEL_PROVIDER else "tongyi",
            api_key=model_setting.QWEN_MODEL_API_KEY,
            base_url=model_setting.QWEN_MODEL_BASE_URL,
            model_name=model_setting.QWEN_MODEL_NAME,
            user_id=1,
        )


    async def _save_message(self, message: Message) -> Message:
        """Save message to DB or mock with print."""
        if MOCK_DB:
            # Assign a fake ID for mock mode
            mock_id = hash(message.content) % 100000
            from datetime import datetime
            print(f"[MOCK] Saving message: id={mock_id}, role={message.role}, content={message.content[:50]}...")
            return Message(
                id=mock_id,
                role=message.role,
                content=message.content,
                chat_session_id=message.chat_session_id,
                thread_id=message.thread_id,
                user_id=message.user_id,
                created_at=datetime.now(),
            )
        
        saved = await self.message_repo.add(message)
        if saved is None:
            raise InternalServerException("Failed to save message to database")
        return saved


    async def _invoke_llm(self, content: str, thread_id: int, model_config: ModelConfig) -> str:
        """Invoke LLM or return mock response."""
        
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
            if MOCK_DB:
                print(f"[MOCK] LLM invocation starting (NO DB Persistence)...")
                agent = create_chat_graph(postgres_saver=None)
                result = await agent.ainvoke(graph_input, run_config)
            else:
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


    async def chat(
        self, 
        user_id: int,
        chat_session_id: int,
        thread_id: int,
        content: str,
    ) -> tuple[Message, Message]:
        # 1. Save human message
        human_message = Message(
            role=1,
            content=content,
            chat_session_id=chat_session_id,
            thread_id=thread_id,
            user_id=user_id,
        )
        human_message = await self._save_message(human_message)

        # 2. Get model config
        model_config = await self.get_model_config(1)

        # 3. Invoke LLM
        ai_content = await self._invoke_llm(content, thread_id, model_config)

        # 4. Save AI message
        ai_message = Message(
            role=2,
            content=ai_content,
            chat_session_id=chat_session_id,
            thread_id=thread_id,
            user_id=user_id,
        )
        ai_message = await self._save_message(ai_message)

        return human_message, ai_message

