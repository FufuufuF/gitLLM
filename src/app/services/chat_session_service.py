from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.db.repositories.chat_sessions import SessionRepository

class SessionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_repo = SessionRepository(db)