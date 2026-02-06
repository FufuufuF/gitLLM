from fastapi import APIRouter

from src.api.v1.endpoints.sessions import router as sessions_router
from src.api.v1.endpoints.threads import router as threads_router
from src.api.v1.endpoints.messages import router as messages_router
from src.api.v1.endpoints.merges import router as merges_router
from src.api.v1.endpoints.settings import router as settings_router
from src.api.v1.endpoints.chat import router as chat_router

router = APIRouter()

router.include_router(sessions_router, prefix="/session", tags=["session"])
router.include_router(threads_router, prefix="/thread", tags=["thread"])
router.include_router(messages_router, prefix="/message", tags=["message"])
router.include_router(merges_router, prefix="/merge", tags=["merge"])
router.include_router(settings_router, prefix="/setting", tags=["setting"])
router.include_router(chat_router, prefix="/chat", tags=["chat"])

# Reserved (not enabled for MVP):
# - auth
# - model_configs
