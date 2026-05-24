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
    as the top hit. `expected_kind` (optional) asserts the kind of the top
    source. `None` for `expected_top_source` marks an out-of-corpus probe:
    the assistant must refuse to answer (`expected_any` is then empty and
    `ooc` is True).
    """

    prompt: str
    expected_any: tuple[str, ...]
    expected_top_source: str | None
    expected_kind: str | None = None
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
                prompt=(
                    "In the article about retrieval-augmented generation, what is the "
                    "full name behind the acronym RAG?"
                ),
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
                    "object detection",
                    "multi-modal",
                    "semantic",
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


REPOSITORY_NAME = "mini_parser"


REPOSITORY_QUESTIONS: tuple[EvalQuestion, ...] = (
    EvalQuestion(
        prompt="What transformation does the slugify helper apply to its input string?",
        expected_any=("lowercase", "lower", "hyphen", "whitespace"),
        expected_top_source="src/utils/strings.py",
        expected_kind="code",
    ),
    EvalQuestion(
        prompt="What does parse_sentence do in the mini_parser project?",
        expected_any=("token", "whitespace", "punctuation", "split"),
        expected_top_source="src/parser.py",
        expected_kind="code",
    ),
    EvalQuestion(
        prompt="According to the README, how do you run the mini_parser project from the command line?",
        expected_any=("python -m mini_parser.cli", "mini_parser.cli"),
        expected_top_source="README.md",
        expected_kind="doc",
    ),
    EvalQuestion(
        prompt="What three layers are described in the architecture document?",
        expected_any=("cli", "parser", "utils"),
        expected_top_source="docs/architecture.html",
        expected_kind="doc",
    ),
    EvalQuestion(
        prompt="Which Python standard-library module does the mini_parser CLI import to parse arguments?",
        expected_any=("argparse",),
        expected_top_source="src/cli.py",
        expected_kind="code",
    ),
    EvalQuestion(
        prompt=(
            "Which two `str` methods does parse_sentence call on each character to "
            "decide whether to keep it or replace it with whitespace?"
        ),
        expected_any=("isalnum", "isspace"),
        expected_top_source="src/parser.py",
        expected_kind="code",
    ),
    EvalQuestion(
        prompt=("Which attribute of the parsed argparse namespace does cli.py pass to " "parse_sentence?"),
        expected_any=("args.text", "text attribute", '"text"', "'text'"),
        expected_top_source="src/cli.py",
        expected_kind="code",
    ),
    EvalQuestion(
        prompt=("How does slugify split its input into pieces before joining them " "with hyphens?"),
        expected_any=("split", "whitespace"),
        expected_top_source="src/utils/strings.py",
        expected_kind="code",
    ),
    EvalQuestion(
        prompt="According to the README, what does the mini_parser project exist as?",
        expected_any=(
            "example project",
            "end-to-end testing",
            "paired with",
            "documentation",
        ),
        expected_top_source="README.md",
        expected_kind="doc",
    ),
    EvalQuestion(
        prompt=(
            "According to the architecture document, in which direction does data "
            "flow through the three layers?"
        ),
        expected_any=("linearly", "from the cli", "no cycles", "no side effects"),
        expected_top_source="docs/architecture.html",
        expected_kind="doc",
    ),
    EvalQuestion(
        prompt="From which module does the mini_parser CLI import the slugify helper?",
        expected_any=("utils.strings", "utils/strings", ".utils.strings"),
        expected_top_source="src/cli.py",
        expected_kind="code",
    ),
    EvalQuestion(
        prompt="Does the mini_parser project document any retry behaviour on network failures?",
        expected_any=(),
        expected_top_source=None,
        ooc=True,
    ),
)
