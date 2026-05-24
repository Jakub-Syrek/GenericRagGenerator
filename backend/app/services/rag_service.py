"""LlamaIndex-backed RAG service: ingest, retrieve, stream chat answers.

Replaces the hand-rolled chunker / embedder / vector store / ingestion / chain
modules with the equivalent LlamaIndex building blocks. ChromaDB is still the
persistence layer; we keep a direct reference to its collection so document-
level listing and deletion remain trivial.
"""

from __future__ import annotations

import uuid
import zipfile
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import chromadb
from chromadb.api.types import IncludeEnum
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.llms import ChatMessage as LiChatMessage
from llama_index.core.llms import MessageRole
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import NodeWithScore
from llama_index.core.vector_stores import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.chroma import ChromaVectorStore
from pydantic import Field

from ..config import Settings
from ..models.schemas import DocumentInfo
from .document_loader import DocumentLoader, Kind, UnsupportedFormatError

COLLECTION_NAME = "documents"

MAX_REPO_FILE_BYTES = 10 * 1024 * 1024
MAX_REPO_TOTAL_BYTES = 100 * 1024 * 1024
MAX_REPO_MEMBERS = 5000

DEFAULT_IGNORE: tuple[str, ...] = (
    ".git/",
    "node_modules/",
    "__pycache__/",
    "dist/",
    "build/",
    ".venv/",
    "venv/",
    "target/",
    "vendor/",
    ".next/",
    ".idea/",
    ".vscode/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".gradle/",
    ".DS_Store",
    "Thumbs.db",
)

SYSTEM_PROMPT = (
    "You are a precise assistant answering questions strictly from the supplied "
    "document excerpts. If the answer is not contained in the context, reply that "
    "the documents do not cover it. Cite source filenames in parentheses when "
    "relevant. Respond in the user's language."
)

_ROLE_MAP: dict[str, MessageRole] = {
    "user": MessageRole.USER,
    "assistant": MessageRole.ASSISTANT,
    "system": MessageRole.SYSTEM,
}


class _PrefixedOllamaEmbedding(OllamaEmbedding):
    """`OllamaEmbedding` subclass that prepends asymmetric task prefixes.

    Models such as `nomic-embed-text` expect different prefixes on query vs
    document inputs (`search_query: ` / `search_document: `). LlamaIndex's
    stock client passes the raw text, so we wrap every embedding call here.
    """

    query_prefix: str = Field(default="", description="Prefix prepended to query inputs.")
    document_prefix: str = Field(default="", description="Prefix prepended to document inputs.")

    def _get_query_embedding(self, query: str) -> list[float]:
        """Embed a single query with the configured prefix.

        @param query Raw query text.
        @returns Embedding vector.
        """
        return super()._get_query_embedding(f"{self.query_prefix}{query}")

    async def _aget_query_embedding(self, query: str) -> list[float]:
        """Async variant of `_get_query_embedding`.

        @param query Raw query text.
        @returns Embedding vector.
        """
        return await super()._aget_query_embedding(f"{self.query_prefix}{query}")

    def _get_text_embedding(self, text: str) -> list[float]:
        """Embed a single document chunk with the configured prefix.

        @param text Raw document text.
        @returns Embedding vector.
        """
        return super()._get_text_embedding(f"{self.document_prefix}{text}")

    async def _aget_text_embedding(self, text: str) -> list[float]:
        """Async variant of `_get_text_embedding`.

        @param text Raw document text.
        @returns Embedding vector.
        """
        return await super()._aget_text_embedding(f"{self.document_prefix}{text}")

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of document chunks with the configured prefix.

        @param texts Raw document texts.
        @returns List of embedding vectors aligned with `texts`.
        """
        return super()._get_text_embeddings([f"{self.document_prefix}{text}" for text in texts])

    async def _aget_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Async variant of `_get_text_embeddings`.

        @param texts Raw document texts.
        @returns List of embedding vectors aligned with `texts`.
        """
        return await super()._aget_text_embeddings([f"{self.document_prefix}{text}" for text in texts])


