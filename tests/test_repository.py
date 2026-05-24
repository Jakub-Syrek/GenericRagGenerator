"""Unit tests for ZIP repository ingest (safety + happy path).

These tests do NOT need Ollama: they exercise the safety guards and the
classification + skip bookkeeping at the service level using monkey-patched
embedding internals.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

import pytest

from app.config import get_settings
from app.services.document_loader import DocumentLoader
from app.services.rag_service import (
    DEFAULT_IGNORE,
    MAX_REPO_FILE_BYTES,
    RagService,
    RepositoryError,
)


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> RagService:
    """Return a RagService with embedding + index calls stubbed out.

    @param monkeypatch pytest monkeypatching fixture.
    @param tmp_path    pytest-managed temp directory.
    @returns RagService instance whose Ollama and Chroma touch-points are no-ops.
    """
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    settings = get_settings()
    # Build the service but neutralise the parts that hit Ollama.
    instance = RagService.__new__(RagService)
    instance._settings = settings
    instance._loader = DocumentLoader()
    instance._upload_dir = settings.upload_dir
    instance._upload_dir.mkdir(parents=True, exist_ok=True)
    instance._collection = None
    instance._chroma_client = None

    from app.services.chunking import ChunkerRegistry, CodeChunker

    class _StubChunker:
        """One-node-per-doc strategy for the safety tests."""

        def split(self, document: object) -> list:
            return [{"document_id": getattr(document, "id_", "")}]

    class _NoopIndex:
        def __init__(self) -> None:
            self.inserted: list[Any] = []

        def insert_nodes(self, nodes: list) -> None:
            self.inserted.extend(nodes)

    instance._chunker_registry = (
        ChunkerRegistry(default=_StubChunker())
        .register_language("markdown", _StubChunker())
        .register_kind("code", _StubChunker())
    )
    # CodeChunker is still re-exported from rag_service for back-compat with
    # tests that import it; this assignment also keeps it imported.
    _ = CodeChunker
    instance._index = _NoopIndex()

    class _StubHybrid:
        """No-op hybrid retriever for tests that don't exercise BM25."""

        def invalidate(self) -> None:
            pass

    instance._hybrid = _StubHybrid()
    instance._search_cache = None
    instance._query_cache = None
    from app.services.reranker import NullReranker

    instance._reranker = NullReranker()
    return instance


def _make_zip(entries: dict[str, bytes], extras: list[zipfile.ZipInfo] | None = None) -> bytes:
    """Build an in-memory ZIP from a `path -> bytes` mapping.

    @param entries Mapping of archive paths to raw file content.
    @param extras  Optional pre-built ZipInfo entries appended verbatim.
    @returns Raw ZIP bytes.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in entries.items():
            archive.writestr(path, content)
        for info in extras or []:
            archive.writestr(info, b"")
    return buffer.getvalue()


def test_ingests_supported_files_with_repository_metadata(service: RagService) -> None:
    """A small ZIP with one .py + one README.md is fully ingested with metadata."""
    payload = _make_zip(
        {
            "demo/README.md": b"# Demo repo\n\nSome docs.",
            "demo/src/hello.py": b"def hello():\n    return 'hi'\n",
        }
    )
    record = service.ingest_repository("demo.zip", payload)
    paths = {file.path for file in record.files}
    assert paths == {"README.md", "src/hello.py"}
    kinds = {file.path: file.kind for file in record.files}
    assert kinds["src/hello.py"] == "code"
    assert kinds["README.md"] == "doc"
    assert record.name == "demo"
    assert record.skipped == []


def test_skips_ignored_directories(service: RagService) -> None:
    """Entries under .git/, node_modules/ etc. are skipped with reason `ignored`."""
    payload = _make_zip(
        {
            "demo/.git/config": b"junk",
            "demo/node_modules/foo/index.js": b"console.log(1);",
            "demo/src/hello.py": b"def hello(): pass\n",
        }
    )
    record = service.ingest_repository("demo.zip", payload)
    skipped_paths = {item.path: item.reason for item in record.skipped}
    assert ".git/config" in skipped_paths
    assert "node_modules/foo/index.js" in skipped_paths
    assert all(reason == "ignored" for reason in skipped_paths.values())
    assert {file.path for file in record.files} == {"src/hello.py"}


def test_skips_unsupported_extensions(service: RagService) -> None:
    """Unknown file types are skipped rather than blowing up the run."""
    payload = _make_zip(
        {
            "demo/notes.txt": b"plain notes",
            "demo/photo.bin": b"\x00\x01\x02",
        }
    )
    record = service.ingest_repository("demo.zip", payload)
    assert {file.path for file in record.files} == {"notes.txt"}
    assert any(item.path == "photo.bin" for item in record.skipped)


def test_rejects_path_traversal_entries(service: RagService) -> None:
    """Entries with `../` segments are skipped, not extracted."""
    payload = _make_zip(
        {
            "demo/ok.md": b"# ok",
            "../etc/passwd": b"root:x:0:0::/root:/bin/sh",
        }
    )
    record = service.ingest_repository("demo.zip", payload)
    assert {file.path for file in record.files} == {"ok.md"}
    bad = [item for item in record.skipped if "passwd" in item.path]
    assert bad and "unsafe path" in bad[0].reason


def test_rejects_symlink_entries(service: RagService) -> None:
    """Symlink members are skipped with reason `symlink`."""
    link_info = zipfile.ZipInfo("demo/link")
    link_info.create_system = 3
    # UNIX symlink mode: 0o120000 << 16
    link_info.external_attr = (0o120777 << 16) | 0x80
    payload = _make_zip(
        {"demo/ok.md": b"# ok"},
        extras=[link_info],
    )
    record = service.ingest_repository("demo.zip", payload)
    symlinks = [item for item in record.skipped if item.reason == "symlink"]
    assert symlinks
    assert {file.path for file in record.files} == {"ok.md"}


def test_oversized_file_is_skipped(service: RagService) -> None:
    """Members exceeding the per-file cap are skipped, the rest still ingested."""
    too_big = b"x" * (MAX_REPO_FILE_BYTES + 10)
    payload = _make_zip(
        {
            "demo/ok.md": b"# ok",
            "demo/huge.txt": too_big,
        }
    )
    record = service.ingest_repository("demo.zip", payload)
    assert {file.path for file in record.files} == {"ok.md"}
    assert any("too large" in item.reason for item in record.skipped)


def test_bad_zip_raises_repository_error(service: RagService) -> None:
    """Passing non-ZIP bytes surfaces a RepositoryError."""
    with pytest.raises(RepositoryError):
        service.ingest_repository("demo.zip", b"this is not a zip")


def test_repository_with_no_usable_files_raises(service: RagService) -> None:
    """A ZIP containing only ignored / unsupported entries surfaces RepositoryError."""
    payload = _make_zip({"demo/.git/HEAD": b"ref"})
    with pytest.raises(RepositoryError):
        service.ingest_repository("demo.zip", payload)


def test_default_ignore_covers_well_known_clutter() -> None:
    """The default ignore list contains the most common excluded directories."""
    assert ".git/" in DEFAULT_IGNORE
    assert "node_modules/" in DEFAULT_IGNORE
    assert "__pycache__/" in DEFAULT_IGNORE
    assert ".venv/" in DEFAULT_IGNORE
