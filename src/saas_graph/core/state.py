from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..models.clarification import ClarificationResult
from ..models.intent import QueryIntent
from ..models.plan import QueryPlan
from ..models.schema import SchemaContext
from ..models.sql import ExecutionResult, SQLSpec


class AgentState(BaseModel):
    """Shared state passed through the pipeline graph.

    Each node reads from and writes to this state. The graph builder
    merges node outputs back into this state between steps.
    """

    # --- Input ---
    tenant_id: str = ""
    session_id: str = ""
    user_query: str = ""
    messages: List[Dict[str, str]] = Field(default_factory=list)

    # --- Router output ---
    intent: Optional[QueryIntent] = None
    is_external: bool = False

    # --- Clarification output ---
    clarification_result: Optional[ClarificationResult] = None
    needs_clarification: bool = False

    # --- Cache output ---
    cache_hit: bool = False

    # --- Schema linker output ---
    schema_context: Optional[SchemaContext] = None

    # --- Plan output ---
    query_plan: Optional[QueryPlan] = None

    # --- SQL generator output ---
    sql_spec: Optional[SQLSpec] = None
    validation_errors: List[str] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 5

    # --- Executor output ---
    execution_result: Optional[ExecutionResult] = None
    query_results: Optional[List[Dict[str, Any]]] = None
    row_count: int = 0
    from_cache: bool = False

    # --- Formatter output ---
    formatted_response: Optional[str] = None
    display_format: Optional[str] = None

    # --- Web search output ---
    web_search_result: Optional[str] = None

    # --- Error handling ---
    error: Optional[str] = None

    # --- Debugging ---
    current_node: Optional[str] = None

    def can_execute(self) -> bool:
        return self.sql_spec is not None and len(self.validation_errors) == 0

    def is_successful(self) -> bool:
        return self.execution_result is not None and self.execution_result.success

    model_config = {"arbitrary_types_allowed": True}
