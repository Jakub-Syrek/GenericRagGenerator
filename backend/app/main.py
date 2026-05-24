"""FastAPI entry point: wires routers, security and the static frontend."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .api import chat, documents, health, repository
from .config import get_settings
from .security import SecurityHeadersMiddleware, limiter

_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    @returns Fully wired FastAPI instance.
    """
    settings = get_settings()
    application = FastAPI(title="GenericRagGenerator", version="0.1.0")

    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    application.add_middleware(SlowAPIMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "Accept"],
        allow_credentials=False,
        max_age=600,
    )

    application.include_router(health.router)
    application.include_router(documents.router)
    application.include_router(repository.router)
    application.include_router(chat.router)
    _mount_frontend(application)
    return application


def _mount_frontend(application: FastAPI) -> None:
    """Mount the bundled static UI when the `frontend/` directory exists.

    @param application FastAPI app to extend.
    """
    if not _FRONTEND_DIR.exists():
        return
    application.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")

    @application.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        """Serve the SPA entry point.

        @returns Static `index.html` response.
        """
        return FileResponse(_FRONTEND_DIR / "index.html")


def _rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render a JSON 429 with a `Retry-After` header.

    @param request Incoming request (unused, kept for Starlette's handler signature).
    @param exc     Underlying exception; expected to be `RateLimitExceeded`.
    @returns Starlette JSON response.
    """
    detail = exc.detail if isinstance(exc, RateLimitExceeded) else str(exc)
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {detail}"},
        headers={"Retry-After": "60"},
    )


app = create_app()
