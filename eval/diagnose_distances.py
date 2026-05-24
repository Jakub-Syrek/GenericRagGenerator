"""One-shot diagnostic: cosine similarity of the failing query against every
corpus doc, with and without the nomic-embed-text asymmetric prefixes.
"""

from __future__ import annotations

import math
from pathlib import Path

from ollama import Client

CORPUS_DIR = Path(__file__).parent / "corpus"
QUERY = "What does RAG stand for?"


def cosine(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two equally-sized vectors.

    @param a First vector.
    @param b Second vector.
    @returns Cosine similarity in [-1, 1].
    """
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def main() -> None:
    """Probe nomic-embed-text similarity scores for the failing question."""
    docs = {p.name: p.read_text(encoding="utf-8") for p in sorted(CORPUS_DIR.glob("*.txt"))}
    client = Client(host="http://localhost:11434")

    print(f"Query: {QUERY!r}\n")
    print("=== plain (no prefix) ===")
    doc_emb = client.embed(model="nomic-embed-text", input=list(docs.values()))["embeddings"]
    q_emb = client.embed(model="nomic-embed-text", input=[QUERY])["embeddings"][0]
    plain = sorted(
        ((name, cosine(q_emb, doc_emb[i])) for i, name in enumerate(docs)),
        key=lambda item: item[1],
        reverse=True,
    )
    for name, score in plain:
        print(f"  {name:30s} {score:.4f}")

    print("\n=== nomic-style prefixes ===")
    doc_emb2 = client.embed(
        model="nomic-embed-text",
        input=[f"search_document: {text}" for text in docs.values()],
    )["embeddings"]
    q_emb2 = client.embed(
        model="nomic-embed-text",
        input=[f"search_query: {QUERY}"],
    )["embeddings"][0]
    prefixed = sorted(
        ((name, cosine(q_emb2, doc_emb2[i])) for i, name in enumerate(docs)),
        key=lambda item: item[1],
        reverse=True,
    )
    for name, score in prefixed:
        print(f"  {name:30s} {score:.4f}")


if __name__ == "__main__":
    main()
