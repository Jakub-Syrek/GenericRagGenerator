"""Administrative endpoints (require the `admin` scope on the bearer)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..dependencies import get_rag_service
from ..security import audit
from ..security.auth import Principal, require_admin
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
def reset_index(
    request: Request,
    principal: Principal = Depends(require_admin),
    service: RagService = Depends(get_rag_service),
) -> ResetResponse:
    """Wipe every chunk in the index (documents + repositories).

    Irreversible. Intended for ops use during decommissioning or after
    a schema migration; gated behind the `admin` scope so accidental
    cross-tenant resets require explicit elevation. Every invocation is
    audit-logged with the calling principal + the correlation id so the
    event can be traced.

    @param request   Incoming request (carries the correlation id).
    @param principal Authenticated admin principal.
    @param service   Injected RAG service.
    @returns Number of chunks removed.
    @raises HTTPException 502 when the underlying store cannot be reached.
    """
    try:
        removed = service.wipe()
    except VectorStoreError as exc:
        audit.event(
            "admin.reset.failed",
            principal=principal.name,
            method=principal.method,
            request_id=getattr(request.state, "request_id", None),
            reason=str(exc),
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    audit.event(
        "admin.reset",
        principal=principal.name,
        method=principal.method,
        request_id=getattr(request.state, "request_id", None),
        chunks_removed=removed,
    )
    return ResetResponse(chunks_removed=removed)
