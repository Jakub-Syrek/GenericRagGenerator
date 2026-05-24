"""Pydantic request/response schemas exposed by the HTTP layer."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    """Metadata for an indexed document."""

    id: str
    filename: str
    chunks: int
    uploaded_at: datetime


class UploadResponse(BaseModel):
    """Response returned after a successful document ingest."""

    document: DocumentInfo
    message: str = "Document indexed successfully."


class ChatMessage(BaseModel):
    """Single chat turn supplied by the client."""

    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1)


class IngestedFileInfo(BaseModel):
    """One source file successfully ingested from an uploaded repository."""

    document_id: str
    path: str
    kind: Literal["doc", "code"]
    language: str
    chunks: int


class SkippedFileInfo(BaseModel):
    """One file skipped during repository ingest, with a reason."""

    path: str
    reason: str


class RepositoryInfo(BaseModel):
    """Aggregate description of an indexed repository archive."""

    id: str
    name: str
    files_indexed: int
    total_chunks: int
    files: list[IngestedFileInfo]
    skipped: list[SkippedFileInfo]
    uploaded_at: datetime


class RepositoryUploadResponse(BaseModel):
    """Response payload returned after a successful repository ingest."""

    repository: RepositoryInfo
    message: str = "Repository indexed successfully."


class ChunkInfo(BaseModel):
    """One indexed chunk with its source metadata."""

    chunk_id: str
    document_id: str
    filename: str
    kind: Literal["doc", "code"]
    language: str
    repository_id: str | None = None
    repository_name: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    preview: str


class SearchHit(ChunkInfo):
    """A `ChunkInfo` augmented with a similarity score."""

    score: float
    distance: float


class DocumentDetail(DocumentInfo):
    """Document descriptor with the first-chunk preview baked in."""

    kind: Literal["doc", "code"]
    language: str
    repository_id: str | None = None
    repository_name: str | None = None
    preview: str


class RepositoryDetail(RepositoryInfo):
    """Repository descriptor populated with its per-file ingest list."""


class SearchRequest(BaseModel):
    """Payload for `/api/search` (retrieval-only, no LLM call)."""

    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=200)
    document_ids: list[str] | None = None
    repository_ids: list[str] | None = None
    kinds: list[Literal["doc", "code"]] | None = None


class SearchResponse(BaseModel):
    """Response payload for `/api/search`."""

    query: str
    results: list[SearchHit]
    total: int


class ChatRequest(BaseModel):
    """Payload for /api/chat."""

    messages: list[ChatMessage] = Field(min_length=1)
    document_ids: list[str] | None = None


class HealthResponse(BaseModel):
    """Health check report."""

    status: Literal["ok", "degraded"]
    ollama_reachable: bool
    chat_model: str
    embedding_model: str
