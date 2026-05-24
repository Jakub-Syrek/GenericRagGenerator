"""Chunking strategies (Strategy + Registry patterns).

Each `Chunker` implements a single `split(document) -> list[BaseNode]`
contract; the `ChunkerRegistry` picks the right implementation per
document based on its `kind` and `language` metadata. New formats can be
plugged in by writing a new `Chunker` and registering it — no changes
required in the orchestrator.

Tree-sitter was deliberately rejected for the code path: pure-Python
line windows are robust on Windows / locked-down corporate boxes that
forbid native compilation, and they still surface exact line ranges in
chunk metadata so citations remain precise.
"""

from __future__ import annotations

from typing import Protocol

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import (
    BaseNode,
    NodeRelationship,
    RelatedNodeInfo,
    TextNode,
)


class Chunker(Protocol):
    """Strategy interface: turn one `Document` into retrieval-ready nodes."""

    def split(self, document: Document) -> list[BaseNode]:
        """Split a document.

        @param document Source LlamaIndex `Document`.
        @returns Ordered list of nodes for the index.
        """
        ...


class SentenceChunker:
    """Default strategy backed by LlamaIndex `SentenceSplitter`."""

    def __init__(self, *, chunk_size: int, chunk_overlap: int) -> None:
        """Configure the underlying splitter.

        @param chunk_size    Target chunk length in characters.
        @param chunk_overlap Trailing overlap, in characters.
        """
        self._splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def split(self, document: Document) -> list[BaseNode]:
        """Forward to `SentenceSplitter`.

        @param document Source document.
        @returns Sentence-aware chunks.
        """
        return list(self._splitter.get_nodes_from_documents([document]))


class MarkdownChunker:
    """Header-aware strategy backed by LlamaIndex `MarkdownNodeParser`."""

    def __init__(self) -> None:
        """Build the underlying parser (no configuration required)."""
        self._parser = MarkdownNodeParser()

    def split(self, document: Document) -> list[BaseNode]:
        """Forward to `MarkdownNodeParser`.

        @param document Source document.
        @returns Header-section chunks.
        """
        return list(self._parser.get_nodes_from_documents([document]))


class CodeChunker:
    """Line-window splitter producing `TextNode`s with `line_start` / `line_end`.

    Tree-sitter would give us syntax-aware chunks but adds native deps
    that don't ship well into restricted corporate environments. A pure-
    Python line window with explicit overlap is robust and good enough:
    it preserves indentation, never crosses an empty-line boundary mid-
    window, and citation gains the exact line range every time.
    """

    def __init__(self, *, lines_per_chunk: int = 60, overlap_lines: int = 10) -> None:
        """Configure window size and overlap.

        @param lines_per_chunk Maximum lines per chunk.
        @param overlap_lines   Number of trailing lines repeated in the next chunk.
        @raises ValueError When parameters are inconsistent.
        """
        if lines_per_chunk <= 0:
            raise ValueError("lines_per_chunk must be positive")
        if overlap_lines < 0 or overlap_lines >= lines_per_chunk:
            raise ValueError("overlap_lines must be in [0, lines_per_chunk)")
        self._lines_per_chunk = lines_per_chunk
        self._overlap_lines = overlap_lines

    def split(self, document: Document) -> list[BaseNode]:
        """Split a code document into overlapping line windows.

        @param document Source LlamaIndex `Document`.
        @returns Ordered list of `TextNode`s with line-range metadata.
        """
        lines = document.text.splitlines()
        if not lines:
            return []
        step = self._lines_per_chunk - self._overlap_lines
        starts = [start for start in range(0, len(lines), step) if start < len(lines)]
        return [self._build_node(document, lines, start) for start in starts]

    def _build_node(self, document: Document, lines: list[str], start: int) -> TextNode:
        """Materialise one chunk node from a line window.

        @param document Source document (for metadata + relationships).
        @param lines    Source lines.
        @param start    Zero-based index of the first line in this window.
        @returns A `TextNode` carrying the windowed text and line metadata.
        """
        end = min(start + self._lines_per_chunk, len(lines))
        metadata = dict(document.metadata)
        metadata["line_start"] = start + 1
        metadata["line_end"] = end
        excluded_embed = [
            *(document.excluded_embed_metadata_keys or []),
            "line_start",
            "line_end",
        ]
        node = TextNode(
            text="\n".join(lines[start:end]),
            metadata=metadata,
            excluded_embed_metadata_keys=excluded_embed,
            excluded_llm_metadata_keys=list(document.excluded_llm_metadata_keys or []),
        )
        node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=document.id_)
        return node


class ChunkerRegistry:
    """Registry that picks a `Chunker` per `(kind, language)` (Strategy + Registry).

    Lookup order: explicit language match → explicit kind match → default.
    Mutable at construction time only — `RagService` builds and freezes
    one instance up front so dispatch is just a dict lookup at runtime.
    """

    def __init__(self, *, default: Chunker) -> None:
        """Configure the fallback strategy used when no rule matches.

        @param default Chunker used when neither language nor kind match.
        """
        self._default: Chunker = default
        self._by_language: dict[str, Chunker] = {}
        self._by_kind: dict[str, Chunker] = {}

    def register_language(self, language: str, chunker: Chunker) -> ChunkerRegistry:
        """Register a chunker keyed on the `language` metadata field.

        @param language Lowercase language identifier (e.g. `markdown`).
        @param chunker  Strategy to use for documents in that language.
        @returns Self (fluent builder).
        """
        self._by_language[language] = chunker
        return self

    def register_kind(self, kind: str, chunker: Chunker) -> ChunkerRegistry:
        """Register a chunker keyed on the `kind` metadata field.

        @param kind    `doc` or `code`.
        @param chunker Strategy to use for documents of that kind.
        @returns Self (fluent builder).
        """
        self._by_kind[kind] = chunker
        return self

    def pick(self, document: Document) -> Chunker:
        """Resolve which `Chunker` should handle a document.

        @param document Document under inspection.
        @returns The matching strategy (always non-null thanks to the default).
        """
        language = str(document.metadata.get("language", ""))
        kind = str(document.metadata.get("kind", "doc"))
        if language in self._by_language:
            return self._by_language[language]
        if kind in self._by_kind:
            return self._by_kind[kind]
        return self._default

    def split(self, document: Document) -> list[BaseNode]:
        """Dispatch to the picked strategy.

        @param document Document to split.
        @returns Nodes from the chosen strategy.
        """
        return self.pick(document).split(document)
