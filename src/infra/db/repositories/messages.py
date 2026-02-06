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

    