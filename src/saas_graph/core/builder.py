"""Graph builder: constructs the pipeline from node instances.

Supports two modes:
1. LangGraph ``StateGraph`` (when ``langgraph`` is installed).
2. ``SimpleGraph`` -- a pure-Python async fallback with zero dependencies.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Callable, Dict, Optional

from .state import AgentState
from .edges import (
    route_after_cache,
    route_after_clarification,
    route_after_executor,
    route_after_router,
    route_after_sql_engine,
)

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None  # type: ignore[assignment,misc]
    END = "END"

logger = logging.getLogger(__name__)

Node = Callable[[AgentState], Any]


def build_graph(
    *,
    router: Node,
    schema_linker: Node,
    sql_generator: Node,
    executor: Node,
    formatter: Node,
    clarifier: Optional[Node] = None,
    cache: Optional[Node] = None,
    planner: Optional[Node] = None,
    enable_checkpointing: bool = False,
) -> Any:
    """Build a LangGraph ``StateGraph`` from node callables.

    Falls back to :class:`SimpleGraph` when ``langgraph`` is not installed.
    """
    if not LANGGRAPH_AVAILABLE:
        logger.info("langgraph not installed -- using SimpleGraph fallback")
        return SimpleGraph(
            router=router,
            schema_linker=schema_linker,
            sql_generator=sql_generator,
            executor=executor,
            formatter=formatter,
            clarifier=clarifier,
            cache=cache,
            planner=planner,
        )

    has_clarifier = clarifier is not None
    has_cache = cache is not None
    has_planner = planner is not None

    graph = StateGraph(AgentState)

    if has_clarifier:
        graph.add_node("clarify_query", clarifier)
    graph.add_node("classify_query", router)
    if has_cache:
        graph.add_node("cache_lookup", cache)
    graph.add_node("resolve_schema", schema_linker)
    if has_planner:
        graph.add_node("generate_plan", planner)
    graph.add_node("generate_sql", sql_generator)
    graph.add_node("execute_query", executor)
    graph.add_node("format_response", formatter)

    if has_clarifier:
        graph.set_entry_point("clarify_query")
        graph.add_conditional_edges(
            "clarify_query",
            route_after_clarification,
            {"classify_query": "classify_query", "format_response": "format_response"},
        )
    else:
        graph.set_entry_point("classify_query")

    cache_hit_target = "generate_plan" if has_planner else "generate_sql"

    if has_cache:
        graph.add_conditional_edges(
            "classify_query",
            route_after_router,
            {"resolve_schema": "cache_lookup", "format_response": "format_response"},
        )
        graph.add_conditional_edges(
            "cache_lookup",
            route_after_cache,
            {cache_hit_target: cache_hit_target, "resolve_schema": "resolve_schema"},
        )
    else:
        graph.add_conditional_edges(
            "classify_query",
            route_after_router,
            {"resolve_schema": "resolve_schema", "format_response": "format_response"},
        )

    if has_planner:
        graph.add_edge("resolve_schema", "generate_plan")
        graph.add_edge("generate_plan", "generate_sql")
    else:
        graph.add_edge("resolve_schema", "generate_sql")

    graph.add_conditional_edges(
        "generate_sql",
        route_after_sql_engine,
        {
            "execute_query": "execute_query",
            "generate_sql": "generate_sql",
            "format_response": "format_response",
        },
    )

    graph.add_conditional_edges(
        "execute_query",
        route_after_executor,
        {"generate_sql": "generate_sql", "format_response": "format_response"},
    )

    graph.add_edge("format_response", END)

    checkpointer = None
    if enable_checkpointing:
        try:
            from langgraph.checkpoint.memory import MemorySaver

            checkpointer = MemorySaver()
        except ImportError:
            pass

    return graph.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Pure-Python fallback
# ---------------------------------------------------------------------------


class SimpleGraph:
    """Async pipeline executor that mirrors the LangGraph topology without the dependency."""

    def __init__(
        self,
        *,
        router: Node,
        schema_linker: Node,
        sql_generator: Node,
        executor: Node,
        formatter: Node,
        clarifier: Optional[Node] = None,
        cache: Optional[Node] = None,
        planner: Optional[Node] = None,
    ) -> None:
        self.router = router
        self.clarifier = clarifier
        self.cache = cache
        self.planner = planner
        self.schema_linker = schema_linker
        self.sql_generator = sql_generator
        self.executor = executor
        self.formatter = formatter

    # -- helpers --

    @staticmethod
    def _get(state: AgentState, field: str, default=None):
        if isinstance(state, dict):
            return state.get(field, default)
        return getattr(state, field, default)

    @staticmethod
    def _apply(state: AgentState, updates: Dict[str, Any]) -> AgentState:
        data = state.model_dump() if hasattr(state, "model_dump") else dict(state)
        data.update(updates)
        return AgentState(**data)

    # -- invoke --

    async def ainvoke(self, initial_state: AgentState, config: Optional[dict] = None) -> AgentState:
        state = initial_state

        if self.clarifier is not None:
            state = self._apply(state, await self.clarifier(state))
            if self._get(state, "needs_clarification", False):
                return self._apply(state, await self.formatter(state))

        state = self._apply(state, await self.router(state))
        if self._get(state, "is_external", False):
            return self._apply(state, await self.formatter(state))

        if self.cache is not None:
            state = self._apply(state, await self.cache(state))
            if not self._get(state, "cache_hit", False):
                state = self._apply(state, await self.schema_linker(state))
        else:
            state = self._apply(state, await self.schema_linker(state))

        if self.planner is not None:
            state = self._apply(state, await self.planner(state))

        max_retries = self._get(state, "max_retries", 5)
        for _ in range(max_retries):
            state = self._apply(state, await self.sql_generator(state))

            if self._get(state, "validation_errors", []):
                continue
            if self._get(state, "error"):
                break

            state = self._apply(state, await self.executor(state))
            if not self._get(state, "validation_errors", []):
                break

        return self._apply(state, await self.formatter(state))

    # -- streaming --

    async def astream(
        self, initial_state: AgentState, config: Optional[dict] = None
    ) -> AsyncIterator[Dict[str, AgentState]]:
        state = initial_state

        if self.clarifier is not None:
            state = self._apply(state, await self.clarifier(state))
            yield {"clarify_query": state}
            if self._get(state, "needs_clarification", False):
                state = self._apply(state, await self.formatter(state))
                yield {"format_response": state}
                return

        state = self._apply(state, await self.router(state))
        yield {"classify_query": state}

        if self._get(state, "is_external", False):
            state = self._apply(state, await self.formatter(state))
            yield {"format_response": state}
            return

        if self.cache is not None:
            state = self._apply(state, await self.cache(state))
            yield {"cache_lookup": state}
            if not self._get(state, "cache_hit", False):
                state = self._apply(state, await self.schema_linker(state))
                yield {"resolve_schema": state}
        else:
            state = self._apply(state, await self.schema_linker(state))
            yield {"resolve_schema": state}

        if self.planner is not None:
            state = self._apply(state, await self.planner(state))
            yield {"generate_plan": state}

        max_retries = self._get(state, "max_retries", 5)
        for _ in range(max_retries):
            state = self._apply(state, await self.sql_generator(state))
            yield {"generate_sql": state}

            if self._get(state, "validation_errors", []):
                continue
            if self._get(state, "error"):
                break

            state = self._apply(state, await self.executor(state))
            yield {"execute_query": state}
            if not self._get(state, "validation_errors", []):
                break

        state = self._apply(state, await self.formatter(state))
        yield {"format_response": state}
