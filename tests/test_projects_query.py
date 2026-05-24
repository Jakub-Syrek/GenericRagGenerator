"""Tests for the multi-source project upload and the non-streaming /api/query."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_rag_service
from app.main import app
from app.services.rag_service import (
    ChunkRecord,
    IngestedFile,
    RepositoryRecord,
    ScoredChunkRecord,
)


class _ProjectsFakeService:
    """Stub exposing the project + query surfaces only."""

    def __init__(self) -> None:
        self.records: dict[str, RepositoryRecord] = {}
        self.stream_payload: list[dict] = []
        self.query_answer: str = "stub answer"

    def ingest_project(self, *, project_name: str, files: list[tuple[str, bytes]]) -> RepositoryRecord:
        """Build a synthetic project record from the supplied filenames."""
        project_id = f"proj-{len(self.records) + 1}"
        record = RepositoryRecord(
            id=project_id,
            name=project_name,
            files=[
                IngestedFile(
                    document_id=f"{project_id}-{idx}",
                    path=filename,
                    kind="doc",
                    language="text",
                    chunks=1,
                )
                for idx, (filename, _payload) in enumerate(files)
            ],
            skipped=[],
            uploaded_at=datetime.now(UTC),
        )
        self.records[project_id] = record
        return record

    def list_projects(self) -> list[tuple[str, str, int, datetime]]:
        return [(rec.id, rec.name, rec.total_chunks, rec.uploaded_at) for rec in self.records.values()]

    def get_project(self, project_id: str) -> RepositoryRecord | None:
        return self.records.get(project_id)

    def delete_project(self, project_id: str) -> int:
        record = self.records.pop(project_id, None)
        return record.total_chunks if record else 0

    async def query_once(self, **_kwargs: object) -> tuple[str, list[ScoredChunkRecord]]:
        chunk = ChunkRecord(
            chunk_id="c-1",
            document_id="d-1",
            filename="notes.txt",
            kind="doc",
            language="text",
            repository_id=None,
            repository_name=None,
            line_start=None,
            line_end=None,
            preview="snippet",
        )
        return self.query_answer, [ScoredChunkRecord(chunk=chunk, score=0.9, distance=0.1)]

    # Methods required because the existing /api/health and /api/documents
    # routes share the same dependency override; keep them stub-friendly.
    def list_documents(self) -> list:
        return []

    async def stream_chat(self, **_kwargs: object) -> AsyncIterator[dict]:
        for event in self.stream_payload:
            yield event

    def ingest(self, *_args: object, **_kwargs: object) -> object:  # pragma: no cover
        raise NotImplementedError


@pytest.fixture
def service() -> _ProjectsFakeService:
    """Provide a stub and wire it as the FastAPI dependency."""
    stub = _ProjectsFakeService()
    app.dependency_overrides[get_rag_service] = lambda: stub
    yield stub
    app.dependency_overrides.pop(get_rag_service, None)


@pytest.fixture
def client(service: _ProjectsFakeService) -> TestClient:
    """`TestClient` with the project stub already wired."""
    _ = service
    return TestClient(app)


def test_upload_project_indexes_each_file(client: TestClient, service: _ProjectsFakeService) -> None:
    """Posting multiple files under one name produces one project record."""
    response = client.post(
        "/api/projects",
        data={"name": "my-project"},
        files=[
            ("files", ("readme.md", b"# Title", "text/markdown")),
            ("files", ("notes.txt", b"hello", "text/plain")),
        ],
    )
    assert response.status_code == 201
    body = response.json()["project"]
    assert body["name"] == "my-project"
    assert body["files_indexed"] == 2
    assert {f["path"] for f in body["files"]} == {"readme.md", "notes.txt"}
    assert len(service.records) == 1


def test_list_projects_returns_uploaded(client: TestClient) -> None:
    """After upload the listing surfaces the project."""
    client.post(
        "/api/projects",
        data={"name": "demo"},
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    )
    rows = client.get("/api/projects").json()
    assert len(rows) == 1
    assert rows[0]["name"] == "demo"


def test_get_project_returns_404_when_missing(client: TestClient) -> None:
    """Unknown project id returns 404 on detail + files."""
    assert client.get("/api/projects/missing").status_code == 404
    assert client.get("/api/projects/missing/files").status_code == 404


def test_delete_project_returns_204_when_present(client: TestClient) -> None:
    """Deleting a known project returns 204."""
    upload = client.post(
        "/api/projects",
        data={"name": "demo"},
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    ).json()
    project_id = upload["project"]["id"]
    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert client.delete(f"/api/projects/{project_id}").status_code == 404


def test_query_returns_answer_and_sources(client: TestClient, service: _ProjectsFakeService) -> None:
    """`POST /api/query` echoes the stubbed answer + a single source."""
    service.query_answer = "Two plus two equals four."
    response = client.post(
        "/api/query",
        json={"messages": [{"role": "user", "content": "2+2?"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Two plus two equals four."
    assert body["sources"] and body["sources"][0]["filename"] == "notes.txt"


def test_query_requires_last_message_from_user(client: TestClient) -> None:
    """If the final message role is not `user`, the request is rejected."""
    response = client.post(
        "/api/query",
        json={"messages": [{"role": "assistant", "content": "hi"}]},
    )
    assert response.status_code == 400
