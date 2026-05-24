"""FastAPI entry point: wires routers and serves the static frontend."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import chat, documents, health
from .config import get_settings

_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    @returns Fully wired FastAPI instance.
    """
    get_settings()
    application = FastAPI(title="GenericRagGenerator", version="0.1.0")
    application.include_router(health.router)
    application.include_router(documents.router)
    application.include_router(chat.router)

    if _FRONTEND_DIR.exists():
        application.mount(
            "/static",
            StaticFiles(directory=_FRONTEND_DIR),
            name="static",
        )

        @application.get("/", include_in_schema=False)
        async def index() -> FileResponse:
            """Serve the SPA entry point.

            @returns Static `index.html` response.
            """
            return FileResponse(_FRONTEND_DIR / "index.html")

    return application


app = create_app()
