import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from src.api.v1.router import router as v1_router
from src.core.exceptions import AppException
from src.infra.db.engine import engine
from src.infra.db.models import Base  # 导入 Base 会触发所有模型的注册

logger = logging.getLogger(__name__)


class _PoolTerminateFilter(logging.Filter):
    """过滤 SQLAlchemy 连接池在 Task 取消时产生的无害终止日志。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info and record.exc_info[1] is not None:
            import asyncio
            if isinstance(record.exc_info[1], asyncio.CancelledError):
                return False
        return True


# 仅针对连接池 logger 添加过滤器，不影响其他 SQLAlchemy 日志
logging.getLogger("sqlalchemy.pool").addFilter(_PoolTerminateFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时自动创建数据库表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified successfully!")
    yield


def create_app() -> FastAPI:

    app = FastAPI(title="gitLLM", version="0.1.0", lifespan=lifespan)

    # Configure CORS
    origins = [
        "http://localhost:5173",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router, prefix="/api/v1")

    # ============================================================
    # Global Exception Handlers
    # ============================================================
    
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """Handle all custom application exceptions."""
        logger.warning(
            f"AppException: {exc.message} | Code: {exc.code} | Path: {request.url.path}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "data": None,
                "details": exc.details
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle Pydantic validation errors."""
        logger.warning(f"ValidationError: {exc.errors()} | Path: {request.url.path}")
        return JSONResponse(
            status_code=422,
            content={
                "code": 422,
                "message": "Validation error",
                "data": None,
                "details": {"errors": exc.errors()}
            }
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all handler for unexpected exceptions."""
        logger.exception(f"Unhandled exception: {exc} | Path: {request.url.path}")
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": "Internal server error",
                "data": None,
                "details": None
            }
        )

    # ============================================================
    # Health Check
    # ============================================================

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
