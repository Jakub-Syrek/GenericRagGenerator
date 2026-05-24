"""LlamaIndex-backed RAG service: ingest, retrieve, stream chat answers.

Replaces the hand-rolled chunker / embedder / vector store / ingestion / chain
modules with the equivalent LlamaIndex building blocks. ChromaDB is still the
persistence layer; we keep a direct reference to its collection so document-
level listing and deletion remain trivial.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
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

from ..config import Settings
from ..models.schemas import DocumentInfo
from .document_loader import DocumentLoader

COLLECTION_NAME = "documents"

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


class EmptyDocumentError(ValueError):
    """Raised when an uploaded document yields no extractable text."""


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

        self._chroma_client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        self._collection = self._chroma_client.get_or_create_collection(COLLECTION_NAME)
        vector_store = ChromaVectorStore(chroma_collection=self._collection)

        self._embed_model = OllamaEmbedding(
            model_name=settings.embedding_model,
            base_url=settings.ollama_host,
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
        text = self._loader.load(filename, payload)
        if not text:
            raise EmptyDocumentError("No text could be extracted from the file.")

        document_id = uuid.uuid4().hex
        uploaded_at = datetime.now(UTC)
        document = Document(
            id_=document_id,
            text=text,
            metadata={
                "filename": filename,
                "uploaded_at": uploaded_at.isoformat(),
            },
            excluded_embed_metadata_keys=["uploaded_at"],
            excluded_llm_metadata_keys=["uploaded_at"],
        )
        nodes = self._splitter.get_nodes_from_documents([document])
        if not nodes:
            raise EmptyDocumentError("Document produced no usable chunks.")

        self._index.insert_nodes(nodes)
        self._persist_raw(document_id, filename, payload)
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
        data = self._collection.get(include=[IncludeEnum.metadatas])
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
        existing = self._collection.get(where={"doc_id": document_id}, include=[])
        ids = existing.get("ids", []) or []
        if not ids:
            return 0
        self._collection.delete(ids=ids)
        return len(ids)

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
        response = await self._llm.astream_chat(chat_messages)
        async for chunk in response:
            delta = getattr(chunk, "delta", "") or ""
            if delta:
                yield {"type": "delta", "content": delta}
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
        return await retriever.aretrieve(question)

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
