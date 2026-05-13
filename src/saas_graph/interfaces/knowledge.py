from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from ..models.schema import GoldenQuery, SchemaContext


class IKnowledgeRepository(ABC):
    """Interface for accessing domain knowledge: golden queries, business rules, etc."""

    @abstractmethod
    async def find_golden_query(
        self,
        query: str,
        tenant_id: str = "",
        min_similarity: float = 0.7,
    ) -> Optional[GoldenQuery]:
        """Find the best matching golden query for a user question."""
        ...

    @abstractmethod
    async def find_business_rules(
        self,
        query: str,
        tenant_id: str = "",
    ) -> List[Dict[str, Any]]:
        """Find business rules matching trigger terms in the question."""
        ...

    async def build_schema_context(
        self,
        query: str,
        tenant_id: str = "",
    ) -> Optional[SchemaContext]:
        """Build complete schema context for a query using knowledge base.

        Returns ``None`` if the repository cannot build context (fallback to
        embedding-based schema linking).
        """
        return None
