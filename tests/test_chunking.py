"""Unit tests for the chunking dispatcher and the code-line chunker."""

from __future__ import annotations

import pytest
from llama_index.core import Document

from app.services.chunking import (
    ChunkerRegistry,
    CodeChunker,
    MarkdownChunker,
    SentenceChunker,
)


def _make_python_document(lines: int) -> Document:
    """Build a Python `Document` containing `lines` lines with a code-kind tag.

    @param lines Number of source lines to emit.
    @returns A LlamaIndex Document marked as `kind=code, language=python`.
    """
    text = "\n".join(f"def fn_{index}():\n    return {index}" for index in range(lines // 2))
    return Document(
        id_="doc-1",
        text=text,
        metadata={"filename": "src/sample.py", "kind": "code", "language": "python"},
    )


def test_code_chunker_emits_line_metadata() -> None:
    """Each emitted node carries line_start / line_end matching the window."""
    chunker = CodeChunker(lines_per_chunk=4, overlap_lines=1)
    document = _make_python_document(20)
    nodes = chunker.split(document)
    assert nodes
    for node in nodes:
        assert "line_start" in node.metadata
        assert "line_end" in node.metadata
        assert node.metadata["line_end"] >= node.metadata["line_start"]
    assert nodes[0].metadata["line_start"] == 1


def test_code_chunker_overlap_repeats_trailing_lines() -> None:
    """The first line of the second window is `lines_per_chunk - overlap + 1`."""
    chunker = CodeChunker(lines_per_chunk=5, overlap_lines=2)
    document = Document(
        id_="doc-x",
        text="\n".join(f"line {index}" for index in range(1, 16)),
        metadata={"filename": "x.py", "kind": "code", "language": "python"},
    )
    nodes = chunker.split(document)
    assert nodes[0].metadata["line_start"] == 1
    assert nodes[0].metadata["line_end"] == 5
    assert nodes[1].metadata["line_start"] == 4
    assert nodes[1].metadata["line_end"] == 8


def test_code_chunker_rejects_bad_overlap() -> None:
    """`overlap_lines` >= `lines_per_chunk` is a configuration error."""
    with pytest.raises(ValueError, match="overlap"):
        CodeChunker(lines_per_chunk=4, overlap_lines=4)


def test_code_chunker_empty_document_returns_no_nodes() -> None:
    """An empty document produces zero chunks."""
    chunker = CodeChunker()
    document = Document(
        id_="doc-empty",
        text="",
        metadata={"filename": "empty.py", "kind": "code", "language": "python"},
    )
    assert chunker.split(document) == []


def test_registry_routes_code_through_line_chunker() -> None:
    """`ChunkerRegistry.pick` returns the code strategy for `kind=code` docs."""

    class _Failing:
        def split(self, _document: object) -> list:
            raise AssertionError("non-code strategy must not run on code docs")

    registry = (
        ChunkerRegistry(default=_Failing())
        .register_language("markdown", _Failing())
        .register_kind("code", CodeChunker(lines_per_chunk=3, overlap_lines=1))
    )
    document = _make_python_document(10)
    nodes = registry.split(document)
    assert nodes
    assert all("line_start" in node.metadata for node in nodes)


def test_registry_routes_markdown_through_header_parser() -> None:
    """`kind=doc, language=markdown` documents flow through `MarkdownChunker`."""

    class _Failing:
        def split(self, _document: object) -> list:
            raise AssertionError("default strategy must not run on markdown docs")

    registry = (
        ChunkerRegistry(default=_Failing())
        .register_language("markdown", MarkdownChunker())
        .register_kind("code", _Failing())
    )
    document = Document(
        id_="doc-md",
        text="# Title\n\nIntro.\n\n## Section A\n\nAlpha body.\n\n## Section B\n\nBeta body.",
        metadata={"filename": "README.md", "kind": "doc", "language": "markdown"},
    )
    nodes = registry.split(document)
    assert len(nodes) >= 2


def test_registry_falls_back_to_default() -> None:
    """A document without a registered kind/language hits the default strategy."""
    default = SentenceChunker(chunk_size=200, chunk_overlap=20)
    registry = ChunkerRegistry(default=default)
    document = Document(
        id_="doc-txt",
        text="Just some plain prose to split.",
        metadata={"filename": "note.txt", "kind": "doc", "language": "text"},
    )
    assert registry.pick(document) is default
