"""Tests for ClarifierNode."""

from unittest.mock import AsyncMock

import pytest

from saas_graph.nodes.clarifier import ClarifierNode


def _make_state(**kwargs):
    defaults = {"user_query": "", "messages": []}
    defaults.update(kwargs)
    return defaults


class TestClarifierNode:
    @pytest.mark.asyncio
    async def test_clear_query(self):
        llm = AsyncMock()
        llm.complete.return_value = "CLEAR: Domain: ecommerce, Metric: revenue"

        node = ClarifierNode(llm=llm)
        result = await node(_make_state(user_query="What is total revenue?"))

        assert result["needs_clarification"] is False

    @pytest.mark.asyncio
    async def test_ambiguous_query(self):
        llm = AsyncMock()
        llm.complete.return_value = "Which product category are you interested in?"

        node = ClarifierNode(llm=llm)
        result = await node(_make_state(user_query="show me the data"))

        assert result["needs_clarification"] is True
        assert "category" in result["clarification_result"].clarification_question.lower()

    @pytest.mark.asyncio
    async def test_parse_clear_with_expanded_query(self):
        llm = AsyncMock()
        llm.complete.return_value = (
            "CLEAR:\n"
            "Domain: ecommerce\n"
            "Entity: orders\n"
            "Time period: last 30 days\n"
            "Metric: count\n"
            "Expanded query: How many orders in the last 30 days"
        )

        node = ClarifierNode(llm=llm)
        result = await node(_make_state(user_query="how many orders recently?"))

        assert result["needs_clarification"] is False
        clar = result["clarification_result"]
        assert clar.domain == "ecommerce"
        assert clar.expanded_query is not None
