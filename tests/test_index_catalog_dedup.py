"""Tests for content-hash dedup lookup on `IndexCatalog`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.index_catalog import IndexCatalog


class _FakeCollection:
    """Minimal Chroma collection stand-in for catalog tests."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        """Capture a static row set and record `get()` filters seen.

        @param rows Pre-populated metadata rows.
        """
        self._rows = rows
        self.last_where: dict[str, Any] | None = None

    def get(
        self,
        *,
        where: dict[str, Any] | None = None,
        include: Any = None,
    ) -> dict[str, Any]:
        """Return rows matching a single equality `where` filter."""
        _ = include
        self.last_where = where
        if not where:
            return {"ids": [], "metadatas": list(self._rows)}
        matched = [row for row in self._rows if all(row.get(k) == v for k, v in where.items())]
        return {"ids": [f"id-{i}" for i in range(len(matched))], "metadatas": matched}


def test_find_document_by_content_hash_returns_none_when_unknown() -> None:
    """Missing hash returns `None`, not an exception."""
    catalog = IndexCatalog(_FakeCollection([]))
    assert catalog.find_document_by_content_hash("deadbeef") is None


def test_find_document_by_content_hash_returns_summary_on_hit() -> None:
    """A matching content_hash produces a populated `DocumentSummary`."""
    uploaded_at = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    rows = [
        {
            "doc_id": "doc-1",
            "filename": "notes.txt",
            "uploaded_at": uploaded_at.isoformat(),
            "content_hash": "abc123",
        },
        {
            "doc_id": "doc-1",
            "filename": "notes.txt",
            "uploaded_at": uploaded_at.isoformat(),
            "content_hash": "abc123",
        },
    ]
    collection = _FakeCollection(rows)
    catalog = IndexCatalog(collection)
    summary = catalog.find_document_by_content_hash("abc123")
    assert summary is not None
    assert summary.document_id == "doc-1"
    assert summary.filename == "notes.txt"
    assert summary.chunks == 2
    assert summary.uploaded_at == uploaded_at
    assert collection.last_where == {"content_hash": "abc123"}
