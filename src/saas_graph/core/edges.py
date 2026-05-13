"""Routing functions that determine the next node in the pipeline graph."""

from __future__ import annotations

from typing import Literal, Union

from .state import AgentState


def _get(state: Union[AgentState, dict], field: str, default=None):
    if isinstance(state, dict):
        return state.get(field, default)
    return getattr(state, field, default)


def route_after_clarification(state: AgentState) -> Literal["classify_query", "format_response"]:
    if _get(state, "needs_clarification", False):
        return "format_response"
    return "classify_query"


def route_after_router(state: AgentState) -> Literal["resolve_schema", "format_response"]:
    is_external = _get(state, "is_external", False)
    web_search_result = _get(state, "web_search_result")
    if is_external and web_search_result:
        return "format_response"
    return "resolve_schema"


def route_after_cache(state: AgentState) -> Literal["generate_sql", "resolve_schema"]:
    if _get(state, "cache_hit", False):
        return "generate_sql"
    return "resolve_schema"


def route_after_sql_engine(
    state: AgentState,
) -> Literal["execute_query", "generate_sql", "format_response"]:
    error = _get(state, "error")
    if error:
        return "format_response"

    validation_errors = _get(state, "validation_errors", [])
    if not validation_errors:
        return "execute_query"

    retry_count = _get(state, "retry_count", 0)
    max_retries = _get(state, "max_retries", 5)
    if retry_count < max_retries:
        return "generate_sql"

    return "format_response"


def route_after_executor(state: AgentState) -> Literal["generate_sql", "format_response"]:
    validation_errors = _get(state, "validation_errors", [])
    retry_count = _get(state, "retry_count", 0)
    max_retries = _get(state, "max_retries", 5)

    if validation_errors and retry_count < max_retries:
        return "generate_sql"

    return "format_response"
