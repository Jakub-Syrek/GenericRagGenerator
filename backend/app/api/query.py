"""HTTP route for non-streaming RAG answer (`POST /api/query`)."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, status

from ..dependencies import get_rag_service
from ..models.schemas import QueryRequest, QueryResponse, SearchHit
from ..security import require_api_key
from ..services.rag_service import (
    ChatGenerationError,
    EmbeddingError,
    RagService,
    ScoredChunkRecord,
    VectorStoreError,
)

router = APIRouter(
    prefix="/api/query",
    tags=["query"],
    dependencies=[Depends(require_api_key)],
)


@router.post("", response_model=QueryResponse)
async def query(
    payload: QueryRequest = Body(...),
    service: RagService = Depends(get_rag_service),
) -> QueryResponse:
    """Return a single fully-assembled answer plus the ranked sources.

    Non-streaming sibling of `/api/chat` — preferred for scripts, batch
    jobs and CLI consumers that just want the final text plus citations
    in one shot.

    @param payload Query payload (messages + optional scope filters).
    @param service Injected RAG service.
    @returns `QueryResponse` with answer text and source descriptors.
    @raises HTTPException On retrieval / generation / store failures.
    """
    if payload.messages[-1].role != "user":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The last message must be from the user.")
    messages = [message.model_dump() for message in payload.messages]
    try:
        answer, scored = await service.query_once(
            messages=messages,
            document_ids=payload.document_ids,
            repository_ids=payload.repository_ids,
            project_ids=payload.project_ids,
        )
    except (EmbeddingError, ChatGenerationError, VectorStoreError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return QueryResponse(answer=answer, sources=[_to_hit(item) for item in scored])


def _to_hit(record: ScoredChunkRecord) -> SearchHit:
    """Lift a service-level scored chunk into the API `SearchHit`.

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
