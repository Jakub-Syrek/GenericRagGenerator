"""Administrative endpoints (require the `admin` scope on the bearer)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..dependencies import get_rag_service
from ..security.auth import require_admin
from ..services.rag_service import RagService, VectorStoreError

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


class ResetResponse(BaseModel):
    """Payload returned after a successful index wipe."""

    chunks_removed: int


@router.post("/reset", response_model=ResetResponse)
def reset_index(service: RagService = Depends(get_rag_service)) -> ResetResponse:
    """Wipe every chunk in the index (documents + repositories).

    Irreversible. Intended for ops use during decommissioning or after a
    schema migration; gated behind the `admin` scope so accidental
    cross-tenant resets require explicit elevation.

    @param service Injected RAG service.
    @returns Number of chunks removed.
    @raises HTTPException 502 when the underlying store cannot be reached.
    """
    try:
        removed = service.wipe()
    except VectorStoreError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return ResetResponse(chunks_removed=removed)
