"""Read/write repository over the Chroma metadata layer (Repository pattern).

Hides Chroma-specific calls behind a domain-typed surface so the rest of
the codebase never imports `chromadb` directly. Single source of truth
for every metadata aggregation and every delete-by-scope path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar

from chromadb.api.types import IncludeEnum


@dataclass(frozen=True)
class DocumentSummary:
    """Aggregated document descriptor reconstructed from chunk metadata."""

    document_id: str
    filename: str
    chunks: int
    uploaded_at: datetime


@dataclass(frozen=True)
class RepositorySummary:
    """Aggregated repository descriptor reconstructed from chunk metadata."""

    repository_id: str
    name: str
    chunks: int
    uploaded_at: datetime


@dataclass(frozen=True)
class ChunkRow:
    """Raw chunk row pulled from Chroma plus its decoded metadata."""

    chunk_id: str
    text: str
    metadata: dict[str, Any]


class IndexCatalog:
    """Repository façade over the ChromaDB metadata layer.

    Every read- or delete-by-scope path goes through this class. The
    `RagService` no longer touches Chroma directly: it asks the catalog
    for the data it needs and gets back domain types.
    """

    _CHUNK_INCLUDE: ClassVar[list[IncludeEnum]] = [
        IncludeEnum.metadatas,
        IncludeEnum.documents,
    ]

    def __init__(self, collection: Any) -> None:
        """Wrap an open Chroma collection.

        @param collection Open `chromadb` collection handle.
        """
        self._collection = collection

    def list_documents(self) -> list[DocumentSummary]:
        """Aggregate stored chunks into document-level summaries.

        @returns Documents sorted by upload time (newest first).
        """
        data = self._collection.get(include=[IncludeEnum.metadatas])
        grouped = self._group_by(
            (data.get("metadatas") or []),
            key=lambda meta: _doc_id(meta),
            seed=lambda meta: {
                "filename": str(meta.get("filename", "")),
                "uploaded_at": meta.get("uploaded_at"),
                "chunks": 0,
            },
        )
        summaries = [
            DocumentSummary(
                document_id=doc_id,
                filename=entry["filename"],
                chunks=entry["chunks"],
                uploaded_at=datetime.fromisoformat(entry["uploaded_at"]),
            )
            for doc_id, entry in grouped.items()
            if entry.get("uploaded_at")
        ]
        summaries.sort(key=lambda item: item.uploaded_at, reverse=True)
        return summaries

    def list_projects(self) -> list[RepositorySummary]:
        """Aggregate stored chunks into project-level summaries.

        Re-uses `RepositorySummary` as the carrier type (same shape: id,
        name, chunks, uploaded_at) — projects and repositories are two
        upload flows over the same underlying notion of "collection".

        @returns Projects sorted by upload time (newest first).
        """
        data = self._collection.get(include=[IncludeEnum.metadatas])
        grouped = self._group_by(
            (data.get("metadatas") or []),
            key=lambda meta: meta.get("project_id"),
            seed=lambda meta: {
                "name": str(meta.get("project_name", "")),
                "uploaded_at": meta.get("uploaded_at"),
                "chunks": 0,
            },
        )
        summaries = [
            RepositorySummary(
                repository_id=str(proj_id),
                name=entry["name"],
                chunks=entry["chunks"],
                uploaded_at=datetime.fromisoformat(entry["uploaded_at"]),
            )
            for proj_id, entry in grouped.items()
            if proj_id and entry.get("uploaded_at")
        ]
        summaries.sort(key=lambda item: item.uploaded_at, reverse=True)
        return summaries

    def list_project_chunks(self, project_id: str) -> list[ChunkRow]:
        """Return every chunk belonging to one project.

        @param project_id Project identifier.
        @returns List of chunk rows (may be empty).
        """
        return self._fetch_rows({"project_id": project_id})

    def delete_project(self, project_id: str) -> int:
        """Remove every chunk of one project.

        @param project_id Project identifier.
        @returns Number of chunks removed.
        """
        return self._delete_where({"project_id": project_id})

    def list_repositories(self) -> list[RepositorySummary]:
        """Aggregate stored chunks into repository-level summaries.

        @returns Repositories sorted by upload time (newest first).
        """
        data = self._collection.get(include=[IncludeEnum.metadatas])
        grouped = self._group_by(
            (data.get("metadatas") or []),
            key=lambda meta: meta.get("repository_id"),
            seed=lambda meta: {
                "name": str(meta.get("repository_name", "")),
                "uploaded_at": meta.get("uploaded_at"),
                "chunks": 0,
            },
        )
        summaries = [
            RepositorySummary(
                repository_id=str(repo_id),
                name=entry["name"],
                chunks=entry["chunks"],
                uploaded_at=datetime.fromisoformat(entry["uploaded_at"]),
            )
            for repo_id, entry in grouped.items()
            if repo_id and entry.get("uploaded_at")
        ]
        summaries.sort(key=lambda item: item.uploaded_at, reverse=True)
        return summaries

    def list_document_chunks(self, document_id: str) -> list[ChunkRow]:
        """Return every chunk belonging to one document, in storage order.

        @param document_id Document identifier.
        @returns List of chunk rows (may be empty).
        """
        return self._fetch_rows({"doc_id": document_id})

    def list_repository_chunks(self, repository_id: str) -> list[ChunkRow]:
        """Return every chunk belonging to one repository.

        @param repository_id Repository identifier.
        @returns List of chunk rows (may be empty).
        """
        return self._fetch_rows({"repository_id": repository_id})

    def delete_document(self, document_id: str) -> int:
        """Remove every chunk of one document.

        @param document_id Document identifier.
        @returns Number of chunks removed.
        """
        return self._delete_where({"doc_id": document_id})

    def delete_repository(self, repository_id: str) -> int:
        """Remove every chunk of one repository.

        @param repository_id Repository identifier.
        @returns Number of chunks removed.
        """
        return self._delete_where({"repository_id": repository_id})

    def all_chunks(self) -> list[ChunkRow]:
        """Return every chunk in the collection (metadata + body).

        Used by the BM25 layer to build its in-memory inverted index. The
        result is one list — for very large indices the caller is
        responsible for caching or chunking the consumption.

        @returns Ordered list of every `ChunkRow` (storage order).
        """
        data = self._collection.get(include=self._CHUNK_INCLUDE)
        ids = data.get("ids", []) or []
        metadatas = data.get("metadatas") or []
        documents = data.get("documents") or []
        return [
            ChunkRow(chunk_id=chunk_id, text=str(text or ""), metadata=dict(metadata or {}))
            for chunk_id, metadata, text in zip(ids, metadatas, documents, strict=False)
        ]

    def wipe(self) -> int:
        """Remove every chunk in the index (administrative reset).

        @returns Number of chunks removed.
        """
        existing = self._collection.get(include=[])
        ids = existing.get("ids", []) or []
        if not ids:
            return 0
        self._collection.delete(ids=ids)
        return len(ids)

    def _fetch_rows(self, where: dict[str, Any]) -> list[ChunkRow]:
        """Pull chunks from Chroma with metadata + text body.

        @param where Chroma `where` filter.
        @returns Ordered list of `ChunkRow`.
        """
        data = self._collection.get(where=where, include=self._CHUNK_INCLUDE)
        ids = data.get("ids", []) or []
        metadatas = data.get("metadatas") or []
        documents = data.get("documents") or []
        return [
            ChunkRow(chunk_id=chunk_id, text=str(text or ""), metadata=dict(metadata or {}))
            for chunk_id, metadata, text in zip(ids, metadatas, documents, strict=False)
        ]

    def _delete_where(self, where: dict[str, Any]) -> int:
        """Delete chunks matching a `where` filter and report how many.

        @param where Chroma `where` filter.
        @returns Number of chunks removed.
        """
        existing = self._collection.get(where=where, include=[])
        ids = existing.get("ids", []) or []
        if not ids:
            return 0
        self._collection.delete(ids=ids)
        return len(ids)

    @staticmethod
    def _group_by(
        rows: list[dict[str, Any]],
        *,
        key: Any,
        seed: Any,
    ) -> dict[str, dict[str, Any]]:
        """Group raw metadata rows into accumulator dicts.

        @param rows Raw metadata rows.
        @param key  Callable extracting the grouping key from a row.
        @param seed Callable building the initial accumulator dict from a row.
        @returns Dict from key to accumulator with `chunks` incremented.
        """
        grouped: dict[str, dict[str, Any]] = {}
        for meta in rows:
            value = key(meta)
            if not value:
                continue
            entry = grouped.setdefault(str(value), seed(meta))
            entry["chunks"] += 1
        return grouped


def _doc_id(meta: dict[str, Any]) -> str:
    """Pick the document id from a Chroma metadata row.

    LlamaIndex stores it under `doc_id`, occasionally falls back to
    `ref_doc_id` for chunked nodes; both are accepted here.

    @param meta Chroma metadata row.
    @returns Document id, or an empty string when neither key is present.
    """
    return str(meta.get("doc_id") or meta.get("ref_doc_id") or "")
