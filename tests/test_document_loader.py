"""Unit tests for DocumentLoader (no Ollama, no network)."""

from __future__ import annotations

import io

import pytest
from pypdf import PdfWriter

from app.services.document_loader import (
    CODE_EXTENSIONS,
    DOC_EXTENSIONS,
    DocumentLoader,
    UnsupportedFormatError,
)


@pytest.fixture
def loader() -> DocumentLoader:
    """Return a fresh DocumentLoader instance.

    @returns Stateless loader.
    """
    return DocumentLoader()


def test_load_plain_text(loader: DocumentLoader) -> None:
    """UTF-8 .txt content is returned unchanged and stripped."""
    payload = b"  Hello, RAG!\nSecond line.  "
    result = loader.load("note.txt", payload)
    assert result.text == "Hello, RAG!\nSecond line."
    assert result.kind == "doc"
    assert result.language == "text"


def test_load_markdown(loader: DocumentLoader) -> None:
    """Markdown files are read like plain text and classified as docs."""
    result = loader.load("readme.md", b"# Heading\n\nBody paragraph.")
    assert result.text == "# Heading\n\nBody paragraph."
    assert result.kind == "doc"
    assert result.language == "markdown"


def test_unsupported_extension_raises(loader: DocumentLoader) -> None:
    """Unknown extensions surface a clear domain error."""
    with pytest.raises(UnsupportedFormatError):
        loader.load("archive.zip", b"PK\x03\x04")


def test_decoding_fallback_drops_bad_bytes(loader: DocumentLoader) -> None:
    """Invalid UTF-8 bytes are skipped instead of crashing."""
    result = loader.load("partial.txt", b"Hello \xff world.")
    assert "Hello" in result.text
    assert "world" in result.text


def test_load_pdf_returns_extracted_text(loader: DocumentLoader) -> None:
    """A real (in-memory) PDF round-trips through pypdf."""
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    result = loader.load("blank.pdf", buffer.getvalue())
    assert isinstance(result.text, str)
    assert result.kind == "doc"
    assert result.language == "pdf"


def test_load_html_strips_tags_and_noise(loader: DocumentLoader) -> None:
    """HTML extraction drops scripts/styles and yields whitespace-collapsed prose."""
    html = (
        b"<!doctype html><html><head><title>T</title>"
        b"<style>body{color:red}</style>"
        b"<script>alert(1)</script></head>"
        b"<body><h1>Hello</h1><p>World <b>here</b>.</p></body></html>"
    )
    result = loader.load("page.html", html)
    assert "Hello" in result.text
    assert "World" in result.text
    assert "here" in result.text
    assert "alert" not in result.text
    assert "color:red" not in result.text
    assert result.kind == "doc"
    assert result.language == "html"


def test_load_source_code_returns_code_kind(loader: DocumentLoader) -> None:
    """Source files are read verbatim and classified as code."""
    src = b"def greet(name: str) -> str:\n    return f'Hello, {name}!'\n"
    result = loader.load("hello.py", src)
    assert "def greet" in result.text
    assert result.kind == "code"
    assert result.language == "python"


def test_supported_extensions_are_disjoint() -> None:
    """A given extension should classify as either doc or code, never both."""
    overlap = set(DOC_EXTENSIONS).intersection(CODE_EXTENSIONS)
    assert overlap == set()


def test_classify_typescript(loader: DocumentLoader) -> None:
    """TypeScript and TSX files classify as code."""
    assert loader.classify("App.tsx") == ("code", "typescript")
    assert loader.classify("server.ts") == ("code", "typescript")
