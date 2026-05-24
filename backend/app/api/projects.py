"""HTTP routes for multi-source project upload, listing and deletion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status

from ..dependencies import get_rag_service
from ..models.schemas import (
    IngestedFileInfo,
    ProjectDetail,
    ProjectInfo,
    ProjectUploadResponse,
    SkippedFileInfo,
)
from ..security import require_api_key
from ..services.rag_service import (
    EmbeddingError,
    RagService,
    RepositoryError,
    RepositoryRecord,
    StorageError,
    VectorStoreError,
)

router = APIRouter(
    prefix="/api/projects",
    tags=["projects"],
    dependencies=[Depends(require_api_key)],
)

_MAX_PROJECT_BYTES = 50 * 1024 * 1024
_MAX_PROJECT_FILES = 100


def _to_info(record: RepositoryRecord) -> ProjectInfo:
    """Lift a service-level record into the API schema.

    @param record Service-level project record (re-used `RepositoryRecord`).
    @returns Pydantic schema ready for serialization.
    """
    return ProjectInfo(
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


@router.post("", response_model=ProjectUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_project(
    request: Request,
    name: str = Form(..., min_length=1, max_length=128),
    files: list[UploadFile] = File(..., description="Multiple files comprising the project."),
    service: RagService = Depends(get_rag_service),
) -> ProjectUploadResponse:
    """Index every uploaded file under a single project identifier.

    @param request FastAPI request (used by middleware-level rate limiting).
    @param name    Display name for the project.
    @param files   Non-empty list of multipart files.
    @param service Injected RAG service.
    @returns Aggregate metadata describing the indexed project.
    @raises HTTPException On empty / oversized / unusable uploads.
    """
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "At least one file is required.")
    if len(files) > _MAX_PROJECT_FILES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Too many files (>{_MAX_PROJECT_FILES}).",
        )
    payloads = await _read_payloads(files)
    try:
        record = service.ingest_project(project_name=name, files=payloads)
    except RepositoryError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except (EmbeddingError, VectorStoreError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    return ProjectUploadResponse(project=_to_info(record))


async def _read_payloads(files: list[UploadFile]) -> list[tuple[str, bytes]]:
    """Read and size-check every uploaded file in turn.

    @param files Multipart files supplied by the client.
    @returns `(filename, bytes)` pairs for the service layer.
    @raises HTTPException When the cumulative payload exceeds the project cap.
    """
    payloads: list[tuple[str, bytes]] = []
    total = 0
    for upload in files:
        filename = upload.filename or "upload"
        payload = await upload.read()
        total += len(payload)
        if total > _MAX_PROJECT_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"Project exceeds {_MAX_PROJECT_BYTES // (1024 * 1024)} MB total.",
            )
        payloads.append((filename, payload))
    return payloads


@router.get("", response_model=list[ProjectInfo])
def list_projects(service: RagService = Depends(get_rag_service)) -> list[ProjectInfo]:
    """List indexed projects.

    @param service Injected RAG service.
    @returns Projects sorted from newest to oldest (chunks aggregated).
    """
    try:
        rows = service.list_projects()
    except VectorStoreError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return [
        ProjectInfo(
            id=proj_id,
            name=name,
            files_indexed=0,
            total_chunks=chunks,
            files=[],
            skipped=[],
            uploaded_at=uploaded_at,
        )
        for proj_id, name, chunks, uploaded_at in rows
    ]


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str, service: RagService = Depends(get_rag_service)) -> ProjectDetail:
    """Return metadata + per-file ingest list for one project.

    @param project_id Project identifier.
    @param service    Injected RAG service.
    @returns Detailed project payload.
    @raises HTTPException When the project does not exist.
    """
    try:
        record = service.get_project(project_id)
    except VectorStoreError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    return ProjectDetail(**_to_info(record).model_dump())


@router.get("/{project_id}/files", response_model=list[IngestedFileInfo])
def list_project_files(
    project_id: str, service: RagService = Depends(get_rag_service)
) -> list[IngestedFileInfo]:
    """List every file ingested into one project.

    @param project_id Project identifier.
    @param service    Injected RAG service.
    @returns Per-file ingest list (sorted by path).
    @raises HTTPException When the project does not exist.
    """
    try:
        record = service.get_project(project_id)
    except VectorStoreError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
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


@router.delete("/{project_id}")
def delete_project(project_id: str, service: RagService = Depends(get_rag_service)) -> Response:
    """Remove every chunk belonging to one project.

    @param project_id Project identifier.
    @param service    Injected RAG service.
    @returns 204 No Content on success.
    @raises HTTPException When the project does not exist.
    """
    try:
        removed = service.delete_project(project_id)
    except VectorStoreError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    if removed == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
