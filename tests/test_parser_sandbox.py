"""Tests for the subprocess parser sandbox in `DocumentLoader`."""

from __future__ import annotations

import io
import subprocess
from typing import Any

import pytest
from pypdf import PdfWriter

from app.services.document_loader import DocumentLoader, ParserCrashError


def _blank_pdf_bytes() -> bytes:
    """Build the smallest valid PDF payload (one blank page)."""
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_inline_mode_runs_parser_in_process() -> None:
    """With the sandbox disabled, parsing happens inline (no subprocess)."""
    loader = DocumentLoader(sandbox_enabled=False)
    result = loader.load("blank.pdf", _blank_pdf_bytes())
    assert isinstance(result.text, str)
    assert result.kind == "doc"
    assert result.language == "pdf"


def test_sandbox_routes_pdf_through_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sandbox-enabled PDF parse goes through `subprocess.run`."""
    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> Any:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"sandboxed-text", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    loader = DocumentLoader(sandbox_enabled=True, sandbox_timeout_seconds=2.0)
    result = loader.load("doc.pdf", b"%PDF-1.4 fake")
    assert result.text == "sandboxed-text"
    assert "app.services.parser_worker" in captured["cmd"]
    assert captured["kwargs"]["timeout"] == 2.0
    assert captured["kwargs"]["input"] == b"%PDF-1.4 fake"


def test_sandbox_does_not_touch_plain_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plain text / source-code paths skip the subprocess entirely."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    loader = DocumentLoader(sandbox_enabled=True, sandbox_timeout_seconds=2.0)
    result = loader.load("notes.txt", b"hello world")
    assert result.text == "hello world"


def test_sandbox_timeout_surfaces_as_parser_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """A timed-out worker raises `ParserCrashError` with the limit echoed."""

    def fake_run(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout", 1.0))

    monkeypatch.setattr(subprocess, "run", fake_run)
    loader = DocumentLoader(sandbox_enabled=True, sandbox_timeout_seconds=1.5)
    with pytest.raises(ParserCrashError, match="1.5"):
        loader.load("evil.pdf", b"fake")


def test_sandbox_nonzero_exit_surfaces_as_parser_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """A worker that exits non-zero raises `ParserCrashError` with its stderr."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=139, stdout=b"", stderr=b"Segmentation fault"
        ),
    )
    loader = DocumentLoader(sandbox_enabled=True, sandbox_timeout_seconds=1.0)
    with pytest.raises(ParserCrashError, match="139"):
        loader.load("evil.pdf", b"fake")
