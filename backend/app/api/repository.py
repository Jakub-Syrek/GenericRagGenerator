"""HTTP routes for repository (ZIP) upload, listing and deletion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status

from ..dependencies import get_rag_service
from ..models.schemas import (
    IngestedFileInfo,
    RepositoryDetail,
    RepositoryInfo,
    RepositoryUploadResponse,
    SkippedFileInfo,
)
from ..security import require_api_key
from ..security.auth import Principal, require_credentials
from ..services.rag_service import (
    EmbeddingError,
    RagService,
    RepositoryError,
    RepositoryRecord,
    StorageError,
    UnsafeArchiveError,
    VectorStoreError,
)

router = APIRouter(
    prefix="/api/repositories",
    tags=["repositories"],
    dependencies=[Depends(require_api_key)],
)

_MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
# Upload throttling expected at the reverse proxy; see SECURITY.md.


def _owner_for(principal: Principal) -> str | None:
    """Translate a principal into an ACL filter value.

    @param principal Authenticated identity.
    @returns Owner name to filter by, or `None` for unscoped access.
    """
    if principal.method == "none" or principal.has_scope("admin"):
        return None
    return principal.name


def _to_info(record: RepositoryRecord) -> RepositoryInfo:
    """Lift a service-level record into the API schema.

    @param record Service-level repository record.
    @returns Pydantic schema ready for serialization.
    """
    return RepositoryInfo(
        id=record.id,
        name=record.name,
        files_indexed=record.files_indexed,
        total_chunks=record.total_chunks,
        files=[
            IngestedFileInfo(
                document_id=file.document_id,
                path=file.path,
                kind=file.kind,
                language=file.language,
                chunks=file.chunks,
            )
            for file in record.files
        ],
        skipped=[SkippedFileInfo(path=item.path, reason=item.reason) for item in record.skipped],
        uploaded_at=record.uploaded_at,
    )


@router.post("", response_model=RepositoryUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_repository(
    request: Request,
    file: UploadFile = File(...),
    service: RagService = Depends(get_rag_service),
    principal: Principal = Depends(require_credentials),
) -> RepositoryUploadResponse:
    """Index every supported file inside an uploaded ZIP archive.

    @param file    Multipart ZIP payload.
    @param service Injected RAG service.
    @returns Aggregate metadata describing the indexed repository.
    @raises HTTPException On unsafe, oversized or unusable archives.
    """
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing filename.")
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Only .zip archives are supported.",
        )
    payload = await file.read()
    if len(payload) > _MAX_ARCHIVE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Archive exceeds {_MAX_ARCHIVE_BYTES // (1024 * 1024)} MB limit.",
        )
    try:
        record = service.ingest_repository(file.filename, payload, owner=_owner_for(principal))
    except UnsafeArchiveError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except RepositoryError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except (EmbeddingError, VectorStoreError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    return RepositoryUploadResponse(repository=_to_info(record))


@router.get("", response_model=list[RepositoryInfo])
def list_repositories(
    service: RagService = Depends(get_rag_service),
    principal: Principal = Depends(require_credentials),
) -> list[RepositoryInfo]:
    """List indexed repositories.

    @param service   Injected RAG service.
    @param principal Authenticated identity (ACL scope).
    @returns Repositories sorted from newest to oldest (chunks aggregated).
    """
    try:
        rows = service.list_repositories(owner=_owner_for(principal))
    except VectorStoreError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return [
        RepositoryInfo(
            id=repo_id,
            name=name,
            files_indexed=0,
            total_chunks=chunks,
            files=[],
            skipped=[],
            uploaded_at=uploaded_at,
        )
        for repo_id, name, chunks, uploaded_at in rows
    ]


@router.get("/{repository_id}", response_model=RepositoryDetail)
def get_repository(
    repository_id: str,
    service: RagService = Depends(get_rag_service),
    principal: Principal = Depends(require_credentials),
) -> RepositoryDetail:
    """Return metadata + per-file ingest list for one repository.

    @param repository_id Repository identifier.
    @param service       Injected RAG service.
    @param principal     Authenticated identity (ACL scope).
    @returns Detailed repository payload.
    @raises HTTPException When the repository does not exist or is not yours.
    """
    try:
        record = service.get_repository(repository_id, owner=_owner_for(principal))
    except VectorStoreError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Repository not found.")
    return RepositoryDetail(**_to_info(record).model_dump())


@router.get("/{repository_id}/files", response_model=list[IngestedFileInfo])
def list_repository_files(
    repository_id: str,
    service: RagService = Depends(get_rag_service),
    principal: Principal = Depends(require_credentials),
) -> list[IngestedFileInfo]:
    """List every file ingested from one repository.

    @param repository_id Repository identifier.
    @param service       Injected RAG service.
    @param principal     Authenticated identity (ACL scope).
    @returns Per-file ingest list (sorted by path).
    @raises HTTPException When the repository does not exist or is not yours.
    """
    try:
        record = service.get_repository(repository_id, owner=_owner_for(principal))
    except VectorStoreError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Repository not found.")
    return [
        IngestedFileInfo(
            document_id=file.document_id,
            path=file.path,
            kind=file.kind,
            language=file.language,
            chunks=file.chunks,
        )
        for file in record.files
    ]


@router.delete("/{repository_id}")
def delete_repository(
    repository_id: str,
    service: RagService = Depends(get_rag_service),
    principal: Principal = Depends(require_credentials),
) -> Response:
    """Remove every chunk belonging to one repository.

    @param repository_id Repository identifier.
    @param service       Injected RAG service.
    @param principal     Authenticated identity (ACL scope).
    @returns 204 No Content on success.
    @raises HTTPException When the repository does not exist or is not yours.
    """
    try:
        removed = service.delete_repository(repository_id, owner=_owner_for(principal))
    except VectorStoreError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    if removed == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Repository not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
