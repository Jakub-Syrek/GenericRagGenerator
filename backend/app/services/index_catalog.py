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

    def list_documents(self, *, owner: str | None = None) -> list[DocumentSummary]:
        """Aggregate stored chunks into document-level summaries.

        @param owner Optional owner filter; when set, rows whose
                     `owner` metadata differs are skipped.
        @returns Documents sorted by upload time (newest first).
        """
        data = self._collection.get(include=[IncludeEnum.metadatas])
        rows = self._filter_by_owner(data.get("metadatas") or [], owner)
        grouped = self._group_by(
            rows,
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

    def list_projects(self, *, owner: str | None = None) -> list[RepositorySummary]:
        """Aggregate stored chunks into project-level summaries.

        Re-uses `RepositorySummary` as the carrier type (same shape: id,
        name, chunks, uploaded_at) — projects and repositories are two
        upload flows over the same underlying notion of "collection".

        @param owner Optional owner filter; rows whose `owner` metadata
                     differs are skipped.
        @returns Projects sorted by upload time (newest first).
        """
        data = self._collection.get(include=[IncludeEnum.metadatas])
        rows = self._filter_by_owner(data.get("metadatas") or [], owner)
        grouped = self._group_by(
            rows,
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

    def list_project_chunks(self, project_id: str, *, owner: str | None = None) -> list[ChunkRow]:
        """Return every chunk belonging to one project.

        @param project_id Project identifier.
        @param owner      Optional owner filter; chunks not owned by it
                          are dropped (returns empty list if all dropped).
        @returns List of chunk rows (may be empty).
        """
        return self._fetch_rows(self._owner_scoped({"project_id": project_id}, owner))

    def delete_project(self, project_id: str, *, owner: str | None = None) -> int:
        """Remove every chunk of one project.

        @param project_id Project identifier.
        @param owner      Optional owner filter; only chunks owned by it
                          are removed (zero when ownership mismatches).
        @returns Number of chunks removed.
        """
        return self._delete_where(self._owner_scoped({"project_id": project_id}, owner))

    def list_repositories(self, *, owner: str | None = None) -> list[RepositorySummary]:
        """Aggregate stored chunks into repository-level summaries.

        @param owner Optional owner filter; rows whose `owner` metadata
                     differs are skipped.
        @returns Repositories sorted by upload time (newest first).
        """
        data = self._collection.get(include=[IncludeEnum.metadatas])
        rows = self._filter_by_owner(data.get("metadatas") or [], owner)
        grouped = self._group_by(
            rows,
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

    def list_document_chunks(self, document_id: str, *, owner: str | None = None) -> list[ChunkRow]:
        """Return every chunk belonging to one document, in storage order.

        @param document_id Document identifier.
        @param owner       Optional owner filter; empty list if mismatched.
        @returns List of chunk rows (may be empty).
        """
        return self._fetch_rows(self._owner_scoped({"doc_id": document_id}, owner))

    def list_repository_chunks(self, repository_id: str, *, owner: str | None = None) -> list[ChunkRow]:
        """Return every chunk belonging to one repository.

        @param repository_id Repository identifier.
        @param owner         Optional owner filter; empty list if mismatched.
        @returns List of chunk rows (may be empty).
        """
        return self._fetch_rows(self._owner_scoped({"repository_id": repository_id}, owner))

    def delete_document(self, document_id: str, *, owner: str | None = None) -> int:
        """Remove every chunk of one document.

        @param document_id Document identifier.
        @param owner       Optional owner filter; zero when not the owner.
        @returns Number of chunks removed.
        """
        return self._delete_where(self._owner_scoped({"doc_id": document_id}, owner))

    def delete_repository(self, repository_id: str, *, owner: str | None = None) -> int:
        """Remove every chunk of one repository.

        @param repository_id Repository identifier.
        @param owner         Optional owner filter; zero when not the owner.
        @returns Number of chunks removed.
        """
        return self._delete_where(self._owner_scoped({"repository_id": repository_id}, owner))

    def find_document_by_content_hash(
        self,
        content_hash: str,
        *,
        owner: str | None = None,
    ) -> DocumentSummary | None:
        """Return the existing document with the given `content_hash`, if any.

        Used by the ingest path to skip re-embedding a payload that's
        already been indexed. Returns the first match; uniqueness is
        enforced at write time (we only store a hash when no doc with
        it exists yet).

        @param content_hash SHA-256 hex digest of the raw payload bytes.
        @param owner        Optional owner filter; treats other owners'
                            uploads as invisible (no dedup hit).
        @returns `DocumentSummary` of the prior upload, or `None`.
        """
        data = self._collection.get(
            where=self._owner_scoped({"content_hash": content_hash}, owner),
            include=[IncludeEnum.metadatas],
        )
        metadatas = data.get("metadatas") or []
        if not metadatas:
            return None
        head = metadatas[0]
        doc_id = _doc_id(head)
        if not doc_id:
            return None
        uploaded_at = head.get("uploaded_at")
        if not uploaded_at:
            return None
        return DocumentSummary(
            document_id=doc_id,
            filename=str(head.get("filename", "")),
            chunks=len(metadatas),
            uploaded_at=datetime.fromisoformat(str(uploaded_at)),
        )

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
    def _owner_scoped(where: dict[str, Any], owner: str | None) -> dict[str, Any]:
        """Add an `owner` clause to a Chroma `where` filter when set.

        @param where Base `where` filter.
        @param owner Owner principal name, or `None` for no scoping.
        @returns The original dict (no copy) when `owner` is None,
                 otherwise a new dict with `owner` appended.
        """
        if not owner:
            return where
        return {**where, "owner": owner}

    @staticmethod
    def _filter_by_owner(
        rows: list[dict[str, Any]],
        owner: str | None,
    ) -> list[dict[str, Any]]:
        """Drop rows that don't match the requested owner.

        Used by aggregation methods that pull the whole collection and
        group in Python (Chroma's `where` would force a second round-
        trip per principal — cheaper to filter once here).

        @param rows  Raw metadata rows.
        @param owner Owner principal name, or `None` for no scoping.
        @returns Filtered list (unchanged when `owner` is None).
        """
        if not owner:
            return rows
        return [meta for meta in rows if meta.get("owner") == owner]

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
