from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..models.sql import ExecutionResult, SQLSpec


class IQueryExecutor(ABC):
    """Interface for SQL query execution against a database."""

    @abstractmethod
    async def execute(
        self,
        sql_spec: SQLSpec,
        tenant_id: str = "",
        timeout_seconds: float = 30.0,
        access_policy: Optional[Any] = None,
    ) -> ExecutionResult:
        """Execute a SQL query and return results."""
        ...
