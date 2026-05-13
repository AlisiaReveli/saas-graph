from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SQLSpec(BaseModel):
    """Generated SQL with metadata."""

    sql: str = Field(description="Complete SQL query")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""
    tables_used: List[str] = Field(default_factory=list)
    from_golden_query: bool = False
    golden_query_name: Optional[str] = None
    generation_attempts: int = 1
    validation_passed: bool = False
    agent_output: Optional[str] = Field(
        default=None,
        description="Full agent output when SQL extraction fails",
    )
    is_fallback_sql: bool = Field(
        default=False,
        description="True when fallback SQL was used due to extraction failure",
    )


class QueryMetadata(BaseModel):
    """Metadata about query execution."""

    execution_time_ms: float = 0.0
    rows_returned: int = 0
    cached: bool = False
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutionResult(BaseModel):
    """Result of SQL query execution."""

    success: bool = True
    error_message: Optional[str] = None
    data: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=list)
    metadata: QueryMetadata = Field(default_factory=QueryMetadata)
    sql_executed: Optional[str] = None

    @property
    def row_count(self) -> int:
        return len(self.data)

    @property
    def is_empty(self) -> bool:
        return len(self.data) == 0
