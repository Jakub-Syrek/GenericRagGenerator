"""Definition of the public corpus + canned questions used by the RAG eval.

Each entry points to a Wikipedia REST `summary` endpoint that returns a small,
self-contained `extract` (plain text intro of an article). Questions are paired
with substrings expected in a faithful answer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalQuestion:
    """One canned question with expected-substring scoring rules."""

    prompt: str
    expected_any: tuple[str, ...]


@dataclass(frozen=True)
class EvalDocument:
    """One source document fetched from Wikipedia and ingested into the RAG."""

    title: str
    url: str
    filename: str
    questions: tuple[EvalQuestion, ...]


CORPUS: tuple[EvalDocument, ...] = (
    EvalDocument(
        title="Retrieval-augmented generation",
        url="https://en.wikipedia.org/api/rest_v1/page/summary/Retrieval-augmented_generation",
        filename="retrieval_augmented_generation.txt",
        questions=(
            EvalQuestion(
                prompt="What does RAG stand for?",
                expected_any=("retrieval-augmented generation", "retrieval augmented generation"),
            ),
            EvalQuestion(
                prompt="What kind of model does RAG combine retrieval with?",
                expected_any=("language model", "generative", "llm"),
            ),
            EvalQuestion(
                prompt="What is one benefit of using RAG over a plain language model?",
                expected_any=(
                    "up-to-date",
                    "current",
                    "updated",
                    "private",
                    "external",
                    "domain-specific",
                    "training data",
                    "factual",
                    "hallucin",
                ),
            ),
        ),
    ),
    EvalDocument(
        title="Vector database",
        url="https://en.wikipedia.org/api/rest_v1/page/summary/Vector_database",
        filename="vector_database.txt",
        questions=(
            EvalQuestion(
                prompt="What does a vector database store?",
                expected_any=("vector", "embedding", "high-dimensional", "high dimensional"),
            ),
            EvalQuestion(
                prompt="What kind of search do vector databases enable?",
                expected_any=("similarity", "nearest neighbor", "semantic"),
            ),
            EvalQuestion(
                prompt="Name one common application of vector databases.",
                expected_any=(
                    "recommendation",
                    "search",
                    "retrieval",
                    "rag",
                    "image",
                    "machine learning",
                ),
            ),
        ),
    ),
)
