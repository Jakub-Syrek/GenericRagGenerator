"""Tests for the tenacity-driven retry wrapper around Ollama embeddings."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.services.rag_service import _PrefixedOllamaEmbedding


def _build_embedder(*, attempts: int = 3) -> _PrefixedOllamaEmbedding:
    """Construct a real `_PrefixedOllamaEmbedding` without hitting Ollama.

    @param attempts Retry budget under test.
    @returns Instance with tiny backoffs so tests stay fast.
    """
    return _PrefixedOllamaEmbedding(
        model_name="nomic-embed-text",
        base_url="http://localhost:11434",
        query_prefix="q: ",
        document_prefix="d: ",
        retry_attempts=attempts,
        retry_backoff_min=0.001,
        retry_backoff_max=0.002,
    )


def test_query_embedding_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """A transient ConnectError is retried; the second attempt wins."""
    embedder = _build_embedder()
    calls: list[str] = []

    def flaky(self: Any, text: str) -> list[float]:
        calls.append(text)
        if len(calls) == 1:
            raise httpx.ConnectError("ollama not yet ready")
        return [0.1, 0.2]

    from llama_index.embeddings.ollama import OllamaEmbedding

    monkeypatch.setattr(OllamaEmbedding, "_get_query_embedding", flaky)

    result = embedder._get_query_embedding("hello")
    assert result == [0.1, 0.2]
    assert len(calls) == 2
    assert calls[0] == "q: hello"


def test_query_embedding_gives_up_after_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """When transient errors exhaust the budget the last exception is raised."""
    embedder = _build_embedder(attempts=2)
    attempt_count = 0

    def always_fail(self: Any, text: str) -> list[float]:
        nonlocal attempt_count
        attempt_count += 1
        raise httpx.ReadTimeout("still timing out")

    from llama_index.embeddings.ollama import OllamaEmbedding

    monkeypatch.setattr(OllamaEmbedding, "_get_query_embedding", always_fail)

    with pytest.raises(httpx.ReadTimeout):
        embedder._get_query_embedding("hello")
    assert attempt_count == 2


def test_non_transient_exception_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `ValueError` bubbles out on the first attempt — not retried."""
    embedder = _build_embedder()
    attempt_count = 0

    def boom(self: Any, text: str) -> list[float]:
        nonlocal attempt_count
        attempt_count += 1
        raise ValueError("malformed input")

    from llama_index.embeddings.ollama import OllamaEmbedding

    monkeypatch.setattr(OllamaEmbedding, "_get_query_embedding", boom)

    with pytest.raises(ValueError, match="malformed"):
        embedder._get_query_embedding("hello")
    assert attempt_count == 1


def test_text_embeddings_batch_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """The batch path enjoys the same retry budget as the singular paths."""
    embedder = _build_embedder()
    calls = 0

    def flaky_batch(self: Any, texts: list[str]) -> list[list[float]]:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise httpx.RemoteProtocolError("connection dropped mid-batch")
        return [[0.0] * 4 for _ in texts]

    from llama_index.embeddings.ollama import OllamaEmbedding

    monkeypatch.setattr(OllamaEmbedding, "_get_text_embeddings", flaky_batch)

    vectors = embedder._get_text_embeddings(["alpha", "beta"])
    assert len(vectors) == 2
    assert calls == 2
