"""Tiny TTL cache for API responses."""
from __future__ import annotations

import time
from typing import Any, Callable, TypeVar

from config import CACHE_TTL_SECONDS

T = TypeVar("T")


class TTLCache:
    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        if key not in self._store:
            return None
        ts, val = self._store[key]
        if time.time() - ts > self.ttl:
            del self._store[key]
            return None
        return val

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)

    def clear(self) -> None:
        self._store.clear()


api_cache = TTLCache()


def cached(key: str, factory: Callable[[], T]) -> T:
    hit = api_cache.get(key)
    if hit is not None:
        return hit  # type: ignore[return-value]
    val = factory()
    api_cache.set(key, val)
    return val
