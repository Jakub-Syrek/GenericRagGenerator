"""Health check endpoint reporting Ollama reachability."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from ollama import Client

from ..config import Settings, get_settings
from ..dependencies import get_probe_client
from ..models.schemas import HealthResponse

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health(
    settings: Settings = Depends(get_settings),
    probe: Client = Depends(get_probe_client),
) -> HealthResponse:
    """Return service status plus Ollama reachability.

    @param settings Application settings.
    @param probe    Injected Ollama probe client.
    @returns Health report payload.
    """
    reachable = _probe_ollama(probe)
    return HealthResponse(
        status="ok" if reachable else "degraded",
        ollama_reachable=reachable,
        chat_model=settings.chat_model,
        embedding_model=settings.embedding_model,
    )


def _probe_ollama(client: Client) -> bool:
    """Best-effort connectivity probe against the Ollama server.

    @param client Ollama client.
    @returns True when the server responded, False otherwise.
    """
    try:
        client.list()
        return True
    except Exception:
        return False
