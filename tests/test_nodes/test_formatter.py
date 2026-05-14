"""Tests for FormatterNode."""

from unittest.mock import AsyncMock

import pytest

from saas_graph.nodes.formatter import DisplayFormat, FormatterNode


def _make_state(**kwargs):
    defaults = {
        "needs_clarification": False,
        "clarification_result": None,
        "web_search_result": None,
        "error": None,
        "validation_errors": [],
        "retry_count": 0,
        "max_retries": 5,
        "query_results": [],
        "user_query": "test query",
        "sql_spec": None,
    }
    defaults.update(kwargs)
    return defaults


class TestFormatterNode:
    @pytest.mark.asyncio
    async def test_clarification_response(self):
        from saas_graph.models.clarification import ClarificationResult

        llm = AsyncMock()
        node = FormatterNode(llm=llm)
        clar = ClarificationResult(is_clear=False, clarification_question="Which department?")
        state = _make_state(needs_clarification=True, clarification_result=clar)

        result = await node(state)
        assert result["display_format"] == DisplayFormat.CLARIFICATION.value
        assert "Which department?" in result["formatted_response"]

    @pytest.mark.asyncio
    async def test_web_search_response(self):
        llm = AsyncMock()
        node = FormatterNode(llm=llm)
        state = _make_state(web_search_result="The answer is 42.")

        result = await node(state)
        assert result["display_format"] == DisplayFormat.WEB_SEARCH.value
        assert result["formatted_response"] == "The answer is 42."

    @pytest.mark.asyncio
    async def test_error_response(self):
        llm = AsyncMock()
        node = FormatterNode(llm=llm)
        state = _make_state(error="Something went wrong")

        result = await node(state)
        assert result["display_format"] == DisplayFormat.ERROR.value
        assert "Something went wrong" in result["formatted_response"]

    @pytest.mark.asyncio
    async def test_empty_results(self):
        llm = AsyncMock()
        node = FormatterNode(llm=llm)
        state = _make_state(query_results=[])

        result = await node(state)
        assert result["display_format"] == DisplayFormat.EMPTY.value
        assert "No results" in result["formatted_response"]

    def test_detect_format_single_value(self):
        llm = AsyncMock()
        node = FormatterNode(llm=llm)
        results = [{"count": 42}]
        assert node._detect_format(results, "how many?") == DisplayFormat.SINGLE_VALUE

    def test_detect_format_ranking(self):
        llm = AsyncMock()
        node = FormatterNode(llm=llm)
        results = [{"name": f"p{i}", "rev": i} for i in range(10)]
        assert node._detect_format(results, "top products") == DisplayFormat.RANKING

    def test_apply_display_names(self):
        llm = AsyncMock()
        node = FormatterNode(llm=llm, column_display_names={"total_amount": "Total ($)"})
        results = [{"total_amount": 100, "name": "Test"}]
        renamed = node._apply_display_names(results)
        assert renamed == [{"Total ($)": 100, "name": "Test"}]

    def test_markdown_table_uses_display_names(self):
        llm = AsyncMock()
        node = FormatterNode(
            llm=llm,
            column_display_names={"price": "Price ($)", "name": "Product"},
        )
        results = [{"name": "Widget", "price": 9.99}]
        table = node._to_markdown_table(results)
        assert "Product" in table
        assert "Price ($)" in table
