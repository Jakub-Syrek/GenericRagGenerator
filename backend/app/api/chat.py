"""Streaming chat endpoint backed by the RAG service."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ..dependencies import get_rag_service
from ..models.schemas import ChatRequest
from ..services.rag_service import (
    ChatGenerationError,
    EmbeddingError,
    RagService,
    VectorStoreError,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
async def chat(
    payload: ChatRequest,
    service: RagService = Depends(get_rag_service),
) -> StreamingResponse:
    """Stream a RAG answer as newline-delimited JSON events.

    @param payload Chat request from the client.
    @param service Injected RAG service.
    @returns Streaming HTTP response (`application/x-ndjson`).
    @raises HTTPException On validation errors.
    """
    messages = [message.model_dump() for message in payload.messages]
    try:
        stream = service.stream_chat(messages=messages, document_ids=payload.document_ids)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    async def event_stream() -> AsyncIterator[bytes]:
        """Serialize each event from the RAG service as an NDJSON line.

        @returns Async generator yielding UTF-8 encoded JSON lines.
        """
        try:
            async for event in stream:
                yield (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
        except (EmbeddingError, ChatGenerationError, VectorStoreError) as exc:
            yield (json.dumps({"type": "error", "message": str(exc)}) + "\n").encode("utf-8")

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
