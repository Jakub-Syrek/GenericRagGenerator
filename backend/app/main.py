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

from .api import (
    admin,
    auth,
    chat,
    documents,
    health,
    projects,
    query,
    repository,
    search,
)
from .config import get_settings
from .security import SecurityHeadersMiddleware, limiter

_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    @returns Fully wired FastAPI instance.
    """
    settings = get_settings()
    application = FastAPI(
        title="GenericRagGenerator",
        version="0.2.0",
        summary="Local RAG service exposing a fully RESTful API over documents, repositories and chat.",
        description=(
            "Upload documents or whole repositories (code + docs), then retrieve "
            "and chat against them. Every endpoint is consumable by browsers, "
            "scripts and other services — the same surface is exposed whether "
            "the app runs as a foreground process, a Windows service or inside "
            "the bundled Docker compose stack. Interactive docs at `/docs` "
            "(Swagger UI) and `/redoc`."
        ),
        contact={"name": "Jakub Syrek", "email": "jakubvonsyrek@gmail.com"},
        openapi_tags=[
            {"name": "health", "description": "Liveness + Ollama reachability probe."},
            {
                "name": "auth",
                "description": "Credential login + JWT bearer issuance.",
            },
            {
                "name": "admin",
                "description": "Administrative operations (require the `admin` scope).",
            },
            {
                "name": "documents",
                "description": "CRUD over individually uploaded documents and their chunks.",
            },
            {
                "name": "repositories",
                "description": "CRUD over uploaded ZIP repositories and their files.",
            },
            {
                "name": "projects",
                "description": "CRUD over multi-source projects (many raw files in one upload).",
            },
            {"name": "search", "description": "Retrieval-only similarity search (no LLM call)."},
            {"name": "query", "description": "Synchronous RAG answer (non-streaming JSON)."},
            {"name": "chat", "description": "Streaming RAG answer (NDJSON), grounded in the index."},
        ],
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

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
    application.include_router(auth.router)
    application.include_router(admin.router)
    application.include_router(documents.router)
    application.include_router(repository.router)
    application.include_router(projects.router)
    application.include_router(search.router)
    application.include_router(query.router)
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
