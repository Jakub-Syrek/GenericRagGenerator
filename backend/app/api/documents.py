"""HTTP routes for document upload, listing and deletion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status

from ..dependencies import get_rag_service
from ..models.schemas import ChunkInfo, DocumentDetail, DocumentInfo, UploadResponse
from ..security import require_api_key
from ..security.auth import Principal, require_credentials
from ..services.document_loader import UnsupportedFormatError
from ..services.rag_service import (
    ChunkRecord,
    DocumentDetailRecord,
    EmbeddingError,
    EmptyDocumentError,
    RagService,
    StorageError,
    VectorStoreError,
)

router = APIRouter(
    prefix="/api/documents",
    tags=["documents"],
    dependencies=[Depends(require_api_key)],
)


def _owner_for(principal: Principal) -> str | None:
    """Translate a principal into an ACL filter value.

    Admin scope (API key, JWT with admin) bypasses the filter — they
    see every owner. Anonymous principals (no credentials configured)
    also bypass: the deployment is effectively single-tenant.

    @param principal Authenticated identity.
    @returns Owner name to filter by, or `None` for unscoped access.
    """
    if principal.method == "none" or principal.has_scope("admin"):
        return None
    return principal.name


_MAX_BYTES = 25 * 1024 * 1024
# NOTE: slowapi's @limiter.limit cannot wrap endpoints that take an UploadFile
# parameter without breaking FastAPI's introspection. Upload throttling is
# expected to happen at the reverse proxy (nginx limit_req, AWS WAF, etc.),
# documented in SECURITY.md. The 25 MB cap below still prevents single-shot
# abuse.


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    service: RagService = Depends(get_rag_service),
    principal: Principal = Depends(require_credentials),
) -> UploadResponse:
    """Index a single uploaded document.

    @param file      Multipart file payload.
    @param service   Injected RAG service.
    @param principal Authenticated identity (drives the ACL owner stamp).
    @returns Metadata describing the indexed document.
    @raises HTTPException On unsupported, empty or oversized payloads.
    """
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing filename.")
    payload = await file.read()
    if len(payload) > _MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds 25 MB limit.")

    try:
        info, deduplicated = service.ingest(file.filename, payload, owner=_owner_for(principal))
    except UnsupportedFormatError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    except EmptyDocumentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except (EmbeddingError, VectorStoreError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    message = (
        "Document already indexed; returning existing record."
        if deduplicated
        else "Document indexed successfully."
    )
    return UploadResponse(document=info, message=message, deduplicated=deduplicated)


@router.get("", response_model=list[DocumentInfo])
def list_documents(
    service: RagService = Depends(get_rag_service),
    principal: Principal = Depends(require_credentials),
) -> list[DocumentInfo]:
    """List indexed documents.

    @param service   Injected RAG service.
    @param principal Authenticated identity (filters listing by owner).
    @returns Documents sorted from newest to oldest.
    """
    try:
        records = service.list_documents(owner=_owner_for(principal))
    except VectorStoreError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return [
        DocumentInfo(
            id=record.id,
            filename=record.filename,
            chunks=record.chunks,
            uploaded_at=record.uploaded_at,
        )
        for record in records
    ]


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: str,
    service: RagService = Depends(get_rag_service),
    principal: Principal = Depends(require_credentials),
) -> DocumentDetail:
    """Return metadata + content preview for one indexed document.

    @param document_id Document identifier.
    @param service     Injected RAG service.
    @param principal   Authenticated identity (ACL scope).
    @returns Document detail payload.
    @raises HTTPException When the document does not exist or is not yours.
    """
    try:
        record = service.get_document(document_id, owner=_owner_for(principal))
    except VectorStoreError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    return _detail_to_schema(record)


@router.get("/{document_id}/chunks", response_model=list[ChunkInfo])
def list_chunks(
    document_id: str,
    service: RagService = Depends(get_rag_service),
    principal: Principal = Depends(require_credentials),
) -> list[ChunkInfo]:
    """List every chunk produced from one document, ordered by their stored index.

    @param document_id Document identifier.
    @param service     Injected RAG service.
    @param principal   Authenticated identity (ACL scope).
    @returns Ordered list of chunk descriptors.
    @raises HTTPException When the document does not exist or is not yours.
    """
    try:
        chunks = service.list_document_chunks(document_id, owner=_owner_for(principal))
    except VectorStoreError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    if not chunks:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    return [_chunk_to_schema(chunk) for chunk in chunks]


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    service: RagService = Depends(get_rag_service),
    principal: Principal = Depends(require_credentials),
) -> Response:
    """Remove every chunk belonging to one document.

    @param document_id Document identifier.
    @param service     Injected RAG service.
    @param principal   Authenticated identity (ACL scope).
    @returns 204 No Content on success.
    @raises HTTPException When the document does not exist or is not yours.
    """
    try:
        removed = service.delete(document_id, owner=_owner_for(principal))
    except VectorStoreError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    if removed == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _detail_to_schema(record: DocumentDetailRecord) -> DocumentDetail:
    """Lift a service-level detail record into the API schema.

    @param record Service-level record.
    @returns Pydantic `DocumentDetail` ready for serialization.
    """
    return DocumentDetail(
        id=record.id,
        filename=record.filename,
        chunks=record.chunks,
        uploaded_at=record.uploaded_at,
        kind=record.kind,
        language=record.language,
        repository_id=record.repository_id,
        repository_name=record.repository_name,
        preview=record.preview,
    )


def _chunk_to_schema(chunk: ChunkRecord) -> ChunkInfo:
    """Lift a service-level `ChunkRecord` into the API schema.

    @param chunk Service-level chunk record.
    @returns Pydantic `ChunkInfo` ready for serialization.
    """
    return ChunkInfo(
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
    )
