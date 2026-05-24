"""In-memory LRU + TTL cache for retrieval / query responses.

A real production RAG repeats the same questions a lot — same prompt
from a chat client, the same /search call from an IDE plugin polling
on every keystroke. Re-embedding the question and re-running BM25 +
Ollama costs latency that nothing useful does.

This cache stores keyed answers in memory with two limits:

- TTL — entries older than `ttl_seconds` are dropped on read.
- Size — when the LRU exceeds `max_entries`, the oldest one is evicted.

The cache is opt-in (`CACHE_ENABLED=false` by default). Every write
path (ingest / delete / wipe) calls `clear()` so a refreshed index
doesn't serve stale answers.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


def make_key(*parts: Any) -> str:
    """Build a stable cache key from a list of arbitrary parts.

    The parts are JSON-serialised (sorted keys) and SHA-256'd so order
    inside dicts doesn't matter and the key length is bounded.

    @param parts Arbitrary cache key components (strings, ints, lists, dicts).
    @returns Hex digest suitable as a dict key.
    """
    blob = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _Entry(Generic[T]):
    """Cache entry tagged with insertion time for TTL bookkeeping."""

    value: T
    stored_at: float


class QueryCache(Generic[T]):
    """Thread-safe LRU cache with per-entry TTL.

    Generic over the stored value type so callers can hold whatever
    they like (`SearchResponse`, `QueryResponse`, etc.). The cache
    itself doesn't know — it's pure key/value plumbing.
    """

    def __init__(self, *, max_entries: int, ttl_seconds: int) -> None:
        """Configure the cache size + lifetime.

        @param max_entries Upper bound on the number of cached values.
        @param ttl_seconds Maximum age of a cached value before it's
                           treated as a miss. Use `0` to disable TTL.
        @raises ValueError When `max_entries` is non-positive.
        """
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must be non-negative")
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._store: OrderedDict[str, _Entry[T]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> T | None:
        """Look up `key`, returning the cached value or `None` on miss.

        Expired entries are removed inline so the next call hits cleanly.

        @param key Cache key produced by `make_key`.
        @returns The stored value, or `None` when missing / expired.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if self._ttl_seconds and time.monotonic() - entry.stored_at > self._ttl_seconds:
                del self._store[key]
                self._misses += 1
                return None
            self._store.move_to_end(key)
            self._hits += 1
            return entry.value

    def put(self, key: str, value: T) -> None:
        """Store `value` under `key`, evicting the oldest entry on overflow.

        @param key   Cache key produced by `make_key`.
        @param value Value to store.
        """
        with self._lock:
            self._store[key] = _Entry(value=value, stored_at=time.monotonic())
            self._store.move_to_end(key)
            while len(self._store) > self._max_entries:
                self._store.popitem(last=False)

    def clear(self) -> None:
        """Drop every cached entry (called after writes to the index)."""
        with self._lock:
            self._store.clear()

    def stats(self) -> dict[str, int]:
        """Return hit / miss counters + current size for diagnostics.

        @returns Dict with `hits`, `misses`, `size` keys.
        """
        with self._lock:
            return {"hits": self._hits, "misses": self._misses, "size": len(self._store)}
