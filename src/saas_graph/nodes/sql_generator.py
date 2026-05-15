"""SQLGeneratorNode: generates SQL from schema context using an LLM with retry logic."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..core.emitter import get_emitter
from ..core.state import AgentState
from ..interfaces.llm import ILLMGateway
from ..models.intent import QueryIntent
from ..models.plan import QueryPlan
from ..models.schema import SchemaContext

logger = logging.getLogger(__name__)


class SQLGeneratorNode:
    """Generates SQL queries using an LLM with full schema context.

    Supports retry with error feedback: when SQL execution fails, the error
    is fed back to the LLM on the next attempt for self-correction.

    Args:
        llm: LLM gateway for SQL generation.
        max_retries: Maximum generation attempts.
        extra_instructions: Domain-specific SQL generation instructions.
    """

    def __init__(
        self,
        llm: ILLMGateway,
        max_retries: int = 5,
        extra_instructions: Optional[List[str]] = None,
        database_type: str = "postgres",
    ) -> None:
        self.llm = llm
        self.max_retries = max_retries
        self.extra_instructions = extra_instructions or []
        self.database_type = database_type

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        user_query = _get(state, "user_query", "")
        intent: Optional[QueryIntent] = _get(state, "intent")
        schema_context: Optional[SchemaContext] = _get(state, "schema_context")
        query_plan: Optional[QueryPlan] = _get(state, "query_plan")
        retry_count = _get(state, "retry_count", 0)
        validation_errors = _get(state, "validation_errors", [])
        previous_spec = _get(state, "sql_spec")

        if retry_count >= self.max_retries:
            logger.error("Max retries (%d) exceeded", self.max_retries)
            return {
                "error": f"Failed to generate valid query after {self.max_retries} attempts",
                "current_node": "generate_sql",
                "max_retries": self.max_retries,
            }

        if not schema_context:
            return {
                "error": "No schema context available",
                "current_node": "generate_sql",
                "max_retries": self.max_retries,
            }

        attempt = retry_count + 1
        emitter = get_emitter()
        if emitter:
            label = "Building the query" if attempt == 1 else f"Retrying query (attempt {attempt})"
            emitter.emit_step(label)

        augmented_query = user_query
        if validation_errors:
            error_ctx = (
                "\n\nPREVIOUS ATTEMPT FAILED:\n"
                + "\n".join(f"- {e}" for e in validation_errors)
            )
            augmented_query = user_query + error_ctx

        previous_sql = previous_spec.sql if previous_spec and validation_errors else None

        try:
            sql_spec = await self.llm.generate_sql(
                query=augmented_query,
                intent=intent or QueryIntent(raw_query=user_query),
                schema_context=schema_context,
                query_plan=query_plan,
                validation_errors=validation_errors if validation_errors else None,
                previous_sql=previous_sql,
                attempt_number=attempt,
                max_attempts=self.max_retries,
                database_type=self.database_type,
            )

            logger.info("SQL generated (attempt %d): %s", attempt, sql_spec.sql[:200])

            if emitter:
                emitter.emit_step("Validating the generated SQL")

            return {
                "sql_spec": sql_spec,
                "validation_errors": [],
                "current_node": "generate_sql",
                "max_retries": self.max_retries,
            }

        except Exception as exc:
            logger.error("SQL generation failed: %s", exc)
            return {
                "validation_errors": [f"SQL generation error: {exc}"],
                "retry_count": retry_count + 1,
                "current_node": "generate_sql",
                "max_retries": self.max_retries,
            }


def _get(state: Any, field: str, default=None):
    return state.get(field, default) if isinstance(state, dict) else getattr(state, field, default)
