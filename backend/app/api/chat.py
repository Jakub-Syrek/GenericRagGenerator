"""Streaming chat endpoint backed by the RAG chain."""
from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ..dependencies import get_rag_chain
from ..models.schemas import ChatRequest
from ..services.embedder import EmbeddingError
from ..services.rag_chain import RagChain

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
async def chat(
    payload: ChatRequest,
    chain: RagChain = Depends(get_rag_chain),
) -> StreamingResponse:
    """Stream a RAG answer as newline-delimited JSON events.

    @param payload Chat request from the client.
    @param chain   Injected RAG chain.
    @returns Streaming HTTP response (`application/x-ndjson`).
    @raises HTTPException On embedding failures or validation errors.
    """
    messages = [message.model_dump() for message in payload.messages]
    try:
        stream = chain.stream(messages=messages, document_ids=payload.document_ids)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    async def event_stream() -> AsyncIterator[bytes]:
        """Serialize each event from the RAG chain as an NDJSON line.

        @returns Async generator yielding UTF-8 encoded JSON lines.
        """
        try:
            async for event in stream:
                yield (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
        except EmbeddingError as exc:
            yield (json.dumps({"type": "error", "message": str(exc)}) + "\n").encode("utf-8")

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
