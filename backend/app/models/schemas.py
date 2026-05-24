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
