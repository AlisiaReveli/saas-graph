"""In-memory cache store — zero dependencies, suitable for development and testing."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

from ..interfaces.cache import ICacheStore


class InMemoryCache(ICacheStore):
    """Simple in-memory cache with TTL support."""

    def __init__(self, default_ttl: int = 3600) -> None:
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._default_ttl = default_ttl

    async def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at and time.time() > expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires_at = time.time() + ttl if ttl > 0 else 0
        self._store[key] = (value, expires_at)

    def clear(self) -> None:
        self._store.clear()
