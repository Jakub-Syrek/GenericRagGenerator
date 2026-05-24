"""Extract plain text from supported document and source-code formats."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal

import docx2txt
from bs4 import BeautifulSoup
from pypdf import PdfReader

Kind = Literal["doc", "code"]


DOC_EXTENSIONS: dict[str, str] = {
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
    ".rst": "restructuredtext",
    ".pdf": "pdf",
    ".html": "html",
    ".htm": "html",
    ".docx": "docx",
}


CODE_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".ps1": "powershell",
    ".sql": "sql",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".xml": "xml",
    ".ini": "ini",
    ".cfg": "ini",
    ".css": "css",
    ".scss": "css",
}


SUPPORTED_EXTENSIONS: set[str] = set(DOC_EXTENSIONS) | set(CODE_EXTENSIONS)


class UnsupportedFormatError(ValueError):
    """Raised when a file extension is not supported by the loader."""


@dataclass(frozen=True)
class LoadedDocument:
    """Extracted text plus classification metadata."""

    text: str
    kind: Kind
    language: str
    extension: str


class DocumentLoader:
    """Dispatch raw bytes through the appropriate parser per file extension."""

    def classify(self, filename: str) -> tuple[Kind, str]:
        """Return `(kind, language)` for a filename.

        @param filename Original file name (only the extension is inspected).
        @returns Tuple of kind (`"doc"`/`"code"`) and language identifier.
        @raises UnsupportedFormatError When the extension is not supported.
        """
        suffix = Path(filename).suffix.lower()
        if suffix in CODE_EXTENSIONS:
            return "code", CODE_EXTENSIONS[suffix]
        if suffix in DOC_EXTENSIONS:
            return "doc", DOC_EXTENSIONS[suffix]
        raise UnsupportedFormatError(f"Unsupported file type: {suffix}")

    def load(self, filename: str, payload: bytes) -> LoadedDocument:
        """Decode raw bytes into plain text plus classification metadata.

        @param filename Original file name (used to pick the parser).
        @param payload  Raw file bytes.
        @returns Populated `LoadedDocument` with stripped text.
        @raises UnsupportedFormatError When the extension is not supported.
        """
        kind, language = self.classify(filename)
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            text = self._read_pdf(payload)
        elif suffix in {".html", ".htm"}:
            text = self._read_html(payload)
        elif suffix == ".docx":
            text = self._read_docx(payload)
        else:
            text = self._read_text(payload)
        return LoadedDocument(text=text, kind=kind, language=language, extension=suffix)

    @staticmethod
    def _read_text(payload: bytes) -> str:
        """Decode payload as UTF-8 with a permissive fallback.

        @param payload Raw bytes.
        @returns Decoded text, stripped of trailing whitespace.
        """
        try:
            return payload.decode("utf-8").strip()
        except UnicodeDecodeError:
            return payload.decode("utf-8", errors="ignore").strip()

    @staticmethod
    def _read_pdf(payload: bytes) -> str:
        """Extract text from every page of a PDF.

        @param payload Raw PDF bytes.
        @returns Newline-joined text of all pages.
        """
        reader = PdfReader(BytesIO(payload))
        pages = (page.extract_text() or "" for page in reader.pages)
        return "\n".join(pages).strip()

    @staticmethod
    def _read_html(payload: bytes) -> str:
        """Strip tags and non-content elements from HTML.

        @param payload Raw HTML bytes.
        @returns Whitespace-collapsed prose text.
        """
        soup = BeautifulSoup(payload, "html.parser")
        for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = (line.strip() for line in text.splitlines())
        return "\n".join(line for line in lines if line).strip()

    @staticmethod
    def _read_docx(payload: bytes) -> str:
        """Extract text from a .docx file via docx2txt.

        @param payload Raw .docx bytes.
        @returns Extracted text, stripped of trailing whitespace.
        """
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
            handle.write(payload)
            tmp_path = Path(handle.name)
        try:
            return (docx2txt.process(str(tmp_path)) or "").strip()
        finally:
            tmp_path.unlink(missing_ok=True)
