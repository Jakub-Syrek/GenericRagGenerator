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
