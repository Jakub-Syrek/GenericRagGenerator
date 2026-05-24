"""Extract plain text from supported document formats."""

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

SUPPORTED_EXTENSIONS: set[str] = {".pdf", ".txt", ".md", ".markdown"}


class UnsupportedFormatError(ValueError):
    """Raised when a file extension is not supported by the loader."""


class DocumentLoader:
    """Read raw bytes from supported formats and return clean text."""

    def load(self, filename: str, payload: bytes) -> str:
        """Return concatenated text extracted from the given file payload.

        @param filename Original file name (used only to detect extension).
        @param payload  Raw file bytes.
        @returns Extracted text (UTF-8 string), stripped of trailing whitespace.
        @raises UnsupportedFormatError When the extension is not supported.
        """
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFormatError(f"Unsupported file type: {suffix}")

        if suffix == ".pdf":
            return self._read_pdf(payload)
        return self._read_text(payload)

    @staticmethod
    def _read_text(payload: bytes) -> str:
        """Decode payload as UTF-8 with a permissive fallback.

        @param payload Raw bytes.
        @returns Decoded string.
        """
        try:
            return payload.decode("utf-8").strip()
        except UnicodeDecodeError:
            return payload.decode("utf-8", errors="ignore").strip()

    @staticmethod
    def _read_pdf(payload: bytes) -> str:
        """Extract text from every page of a PDF document.

        @param payload Raw PDF bytes.
        @returns Newline-joined text of all pages.
        """
        reader = PdfReader(BytesIO(payload))
        pages = (page.extract_text() or "" for page in reader.pages)
        return "\n".join(pages).strip()
