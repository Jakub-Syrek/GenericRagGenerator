"""ChromaDB-backed vector store with document-level metadata."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import chromadb
from chromadb.api.types import QueryResult


@dataclass(frozen=True)
class StoredChunk:
    """A single retrieved chunk along with its source metadata."""

    text: str
    document_id: str
    filename: str
    distance: float


@dataclass(frozen=True)
class DocumentRecord:
    """High-level document descriptor reconstructed from chunk metadata."""

    id: str
    filename: str
    chunks: int
    uploaded_at: datetime


class VectorStore:
    """Persistent ChromaDB collection holding embedded chunks."""

    _COLLECTION = "documents"

    def __init__(self, persist_dir: Path) -> None:
        """Open (or create) the on-disk Chroma collection.

        @param persist_dir Directory used by Chroma for persistence.
        """
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(self._COLLECTION)

    def add(
        self,
        *,
        document_id: str,
        filename: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> int:
        """Insert chunks belonging to one document.

        @param document_id Unique document identifier.
        @param filename    Original file name (stored as metadata).
        @param chunks      Text chunks (must align with `embeddings`).
        @param embeddings  Embedding vectors (must align with `chunks`).
        @returns Number of stored chunks.
        @raises ValueError When chunk and embedding counts disagree.
        """
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if not chunks:
            return 0
        uploaded_at = datetime.now(timezone.utc).isoformat()
        ids = [f"{document_id}:{index}" for index in range(len(chunks))]
        metadatas = [
            {
                "document_id": document_id,
                "filename": filename,
                "chunk_index": index,
                "uploaded_at": uploaded_at,
            }
            for index in range(len(chunks))
        ]
        self._collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return len(chunks)

    def query(
        self,
        *,
        query_embedding: list[float],
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[StoredChunk]:
        """Return the top-k chunks closest to the query embedding.

        @param query_embedding Embedded user question.
        @param top_k           Maximum number of chunks to return.
        @param document_ids    Optional filter restricting the search corpus.
        @returns Ordered list of `StoredChunk` from nearest to farthest.
        """
        where = self._build_where(document_ids)
        result: QueryResult = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
        )
        return list(self._materialize(result))

    def list_documents(self) -> list[DocumentRecord]:
        """Aggregate stored chunks into document-level records.

        @returns Document records sorted by upload time (newest first).
        """
        data = self._collection.get(include=["metadatas"])
        grouped: dict[str, dict] = {}
        for metadata in data.get("metadatas", []) or []:
            doc_id = str(metadata.get("document_id"))
            entry = grouped.setdefault(
                doc_id,
                {"filename": metadata.get("filename", ""), "chunks": 0, "uploaded_at": metadata.get("uploaded_at")},
            )
            entry["chunks"] += 1
        records = [
            DocumentRecord(
                id=doc_id,
                filename=entry["filename"],
                chunks=entry["chunks"],
                uploaded_at=datetime.fromisoformat(entry["uploaded_at"]),
            )
            for doc_id, entry in grouped.items()
            if entry.get("uploaded_at")
        ]
        records.sort(key=lambda record: record.uploaded_at, reverse=True)
        return records

    def delete(self, document_id: str) -> int:
        """Remove every chunk belonging to a document.

        @param document_id Identifier of the document to remove.
        @returns Number of chunks deleted.
        """
        existing = self._collection.get(where={"document_id": document_id}, include=[])
        ids = existing.get("ids", []) or []
        if not ids:
            return 0
        self._collection.delete(ids=ids)
        return len(ids)

    @staticmethod
    def _build_where(document_ids: list[str] | None) -> dict | None:
        """Construct a Chroma `where` filter for an optional document scope.

        @param document_ids Optional list of document identifiers.
        @returns Chroma-compatible filter dict, or None when unrestricted.
        """
        if not document_ids:
            return None
        if len(document_ids) == 1:
            return {"document_id": document_ids[0]}
        return {"document_id": {"$in": document_ids}}

    @staticmethod
    def _materialize(result: QueryResult) -> Iterable[StoredChunk]:
        """Convert Chroma's columnar query result into `StoredChunk` objects.

        @param result Raw Chroma query result.
        @returns Iterator over hydrated chunks for the first (and only) query.
        """
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        for text, metadata, distance in zip(documents, metadatas, distances):
            yield StoredChunk(
                text=text,
                document_id=str(metadata.get("document_id", "")),
                filename=str(metadata.get("filename", "")),
                distance=float(distance),
            )
