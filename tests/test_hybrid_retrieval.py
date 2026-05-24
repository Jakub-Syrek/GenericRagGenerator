"""Tests for the BM25 + vector hybrid retriever (RRF fusion math)."""

from __future__ import annotations

import pytest

from app.services.hybrid_retrieval import HybridRetriever, _Bm25Index, _tokenise
from app.services.index_catalog import ChunkRow


def test_tokeniser_lowercases_and_splits_on_non_word_characters() -> None:
    """Tokens are lowercase, alphanumeric, and split on punctuation."""
    assert _tokenise("Foo-bar BAZ! qux_1") == ["foo", "bar", "baz", "qux_1"]


def test_bm25_index_returns_empty_when_unbuilt() -> None:
    """Querying an empty index yields nothing (no exception)."""
    index = _Bm25Index()
    assert index.query("anything", top_k=5) == []
    assert not index.is_ready()


def test_bm25_index_ranks_matching_chunks_first() -> None:
    """Tokens overlapping with the query lift the matching chunk to top-1."""
    rows = [
        ChunkRow(chunk_id="a", text="the quick brown fox jumps", metadata={}),
        ChunkRow(chunk_id="b", text="lazy dog naps on the porch", metadata={}),
        ChunkRow(chunk_id="c", text="brown fox brown fox brown fox", metadata={}),
    ]
    index = _Bm25Index()
    index.rebuild(rows)
    assert index.is_ready()
    ranked = index.query("brown fox", top_k=3)
    assert ranked[0][0].chunk_id == "c"
    assert {row.chunk_id for row, _score in ranked[:2]} == {"a", "c"}


def test_bm25_index_invalidate_clears_state() -> None:
    """`invalidate` drops the cached BM25 model entirely."""
    index = _Bm25Index()
    index.rebuild([ChunkRow(chunk_id="x", text="hello world", metadata={})])
    assert index.is_ready()
    index.invalidate()
    assert not index.is_ready()
    assert index.query("hello", top_k=1) == []


class _FakeCatalog:
    """Minimal IndexCatalog stand-in returning a fixed corpus."""

    def __init__(self, rows: list[ChunkRow]) -> None:
        self.rows = rows
        self.calls = 0

    def all_chunks(self) -> list[ChunkRow]:
        self.calls += 1
        return list(self.rows)


def test_hybrid_search_surfaces_bm25_only_hits() -> None:
    """BM25 contributes chunks the dense ranker never saw.

    The pure-lexical match (`bm25-only`) is invisible to the dense
    retriever in this scenario, yet it ends up in the fused result set
    — that's the headline win of hybrid retrieval over a vanilla
    embedding query.
    """
    rows = [
        ChunkRow(chunk_id="dense-only", text="paraphrased prose about cats", metadata={}),
        ChunkRow(chunk_id="both", text="slugify replaces whitespace with hyphens", metadata={}),
        ChunkRow(chunk_id="bm25-only", text="slugify slugify slugify hyphens hyphens", metadata={}),
    ]
    retriever = HybridRetriever(catalog=_FakeCatalog(rows))  # type: ignore[arg-type]
    dense_hits = [
        ("dense-only", 0.9, "paraphrased prose about cats", {}),
        ("both", 0.7, "slugify replaces whitespace with hyphens", {}),
    ]
    fused = retriever.search(query="slugify", dense_hits=dense_hits, top_k=3)
    ids = {hit.chunk_id for hit in fused}
    assert ids == {"dense-only", "both", "bm25-only"}


def test_hybrid_search_falls_back_to_dense_when_corpus_empty() -> None:
    """With no BM25 corpus the fused list still surfaces the dense hits."""
    retriever = HybridRetriever(catalog=_FakeCatalog([]))  # type: ignore[arg-type]
    dense_hits = [("a", 0.5, "hello", {}), ("b", 0.4, "world", {})]
    fused = retriever.search(query="hello", dense_hits=dense_hits, top_k=2)
    assert {hit.chunk_id for hit in fused} == {"a", "b"}


def test_scope_predicate_filters_bm25_hits() -> None:
    """A scope predicate excludes BM25 rows whose metadata doesn't match."""
    rows = [
        ChunkRow(chunk_id="code", text="def slugify(value): pass", metadata={"kind": "code"}),
        ChunkRow(chunk_id="doc", text="slugify converts text to slugs", metadata={"kind": "doc"}),
    ]
    retriever = HybridRetriever(catalog=_FakeCatalog(rows))  # type: ignore[arg-type]
    fused = retriever.search(
        query="slugify",
        dense_hits=[],
        top_k=5,
        scope_predicate=lambda metadata: metadata.get("kind") == "code",
    )
    ids = {hit.chunk_id for hit in fused}
    assert ids == {"code"}


@pytest.mark.parametrize("query", ["", "   ", "\n"])
def test_hybrid_search_handles_empty_query(query: str) -> None:
    """Queries that tokenise to nothing yield no BM25 hits (dense passes through)."""
    retriever = HybridRetriever(
        catalog=_FakeCatalog([ChunkRow(chunk_id="x", text="abc", metadata={})])  # type: ignore[arg-type]
    )
    dense_hits = [("y", 0.5, "irrelevant", {})]
    fused = retriever.search(query=query, dense_hits=dense_hits, top_k=2)
    assert [hit.chunk_id for hit in fused] == ["y"]
