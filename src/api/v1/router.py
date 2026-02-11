from fastapi import APIRouter

from src.api.v1.endpoints.chat_sessions import router as chat_sessions_router
from src.api.v1.endpoints.threads import router as threads_router
from src.api.v1.endpoints.messages import router as messages_router
from src.api.v1.endpoints.settings import router as settings_router
from src.api.v1.endpoints.chat import router as chat_router

router = APIRouter()

router.include_router(chat_sessions_router, prefix="/chat_sessions", tags=["chat_sessions"])
router.include_router(threads_router, prefix="/threads", tags=["threads"])
router.include_router(messages_router, prefix="/message", tags=["message"])
router.include_router(settings_router, prefix="/setting", tags=["setting"])
router.include_router(chat_router, prefix="/chat", tags=["chat"])

# Reserved (not enabled for MVP):
# - auth
# - model_configs
