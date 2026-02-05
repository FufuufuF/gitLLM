from src.infra.db.repositories.base import BaseRepository
from src.domain.models import Message
from src.infra.db.models.messages import Message as MessageModel

class MessageRepository(BaseRepository[MessageModel, Message]):
    model = MessageModel
    schema_class = Message
    