"""Hybrid retrieval: BM25 (lexical) + vector (semantic), fused with RRF.

Dense embeddings handle paraphrase / semantic queries well but trip on
rare tokens (function names, error codes, stable IDs). BM25 over the
same chunks handles those exactly. Reciprocal Rank Fusion merges the
two ranked lists without needing to calibrate scores between the
backends:

    RRF(chunk) = sum( 1 / (k + rank_in_list(chunk)) )

where `k=60` is the standard smoothing constant. We do the BM25 pass in
memory: the catalog hands over `(chunk_id, text, metadata)` rows, we
tokenise on whitespace + punctuation, and rebuild the index lazily.

The hybrid layer is opt-in (`RETRIEVAL_MODE=hybrid`) so vector-only
remains the default — same behaviour as before for anyone who hasn't
flipped the flag.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Any

from rank_bm25 import BM25Okapi

from .index_catalog import ChunkRow, IndexCatalog

# Standard RRF smoothing constant — sourced from the original Cormack et
# al. paper. Larger k pushes rare-but-relevant items up; 60 is the
# accepted default across most production setups.
_RRF_K = 60

# Pure-Python tokeniser: split on anything that's not a word character.
# Drops case to make BM25 case-insensitive without needing NLTK / spaCy.
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokenise(text: str) -> list[str]:
    """Lowercase + split on non-word characters.

    @param text Raw text.
    @returns List of lowercase tokens.
    """
    return [match.group(0).lower() for match in _TOKEN_RE.finditer(text)]


@dataclass(frozen=True)
class FusedHit:
    """A chunk surfaced by hybrid retrieval, carrying the fused score."""

    chunk_id: str
    text: str
    metadata: dict[str, Any]
    score: float


class _Bm25Index:
    """In-memory BM25 index rebuilt lazily from `IndexCatalog`.

    Holds tokens, chunk metadata and the underlying `BM25Okapi` model.
    Callers invalidate after writes so the next query rebuilds from the
    current Chroma snapshot.
    """

    def __init__(self) -> None:
        """Initialise an empty index."""
        self._lock = threading.Lock()
        self._rows: list[ChunkRow] = []
        self._tokens: list[list[str]] = []
        self._bm25: BM25Okapi | None = None

    def rebuild(self, rows: list[ChunkRow]) -> None:
        """Replace the corpus with a fresh row list (under a lock).

        @param rows Chunk rows pulled from the catalog.
        """
        with self._lock:
            self._rows = list(rows)
            self._tokens = [_tokenise(row.text) for row in self._rows]
            self._bm25 = BM25Okapi(self._tokens) if self._tokens else None

    def invalidate(self) -> None:
        """Drop the cached model so the next `query` rebuilds."""
        with self._lock:
            self._bm25 = None
            self._rows = []
            self._tokens = []

    def is_ready(self) -> bool:
        """Return True when the index is populated and queryable."""
        return self._bm25 is not None

    def query(self, query_text: str, top_k: int) -> list[tuple[ChunkRow, float]]:
        """Return the top-k chunks for `query_text` with their BM25 scores.

        @param query_text User query.
        @param top_k      How many hits to return.
        @returns Ordered `(row, score)` pairs (highest score first).
        """
        if self._bm25 is None or not self._rows:
            return []
        tokens = _tokenise(query_text)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        # Keep all top-k entries regardless of sign: BM25 idf can go
        # negative on a tiny corpus where every doc shares the term,
        # but the *ranking* is still meaningful and that's all RRF needs.
        indexed = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:top_k]
        return [(self._rows[i], float(score)) for i, score in indexed]


class HybridRetriever:
    """Lexical + semantic retrieval over the same Chroma collection.

    Holds a reference to the catalog so it can rebuild the BM25 corpus
    on demand. Callers (the RAG service) feed in the dense hits already
    sorted by their similarity rank; we merge with the BM25 hits via
    Reciprocal Rank Fusion and return the deduped top-k.
    """

    def __init__(self, catalog: IndexCatalog) -> None:
        """Wire the retriever to its data source.

        @param catalog Repository over the Chroma collection.
        """
        self._catalog = catalog
        self._index = _Bm25Index()

    def invalidate(self) -> None:
        """Drop the cached BM25 model. Call after any ingest / delete."""
        self._index.invalidate()

    def search(
        self,
        *,
        query: str,
        dense_hits: list[tuple[str, float, str, dict[str, Any]]],
        top_k: int,
        scope_predicate: Any = None,
    ) -> list[FusedHit]:
        """Fuse the supplied dense ranking with a fresh BM25 ranking.

        @param query           Raw user query (for BM25 tokenisation).
        @param dense_hits      `(chunk_id, score, text, metadata)` from the
                               vector retriever, already in similarity order.
        @param top_k           Final number of fused hits to return.
        @param scope_predicate Optional callable `(metadata) -> bool` that
                               filters BM25 rows to match the dense scope.
        @returns Ranked list of `FusedHit` (highest fused score first).
        """
        self._ensure_index_ready()
        lexical = self._index.query(query, top_k=top_k * 4)
        if scope_predicate is not None:
            lexical = [(row, score) for row, score in lexical if scope_predicate(row.metadata)]
        fused = self._reciprocal_rank_fusion(dense_hits, lexical)
        fused.sort(key=lambda hit: hit.score, reverse=True)
        return fused[:top_k]

    def _ensure_index_ready(self) -> None:
        """Rebuild the BM25 corpus from Chroma when it has been invalidated."""
        if self._index.is_ready():
            return
        rows = self._catalog.all_chunks()
        self._index.rebuild(rows)

    @staticmethod
    def _reciprocal_rank_fusion(
        dense_hits: list[tuple[str, float, str, dict[str, Any]]],
        lexical_hits: list[tuple[ChunkRow, float]],
    ) -> list[FusedHit]:
        """Merge dense + lexical rankings using RRF.

        @param dense_hits   Vector hits (chunk_id, score, text, metadata) in rank order.
        @param lexical_hits BM25 hits `(ChunkRow, score)` in rank order.
        @returns Deduped list of `FusedHit` with the summed RRF score.
        """
        scores: dict[str, float] = {}
        bodies: dict[str, tuple[str, dict[str, Any]]] = {}
        for rank, (chunk_id, _score, text, metadata) in enumerate(dense_hits, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (_RRF_K + rank)
            bodies.setdefault(chunk_id, (text, metadata))
        for rank, (row, _bm25_score) in enumerate(lexical_hits, start=1):
            scores[row.chunk_id] = scores.get(row.chunk_id, 0.0) + 1.0 / (_RRF_K + rank)
            bodies.setdefault(row.chunk_id, (row.text, row.metadata))
        return [
            FusedHit(chunk_id=chunk_id, text=text, metadata=metadata, score=scores[chunk_id])
            for chunk_id, (text, metadata) in bodies.items()
        ]
