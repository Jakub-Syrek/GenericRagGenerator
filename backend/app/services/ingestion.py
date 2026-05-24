"""Document ingestion pipeline: parse -> chunk -> embed -> store."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..models.schemas import DocumentInfo
from .chunker import TextChunker
from .document_loader import DocumentLoader
from .embedder import OllamaEmbedder
from .vector_store import VectorStore


class EmptyDocumentError(ValueError):
    """Raised when an uploaded document yields no extractable text."""


class IngestionService:
    """Coordinate parsing, chunking, embedding and storage of one document."""

    def __init__(
        self,
        *,
        loader: DocumentLoader,
        chunker: TextChunker,
        embedder: OllamaEmbedder,
        store: VectorStore,
        upload_dir: Path,
    ) -> None:
        """Inject pipeline collaborators.

        @param loader     Document text extractor.
        @param chunker    Text splitter.
        @param embedder   Embedding client.
        @param store      Vector store sink.
        @param upload_dir Directory where raw uploads are archived.
        """
        self._loader = loader
        self._chunker = chunker
        self._embedder = embedder
        self._store = store
        self._upload_dir = upload_dir

    def ingest(self, filename: str, payload: bytes) -> DocumentInfo:
        """Run the full ingestion pipeline for one uploaded file.

        @param filename Original file name (used for extension + metadata).
        @param payload  Raw bytes of the uploaded file.
        @returns Metadata describing the freshly indexed document.
        @raises EmptyDocumentError When no text could be extracted.
        """
        text = self._loader.load(filename, payload)
        if not text:
            raise EmptyDocumentError("No text could be extracted from the file.")

        chunks = self._chunker.split(text)
        if not chunks:
            raise EmptyDocumentError("Document produced no usable chunks.")

        embeddings = self._embedder.embed(chunks)
        document_id = uuid.uuid4().hex
        self._persist_raw(document_id, filename, payload)
        stored = self._store.add(
            document_id=document_id,
            filename=filename,
            chunks=chunks,
            embeddings=embeddings,
        )
        return DocumentInfo(
            id=document_id,
            filename=filename,
            chunks=stored,
            uploaded_at=datetime.now(timezone.utc),
        )

    def _persist_raw(self, document_id: str, filename: str, payload: bytes) -> None:
        """Archive the raw upload on disk for traceability.

        @param document_id Unique document id.
        @param filename    Original file name.
        @param payload     Raw file bytes.
        """
        suffix = Path(filename).suffix.lower()
        destination = self._upload_dir / f"{document_id}{suffix}"
        destination.write_bytes(payload)
