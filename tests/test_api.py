"""API tests using FastAPI TestClient with a stubbed RAG service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_rag_service
from app.main import app
from app.models.schemas import DocumentInfo
from app.services.document_loader import UnsupportedFormatError
from app.services.rag_service import (
    ChunkRecord,
    DocumentDetailRecord,
    DocumentRecord,
    EmbeddingError,
    EmptyDocumentError,
    RepositoryRecord,
    ScoredChunkRecord,
    StorageError,
    VectorStoreError,
)


class FakeRagService:
    """In-memory stand-in for `RagService` used in API tests."""

    def __init__(self) -> None:
        """Initialise an empty in-memory store."""
        self.records: dict[str, DocumentRecord] = {}
        self.stream_payload: list[dict] = []
        self.ingest_failure: Exception | None = None
        self.list_failure: Exception | None = None
        self.delete_failure: Exception | None = None
        self.stream_failure: Exception | None = None

    def ingest(self, filename: str, payload: bytes) -> DocumentInfo:
        """Pretend to ingest a document and return canned metadata.

        @param filename File name supplied by the API.
        @param payload  Raw file bytes (ignored here).
        @returns Fake `DocumentInfo`.
        @raises Exception When `ingest_failure` is configured.
        """
        if self.ingest_failure is not None:
            raise self.ingest_failure
        document_id = f"doc-{len(self.records) + 1}"
        record = DocumentRecord(
            id=document_id,
            filename=filename,
            chunks=max(1, len(payload) // 100),
            uploaded_at=datetime.now(UTC),
        )
        self.records[document_id] = record
        return DocumentInfo(
            id=record.id,
            filename=record.filename,
            chunks=record.chunks,
            uploaded_at=record.uploaded_at,
        )

    def list_documents(self) -> list[DocumentRecord]:
        """Return the in-memory document records."""
        if self.list_failure is not None:
            raise self.list_failure
        return list(self.records.values())

    def get_document(self, document_id: str) -> DocumentDetailRecord | None:
        """Return a synthetic detail record (or None) for a document."""
        if document_id not in self.records:
            return None
        rec = self.records[document_id]
        return DocumentDetailRecord(
            id=rec.id,
            filename=rec.filename,
            chunks=rec.chunks,
            uploaded_at=rec.uploaded_at,
            kind="doc",
            language="text",
            repository_id=None,
            repository_name=None,
            preview="preview text",
        )

    def list_document_chunks(self, document_id: str) -> list[ChunkRecord]:
        """Return synthetic chunks for a known document, empty otherwise."""
        if document_id not in self.records:
            return []
        return [
            ChunkRecord(
                chunk_id=f"{document_id}:{index}",
                document_id=document_id,
                filename=self.records[document_id].filename,
                kind="doc",
                language="text",
                repository_id=None,
                repository_name=None,
                line_start=None,
                line_end=None,
                preview=f"chunk-{index} preview",
            )
            for index in range(self.records[document_id].chunks)
        ]

    def get_repository(self, repository_id: str) -> RepositoryRecord | None:
        """Return None — the fake does not maintain repository records."""
        _ = repository_id
        return None

    def list_repositories(self) -> list[tuple[str, str, int, datetime]]:
        """Return an empty repository list by default."""
        return []

    def search(self, **_kwargs: object) -> list[ScoredChunkRecord]:
        """Return synthetic search hits derived from the stored documents."""
        hits: list[ScoredChunkRecord] = []
        for record in self.records.values():
            chunk = ChunkRecord(
                chunk_id=f"{record.id}:0",
                document_id=record.id,
                filename=record.filename,
                kind="doc",
                language="text",
                repository_id=None,
                repository_name=None,
                line_start=None,
                line_end=None,
                preview="snippet",
            )
            hits.append(ScoredChunkRecord(chunk=chunk, score=0.42, distance=0.58))
        return hits

    def delete(self, document_id: str) -> int:
        """Forget a document by id and report how many chunks were removed."""
        if self.delete_failure is not None:
            raise self.delete_failure
        record = self.records.pop(document_id, None)
        return record.chunks if record else 0

    async def stream_chat(
        self, *, messages: list[dict], document_ids: list[str] | None
    ) -> AsyncIterator[dict]:
        """Replay the canned `stream_payload` as if it came from a real LLM."""
        _ = messages, document_ids
        for event in self.stream_payload:
            yield event
        if self.stream_failure is not None:
            raise self.stream_failure


@pytest.fixture
def fake_service() -> FakeRagService:
    """Provide a fresh stub and wire it via FastAPI dependency overrides.

    @returns The stub instance bound to the running app.
    """
    stub = FakeRagService()
    app.dependency_overrides[get_rag_service] = lambda: stub
    yield stub
    app.dependency_overrides.pop(get_rag_service, None)


@pytest.fixture
def client(fake_service: FakeRagService) -> TestClient:
    """Return a `TestClient` with the fake service already wired."""
    _ = fake_service
    return TestClient(app)


def test_upload_then_list(client: TestClient, fake_service: FakeRagService) -> None:
    """Uploading a TXT file should index it and surface it in the listing."""
    response = client.post(
        "/api/documents",
        files={"file": ("notes.txt", b"Some content " * 20, "text/plain")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["document"]["filename"] == "notes.txt"
    assert body["document"]["chunks"] >= 1
    assert len(fake_service.records) == 1

    listing = client.get("/api/documents").json()
    assert len(listing) == 1
    assert listing[0]["filename"] == "notes.txt"


def test_upload_rejects_unsupported_format(client: TestClient, fake_service: FakeRagService) -> None:
    """Unsupported formats raise 415 from the loader."""
    fake_service.ingest_failure = UnsupportedFormatError("nope")
    response = client.post(
        "/api/documents",
        files={"file": ("ignored.txt", b"junk", "text/plain")},
    )
    assert response.status_code == 415


def test_upload_rejects_empty_document(client: TestClient, fake_service: FakeRagService) -> None:
    """Empty documents raise 422."""
    fake_service.ingest_failure = EmptyDocumentError("blank")
    response = client.post(
        "/api/documents",
        files={"file": ("blank.txt", b"  ", "text/plain")},
    )
    assert response.status_code == 422


def test_delete_missing_returns_404(client: TestClient) -> None:
    """Deleting a non-existent id returns 404."""
    response = client.delete("/api/documents/does-not-exist")
    assert response.status_code == 404


def test_delete_existing_returns_204(client: TestClient) -> None:
    """Deleting an existing document returns 204."""
    upload = client.post(
        "/api/documents",
        files={"file": ("x.txt", b"hello", "text/plain")},
    ).json()
    response = client.delete(f"/api/documents/{upload['document']['id']}")
    assert response.status_code == 204


def test_chat_streams_ndjson(client: TestClient, fake_service: FakeRagService) -> None:
    """The chat endpoint streams the canned events as NDJSON."""
    fake_service.stream_payload = [
        {"type": "sources", "sources": [{"filename": "x.txt"}]},
        {"type": "delta", "content": "Hello "},
        {"type": "delta", "content": "world."},
        {"type": "done"},
    ]
    response = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.strip()]
    types = [eval_line(line)["type"] for line in lines]
    assert types == ["sources", "delta", "delta", "done"]


def test_upload_returns_502_on_embedding_failure(client: TestClient, fake_service: FakeRagService) -> None:
    """Ollama failures during ingest surface as 502 Bad Gateway."""
    fake_service.ingest_failure = EmbeddingError("ollama unreachable")
    response = client.post(
        "/api/documents",
        files={"file": ("x.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 502


def test_upload_returns_502_on_vector_store_failure(client: TestClient, fake_service: FakeRagService) -> None:
    """Chroma failures during ingest surface as 502 Bad Gateway."""
    fake_service.ingest_failure = VectorStoreError("chroma down")
    response = client.post(
        "/api/documents",
        files={"file": ("x.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 502


def test_upload_returns_500_on_storage_failure(client: TestClient, fake_service: FakeRagService) -> None:
    """Filesystem failures during ingest surface as 500 Internal Server Error."""
    fake_service.ingest_failure = StorageError("disk full")
    response = client.post(
        "/api/documents",
        files={"file": ("x.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 500


def test_list_returns_502_on_vector_store_failure(client: TestClient, fake_service: FakeRagService) -> None:
    """Chroma failures while listing surface as 502 Bad Gateway."""
    fake_service.list_failure = VectorStoreError("chroma down")
    response = client.get("/api/documents")
    assert response.status_code == 502


def test_delete_returns_502_on_vector_store_failure(client: TestClient, fake_service: FakeRagService) -> None:
    """Chroma failures while deleting surface as 502 Bad Gateway."""
    fake_service.delete_failure = VectorStoreError("chroma down")
    response = client.delete("/api/documents/any-id")
    assert response.status_code == 502


def test_chat_emits_error_event_on_embedding_failure(
    client: TestClient, fake_service: FakeRagService
) -> None:
    """Errors raised mid-stream are reported as a final `error` event, not HTTP 500."""
    fake_service.stream_payload = [{"type": "sources", "sources": []}]
    fake_service.stream_failure = EmbeddingError("retrieval boom")
    response = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200
    events = [eval_line(line) for line in response.text.splitlines() if line.strip()]
    assert events[-1]["type"] == "error"
    assert "retrieval boom" in events[-1]["message"]


def test_get_document_detail_returns_404_for_unknown(client: TestClient) -> None:
    """Unknown document id surfaces a 404 from /api/documents/{id}."""
    response = client.get("/api/documents/missing")
    assert response.status_code == 404


def test_get_document_detail_returns_payload(client: TestClient, fake_service: FakeRagService) -> None:
    """An ingested document is retrievable with its kind / language / preview."""
    _ = fake_service
    upload = client.post(
        "/api/documents",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    ).json()
    document_id = upload["document"]["id"]
    detail = client.get(f"/api/documents/{document_id}").json()
    assert detail["id"] == document_id
    assert detail["kind"] == "doc"
    assert detail["language"] == "text"
    assert detail["preview"]


def test_list_document_chunks_returns_one_per_chunk(client: TestClient, fake_service: FakeRagService) -> None:
    """The chunks endpoint returns one descriptor per stored chunk."""
    _ = fake_service
    upload = client.post(
        "/api/documents",
        files={"file": ("notes.txt", b"x" * 300, "text/plain")},
    ).json()
    chunks = client.get(f"/api/documents/{upload['document']['id']}/chunks").json()
    assert len(chunks) == upload["document"]["chunks"]
    assert all(item["preview"] for item in chunks)


def test_get_repository_returns_404_when_missing(client: TestClient) -> None:
    """Unknown repository id returns 404."""
    response = client.get("/api/repositories/missing")
    assert response.status_code == 404


def test_list_repository_files_returns_404_when_missing(client: TestClient) -> None:
    """Unknown repository id on /files also returns 404."""
    response = client.get("/api/repositories/missing/files")
    assert response.status_code == 404


def test_search_returns_scored_hits(client: TestClient, fake_service: FakeRagService) -> None:
    """/api/search returns scored chunks for ingested documents."""
    _ = fake_service
    client.post(
        "/api/documents",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    response = client.post("/api/search", json={"query": "hello"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(body["results"])
    assert body["results"][0]["score"] == 0.42
    assert body["results"][0]["filename"] == "notes.txt"


def test_search_rejects_empty_query(client: TestClient) -> None:
    """Empty query strings are rejected at the schema layer."""
    response = client.post("/api/search", json={"query": ""})
    assert response.status_code == 422


def eval_line(line: str) -> dict:
    """Parse an NDJSON line into a dict.

    @param line One NDJSON line from the chat stream.
    @returns Decoded event dict.
    """
    import json

    return json.loads(line)
