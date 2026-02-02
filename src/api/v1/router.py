from fastapi import APIRouter

from src.api.v1.sessions import router as sessions_router
from src.api.v1.threads import router as threads_router
from src.api.v1.messages import router as messages_router
from src.api.v1.merges import router as merges_router
from src.api.v1.settings import router as settings_router

router = APIRouter()

router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
router.include_router(threads_router, prefix="/threads", tags=["threads"])
router.include_router(messages_router, prefix="/messages", tags=["messages"])
router.include_router(merges_router, prefix="/merges", tags=["merges"])
router.include_router(settings_router, prefix="/settings", tags=["settings"])

# Reserved (not enabled for MVP):
# - auth
# - model_configs
