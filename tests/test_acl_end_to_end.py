"""End-to-end ACL tests: two JWT users cannot see each other's uploads.

Exercises the full Principal → `_owner_for` → service → `IndexCatalog`
chain by spinning up the real FastAPI app with auth configured, then
injecting a fake `RagService` that stores `owner` on every record.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_rag_service
from app.main import app
from app.models.schemas import DocumentInfo
from app.services.rag_service import DocumentDetailRecord, DocumentRecord

_JWT_SECRET = "secret-for-tests"  # pragma: allowlist secret
_AUTH_PASSWORD = "letmein"  # pragma: allowlist secret


class _AclFakeService:
    """RagService stand-in that honours the `owner` kwarg on every path."""

    def __init__(self) -> None:
        """Initialise an empty owner-keyed store."""
        self.records: dict[str, tuple[DocumentRecord, str | None]] = {}

    def ingest(
        self,
        filename: str,
        payload: bytes,
        *,
        owner: str | None = None,
    ) -> tuple[DocumentInfo, bool]:
        """Index a document under the principal's owner stamp."""
        document_id = f"doc-{len(self.records) + 1}"
        record = DocumentRecord(
            id=document_id,
            filename=filename,
            chunks=max(1, len(payload) // 100),
            uploaded_at=datetime.now(UTC),
        )
        self.records[document_id] = (record, owner)
        info = DocumentInfo(
            id=record.id,
            filename=record.filename,
            chunks=record.chunks,
            uploaded_at=record.uploaded_at,
        )
        return info, False

    def list_documents(self, *, owner: str | None = None) -> list[DocumentRecord]:
        """Return only the records matching the supplied owner (or all when None)."""
        return [rec for rec, rec_owner in self.records.values() if owner is None or rec_owner == owner]

    def get_document(
        self,
        document_id: str,
        *,
        owner: str | None = None,
    ) -> DocumentDetailRecord | None:
        """Return a detail record only when the owner matches."""
        if document_id not in self.records:
            return None
        rec, rec_owner = self.records[document_id]
        if owner is not None and rec_owner != owner:
            return None
        return DocumentDetailRecord(
            id=rec.id,
            filename=rec.filename,
            chunks=rec.chunks,
            uploaded_at=rec.uploaded_at,
            kind="doc",
            language="text",
            repository_id=None,
            repository_name=None,
            preview="preview",
        )

    def delete(self, document_id: str, *, owner: str | None = None) -> int:
        """Forget a document only when the owner matches."""
        if document_id not in self.records:
            return 0
        rec, rec_owner = self.records[document_id]
        if owner is not None and rec_owner != owner:
            return 0
        self.records.pop(document_id)
        return rec.chunks

    # The router pulls these endpoints regardless of test scope — keep them
    # stub-friendly so the dependency override covers every route.
    def list_document_chunks(self, document_id: str, **_kwargs: object) -> list[Any]:
        """Unused in these tests; returns empty for any document."""
        _ = document_id
        return []

    def get_repository(self, *_args: object, **_kwargs: object) -> None:
        """Unused; return None to mimic an empty repository scope."""
        return None

    def list_repositories(self, **_kwargs: object) -> list:
        """Unused; return empty."""
        return []

    async def stream_chat(self, **_kwargs: object) -> AsyncIterator[dict]:
        """Unused; emit one sentinel event."""
        yield {"type": "done"}

    def search(self, **_kwargs: object) -> list:
        """Unused; return empty."""
        return []


def _issue_token(subject: str, scopes: tuple[str, ...] = ()) -> str:
    """Mint a HS256 JWT carrying `sub` + `scopes` for end-to-end use."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + 60,
        "scopes": list(scopes),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch) -> _AclFakeService:
    """Wire the ACL-aware fake into the app + configure auth env vars."""
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    monkeypatch.setenv("AUTH_PASSWORD", _AUTH_PASSWORD)
    monkeypatch.delenv("API_KEY", raising=False)
    get_settings.cache_clear()
    stub = _AclFakeService()
    app.dependency_overrides[get_rag_service] = lambda: stub
    yield stub
    app.dependency_overrides.pop(get_rag_service, None)
    get_settings.cache_clear()


@pytest.fixture
def client(service: _AclFakeService) -> TestClient:
    """`TestClient` with the ACL-aware fake already wired."""
    _ = service
    return TestClient(app)


def _bearer(token: str) -> dict[str, str]:
    """Build an Authorization header dict from a bearer token."""
    return {"Authorization": f"Bearer {token}"}


def test_two_users_cannot_see_each_others_documents(client: TestClient, service: _AclFakeService) -> None:
    """Alice and Bob each upload one document; the listing is owner-scoped."""
    alice = _issue_token("alice")
    bob = _issue_token("bob")

    upload_alice = client.post(
        "/api/documents",
        files={"file": ("alice.txt", b"alice content", "text/plain")},
        headers=_bearer(alice),
    )
    upload_bob = client.post(
        "/api/documents",
        files={"file": ("bob.txt", b"bob content", "text/plain")},
        headers=_bearer(bob),
    )
    assert upload_alice.status_code == 201
    assert upload_bob.status_code == 201
    assert len(service.records) == 2

    alice_listing = client.get("/api/documents", headers=_bearer(alice)).json()
    bob_listing = client.get("/api/documents", headers=_bearer(bob)).json()
    assert {row["filename"] for row in alice_listing} == {"alice.txt"}
    assert {row["filename"] for row in bob_listing} == {"bob.txt"}


def test_user_cannot_get_or_delete_other_users_document(client: TestClient, service: _AclFakeService) -> None:
    """Bob's GET and DELETE on Alice's document return 404, not the data."""
    alice = _issue_token("alice")
    bob = _issue_token("bob")
    alice_doc = client.post(
        "/api/documents",
        files={"file": ("alice.txt", b"alice content", "text/plain")},
        headers=_bearer(alice),
    ).json()["document"]["id"]

    assert client.get(f"/api/documents/{alice_doc}", headers=_bearer(bob)).status_code == 404
    assert client.delete(f"/api/documents/{alice_doc}", headers=_bearer(bob)).status_code == 404
    # Alice's record is still there.
    assert client.get(f"/api/documents/{alice_doc}", headers=_bearer(alice)).status_code == 200
    assert len(service.records) == 1


def test_admin_jwt_scope_bypasses_owner_filter(client: TestClient, service: _AclFakeService) -> None:
    """A JWT with the `admin` scope sees every owner's documents."""
    alice = _issue_token("alice")
    bob = _issue_token("bob")
    admin = _issue_token("ops", scopes=("admin",))
    client.post(
        "/api/documents",
        files={"file": ("alice.txt", b"alice content", "text/plain")},
        headers=_bearer(alice),
    )
    client.post(
        "/api/documents",
        files={"file": ("bob.txt", b"bob content", "text/plain")},
        headers=_bearer(bob),
    )

    admin_listing = client.get("/api/documents", headers=_bearer(admin)).json()
    assert {row["filename"] for row in admin_listing} == {"alice.txt", "bob.txt"}
