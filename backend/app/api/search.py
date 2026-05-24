"""HTTP route for retrieval-only search (no LLM call)."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Body, Depends, HTTPException, status

from ..dependencies import get_rag_service
from ..models.schemas import SearchHit, SearchRequest, SearchResponse
from ..security import require_api_key
from ..services.rag_service import (
    EmbeddingError,
    RagService,
    ScoredChunkRecord,
    VectorStoreError,
)

router = APIRouter(
    prefix="/api/search",
    tags=["search"],
    dependencies=[Depends(require_api_key)],
)


@router.post("", response_model=SearchResponse)
def search(
    payload: SearchRequest = Body(...),
    service: RagService = Depends(get_rag_service),
) -> SearchResponse:
    """Return ranked chunks for a query without invoking the chat model.

    Useful as a debugging tool and as a building block for non-chat consumers
    (e.g. autocomplete, IDE integrations) that want retrieval signal without
    paying for an LLM completion.

    @param payload Search request body.
    @param service Injected RAG service.
    @returns Ranked list of `SearchHit`.
    @raises HTTPException On Ollama / Chroma failures.
    """
    try:
        results = service.search(
            query=payload.query,
            top_k=payload.top_k,
            document_ids=payload.document_ids,
            repository_ids=payload.repository_ids,
            kinds=cast("list[str] | None", payload.kinds),
        )
    except (EmbeddingError, VectorStoreError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return SearchResponse(
        query=payload.query,
        results=[_to_hit(item) for item in results],
        total=len(results),
    )


def _to_hit(record: ScoredChunkRecord) -> SearchHit:
    """Lift a service-level scored chunk into the API schema.

    @param record Service-level scored chunk.
    @returns Pydantic `SearchHit` ready for serialization.
    """
    chunk = record.chunk
    return SearchHit(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        filename=chunk.filename,
        kind=chunk.kind,
        language=chunk.language,
        repository_id=chunk.repository_id,
        repository_name=chunk.repository_name,
        line_start=chunk.line_start,
        line_end=chunk.line_end,
        preview=chunk.preview,
        score=record.score,
        distance=record.distance,
    )
