from abc import ABC, abstractmethod
from typing import Optional


class IWebSearchService(ABC):
    """Interface for web search functionality.

    Used when the router classifies a query as EXTERNAL (general knowledge)
    rather than INTERNAL (answerable from the database).
    """

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 5,
        domain: Optional[str] = None,
    ) -> dict:
        """Perform a web search and return structured results.

        Args:
            query: Pre-optimized search query string.
            max_results: Maximum number of results.
            domain: Optional domain hint for search context.

        Returns:
            Dict with ``success`` (bool), ``results`` (list), and optional ``error``.
        """
        ...
