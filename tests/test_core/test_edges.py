"""Tests for edge routing functions."""

from saas_graph.core.edges import (
    route_after_clarification,
    route_after_executor,
    route_after_router,
    route_after_sql_engine,
)
from saas_graph.core.state import AgentState


def test_route_after_clarification_clear():
    state = AgentState(needs_clarification=False)
    assert route_after_clarification(state) == "classify_query"


def test_route_after_clarification_needs():
    state = AgentState(needs_clarification=True)
    assert route_after_clarification(state) == "format_response"


def test_route_after_router_internal():
    state = AgentState(is_external=False)
    assert route_after_router(state) == "resolve_schema"


def test_route_after_router_external():
    state = AgentState(is_external=True, web_search_result="some result")
    assert route_after_router(state) == "format_response"


def test_route_after_sql_engine_success():
    state = AgentState(validation_errors=[])
    assert route_after_sql_engine(state) == "execute_query"


def test_route_after_sql_engine_retry():
    state = AgentState(validation_errors=["error"], retry_count=1, max_retries=5)
    assert route_after_sql_engine(state) == "generate_sql"


def test_route_after_sql_engine_exhausted():
    state = AgentState(validation_errors=["error"], retry_count=5, max_retries=5)
    assert route_after_sql_engine(state) == "format_response"


def test_route_after_executor_success():
    state = AgentState(validation_errors=[])
    assert route_after_executor(state) == "format_response"


def test_route_after_executor_retry():
    state = AgentState(validation_errors=["err"], retry_count=1, max_retries=5)
    assert route_after_executor(state) == "generate_sql"
