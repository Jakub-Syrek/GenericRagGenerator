"""Unit tests for the chunking dispatcher and the code-line chunker."""

from __future__ import annotations

import pytest
from llama_index.core import Document

from app.services.rag_service import CodeChunker


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


def test_dispatcher_routes_code_through_line_chunker(monkeypatch: pytest.MonkeyPatch) -> None:
    """RagService._split_document picks CodeChunker for `kind=code` documents."""
    from app.services import rag_service as module

    class _StubMarkdown:
        def get_nodes_from_documents(self, _docs: list) -> list:
            raise AssertionError("markdown parser must not run on code docs")

    class _StubSentence:
        def get_nodes_from_documents(self, _docs: list) -> list:
            raise AssertionError("sentence splitter must not run on code docs")

    service = module.RagService.__new__(module.RagService)
    service._code_chunker = CodeChunker(lines_per_chunk=3, overlap_lines=1)
    service._markdown_parser = _StubMarkdown()
    service._splitter = _StubSentence()

    document = _make_python_document(10)
    nodes = service._split_document(document)
    assert nodes
    assert all("line_start" in node.metadata for node in nodes)


def test_dispatcher_routes_markdown_through_header_parser() -> None:
    """`kind=doc, language=markdown` documents flow through MarkdownNodeParser."""
    from app.services import rag_service as module

    class _StubSentence:
        def get_nodes_from_documents(self, _docs: list) -> list:
            raise AssertionError("sentence splitter must not run on markdown docs")

    service = module.RagService.__new__(module.RagService)
    service._code_chunker = CodeChunker()
    service._markdown_parser = module.MarkdownNodeParser()
    service._splitter = _StubSentence()

    document = Document(
        id_="doc-md",
        text="# Title\n\nIntro.\n\n## Section A\n\nAlpha body.\n\n## Section B\n\nBeta body.",
        metadata={"filename": "README.md", "kind": "doc", "language": "markdown"},
    )
    nodes = service._split_document(document)
    assert len(nodes) >= 2
