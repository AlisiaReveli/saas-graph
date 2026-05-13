"""NLQPipeline: the high-level entry point for saas-graph.

Usage::

    from saas_graph import NLQPipeline, DomainConfig
    from saas_graph.contrib.openai import OpenAIGateway
    from saas_graph.contrib.memory import InMemoryCache

    pipeline = NLQPipeline(
        llm=OpenAIGateway(api_key="sk-..."),
        domain=DomainConfig(name="healthcare", schema_path="schema.yaml"),
    )
    result = await pipeline.query("How many patients last month?")
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

from .core.builder import SimpleGraph, build_graph
from .core.emitter import ThinkingEmitter, set_emitter
from .core.state import AgentState
from .interfaces.cache import ICacheStore
from .interfaces.embedding import IEmbeddingService
from .interfaces.knowledge import IKnowledgeRepository
from .interfaces.executor import IQueryExecutor
from .interfaces.llm import ILLMGateway
from .interfaces.schema_loader import ISchemaContextLoader
from .interfaces.search import IWebSearchService
from .interfaces.session import ISessionStore
from .models.config import DomainConfig, NodeConfig
from .nodes import (
    CacheNode,
    ClarifierNode,
    ExecutorNode,
    FormatterNode,
    PlannerNode,
    RouterNode,
    SchemaLinkerNode,
    SQLGeneratorNode,
)

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result returned by :meth:`NLQPipeline.query`."""

    success: bool
    response: str = ""
    sql: str = ""
    data: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    display_format: str = ""
    from_cache: bool = False
    error: Optional[str] = None
    session_id: str = ""


