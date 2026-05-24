"""FastAPI dependency providers (single source of wiring)."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends
from ollama import Client

from .config import Settings, get_settings
from .services.document_loader import DocumentLoader
from .services.rag_service import RagService


def _document_loader(settings: Settings) -> DocumentLoader:
    """Build a `DocumentLoader` honouring the sandbox settings.

    @param settings Application settings.
    @returns Configured loader (sandbox flag passed through).
    """
    return DocumentLoader(
        sandbox_enabled=settings.parser_sandbox_enabled,
        sandbox_timeout_seconds=settings.parser_sandbox_timeout_seconds,
    )


@lru_cache
def _ollama_probe_client(host: str) -> Client:
    """Return a cached Ollama client used only for connectivity probing.

    @param host Base URL of the Ollama server.
    @returns Memoized synchronous Ollama client.
    """
    return Client(host=host)


@lru_cache
def _rag_service(_cache_key: str) -> RagService:
    """Return a cached `RagService` keyed by a stable cache key.

    @param _cache_key Stable identifier (chroma dir) used purely for caching.
    @returns Memoized RAG service.
    """
    settings = get_settings()
    return RagService(settings=settings, loader=_document_loader(get_settings()))


def get_document_loader() -> DocumentLoader:
    """Provide a fresh `DocumentLoader` (stateless).

    @returns New loader instance.
    """
    return _document_loader(get_settings())


def get_rag_service(settings: Settings = Depends(get_settings)) -> RagService:
    """Provide the shared `RagService` singleton.

    @param settings Application settings.
    @returns Memoized RAG service.
    """
    return _rag_service(str(settings.chroma_dir))


def get_probe_client(settings: Settings = Depends(get_settings)) -> Client:
    """Provide the Ollama client used for health probes.

    @param settings Application settings.
    @returns Memoized probe client.
    """
    return _ollama_probe_client(settings.ollama_host)
