"""Tavily web search adapter."""

from __future__ import annotations

import logging
from typing import Optional

from ..interfaces.search import IWebSearchService

logger = logging.getLogger(__name__)


class TavilySearchService(IWebSearchService):
    """Web search using the Tavily API.

    Args:
        api_key: Tavily API key.
        search_depth: ``"basic"`` (1 credit) or ``"advanced"`` (2 credits, better results).
    """

    def __init__(self, api_key: str, search_depth: str = "basic") -> None:
        try:
            from tavily import AsyncTavilyClient
        except ImportError as exc:
            raise ImportError("pip install saas-graph[tavily]") from exc

        self._client = AsyncTavilyClient(api_key=api_key)
        self._search_depth = search_depth

    async def search(
        self,
        query: str,
        max_results: int = 5,
        domain: Optional[str] = None,
    ) -> dict:
        try:
            response = await self._client.search(
                query=query,
                search_depth=self._search_depth,
                max_results=max_results,
            )

            results = [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                    "score": r.get("score", 0.0),
                }
                for r in response.get("results", [])
            ]

            return {"success": True, "results": results}

        except Exception as exc:
            logger.error("Tavily search failed: %s", exc)
            return {"success": False, "results": [], "error": str(exc)}
