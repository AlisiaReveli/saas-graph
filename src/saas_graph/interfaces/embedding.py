from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IEmbeddingService(ABC):
    """Interface for vector embedding and semantic search operations."""

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Generate an embedding vector for a single text."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a batch of texts."""
        ...

    @abstractmethod
    async def search(
        self,
        query: str,
        tenant_id: str = "",
        embedding_types: Optional[List[str]] = None,
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """Semantic search across embedded entities.

        Args:
            query: Natural language search query.
            tenant_id: Scope search to a specific tenant.
            embedding_types: Filter by entity types (e.g. ``["table", "column"]``).
            top_k: Maximum results to return.
            min_similarity: Minimum cosine similarity threshold.

        Returns:
            List of dicts with at least ``entity_type``, ``entity_name``,
            ``similarity``, and ``metadata``.
        """
        ...

    async def search_tables(
        self,
        query: str,
        tenant_id: str = "",
        top_k: int = 5,
        min_similarity: float = 0.5,
    ) -> List[str]:
        """Convenience: search for relevant table names."""
        results = await self.search(
            query=query,
            tenant_id=tenant_id,
            embedding_types=["table"],
            top_k=top_k,
            min_similarity=min_similarity,
        )
        return [r["entity_name"] for r in results]
