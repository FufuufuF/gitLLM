from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models import Message
from src.infra.db.repositories.messages import MessageRepository


class MessageService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.message_repo = MessageRepository(db_session)

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
        
        
