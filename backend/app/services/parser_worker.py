"""Subprocess entry point for sandboxed parsing.

Invoked as `python -m app.services.parser_worker <suffix>` with the
raw file bytes on stdin. Prints the extracted text on stdout. Any
exception inside `pypdf` / `docx2txt` / BeautifulSoup crashes this
worker — never the parent — and surfaces as `ParserCrashError` to the
caller.
"""

from __future__ import annotations

import sys

from .document_loader import (
    SANDBOXABLE_EXTENSIONS,
    read_docx,
    read_html,
    read_pdf,
    read_text,
)


def _parse(suffix: str, payload: bytes) -> str:
    """Dispatch one parse call by extension.

    @param suffix  Lowercase extension (with leading dot).
    @param payload Raw file bytes from stdin.
    @returns Extracted text.
    """
    if suffix == ".pdf":
        return read_pdf(payload)
    if suffix in {".html", ".htm"}:
        return read_html(payload)
    if suffix == ".docx":
        return read_docx(payload)
    return read_text(payload)


def main() -> int:
    """Entry point: read stdin → write parsed text to stdout.

    @returns Process exit code (0 success, 2 unsupported suffix).
    """
    if len(sys.argv) < 2:
        sys.stderr.write("missing suffix argument\n")
        return 2
    suffix = sys.argv[1].lower()
    if suffix not in SANDBOXABLE_EXTENSIONS and suffix:
        # Plain text / source code paths shouldn't go through the
        # sandbox in the first place; refuse so misuse is loud.
        sys.stderr.write(f"unsupported sandbox suffix: {suffix}\n")
        return 2
    payload = sys.stdin.buffer.read()
    text = _parse(suffix, payload)
    sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
