"""Tests for AgentState."""

from saas_graph.core.state import AgentState
from saas_graph.models.sql import ExecutionResult, SQLSpec


def test_default_state():
    s = AgentState()
    assert s.user_query == ""
    assert s.retry_count == 0
    assert s.max_retries == 5
    assert s.can_execute() is False


def test_can_execute():
    s = AgentState(sql_spec=SQLSpec(sql="SELECT 1"), validation_errors=[])
    assert s.can_execute() is True


def test_cannot_execute_with_errors():
    s = AgentState(sql_spec=SQLSpec(sql="SELECT 1"), validation_errors=["err"])
    assert s.can_execute() is False


def test_is_successful():
    s = AgentState(execution_result=ExecutionResult(success=True))
    assert s.is_successful() is True
