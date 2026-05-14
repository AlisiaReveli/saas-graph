"""Tests for RouterNode."""

import json
from unittest.mock import AsyncMock

import pytest

from saas_graph.nodes.router import RouterNode


def _make_state(**kwargs):
    defaults = {"user_query": "", "messages": []}
    defaults.update(kwargs)
    return defaults


class TestRouterNode:
    @pytest.mark.asyncio
    async def test_internal_classification(self):
        llm = AsyncMock()
        llm.classify_query.return_value = {"classification": "INTERNAL", "reasoning": "database query"}

        node = RouterNode(llm=llm)
        result = await node(_make_state(user_query="How many orders last month?"))

        assert result["is_external"] is False
        assert result["web_search_result"] is None

    @pytest.mark.asyncio
    async def test_external_without_search_service(self):
        llm = AsyncMock()
        llm.classify_query.return_value = {"classification": "EXTERNAL", "reasoning": "general knowledge"}

        node = RouterNode(llm=llm, web_search=None)
        result = await node(_make_state(user_query="What is inflation?"))

        assert result["is_external"] is True
        assert result["web_search_result"] is None

    @pytest.mark.asyncio
    async def test_external_with_search_service(self):
        llm = AsyncMock()
        llm.classify_query.return_value = {"classification": "EXTERNAL", "reasoning": "general knowledge"}
        llm.optimize_search_query.return_value = "current inflation rate 2026"
        llm.summarize_web_results.return_value = "Inflation is approximately 3%."

        search = AsyncMock()
        search.search.return_value = {
            "success": True,
            "results": [{"title": "Inflation", "url": "https://example.com", "content": "3%"}],
        }

        node = RouterNode(llm=llm, web_search=search)
        result = await node(_make_state(user_query="What is the current inflation rate?"))

        assert result["is_external"] is True
        assert result["web_search_result"] == "Inflation is approximately 3%."
        search.search.assert_called_once()
