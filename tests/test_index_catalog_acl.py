"""ACL filter tests on `IndexCatalog`: owner scoping on read/delete paths."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.index_catalog import IndexCatalog


class _FakeCollection:
    """Minimal Chroma collection stand-in tracking ids + metadata."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        """Capture a static `(id, meta, text)` corpus."""
        self._ids: list[str] = [row["id"] for row in rows]
        self._metas: list[dict[str, Any]] = [row["meta"] for row in rows]
        self._texts: list[str] = [row.get("text", "") for row in rows]
        self.deleted: list[str] = []

    def get(
        self,
        *,
        where: dict[str, Any] | None = None,
        include: Any = None,
    ) -> dict[str, Any]:
        """Return rows whose metadata matches every key in `where`."""
        _ = include
        if not where:
            indexes = list(range(len(self._ids)))
        else:
            indexes = [
                idx for idx, meta in enumerate(self._metas) if all(meta.get(k) == v for k, v in where.items())
            ]
        return {
            "ids": [self._ids[i] for i in indexes],
            "metadatas": [self._metas[i] for i in indexes],
            "documents": [self._texts[i] for i in indexes],
        }

    def delete(self, *, ids: list[str]) -> None:
        """Record the ids requested for deletion (sufficient for our assertions)."""
        self.deleted.extend(ids)


def _uploaded_at() -> str:
    """Return one fixed ISO timestamp used by the fixtures."""
    return datetime(2026, 5, 24, 12, 0, tzinfo=UTC).isoformat()


def _doc_rows() -> list[dict[str, Any]]:
    """Build a two-owner, two-document corpus for the ACL tests."""
    when = _uploaded_at()
    return [
        {
            "id": "c-alice-1",
            "text": "alice chunk 1",
            "meta": {
                "doc_id": "doc-alice",
                "filename": "alice.txt",
                "uploaded_at": when,
                "owner": "alice",
            },
        },
        {
            "id": "c-alice-2",
            "text": "alice chunk 2",
            "meta": {
                "doc_id": "doc-alice",
                "filename": "alice.txt",
                "uploaded_at": when,
                "owner": "alice",
            },
        },
        {
            "id": "c-bob-1",
            "text": "bob chunk 1",
            "meta": {
                "doc_id": "doc-bob",
                "filename": "bob.txt",
                "uploaded_at": when,
                "owner": "bob",
            },
        },
    ]


def test_list_documents_filters_by_owner() -> None:
    """Each owner sees only their own documents; no filter sees everything."""
    catalog = IndexCatalog(_FakeCollection(_doc_rows()))
    alice = catalog.list_documents(owner="alice")
    bob = catalog.list_documents(owner="bob")
    everyone = catalog.list_documents()
    assert {summary.document_id for summary in alice} == {"doc-alice"}
    assert {summary.document_id for summary in bob} == {"doc-bob"}
    assert {summary.document_id for summary in everyone} == {"doc-alice", "doc-bob"}


def test_list_document_chunks_filters_by_owner() -> None:
    """A foreign owner gets an empty chunk list even if the doc id is correct."""
    catalog = IndexCatalog(_FakeCollection(_doc_rows()))
    assert catalog.list_document_chunks("doc-alice", owner="bob") == []
    assert len(catalog.list_document_chunks("doc-alice", owner="alice")) == 2


def test_delete_document_refuses_other_owner() -> None:
    """Deleting under the wrong owner removes nothing and reports zero."""
    collection = _FakeCollection(_doc_rows())
    catalog = IndexCatalog(collection)
    assert catalog.delete_document("doc-alice", owner="bob") == 0
    assert collection.deleted == []
    assert catalog.delete_document("doc-alice", owner="alice") == 2
    assert sorted(collection.deleted) == ["c-alice-1", "c-alice-2"]


def test_find_document_by_content_hash_scopes_dedup_per_owner() -> None:
    """The same payload uploaded by two owners produces two distinct docs."""
    when = _uploaded_at()
    rows = [
        {
            "id": "c-alice",
            "meta": {
                "doc_id": "doc-alice",
                "filename": "shared.txt",
                "uploaded_at": when,
                "owner": "alice",
                "content_hash": "abc",
            },
        },
        {
            "id": "c-bob",
            "meta": {
                "doc_id": "doc-bob",
                "filename": "shared.txt",
                "uploaded_at": when,
                "owner": "bob",
                "content_hash": "abc",
            },
        },
    ]
    catalog = IndexCatalog(_FakeCollection(rows))
    alice_hit = catalog.find_document_by_content_hash("abc", owner="alice")
    bob_hit = catalog.find_document_by_content_hash("abc", owner="bob")
    assert alice_hit is not None
    assert bob_hit is not None
    assert alice_hit.document_id == "doc-alice"
    assert bob_hit.document_id == "doc-bob"
