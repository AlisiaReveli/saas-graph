from abc import ABC, abstractmethod
from typing import Any, Optional


class ICacheStore(ABC):
    """Interface for caching query results and intermediate data."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a cached value by key. Returns ``None`` on miss."""
        ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set a cached value with an optional TTL."""
        ...

    def build_key(self, *parts: str) -> str:
        """Build a namespaced cache key from parts."""
        return ":".join(p for p in parts if p)
