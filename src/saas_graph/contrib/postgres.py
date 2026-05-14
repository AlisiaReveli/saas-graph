"""PostgreSQL query executor using asyncpg."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from ..interfaces.executor import IQueryExecutor
from ..models.sql import ExecutionResult, QueryMetadata, SQLSpec


class PostgresExecutor(IQueryExecutor):
    """Execute SQL against a PostgreSQL database via asyncpg."""

    def __init__(self, database_url: str, *, pool_min: int = 2, pool_max: int = 10):
        try:
            import asyncpg as _  # noqa: F811
        except ImportError as exc:
            raise ImportError("pip install saas-graph[postgres]") from exc

        self._database_url = database_url
        self._pool_min = pool_min
        self._pool_max = pool_max
        self._pool = None

    async def _get_pool(self):
        import asyncpg

        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self._database_url,
                min_size=self._pool_min,
                max_size=self._pool_max,
            )
        return self._pool

    async def execute(
        self,
        sql_spec: SQLSpec,
        tenant_id: str = "",
        timeout_seconds: float = 30.0,
        access_policy: Optional[Any] = None,
    ) -> ExecutionResult:
        import asyncpg

        pool = await self._get_pool()
        start = time.perf_counter()

        def _elapsed() -> float:
            return (time.perf_counter() - start) * 1000

        try:
            async with pool.acquire(timeout=timeout_seconds) as conn:
                rows = await conn.fetch(sql_spec.sql, timeout=timeout_seconds)

                columns = list(rows[0].keys()) if rows else []
                data = [dict(row) for row in rows]

                return ExecutionResult(
                    success=True,
                    data=data,
                    columns=columns,
                    sql_executed=sql_spec.sql,
                    metadata=QueryMetadata(
                        execution_time_ms=_elapsed(),
                        rows_returned=len(data),
                        executed_at=datetime.now(timezone.utc),
                    ),
                )

        except asyncpg.PostgresError as exc:
            return ExecutionResult(
                success=False,
                error_message=str(exc),
                sql_executed=sql_spec.sql,
                metadata=QueryMetadata(
                    execution_time_ms=_elapsed(),
                    executed_at=datetime.now(timezone.utc),
                ),
            )
        except TimeoutError:
            return ExecutionResult(
                success=False,
                error_message=f"Query timed out after {timeout_seconds}s",
                sql_executed=sql_spec.sql,
                metadata=QueryMetadata(
                    execution_time_ms=_elapsed(),
                    executed_at=datetime.now(timezone.utc),
                ),
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
