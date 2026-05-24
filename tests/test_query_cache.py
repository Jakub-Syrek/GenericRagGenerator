"""Unit tests for the LRU + TTL query cache."""

from __future__ import annotations

import time

import pytest

from app.services.query_cache import QueryCache, make_key


def test_make_key_is_stable_across_dict_ordering() -> None:
    """Dict insertion order does not affect the cache key digest."""
    left = make_key("search", {"a": 1, "b": 2})
    right = make_key("search", {"b": 2, "a": 1})
    assert left == right


def test_make_key_differs_for_different_inputs() -> None:
    """Different query payloads yield different keys."""
    assert make_key("search", "alpha") != make_key("search", "beta")


def test_put_then_get_returns_stored_value() -> None:
    """A value put under a key is read back on the next get."""
    cache: QueryCache[str] = QueryCache(max_entries=4, ttl_seconds=10)
    cache.put("k", "v")
    assert cache.get("k") == "v"


def test_get_returns_none_on_miss() -> None:
    """Unknown keys read as `None` and don't crash."""
    cache: QueryCache[str] = QueryCache(max_entries=4, ttl_seconds=10)
    assert cache.get("nope") is None


def test_lru_eviction_drops_least_recently_used() -> None:
    """Filling the cache past capacity evicts the oldest entry."""
    cache: QueryCache[str] = QueryCache(max_entries=2, ttl_seconds=60)
    cache.put("a", "1")
    cache.put("b", "2")
    cache.put("c", "3")
    assert cache.get("a") is None  # evicted
    assert cache.get("b") == "2"
    assert cache.get("c") == "3"


def test_get_promotes_entry_to_most_recent() -> None:
    """Reading an entry resets its LRU position."""
    cache: QueryCache[str] = QueryCache(max_entries=2, ttl_seconds=60)
    cache.put("a", "1")
    cache.put("b", "2")
    assert cache.get("a") == "1"  # bumps "a" to most-recent
    cache.put("c", "3")
    assert cache.get("a") == "1"  # still alive
    assert cache.get("b") is None  # evicted


def test_ttl_expires_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Entries older than `ttl_seconds` are treated as misses."""
    fake_now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])
    cache: QueryCache[str] = QueryCache(max_entries=4, ttl_seconds=5)
    cache.put("k", "v")
    assert cache.get("k") == "v"
    fake_now[0] += 6.0
    assert cache.get("k") is None


def test_clear_drops_everything() -> None:
    """`clear` purges every stored entry."""
    cache: QueryCache[int] = QueryCache(max_entries=4, ttl_seconds=60)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None


def test_stats_counts_hits_misses_and_size() -> None:
    """The stats dict tracks hit / miss counts and current size."""
    cache: QueryCache[int] = QueryCache(max_entries=4, ttl_seconds=60)
    cache.put("a", 1)
    cache.get("a")  # hit
    cache.get("b")  # miss
    stats = cache.stats()
    assert stats == {"hits": 1, "misses": 1, "size": 1}


def test_constructor_rejects_bad_arguments() -> None:
    """Non-positive size or negative TTL is caught at construction time."""
    with pytest.raises(ValueError):
        QueryCache(max_entries=0, ttl_seconds=10)
    with pytest.raises(ValueError):
        QueryCache(max_entries=1, ttl_seconds=-1)
