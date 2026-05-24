"""Extract plain text from supported document and source-code formats."""

from __future__ import annotations

import subprocess  # nosec B404 - subprocess use is the whole point of the sandbox
import sys
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal

import docx2txt
from bs4 import BeautifulSoup
from pypdf import PdfReader

Kind = Literal["doc", "code"]


class ParserCrashError(RuntimeError):
    """Raised when a sandboxed parser worker crashes or times out."""


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


# Sandboxed extensions: parsers in this set can be routed through a
# subprocess to isolate the worker from malformed-input crashes.
SANDBOXABLE_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx", ".html", ".htm"})


class UnsupportedFormatError(ValueError):
    """Raised when a file extension is not supported by the loader."""


def read_pdf(payload: bytes) -> str:
    """Extract text from every page of a PDF (module-level helper).

    Module-level so the subprocess worker can import it without
    instantiating `DocumentLoader`.

    @param payload Raw PDF bytes.
    @returns Newline-joined text of all pages, stripped.
    """
    reader = PdfReader(BytesIO(payload))
    pages = (page.extract_text() or "" for page in reader.pages)
    return "\n".join(pages).strip()


def read_html(payload: bytes) -> str:
    """Strip tags + non-content elements from HTML (module-level helper).

    @param payload Raw HTML bytes.
    @returns Whitespace-collapsed prose text.
    """
    soup = BeautifulSoup(payload, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = (line.strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line).strip()


def read_docx(payload: bytes) -> str:
    """Extract text from a .docx via docx2txt (module-level helper).

    @param payload Raw .docx bytes.
    @returns Extracted text, stripped.
    """
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
        handle.write(payload)
        tmp_path = Path(handle.name)
    try:
        return (docx2txt.process(str(tmp_path)) or "").strip()
    finally:
        tmp_path.unlink(missing_ok=True)


def read_text(payload: bytes) -> str:
    """Decode payload as UTF-8 with a permissive fallback (module-level helper).

    @param payload Raw bytes.
    @returns Decoded text, stripped.
    """
    try:
        return payload.decode("utf-8").strip()
    except UnicodeDecodeError:
        return payload.decode("utf-8", errors="ignore").strip()


@dataclass(frozen=True)
class LoadedDocument:
    """Extracted text plus classification metadata."""

    text: str
    kind: Kind
    language: str
    extension: str


class DocumentLoader:
    """Dispatch raw bytes through the appropriate parser per file extension.

    Optionally routes binary parsers (PDF / DOCX / HTML) through a
    subprocess sandbox so a crash or runaway parser doesn't take down
    the worker. The sandbox is opt-in (`sandbox_enabled=True`); plain
    text and source-code paths always run inline since they have no
    parser-crash surface.
    """

    def __init__(
        self,
        *,
        sandbox_enabled: bool = False,
        sandbox_timeout_seconds: float = 10.0,
    ) -> None:
        """Configure the optional subprocess sandbox.

        @param sandbox_enabled         Route PDF / DOCX / HTML through a
                                       subprocess. Off by default — keeps
                                       single-process semantics for the
                                       cases that don't need isolation.
        @param sandbox_timeout_seconds Hard wall-clock limit per parse.
                                       A worker that runs longer is killed
                                       and the call raises `ParserCrashError`.
        """
        self._sandbox_enabled = sandbox_enabled
        self._sandbox_timeout = sandbox_timeout_seconds

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
        @raises ParserCrashError       When the sandboxed worker crashes
                                       or exceeds the timeout.
        """
        kind, language = self.classify(filename)
        suffix = Path(filename).suffix.lower()
        if self._sandbox_enabled and suffix in SANDBOXABLE_EXTENSIONS:
            text = self._sandbox_parse(suffix, payload)
        else:
            text = self._inline_parse(suffix, payload)
        return LoadedDocument(text=text, kind=kind, language=language, extension=suffix)

    @staticmethod
    def _inline_parse(suffix: str, payload: bytes) -> str:
        """Run the right module-level parser in-process.

        @param suffix  Lowercase extension (with leading dot).
        @param payload Raw file bytes.
        @returns Extracted text.
        """
        if suffix == ".pdf":
            return read_pdf(payload)
        if suffix in {".html", ".htm"}:
            return read_html(payload)
        if suffix == ".docx":
            return read_docx(payload)
        return read_text(payload)

    def _sandbox_parse(self, suffix: str, payload: bytes) -> str:
        """Run the parser in a subprocess with a wall-clock timeout.

        The worker script lives at `app.services.parser_worker`. We
        pass the suffix via argv and the payload via stdin (so binary
        content doesn't blow up the argv length limit), and read text
        back from stdout. Anything non-zero on the return code or a
        timeout becomes a `ParserCrashError`.

        @param suffix  Lowercase extension (with leading dot).
        @param payload Raw file bytes.
        @returns Extracted text.
        @raises ParserCrashError On crash, timeout or non-zero exit.
        """
        backend_dir = Path(__file__).resolve().parents[2]
        try:
            completed = subprocess.run(  # nosec B603 - argv is fully controlled, payload arrives via stdin
                [sys.executable, "-m", "app.services.parser_worker", suffix],
                input=payload,
                capture_output=True,
                timeout=self._sandbox_timeout,
                cwd=str(backend_dir),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ParserCrashError(f"Sandboxed parser timed out after {self._sandbox_timeout}s") from exc
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace")[:200]
            raise ParserCrashError(f"Sandboxed parser exited {completed.returncode}: {stderr}")
        return completed.stdout.decode("utf-8", errors="replace").strip()
