"""Orchestrate retrieval and Ollama chat completion (with streaming)."""
from __future__ import annotations

from typing import AsyncIterator

from ollama import AsyncClient

from .embedder import OllamaEmbedder
from .vector_store import StoredChunk, VectorStore

SYSTEM_PROMPT = (
    "You are a precise assistant answering questions strictly from the supplied "
    "document excerpts. If the answer is not contained in the context, reply that "
    "the documents do not cover it. Cite source filenames in parentheses when "
    "relevant. Respond in the user's language."
)


class RagChain:
    """Retrieve relevant chunks then stream a chat completion."""

    def __init__(
        self,
        *,
        embedder: OllamaEmbedder,
        store: VectorStore,
        chat_client: AsyncClient,
        chat_model: str,
        top_k: int,
    ) -> None:
        """Inject the required collaborators.

        @param embedder    Embedding client used for the user query.
        @param store       Vector store holding indexed document chunks.
        @param chat_client Async Ollama client used for chat completion.
        @param chat_model  Identifier of the chat model to invoke.
        @param top_k       Number of chunks retrieved per query.
        """
        self._embedder = embedder
        self._store = store
        self._chat_client = chat_client
        self._chat_model = chat_model
        self._top_k = top_k

    async def stream(
        self,
        *,
        messages: list[dict],
        document_ids: list[str] | None,
    ) -> AsyncIterator[dict]:
        """Yield NDJSON-friendly events describing the streamed answer.

        @param messages     Conversation so far (`role`/`content` dicts).
        @param document_ids Optional document filter.
        @returns Async iterator producing `{type, ...}` event dicts.
        @raises ValueError When the latest message is not from the user.
        """
        if not messages or messages[-1].get("role") != "user":
            raise ValueError("The last message must be from the user.")

        question = messages[-1]["content"]
        context_chunks = self._retrieve(question, document_ids)
        yield {"type": "sources", "sources": [self._source(chunk) for chunk in context_chunks]}

        prompt_messages = self._build_prompt(messages, context_chunks)
        async for part in await self._chat_client.chat(
            model=self._chat_model,
            messages=prompt_messages,
            stream=True,
        ):
            content = part.get("message", {}).get("content", "")
            if content:
                yield {"type": "delta", "content": content}
            if part.get("done"):
                yield {"type": "done"}

    def _retrieve(self, question: str, document_ids: list[str] | None) -> list[StoredChunk]:
        """Embed the question and return the top-k matching chunks.

        @param question     Latest user question.
        @param document_ids Optional document filter.
        @returns Retrieved chunks (possibly empty).
        """
        embedding = self._embedder.embed([question])
        if not embedding:
            return []
        return self._store.query(
            query_embedding=embedding[0],
            top_k=self._top_k,
            document_ids=document_ids,
        )

    @staticmethod
    def _source(chunk: StoredChunk) -> dict:
        """Render a chunk as a compact JSON source descriptor.

        @param chunk Stored chunk hydrated by the vector store.
        @returns Dict with id, filename, distance and a short preview.
        """
        return {
            "document_id": chunk.document_id,
            "filename": chunk.filename,
            "distance": chunk.distance,
            "preview": chunk.text[:240],
        }

    @staticmethod
    def _build_prompt(messages: list[dict], chunks: list[StoredChunk]) -> list[dict]:
        """Prepend the system prompt and inject the retrieved context.

        @param messages Conversation history (user + assistant turns).
        @param chunks   Retrieved context chunks.
        @returns Full message list suitable for Ollama chat.
        """
        if chunks:
            context = "\n\n".join(
                f"[Source: {chunk.filename}]\n{chunk.text}" for chunk in chunks
            )
            system_content = f"{SYSTEM_PROMPT}\n\nContext:\n{context}"
        else:
            system_content = (
                f"{SYSTEM_PROMPT}\n\nContext: (no relevant excerpts were found in the indexed documents)"
            )
        return [{"role": "system", "content": system_content}, *messages]
