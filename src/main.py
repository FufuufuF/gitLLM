from fastapi import FastAPI

from src.api.v1.router import router as v1_router
from src.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(title="gitLLM", version="0.1.0")
    app.include_router(v1_router, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