class EmptyDocumentError(ValueError):
    """Raised when an uploaded document yields no extractable text."""


class EmbeddingError(RuntimeError):
    """Raised when Ollama embedding generation or retrieval fails."""


class ChatGenerationError(RuntimeError):
    """Raised when Ollama chat generation fails."""


class VectorStoreError(RuntimeError):
    """Raised when a ChromaDB operation fails."""


class StorageError(OSError):
    """Raised when persisting raw uploads to disk fails."""


class UnsafeArchiveError(ValueError):
    """Raised when an archive contains unsafe entries (traversal, symlinks...)."""


class RepositoryError(ValueError):
    """Raised when a repository archive yields no usable files."""


@dataclass(frozen=True)
class IngestedFile:
    """Per-file ingest record for an uploaded repository."""

    document_id: str
    path: str
    kind: Kind
    language: str
    chunks: int


@dataclass(frozen=True)
class SkippedFile:
    """Per-file skip record for an uploaded repository."""

    path: str
    reason: str


@dataclass(frozen=True)
class RepositoryRecord:
    """High-level record of a freshly ingested repository archive."""

    id: str
    name: str
    files: list[IngestedFile] = field(default_factory=list)
    skipped: list[SkippedFile] = field(default_factory=list)
    uploaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def files_indexed(self) -> int:
        """Number of files successfully ingested from the archive."""
        return len(self.files)

    @property
    def total_chunks(self) -> int:
        """Total number of chunks produced across all ingested files."""
        return sum(item.chunks for item in self.files)


@dataclass(frozen=True)
class DocumentRecord:
    """High-level document descriptor reconstructed from chunk metadata."""

    id: str
    filename: str
    chunks: int
    uploaded_at: datetime


