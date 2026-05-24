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
from app.services.rag_service import DocumentRecord, EmptyDocumentError


class FakeRagService:
    """In-memory stand-in for `RagService` used in API tests."""

    def __init__(self) -> None:
        """Initialise an empty in-memory store."""
        self.records: dict[str, DocumentRecord] = {}
        self.stream_payload: list[dict] = []
        self.ingest_failure: Exception | None = None

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
        return list(self.records.values())

    def delete(self, document_id: str) -> int:
        """Forget a document by id and report how many chunks were removed."""
        record = self.records.pop(document_id, None)
        return record.chunks if record else 0

    async def stream_chat(
        self, *, messages: list[dict], document_ids: list[str] | None
    ) -> AsyncIterator[dict]:
        """Replay the canned `stream_payload` as if it came from a real LLM."""
        _ = messages, document_ids
        for event in self.stream_payload:
            yield event


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


def eval_line(line: str) -> dict:
    """Parse an NDJSON line into a dict.

    @param line One NDJSON line from the chat stream.
    @returns Decoded event dict.
    """
    import json

    return json.loads(line)
