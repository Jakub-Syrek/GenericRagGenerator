"""Ollama-backed embedding client."""
from __future__ import annotations

from ollama import Client


class EmbeddingError(RuntimeError):
    """Raised when the Ollama embedding endpoint fails."""


class OllamaEmbedder:
    """Generate vector embeddings via a local Ollama instance."""

    def __init__(self, client: Client, model: str) -> None:
        """Inject the Ollama client and model identifier.

        @param client Pre-configured `ollama.Client` instance.
        @param model  Name of the embedding model (e.g. `nomic-embed-text`).
        """
        self._client = client
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts and return one vector per input.

        @param texts Non-empty list of input strings.
        @returns List of embedding vectors aligned with the inputs.
        @raises EmbeddingError When the underlying call fails.
        """
        if not texts:
            return []
        try:
            response = self._client.embed(model=self._model, input=texts)
        except Exception as exc:
            raise EmbeddingError(f"Ollama embed call failed: {exc}") from exc
        embeddings = response.get("embeddings") if isinstance(response, dict) else response.embeddings
        if embeddings is None:
            raise EmbeddingError("Ollama response did not contain embeddings.")
        return list(embeddings)