class RagService:
    """End-to-end RAG: ingest documents, retrieve context, stream answers."""

    def __init__(self, settings: Settings, loader: DocumentLoader) -> None:
        """Wire LlamaIndex with Ollama + Chroma using the provided settings.

        @param settings Application settings.
        @param loader   Raw-file text extractor.
        """
        self._settings = settings
        self._loader = loader
        self._upload_dir = settings.upload_dir

        try:
            self._chroma_client = chromadb.PersistentClient(path=str(settings.chroma_dir))
            self._collection = self._chroma_client.get_or_create_collection(COLLECTION_NAME)
        except Exception as exc:
            raise VectorStoreError(f"Failed to open Chroma collection: {exc}") from exc
        vector_store = ChromaVectorStore(chroma_collection=self._collection)

        self._embed_model = _PrefixedOllamaEmbedding(
            model_name=settings.embedding_model,
            base_url=settings.ollama_host,
            query_prefix=settings.embedding_query_prefix,
            document_prefix=settings.embedding_document_prefix,
        )
        self._llm = Ollama(
            model=settings.chat_model,
            base_url=settings.ollama_host,
            request_timeout=120.0,
        )
        self._splitter = SentenceSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        self._index = VectorStoreIndex.from_vector_store(
            vector_store,
            embed_model=self._embed_model,
            storage_context=storage_context,
        )

    def ingest(self, filename: str, payload: bytes) -> DocumentInfo:
        """Parse, chunk, embed and persist one uploaded file.

        @param filename Original file name (used for extension + metadata).
        @param payload  Raw bytes of the uploaded file.
        @returns Metadata describing the freshly indexed document.
        @raises EmptyDocumentError When the file yields no usable text.
        """
        loaded = self._loader.load(filename, payload)
        if not loaded.text:
            raise EmptyDocumentError("No text could be extracted from the file.")

        document_id = uuid.uuid4().hex
        uploaded_at = datetime.now(UTC)
        document = Document(
            id_=document_id,
            text=loaded.text,
            metadata={
                "filename": filename,
                "uploaded_at": uploaded_at.isoformat(),
                "kind": loaded.kind,
                "language": loaded.language,
            },
            excluded_embed_metadata_keys=["uploaded_at", "kind", "language"],
            excluded_llm_metadata_keys=["uploaded_at"],
        )
        nodes = self._splitter.get_nodes_from_documents([document])
        if not nodes:
            raise EmptyDocumentError("Document produced no usable chunks.")

        try:
            self._index.insert_nodes(nodes)
        except Exception as exc:
            raise EmbeddingError(f"Failed to embed and store chunks: {exc}") from exc

        try:
            self._persist_raw(document_id, filename, payload)
        except OSError as exc:
            raise StorageError(f"Failed to archive raw upload: {exc}") from exc

        return DocumentInfo(
            id=document_id,
            filename=filename,
            chunks=len(nodes),
            uploaded_at=uploaded_at,
        )

    def list_documents(self) -> list[DocumentRecord]:
        """Aggregate stored chunks into document-level records.

        @returns Document records sorted by upload time (newest first).
        """
        try:
            data = self._collection.get(include=[IncludeEnum.metadatas])
        except Exception as exc:
            raise VectorStoreError(f"Failed to list documents: {exc}") from exc
        grouped: dict[str, dict] = {}
        for metadata in data.get("metadatas", []) or []:
            doc_id = metadata.get("doc_id") or metadata.get("ref_doc_id")
            if not doc_id:
                continue
            entry = grouped.setdefault(
                str(doc_id),
                {
                    "filename": metadata.get("filename", ""),
                    "chunks": 0,
                    "uploaded_at": metadata.get("uploaded_at"),
                },
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
        try:
            existing = self._collection.get(where={"doc_id": document_id}, include=[])
            ids = existing.get("ids", []) or []
            if not ids:
                return 0
            self._collection.delete(ids=ids)
        except Exception as exc:
            raise VectorStoreError(f"Failed to delete document {document_id}: {exc}") from exc
        return len(ids)

    def ingest_repository(self, archive_name: str, payload: bytes) -> RepositoryRecord:
        """Open a ZIP archive and index every supported file inside.

        @param archive_name Original archive file name (used for repository name).
        @param payload      Raw ZIP bytes.
        @returns Record describing what was indexed and skipped.
        @raises UnsafeArchiveError On path traversal, symlinks or oversize totals.
        @raises RepositoryError    When no usable files are found.
        @raises EmbeddingError     When the underlying embedding call fails.
        @raises StorageError       When archiving the raw upload fails.
        """
        archive = self._open_zip(payload)
        members = self._screen_archive(archive)
        prefix = self._zip_common_prefix(members)
        repository_id = uuid.uuid4().hex
        repository_name = Path(archive_name).stem
        uploaded_at = datetime.now(UTC)
        documents, skipped = self._collect_repository_documents(
            archive=archive,
            members=members,
            prefix=prefix,
            uploaded_at=uploaded_at,
            repository_id=repository_id,
            repository_name=repository_name,
        )
        if not documents:
            raise RepositoryError("No usable files were found in the archive.")
        files = self._embed_repository_documents(documents)
        self._persist_raw_repository(repository_id, archive_name, payload)
        return RepositoryRecord(
            id=repository_id,
            name=repository_name,
            files=files,
            skipped=skipped,
            uploaded_at=uploaded_at,
        )

    def list_repositories(self) -> list[tuple[str, str, int, datetime]]:
        """Aggregate stored chunks into repository-level records.

        @returns List of `(repository_id, repository_name, chunks, uploaded_at)`
                 sorted by upload time (newest first).
        """
        try:
            data = self._collection.get(include=[IncludeEnum.metadatas])
        except Exception as exc:
            raise VectorStoreError(f"Failed to list repositories: {exc}") from exc
        grouped: dict[str, dict] = {}
        for metadata in data.get("metadatas", []) or []:
            repo_id = metadata.get("repository_id")
            if not repo_id:
                continue
            entry = grouped.setdefault(
                str(repo_id),
                {
                    "name": metadata.get("repository_name", ""),
                    "chunks": 0,
                    "uploaded_at": metadata.get("uploaded_at"),
                },
            )
            entry["chunks"] += 1
        records = [
            (repo_id, entry["name"], entry["chunks"], datetime.fromisoformat(entry["uploaded_at"]))
            for repo_id, entry in grouped.items()
            if entry.get("uploaded_at")
        ]
        records.sort(key=lambda item: item[3], reverse=True)
        return records

    def delete_repository(self, repository_id: str) -> int:
        """Remove every chunk belonging to a repository.

        @param repository_id Identifier of the repository to remove.
        @returns Number of chunks deleted.
        @raises VectorStoreError On Chroma failures.
        """
        try:
            existing = self._collection.get(where={"repository_id": repository_id}, include=[])
            ids = existing.get("ids", []) or []
            if not ids:
                return 0
            self._collection.delete(ids=ids)
        except Exception as exc:
            raise VectorStoreError(f"Failed to delete repository {repository_id}: {exc}") from exc
        return len(ids)

    @staticmethod
    def _open_zip(payload: bytes) -> zipfile.ZipFile:
        """Open a ZIP archive from raw bytes.

        @param payload Raw ZIP bytes.
        @returns Read-only `ZipFile` instance.
        @raises RepositoryError When the bytes are not a valid ZIP archive.
        """
        try:
            return zipfile.ZipFile(BytesIO(payload), "r")
        except zipfile.BadZipFile as exc:
            raise RepositoryError(f"Not a valid ZIP archive: {exc}") from exc

    @staticmethod
    def _screen_archive(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
        """Return non-directory members after applying the global member-count cap.

        @param archive Open ZIP archive.
        @returns Filtered list of file members.
        @raises UnsafeArchiveError When the archive has too many members.
        """
        members = [info for info in archive.infolist() if not info.is_dir()]
        if len(members) > MAX_REPO_MEMBERS:
            raise UnsafeArchiveError(f"Archive has too many members ({len(members)} > {MAX_REPO_MEMBERS}).")
        return members

    @staticmethod
    def _zip_common_prefix(members: list[zipfile.ZipInfo]) -> str:
        """Detect a shared top-level directory across safe members.

        Entries that already look unsafe (absolute paths, parent traversal) are
        ignored here because they will be skipped later anyway; including them
        would derail prefix detection for the legitimate files.

        @param members Non-directory archive members.
        @returns The shared prefix (with trailing slash), or `""` when absent.
        """
        first_segments: set[str] = set()
        for member in members:
            name = member.filename.replace("\\", "/")
            head, _, _ = name.partition("/")
            if not head or head in {".", ".."} or name.startswith("/"):
                continue
            if "/" in name:
                first_segments.add(head)
            else:
                return ""
        if len(first_segments) == 1:
            return next(iter(first_segments)) + "/"
        return ""

    @staticmethod
    def _strip_zip_prefix(name: str, prefix: str) -> str:
        """Remove the shared top-level prefix from an archive member name.

        @param name   Archive member name (may use either slash style).
        @param prefix Detected common prefix (with trailing slash) or `""`.
        @returns Path relative to the repository root, using forward slashes.
        """
        normalized = name.replace("\\", "/")
        if prefix and normalized.startswith(prefix):
            return normalized[len(prefix) :]
        return normalized

    @staticmethod
    def _validate_zip_path(name: str) -> None:
        """Reject archive entries that try to escape the virtual root.

        @param name Archive member name (forward-slash form).
        @raises UnsafeArchiveError When the path is absolute, has a drive prefix,
                contains NUL bytes or resolves above the virtual root.
        """
        if not name:
            raise UnsafeArchiveError("empty path")
        if "\x00" in name:
            raise UnsafeArchiveError("null byte in path")
        normalized = name.replace("\\", "/")
        if normalized.startswith("/"):
            raise UnsafeArchiveError("absolute path")
        if len(normalized) >= 2 and normalized[1] == ":":
            raise UnsafeArchiveError("drive prefix")
        depth = 0
        for part in (segment for segment in normalized.split("/") if segment):
            if part == "..":
                depth -= 1
                if depth < 0:
                    raise UnsafeArchiveError("path traversal")
            elif part != ".":
                depth += 1

    @staticmethod
    def _is_ignored(rel_path: str) -> bool:
        """Match a path against the default-ignore patterns.

        @param rel_path Path relative to the repository root.
        @returns True when any path segment matches an ignore rule.
        """
        parts = rel_path.split("/")
        for pattern in DEFAULT_IGNORE:
            if pattern.endswith("/"):
                if pattern[:-1] in parts:
                    return True
            elif pattern in parts or rel_path.endswith(pattern):
                return True
        return False

    @staticmethod
    def _is_symlink(member: zipfile.ZipInfo) -> bool:
        """Detect a symlink member by its UNIX file-mode bits.

        @param member ZIP member info.
        @returns True when the entry is a symlink.
        """
        mode = (member.external_attr >> 16) & 0xFFFF
        return bool(mode) and (mode & 0xF000) == 0xA000

    def _collect_repository_documents(
        self,
        *,
        archive: zipfile.ZipFile,
        members: list[zipfile.ZipInfo],
        prefix: str,
        uploaded_at: datetime,
        repository_id: str,
        repository_name: str,
    ) -> tuple[list[Document], list[SkippedFile]]:
        """Walk archive members and turn the safe, supported ones into Documents.

        @param archive         Open ZIP archive (read-only).
        @param members         Pre-screened member list (no directories).
        @param prefix          Common top-level prefix to strip from member names.
        @param uploaded_at     Timestamp baked into every document's metadata.
        @param repository_id   Generated repository identifier.
        @param repository_name Repository name (archive stem).
        @returns Tuple of (documents to index, skipped-file records).
        @raises UnsafeArchiveError When the total uncompressed size exceeds the cap.
        """
        documents: list[Document] = []
        skipped: list[SkippedFile] = []
        total_bytes = 0
        for member in members:
            rel_path = self._strip_zip_prefix(member.filename, prefix)
            outcome = self._examine_member(member, rel_path)
            if outcome is not None:
                skipped.append(outcome)
                continue
            total_bytes += member.file_size
            if total_bytes > MAX_REPO_TOTAL_BYTES:
                raise UnsafeArchiveError(f"Archive exceeds total size cap of {MAX_REPO_TOTAL_BYTES} bytes.")
            document_or_skip = self._read_archive_member(
                archive=archive,
                member=member,
                rel_path=rel_path,
                uploaded_at=uploaded_at,
                repository_id=repository_id,
                repository_name=repository_name,
            )
            if isinstance(document_or_skip, SkippedFile):
                skipped.append(document_or_skip)
            else:
                documents.append(document_or_skip)
        return documents, skipped

    def _examine_member(self, member: zipfile.ZipInfo, rel_path: str) -> SkippedFile | None:
        """Apply safety / ignore / size filters to a single archive member.

        @param member   ZIP member info.
        @param rel_path Path relative to the repository root.
        @returns A `SkippedFile` if the member should be skipped, `None` otherwise.
        """
        if self._is_symlink(member):
            return SkippedFile(path=rel_path, reason="symlink")
        try:
            self._validate_zip_path(member.filename)
        except UnsafeArchiveError as exc:
            return SkippedFile(path=member.filename, reason=f"unsafe path: {exc}")
        if self._is_ignored(rel_path):
            return SkippedFile(path=rel_path, reason="ignored")
        if member.file_size > MAX_REPO_FILE_BYTES:
            return SkippedFile(
                path=rel_path,
                reason=f"too large ({member.file_size} bytes)",
            )
        return None

    def _read_archive_member(
        self,
        *,
        archive: zipfile.ZipFile,
        member: zipfile.ZipInfo,
        rel_path: str,
        uploaded_at: datetime,
        repository_id: str,
        repository_name: str,
    ) -> Document | SkippedFile:
        """Decode one archive member and wrap it in a LlamaIndex `Document`.

        @param archive         Open ZIP archive.
        @param member          ZIP member info to read.
        @param rel_path        Path relative to the repository root.
        @param uploaded_at     Timestamp baked into the document's metadata.
        @param repository_id   Repository identifier.
        @param repository_name Repository display name.
        @returns A populated `Document`, or a `SkippedFile` describing the failure.
        """
        try:
            content = archive.read(member)
        except Exception as exc:
            return SkippedFile(path=rel_path, reason=f"read failed: {exc}")
        try:
            loaded = self._loader.load(rel_path, content)
        except UnsupportedFormatError:
            return SkippedFile(path=rel_path, reason="unsupported format")
        if not loaded.text.strip():
            return SkippedFile(path=rel_path, reason="empty after extraction")
        return Document(
            id_=uuid.uuid4().hex,
            text=loaded.text,
            metadata={
                "filename": rel_path,
                "uploaded_at": uploaded_at.isoformat(),
                "kind": loaded.kind,
                "language": loaded.language,
                "repository_id": repository_id,
                "repository_name": repository_name,
            },
            excluded_embed_metadata_keys=[
                "uploaded_at",
                "kind",
                "language",
                "repository_id",
                "repository_name",
            ],
            excluded_llm_metadata_keys=["uploaded_at", "repository_id"],
        )

    def _embed_repository_documents(self, documents: list[Document]) -> list[IngestedFile]:
        """Split, embed and index a batch of repository documents.

        @param documents Documents produced by `_collect_repository_documents`.
        @returns Per-file ingest records (paths and chunk counts).
        @raises EmbeddingError When the underlying embedding call fails.
        """
        all_nodes: list = []
        files: list[IngestedFile] = []
        for document in documents:
            nodes = self._splitter.get_nodes_from_documents([document])
            kind_value = document.metadata.get("kind", "doc")
            kind: Kind = "code" if kind_value == "code" else "doc"
            files.append(
                IngestedFile(
                    document_id=document.id_,
                    path=str(document.metadata.get("filename", "")),
                    kind=kind,
                    language=str(document.metadata.get("language", "text")),
                    chunks=len(nodes),
                )
            )
            all_nodes.extend(nodes)
        try:
            self._index.insert_nodes(all_nodes)
        except Exception as exc:
            raise EmbeddingError(f"Failed to embed repository chunks: {exc}") from exc
        return files

    def _persist_raw_repository(self, repository_id: str, archive_name: str, payload: bytes) -> None:
        """Archive the original ZIP next to the per-file uploads.

        @param repository_id Repository identifier (used as filename stem).
        @param archive_name  Original archive name (used for extension).
        @param payload       Raw archive bytes.
        @raises StorageError When the disk write fails.
        """
        try:
            suffix = Path(archive_name).suffix.lower() or ".zip"
            destination = self._upload_dir / f"{repository_id}{suffix}"
            destination.write_bytes(payload)
        except OSError as exc:
            raise StorageError(f"Failed to archive raw repository: {exc}") from exc

    async def stream_chat(
        self,
        *,
        messages: list[dict],
        document_ids: list[str] | None,
    ) -> AsyncIterator[dict]:
        """Yield NDJSON events: first the retrieved sources, then the answer tokens.

        @param messages     Conversation so far (`role`/`content` dicts).
        @param document_ids Optional document filter.
        @returns Async iterator producing `{type, ...}` event dicts.
        @raises ValueError When the latest message is not from the user.
        """
        if not messages or messages[-1].get("role") != "user":
            raise ValueError("The last message must be from the user.")

        question = messages[-1]["content"]
        nodes = await self._retrieve(question, document_ids)
        yield {"type": "sources", "sources": [self._source(node) for node in nodes]}

        chat_messages = self._build_prompt(messages, nodes)
        try:
            response = await self._llm.astream_chat(chat_messages)
            async for chunk in response:
                delta = getattr(chunk, "delta", "") or ""
                if delta:
                    yield {"type": "delta", "content": delta}
        except Exception as exc:
            raise ChatGenerationError(f"Chat generation failed: {exc}") from exc
        yield {"type": "done"}

    async def _retrieve(
        self,
        question: str,
        document_ids: list[str] | None,
    ) -> list[NodeWithScore]:
        """Run a similarity search restricted to the optional document scope.

        @param question     Latest user question.
        @param document_ids Optional document identifiers used to scope retrieval.
        @returns Retrieved nodes (possibly empty).
        """
        retriever = self._index.as_retriever(
            similarity_top_k=self._settings.top_k,
            filters=self._build_filters(document_ids),
        )
        try:
            return await retriever.aretrieve(question)
        except Exception as exc:
            raise EmbeddingError(f"Retrieval failed: {exc}") from exc

    @staticmethod
    def _build_filters(document_ids: list[str] | None) -> MetadataFilters | None:
        """Convert a list of document ids into a LlamaIndex metadata filter.

        @param document_ids Optional list of document identifiers.
        @returns `MetadataFilters` restricting the search, or None.
        """
        if not document_ids:
            return None
        operator = FilterOperator.IN if len(document_ids) > 1 else FilterOperator.EQ
        value: list[str] | str = document_ids if len(document_ids) > 1 else document_ids[0]
        return MetadataFilters(filters=[MetadataFilter(key="doc_id", value=value, operator=operator)])

    @staticmethod
    def _source(node: NodeWithScore) -> dict:
        """Render a retrieved node as a compact JSON source descriptor.

        @param node Retrieved node returned by the LlamaIndex retriever.
        @returns Dict with id, filename, distance and a short preview.
        """
        metadata = node.metadata or {}
        text = node.get_content() or ""
        score = node.score if node.score is not None else 0.0
        return {
            "document_id": str(metadata.get("doc_id") or metadata.get("ref_doc_id") or ""),
            "filename": str(metadata.get("filename", "")),
            "distance": float(1.0 - score),
            "preview": text[:240],
        }

    @staticmethod
    def _build_prompt(messages: list[dict], nodes: list[NodeWithScore]) -> list[LiChatMessage]:
        """Prepend the system prompt with retrieved context and lift to LiChatMessage.

        @param messages Conversation history (user + assistant turns).
        @param nodes    Retrieved context nodes.
        @returns Full message list ready for `Ollama.astream_chat`.
        """
        if nodes:
            context = "\n\n".join(
                f"[Source: {node.metadata.get('filename', 'unknown')}]\n{node.get_content()}"
                for node in nodes
            )
            system_content = f"{SYSTEM_PROMPT}\n\nContext:\n{context}"
        else:
            system_content = (
                f"{SYSTEM_PROMPT}\n\nContext: (no relevant excerpts were found in the indexed documents)"
            )
        result: list[LiChatMessage] = [LiChatMessage(role=MessageRole.SYSTEM, content=system_content)]
        for message in messages:
            role = _ROLE_MAP.get(message.get("role", "user"), MessageRole.USER)
            result.append(LiChatMessage(role=role, content=message.get("content", "")))
        return result

    def _persist_raw(self, document_id: str, filename: str, payload: bytes) -> None:
        """Archive the raw upload on disk for traceability.

        @param document_id Unique document id.
        @param filename    Original file name.
        @param payload     Raw file bytes.
        """
        suffix = Path(filename).suffix.lower()
        destination = self._upload_dir / f"{document_id}{suffix}"
        destination.write_bytes(payload)