class NLQPipeline:
    """High-level pipeline builder and executor.

    Wires together all nodes, interfaces, and configuration into a
    ready-to-use analytics assistant pipeline.

    Args:
        llm: LLM gateway (required).
        executor: Database query executor. If ``None``, the pipeline cannot
            execute SQL (useful for dry-run / SQL generation only).
        embedding: Embedding service for semantic schema search.
        schema_loader: Schema context loader.
        knowledge: Knowledge repository for golden queries and rules.
        cache: Cache store for query results.
        session_store: Session persistence.
        web_search: Web search for external queries.
        domain: Domain configuration.
        node_config: Node-level settings.
    """

    def __init__(
        self,
        llm: ILLMGateway,
        executor: Optional[IQueryExecutor] = None,
        embedding: Optional[IEmbeddingService] = None,
        schema_loader: Optional[ISchemaContextLoader] = None,
        knowledge: Optional[IKnowledgeRepository] = None,
        cache: Optional[ICacheStore] = None,
        session_store: Optional[ISessionStore] = None,
        web_search: Optional[IWebSearchService] = None,
        domain: Optional[DomainConfig] = None,
        node_config: Optional[NodeConfig] = None,
    ) -> None:
        from .contrib.memory import InMemoryCache
        from .contrib.memory_session import InMemorySessionStore

        self.llm = llm
        self.domain = domain or DomainConfig()
        self.node_config = node_config or NodeConfig()

        self.cache = cache or InMemoryCache()
        self.session_store = session_store or InMemorySessionStore()

        if schema_loader is None and self.domain.schema_path:
            from .utils.schema_loader import YAMLSchemaLoader

            schema_loader = YAMLSchemaLoader(
                schema_path=self.domain.schema_path,
                golden_queries_path=self.domain.golden_queries_path,
                business_rules_path=self.domain.business_rules_path,
            )

        self.schema_loader = schema_loader
        self.embedding = embedding
        self.knowledge = knowledge
        self.executor = executor
        self.web_search = web_search

        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        nc = self.node_config

        router = RouterNode(
            llm=self.llm,
            web_search=self.web_search if nc.enable_web_search else None,
            domain=self.domain.search_domain,
        )

        clarifier = None
        if nc.enable_clarification:
            clarifier = ClarifierNode(
                llm=self.llm,
                system_prompt=self.domain.clarification_prompt,
            )

        cache_node = None
        if nc.enable_cache and self.knowledge:
            cache_node = CacheNode(
                knowledge_repo=self.knowledge,
                min_similarity=nc.golden_query_threshold,
            )

        schema_linker = None
        if self.embedding and self.schema_loader:
            schema_linker = SchemaLinkerNode(
                embedding_service=self.embedding,
                schema_loader=self.schema_loader,
                knowledge_repo=self.knowledge,
                table_top_k=nc.semantic_search_top_k,
                table_min_score=nc.semantic_search_threshold,
            )
        else:
            schema_linker = _PassthroughSchemaLinker(self.schema_loader)

        planner = None
        if nc.enable_planning:
            planner = PlannerNode(
                llm=self.llm,
                tenant_customizer=self.domain.tenant_customizer,
            )

        sql_gen = SQLGeneratorNode(
            llm=self.llm,
            max_retries=nc.max_sql_retries,
            extra_instructions=self.domain.sql_instructions,
        )

        from .contrib.memory import InMemoryCache as _FallbackCache

        exec_cache = self.cache or _FallbackCache()
        if self.executor:
            executor_node = ExecutorNode(
                query_executor=self.executor,
                cache_store=exec_cache,
                cache_ttl_seconds=nc.cache_ttl_seconds,
                execution_timeout=nc.execution_timeout_seconds,
            )
        else:
            executor_node = _DryRunExecutor()

        formatter = FormatterNode(
            llm=self.llm,
            column_display_names=self.domain.column_display_names or None,
        )

        return build_graph(
            router=router,
            schema_linker=schema_linker,
            sql_generator=sql_gen,
            executor=executor_node,
            formatter=formatter,
            clarifier=clarifier,
            cache=cache_node,
            planner=planner,
        )

    async def query(
        self,
        question: str,
        tenant_id: str = "",
        session_id: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
    ) -> QueryResult:
        """Run a natural language query through the full pipeline.

        Args:
            question: The user's natural language question.
            tenant_id: Tenant identifier for multi-tenant isolation.
            session_id: Conversation session ID (auto-generated if omitted).
            messages: Prior conversation messages for context.

        Returns:
            A :class:`QueryResult` with the formatted response, SQL, and data.
        """
        sid = session_id or str(uuid.uuid4())

        emitter = ThinkingEmitter()
        token = set_emitter(emitter)

        try:
            initial = AgentState(
                tenant_id=tenant_id,
                session_id=sid,
                user_query=question,
                messages=messages or [],
            )

            if hasattr(self._graph, "ainvoke"):
                final_state = await self._graph.ainvoke(initial)
            else:
                final_state = await self._graph.ainvoke(initial)

            return self._to_result(final_state, sid)
        finally:
            set_emitter(None)

    async def query_stream(
        self,
        question: str,
        tenant_id: str = "",
        session_id: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream pipeline execution, yielding events for each node completion.

        Yields dicts of ``{node_name: state}`` as each pipeline stage finishes.
        """
        sid = session_id or str(uuid.uuid4())
        emitter = ThinkingEmitter()
        token = set_emitter(emitter)

        try:
            initial = AgentState(
                tenant_id=tenant_id,
                session_id=sid,
                user_query=question,
                messages=messages or [],
            )

            if hasattr(self._graph, "astream"):
                async for event in self._graph.astream(initial):
                    yield event
            else:
                result = await self._graph.ainvoke(initial)
                yield {"format_response": result}
        finally:
            set_emitter(None)

    @staticmethod
    def _to_result(state: Any, session_id: str) -> QueryResult:
        def _g(field: str, default=None):
            if isinstance(state, dict):
                return state.get(field, default)
            return getattr(state, field, default)

        error = _g("error")
        sql_spec = _g("sql_spec")
        return QueryResult(
            success=error is None,
            response=_g("formatted_response", ""),
            sql=sql_spec.sql if sql_spec else "",
            data=_g("query_results") or [],
            row_count=_g("row_count", 0),
            display_format=_g("display_format", ""),
            from_cache=_g("from_cache", False),
            error=error,
            session_id=session_id,
        )


class _PassthroughSchemaLinker:
    """Fallback schema linker that returns the full schema context from the loader."""

    def __init__(self, loader: Optional[ISchemaContextLoader]) -> None:
        self.loader = loader

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        if self.loader:
            ctx = await self.loader.get_context(
                tenant_id=getattr(state, "tenant_id", "") if not isinstance(state, dict) else state.get("tenant_id", "")
            )
            return {"schema_context": ctx, "current_node": "resolve_schema"}
        return {"error": "No schema loader configured", "current_node": "resolve_schema"}


class _DryRunExecutor:
    """Stub executor that returns an error — used when no real executor is provided."""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        sql_spec = state.sql_spec if hasattr(state, "sql_spec") else state.get("sql_spec")
        return {
            "error": "No database executor configured (dry-run mode)",
            "query_results": [],
            "row_count": 0,
            "current_node": "execute_query",
        }
