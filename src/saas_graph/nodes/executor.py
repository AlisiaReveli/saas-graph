"""ExecutorNode: runs SQL against the database with caching and error handling."""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict

from ..core.emitter import get_emitter
from ..core.state import AgentState
from ..interfaces.cache import ICacheStore
from ..interfaces.executor import IQueryExecutor

logger = logging.getLogger(__name__)


class ExecutorNode:
    """Executes generated SQL against the database.

    Features:
    - Result caching with configurable TTL.
    - Timeout handling.
    - Error propagation that triggers SQL regeneration.
    """

    def __init__(
        self,
        query_executor: IQueryExecutor,
        cache_store: ICacheStore,
        cache_ttl_seconds: int = 300,
        execution_timeout: float = 30.0,
    ) -> None:
        self.executor = query_executor
        self.cache = cache_store
        self.cache_ttl = cache_ttl_seconds
        self.timeout = execution_timeout

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        sql_spec = _get(state, "sql_spec")
        tenant_id = _get(state, "tenant_id", "")
        retry_count = _get(state, "retry_count", 0)

        emitter = get_emitter()
        if emitter:
            emitter.emit_step("Running the query")

        if not sql_spec:
            return {"error": "No SQL to execute", "current_node": "execute_query"}

        cache_key = self._cache_key(sql_spec.sql, tenant_id)
        cached = await self.cache.get(cache_key)
        if cached:
            logger.info("Cache hit for query")
            if emitter:
                emitter.emit_step("Found cached results")
            return {
                "query_results": cached.get("data", []),
                "row_count": cached.get("row_count", 0),
                "from_cache": True,
                "current_node": "execute_query",
            }

        try:
            result = await self.executor.execute(
                sql_spec=sql_spec,
                tenant_id=tenant_id,
                timeout_seconds=self.timeout,
            )

            if not result.success:
                logger.error("Query failed: %s", result.error_message)
                return {
                    "validation_errors": [f"Execution error: {result.error_message}"],
                    "retry_count": retry_count + 1,
                    "execution_result": result,
                    "current_node": "execute_query",
                }

            logger.info("Query returned %d rows", result.row_count)
            if emitter:
                emitter.emit_step(f"Query returned {result.row_count} rows")

            if result.row_count == 0:
                return {
                    "validation_errors": ["Query returned 0 rows — no matching data found."],
                    "retry_count": retry_count + 1,
                    "execution_result": result,
                    "query_results": [],
                    "row_count": 0,
                    "current_node": "execute_query",
                }

            if result.data:
                await self.cache.set(
                    cache_key,
                    {"data": result.data, "row_count": result.row_count},
                    ttl_seconds=self.cache_ttl,
                )

            return {
                "execution_result": result,
                "query_results": result.data,
                "row_count": result.row_count,
                "validation_errors": [],
                "current_node": "execute_query",
            }

        except Exception as exc:
            logger.error("Execution error: %s", exc)
            return {
                "validation_errors": [f"Query execution error: {exc}"],
                "retry_count": retry_count + 1,
                "current_node": "execute_query",
            }

    def _cache_key(self, sql: str, tenant_id: str) -> str:
        sql_hash = hashlib.md5(sql.encode()).hexdigest()[:12]
        return self.cache.build_key("query", tenant_id, sql_hash)


def _get(state: Any, field: str, default=None):
    return state.get(field, default) if isinstance(state, dict) else getattr(state, field, default)
