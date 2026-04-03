from __future__ import annotations

import time
from typing import Any, Callable, TypeVar

from config import CACHE_TTL_SECONDS

T = TypeVar("T")


class TTLCache:
    """Remember (key -> value) for a while, then forget. Stops the API from hammering SQLite."""

    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        if key not in self._store:
            return None
        saved_at, value = self._store[key]
        if time.time() - saved_at > self.ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)

    def clear(self) -> None:
        self._store.clear()


api_cache = TTLCache()


def cached(key: str, factory: Callable[[], T]) -> T:
    previous = api_cache.get(key)
    if previous is not None:
        return previous  # type: ignore[return-value]
    fresh = factory()
    api_cache.set(key, fresh)
    return fresh
