"""PixVerse Bridge — FastAPI application factory.

Middleware that translates Semantic-Canvas structured output into
PixVerse V6 LPD (Literal Physical Description) video generation prompts.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.config import get_settings
from app.core.exceptions import PixVerseBridgeError
from app.core.logging import setup_logging


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    setup_logging(settings)

    app = FastAPI(
        title="PixVerse Bridge",
        description=(
            "Middleware translating Semantic-Canvas structured output "
            "into PixVerse V6 LPD video generation prompts."
        ),
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # --- Exception handlers ---

    @app.exception_handler(PixVerseBridgeError)
    async def bridge_exception_handler(
        request: Request, exc: PixVerseBridgeError
    ) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    # --- Health check ---

    @app.get("/health")
    async def health_check() -> dict:
        return {"status": "healthy", "version": "0.1.0"}

    # --- Routers ---

    app.include_router(v1_router, prefix="/v1/bridge")

    return app


# Module-level app instance for uvicorn (uvicorn app.main:app)
app = create_app()
