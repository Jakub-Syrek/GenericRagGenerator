"""Cross-encoder reranking after retrieval.

Embeddings give cheap recall; a cross-encoder re-scores the shortlist
by jointly attending to the query and each candidate, which is much
more accurate at the price of being slower (you only run it on the
top-N, never the whole corpus).

This module ships two concrete rerankers:

- `NullReranker` — pass-through, default. Zero cost, zero behaviour
  change vs vector-only.
- `FlashRankReranker` — wraps the `flashrank` package (ONNX-based,
  reuses the onnxruntime already pulled in by ChromaDB; ~80 MB model
  download on first use, cached locally).

Custom rerankers (Cohere API, sentence-transformers, in-house) plug in
by implementing the `Reranker` protocol — no other code changes.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class RerankCandidate:
    """One input to the reranker: an opaque id paired with its text."""

    chunk_id: str
    text: str


class Reranker(Protocol):
    """Re-score a shortlist of candidates against the original query."""

    def rerank(
        self,
        *,
        query: str,
        candidates: list[RerankCandidate],
        top_k: int,
    ) -> list[str]:
        """Return the chunk ids of the top-k candidates in their new order.

        @param query      Original user query.
        @param candidates Shortlist to re-score.
        @param top_k      How many ids to return.
        @returns Ordered list of chunk ids (highest relevance first).
        """
        ...


class NullReranker:
    """Pass-through reranker: preserves the input order untouched.

    Used as the default so vector-only deployments don't pay a single
    extra cycle until the operator opts in via `RERANKER_ENABLED=true`.
    """

    def rerank(
        self,
        *,
        query: str,
        candidates: list[RerankCandidate],
        top_k: int,
    ) -> list[str]:
        """Echo the input order, clipped to `top_k`.

        @param query      Unused — kept for protocol parity.
        @param candidates Input order is preserved.
        @param top_k      Maximum number of ids to return.
        @returns First `top_k` chunk ids from the input.
        """
        _ = query
        return [candidate.chunk_id for candidate in candidates[:top_k]]


class FlashRankReranker:
    """ONNX-based cross-encoder reranker backed by `flashrank`.

    Lazily instantiates the underlying `Ranker` on the first call so
    importing the module is cheap and the model download (one-shot,
    cached) only happens when reranking is actually used.
    """

    def __init__(self, *, model_name: str, cache_dir: str | None = None) -> None:
        """Configure the model + cache location.

        @param model_name FlashRank model identifier (see flashrank docs).
        @param cache_dir  Filesystem cache for the downloaded ONNX file.
        """
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._lock = threading.Lock()
        self._ranker: Any | None = None

    def rerank(
        self,
        *,
        query: str,
        candidates: list[RerankCandidate],
        top_k: int,
    ) -> list[str]:
        """Score and reorder `candidates` with the cross-encoder.

        @param query      Original user query.
        @param candidates Shortlist from the (hybrid) retriever.
        @param top_k      How many ids to return.
        @returns Ordered list of chunk ids (highest cross-encoder score first).
        """
        if not candidates:
            return []
        ranker = self._ensure_ranker()
        from flashrank import RerankRequest

        passages = [{"id": item.chunk_id, "text": item.text} for item in candidates]
        scored = ranker.rerank(RerankRequest(query=query, passages=passages))
        return [str(item["id"]) for item in scored[:top_k]]

    def _ensure_ranker(self) -> Any:
        """Build the `Ranker` once, behind a lock so concurrent calls share it.

        @returns The cached `flashrank.Ranker` instance.
        """
        if self._ranker is not None:
            return self._ranker
        with self._lock:
            if self._ranker is None:
                from flashrank import Ranker

                kwargs: dict[str, Any] = {"model_name": self._model_name}
                if self._cache_dir:
                    kwargs["cache_dir"] = self._cache_dir
                self._ranker = Ranker(**kwargs)
        return self._ranker
