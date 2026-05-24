"""Definition of the public corpus + canned questions used by the RAG eval.

Each entry points to a Wikipedia REST `summary` endpoint that returns a small,
self-contained `extract` (plain text intro of an article). Questions are paired
with the filename that should be retrieved top-1 and a list of substrings any
of which must appear in a faithful answer. A trailing "out-of-corpus" question
tests that the assistant refuses to answer when the documents don't cover the
topic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalQuestion:
    """One canned question with scoring rules.

    `expected_top_source` is the filename the retriever is expected to surface
    as the top hit. `None` marks an out-of-corpus probe: the assistant must
    refuse to answer (`expected_any` is then empty and `ooc` is True).
    """

    prompt: str
    expected_any: tuple[str, ...]
    expected_top_source: str | None
    ooc: bool = False


@dataclass(frozen=True)
class EvalDocument:
    """One source document fetched from Wikipedia and ingested into the RAG."""

    title: str
    url: str
    filename: str
    questions: tuple[EvalQuestion, ...]


REFUSAL_PHRASES: tuple[str, ...] = (
    "do not cover",
    "don't cover",
    "not covered",
    "not contained",
    "no information",
    "outside the scope",
    "documents don't",
    "documents do not",
    "i cannot",
    "i can't",
    "i don't have",
    "cannot answer",
    "can't answer",
    "no relevant",
    "not mentioned",
    "no mention",
)


CORPUS: tuple[EvalDocument, ...] = (
    EvalDocument(
        title="Retrieval-augmented generation",
        url="https://en.wikipedia.org/api/rest_v1/page/summary/Retrieval-augmented_generation",
        filename="rag.txt",
        questions=(
            EvalQuestion(
                prompt="What does RAG stand for?",
                expected_any=("retrieval-augmented generation", "retrieval augmented generation"),
                expected_top_source="rag.txt",
            ),
            EvalQuestion(
                prompt="What kind of model does RAG combine retrieval with?",
                expected_any=("language model", "generative", "llm"),
                expected_top_source="rag.txt",
            ),
            EvalQuestion(
                prompt="Why would someone use RAG instead of a plain language model?",
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
                expected_top_source="rag.txt",
            ),
        ),
    ),
    EvalDocument(
        title="Vector database",
        url="https://en.wikipedia.org/api/rest_v1/page/summary/Vector_database",
        filename="vector_database.txt",
        questions=(
            EvalQuestion(
                prompt="What kind of data does a vector database store?",
                expected_any=("vector", "embedding", "high-dimensional", "high dimensional"),
                expected_top_source="vector_database.txt",
            ),
            EvalQuestion(
                prompt="What kind of search do vector databases enable?",
                expected_any=("similarity", "nearest neighbor", "semantic"),
                expected_top_source="vector_database.txt",
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
                expected_top_source="vector_database.txt",
            ),
        ),
    ),
    EvalDocument(
        title="Word embedding",
        url="https://en.wikipedia.org/api/rest_v1/page/summary/Word_embedding",
        filename="word_embedding.txt",
        questions=(
            EvalQuestion(
                prompt="In word embeddings, what are words mapped to?",
                expected_any=(
                    "vector",
                    "real number",
                    "real-valued",
                    "real value",
                    "embedding",
                    "numeric",
                ),
                expected_top_source="word_embedding.txt",
            ),
            EvalQuestion(
                prompt="What property of words is captured by their embedding vectors?",
                expected_any=("meaning", "semantic", "similar", "context", "syntactic", "distribution"),
                expected_top_source="word_embedding.txt",
            ),
        ),
    ),
    EvalDocument(
        title="Photosynthesis",
        url="https://en.wikipedia.org/api/rest_v1/page/summary/Photosynthesis",
        filename="photosynthesis.txt",
        questions=(
            EvalQuestion(
                prompt="What gas does photosynthesis release as a byproduct?",
                expected_any=("oxygen",),
                expected_top_source="photosynthesis.txt",
            ),
            EvalQuestion(
                prompt="What kind of energy do photosynthetic organisms convert during photosynthesis?",
                expected_any=("light", "sunlight", "chemical"),
                expected_top_source="photosynthesis.txt",
            ),
        ),
    ),
    EvalDocument(
        title="Out-of-corpus probe",
        url="",
        filename="(none)",
        questions=(
            EvalQuestion(
                prompt="What are the typical symptoms of malaria in humans?",
                expected_any=(),
                expected_top_source=None,
                ooc=True,
            ),
            EvalQuestion(
                prompt="Who won the FIFA World Cup in 2022?",
                expected_any=(),
                expected_top_source=None,
                ooc=True,
            ),
        ),
    ),
)
