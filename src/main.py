import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from src.api.v1.router import router as v1_router
from src.core.exceptions import AppException

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:

    app = FastAPI(title="gitLLM", version="0.1.0")
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
