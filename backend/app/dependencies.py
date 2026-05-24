"""FastAPI dependency providers (single source of wiring)."""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends
from ollama import AsyncClient, Client

from .config import Settings, get_settings
from .services.chunker import TextChunker
from .services.document_loader import DocumentLoader
from .services.embedder import OllamaEmbedder
from .services.ingestion import IngestionService
from .services.rag_chain import RagChain
from .services.vector_store import VectorStore


@lru_cache
def _ollama_client(host: str) -> Client:
    """Return a cached synchronous Ollama client.

    @param host Base URL of the Ollama server.
    @returns Memoized `ollama.Client` instance.
    """
    return Client(host=host)


@lru_cache
def _ollama_async_client(host: str) -> AsyncClient:
    """Return a cached asynchronous Ollama client.

    @param host Base URL of the Ollama server.
    @returns Memoized `ollama.AsyncClient` instance.
    """
    return AsyncClient(host=host)


@lru_cache
def _vector_store(persist_dir: str) -> VectorStore:
    """Return a cached `VectorStore` bound to the given persistence directory.

    @param persist_dir Filesystem path used by Chroma.
    @returns Memoized `VectorStore` instance.
    """
    from pathlib import Path
    return VectorStore(Path(persist_dir))


def get_document_loader() -> DocumentLoader:
    """Provide a fresh `DocumentLoader` (stateless).

    @returns New loader instance.
    """
    return DocumentLoader()


def get_chunker(settings: Settings = Depends(get_settings)) -> TextChunker:
    """Provide a `TextChunker` configured from settings.

    @param settings Application settings.
    @returns Configured chunker.
    """
    return TextChunker(chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)


def get_embedder(settings: Settings = Depends(get_settings)) -> OllamaEmbedder:
    """Provide an `OllamaEmbedder` bound to the configured model.

    @param settings Application settings.
    @returns Configured embedder.
    """
    return OllamaEmbedder(client=_ollama_client(settings.ollama_host), model=settings.embedding_model)


def get_vector_store(settings: Settings = Depends(get_settings)) -> VectorStore:
    """Provide the shared `VectorStore` instance.

    @param settings Application settings.
    @returns Memoized vector store.
    """
    return _vector_store(str(settings.chroma_dir))


def get_ingestion_service(
    settings: Settings = Depends(get_settings),
    loader: DocumentLoader = Depends(get_document_loader),
    chunker: TextChunker = Depends(get_chunker),
    embedder: OllamaEmbedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
) -> IngestionService:
    """Provide an `IngestionService` with all collaborators wired in.

    @param settings Application settings.
    @param loader   Document loader.
    @param chunker  Text chunker.
    @param embedder Embedding client.
    @param store    Vector store.
    @returns Configured ingestion service.
    """
    return IngestionService(
        loader=loader,
        chunker=chunker,
        embedder=embedder,
        store=store,
        upload_dir=settings.upload_dir,
    )


def get_rag_chain(
    settings: Settings = Depends(get_settings),
    embedder: OllamaEmbedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
) -> RagChain:
    """Provide a `RagChain` ready to stream answers.

    @param settings Application settings.
    @param embedder Embedding client.
    @param store    Vector store.
    @returns Configured RAG chain.
    """
    return RagChain(
        embedder=embedder,
        store=store,
        chat_client=_ollama_async_client(settings.ollama_host),
        chat_model=settings.chat_model,
        top_k=settings.top_k,
    )
