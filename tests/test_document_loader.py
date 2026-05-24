"""Unit tests for DocumentLoader (no Ollama, no network)."""

from __future__ import annotations

import io

import pytest
from pypdf import PdfWriter

from app.services.document_loader import DocumentLoader, UnsupportedFormatError


@pytest.fixture
def loader() -> DocumentLoader:
    """Return a fresh DocumentLoader instance.

    @returns Stateless loader.
    """
    return DocumentLoader()


def test_load_plain_text(loader: DocumentLoader) -> None:
    """UTF-8 .txt content is returned unchanged and stripped."""
    payload = b"  Hello, RAG!\nSecond line.  "
    assert loader.load("note.txt", payload) == "Hello, RAG!\nSecond line."


def test_load_markdown(loader: DocumentLoader) -> None:
    """Markdown files are read like plain text."""
    payload = b"# Heading\n\nBody paragraph."
    assert loader.load("readme.md", payload) == "# Heading\n\nBody paragraph."


def test_unsupported_extension_raises(loader: DocumentLoader) -> None:
    """Unknown extensions surface a clear domain error."""
    with pytest.raises(UnsupportedFormatError):
        loader.load("archive.zip", b"PK\x03\x04")


def test_decoding_fallback_drops_bad_bytes(loader: DocumentLoader) -> None:
    """Invalid UTF-8 bytes are skipped instead of crashing."""
    payload = b"Hello \xff world."
    result = loader.load("partial.txt", payload)
    assert "Hello" in result and "world" in result


def test_load_pdf_returns_extracted_text(loader: DocumentLoader) -> None:
    """A real (in-memory) PDF round-trips through pypdf."""
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    result = loader.load("blank.pdf", buffer.getvalue())
    assert isinstance(result, str)
