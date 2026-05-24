"""Tests for the reranker protocol and its two shipped implementations."""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from app.services.reranker import (
    FlashRankReranker,
    NullReranker,
    RerankCandidate,
)


def _candidates(items: list[tuple[str, str]]) -> list[RerankCandidate]:
    """Tiny helper turning `(id, text)` tuples into `RerankCandidate`s."""
    return [RerankCandidate(chunk_id=chunk_id, text=text) for chunk_id, text in items]


def test_null_reranker_preserves_input_order() -> None:
    """`NullReranker.rerank` echoes its input order unchanged."""
    reranker = NullReranker()
    ordered = reranker.rerank(
        query="anything",
        candidates=_candidates([("a", "alpha"), ("b", "beta"), ("c", "gamma")]),
        top_k=10,
    )
    assert ordered == ["a", "b", "c"]


def test_null_reranker_clips_to_top_k() -> None:
    """A `top_k` smaller than the input is honoured."""
    reranker = NullReranker()
    ordered = reranker.rerank(
        query="anything",
        candidates=_candidates([("a", "x"), ("b", "y"), ("c", "z")]),
        top_k=2,
    )
    assert ordered == ["a", "b"]


def test_null_reranker_on_empty_input_returns_empty() -> None:
    """Empty input yields empty output."""
    reranker = NullReranker()
    assert reranker.rerank(query="q", candidates=[], top_k=5) == []


class _FakeRanker:
    """In-memory stand-in mimicking `flashrank.Ranker.rerank`."""

    def __init__(self, score_table: dict[str, float]) -> None:
        self.score_table = score_table
        self.calls = 0

    def rerank(self, request: Any) -> list[dict[str, Any]]:
        self.calls += 1
        passages = list(request.passages)
        passages.sort(key=lambda item: self.score_table.get(item["id"], 0.0), reverse=True)
        return [{**passage, "score": self.score_table.get(passage["id"], 0.0)} for passage in passages]


@pytest.fixture
def fake_flashrank(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace the `flashrank` module with a controllable double.

    Returns a handle the test can use to install a custom scoring
    function before calling `rerank` for the first time.
    """
    state: dict[str, Any] = {"instances": [], "impl": None}

    class _StubRanker:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            state["instances"].append(self)

        def rerank(self, request: Any) -> Any:
            if state["impl"] is None:
                return []
            return state["impl"](request)

    class _StubRequest:
        def __init__(self, query: str, passages: list[dict[str, Any]]) -> None:
            self.query = query
            self.passages = passages

    fake_module = types.ModuleType("flashrank")
    fake_module.Ranker = _StubRanker  # type: ignore[attr-defined]
    fake_module.RerankRequest = _StubRequest  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "flashrank", fake_module)
    return state


def test_flashrank_reranker_lazily_builds_underlying_ranker(
    fake_flashrank: dict[str, Any],
) -> None:
    """The underlying `Ranker` is instantiated only on the first rerank call."""
    score_table = {"a": 0.1, "b": 0.9, "c": 0.5}
    fake_flashrank["impl"] = lambda request: _FakeRanker(score_table).rerank(request)

    reranker = FlashRankReranker(model_name="dummy")
    assert fake_flashrank["instances"] == []

    candidates = _candidates([("a", "alpha"), ("b", "beta"), ("c", "gamma")])
    ordered = reranker.rerank(query="q", candidates=candidates, top_k=3)
    assert ordered == ["b", "c", "a"]
    assert len(fake_flashrank["instances"]) == 1

    # Second call reuses the same Ranker instance (singleton under the lock).
    reranker.rerank(query="q", candidates=candidates, top_k=3)
    assert len(fake_flashrank["instances"]) == 1


def test_flashrank_reranker_clips_to_top_k(fake_flashrank: dict[str, Any]) -> None:
    """`top_k` smaller than the candidate list trims the result."""
    fake_flashrank["impl"] = lambda request: [
        {"id": "b", "text": "beta", "score": 0.9},
        {"id": "a", "text": "alpha", "score": 0.5},
        {"id": "c", "text": "gamma", "score": 0.1},
    ]
    reranker = FlashRankReranker(model_name="dummy")
    candidates = _candidates([("a", "alpha"), ("b", "beta"), ("c", "gamma")])
    ordered = reranker.rerank(query="q", candidates=candidates, top_k=2)
    assert ordered == ["b", "a"]


def test_flashrank_reranker_on_empty_input_skips_model_load(
    fake_flashrank: dict[str, Any],
) -> None:
    """Empty input never even constructs the underlying Ranker."""
    reranker = FlashRankReranker(model_name="dummy")
    assert reranker.rerank(query="q", candidates=[], top_k=5) == []
    assert fake_flashrank["instances"] == []
