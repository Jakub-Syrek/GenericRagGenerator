"""HTTP routes for document upload, listing and deletion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from ..dependencies import get_rag_service
from ..models.schemas import DocumentInfo, UploadResponse
from ..services.document_loader import UnsupportedFormatError
from ..services.rag_service import EmptyDocumentError, RagService

router = APIRouter(prefix="/api/documents", tags=["documents"])

_MAX_BYTES = 25 * 1024 * 1024


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    service: RagService = Depends(get_rag_service),
) -> UploadResponse:
    """Index a single uploaded document.

    @param file    Multipart file payload.
    @param service Injected RAG service.
    @returns Metadata describing the indexed document.
    @raises HTTPException On unsupported, empty or oversized payloads.
    """
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing filename.")
    payload = await file.read()
    if len(payload) > _MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds 25 MB limit.")

    try:
        info = service.ingest(file.filename, payload)
    except UnsupportedFormatError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    except EmptyDocumentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Indexing failed: {exc}") from exc
    return UploadResponse(document=info)


@router.get("", response_model=list[DocumentInfo])
def list_documents(service: RagService = Depends(get_rag_service)) -> list[DocumentInfo]:
    """List indexed documents.

    @param service Injected RAG service.
    @returns Documents sorted from newest to oldest.
    """
    return [
        DocumentInfo(
            id=record.id,
            filename=record.filename,
            chunks=record.chunks,
            uploaded_at=record.uploaded_at,
        )
        for record in service.list_documents()
    ]


@router.delete("/{document_id}")
def delete_document(document_id: str, service: RagService = Depends(get_rag_service)) -> Response:
    """Remove every chunk belonging to one document.

    @param document_id Document identifier.
    @param service     Injected RAG service.
    @returns 204 No Content on success.
    @raises HTTPException When the document does not exist.
    """
    removed = service.delete(document_id)
    if removed == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
