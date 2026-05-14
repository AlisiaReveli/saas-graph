"""Tests for SQLGeneratorNode."""

from unittest.mock import AsyncMock

import pytest

from saas_graph.models.intent import QueryIntent
from saas_graph.models.schema import SchemaContext
from saas_graph.models.sql import SQLSpec
from saas_graph.nodes.sql_generator import SQLGeneratorNode


def _make_state(**kwargs):
    defaults = {
        "user_query": "SELECT something",
        "intent": QueryIntent(raw_query="test"),
        "schema_context": SchemaContext(),
        "query_plan": None,
        "retry_count": 0,
        "validation_errors": [],
    }
    defaults.update(kwargs)
    return defaults


class TestSQLGeneratorNode:
    @pytest.mark.asyncio
    async def test_successful_generation(self):
        llm = AsyncMock()
        llm.generate_sql.return_value = SQLSpec(
            sql="SELECT count(*) FROM orders",
            explanation="Counts all orders",
            tables_used=["orders"],
        )

        node = SQLGeneratorNode(llm=llm)
        result = await node(_make_state(user_query="How many orders?"))

        assert result["sql_spec"].sql == "SELECT count(*) FROM orders"
        assert result["validation_errors"] == []

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        llm = AsyncMock()
        node = SQLGeneratorNode(llm=llm, max_retries=3)
        result = await node(_make_state(retry_count=3))

        assert "error" in result
        assert "3 attempts" in result["error"]
        llm.generate_sql.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_schema_context(self):
        llm = AsyncMock()
        node = SQLGeneratorNode(llm=llm)
        result = await node(_make_state(schema_context=None))

        assert "error" in result
        assert "schema" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_generation_failure_increments_retry(self):
        llm = AsyncMock()
        llm.generate_sql.side_effect = Exception("LLM error")

        node = SQLGeneratorNode(llm=llm)
        result = await node(_make_state(retry_count=0))

        assert result["retry_count"] == 1
        assert any("LLM error" in e for e in result["validation_errors"])
