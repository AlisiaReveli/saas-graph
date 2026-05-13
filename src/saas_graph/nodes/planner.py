"""PlannerNode: generates a query execution plan before SQL generation."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Callable, Dict, List, Optional

from ..core.emitter import get_emitter
from ..core.state import AgentState
from ..interfaces.llm import ILLMGateway
from ..models.plan import QueryPlan
from ..models.schema import SchemaContext

logger = logging.getLogger(__name__)

PLAN_SYSTEM_PROMPT = """You are an expert SQL query planner. Analyze the user's question and schema context to produce a detailed plan for SQL generation.

Generate a JSON object with these fields:
- plan_description: 2-3 sentence plain English description of the query approach
- tables_to_use: List of table names needed
- joins_required: List of join conditions
- required_filters: List of filter descriptions
- date_filter: Date filter condition if applicable
- business_rules: List of business rules to apply
- special_instructions: List of special SQL considerations
- confidence: Float 0.0-1.0 based on how well the schema matches
"""


class PlannerNode:
    """Generates a structured query plan that guides SQL generation.

    Optionally supports tenant-specific customization via a hook function.

    Args:
        llm: LLM gateway for plan generation.
        tenant_customizer: Optional callback ``(tenant_id, query, plan) -> plan``
            that applies tenant-specific adjustments to the generated plan.
    """

    def __init__(
        self,
        llm: ILLMGateway,
        tenant_customizer: Optional[Callable[..., QueryPlan]] = None,
    ) -> None:
        self.llm = llm
        self.tenant_customizer = tenant_customizer

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        user_query = _get(state, "user_query", "")
        tenant_id = _get(state, "tenant_id", "")
        schema_context: Optional[SchemaContext] = _get(state, "schema_context")

        emitter = get_emitter()
        if emitter:
            emitter.emit_step("Planning the approach")

        if not schema_context:
            return {"query_plan": None, "current_node": "generate_plan"}

        try:
            plan = await self._generate_plan(user_query, schema_context)

            if self.tenant_customizer and tenant_id:
                plan = self.tenant_customizer(tenant_id, user_query, plan)

            if emitter:
                for f in plan.required_filters:
                    emitter.emit_filter(f, "planned")
                if plan.date_filter:
                    emitter.emit_filter(plan.date_filter, "date")

            return {"query_plan": plan, "current_node": "generate_plan"}

        except Exception as exc:
            logger.error("PlannerNode failed: %s", exc)
            return {"error": f"Plan generation failed: {exc}", "current_node": "generate_plan"}

    async def _generate_plan(self, query: str, schema: SchemaContext) -> QueryPlan:
        parts: List[str] = [
            f"CURRENT DATE: {date.today().isoformat()}",
            f"\nUSER QUESTION: {query}",
            "\n--- SCHEMA CONTEXT ---",
        ]

        if schema.tables:
            parts.append("\nTABLES:")
            for t in schema.tables:
                parts.append(f"  - {t.table_name}" + (f" ({t.description})" if t.description else ""))

        if schema.joins:
            parts.append("\nJOINS:")
            for j in schema.joins:
                parts.append(f"  - {j.from_table}.{j.from_column} = {j.to_table}.{j.to_column}")

        if schema.filters:
            parts.append("\nFILTERS:")
            for f in schema.filters:
                parts.append(f"  - {f.description}: {f.sql_condition}")

        if schema.tenant_context_prompt:
            parts.append("\nBUSINESS RULES:")
            parts.append(schema.tenant_context_prompt)

        parts.append("\nGenerate a detailed query plan.")
        prompt = "\n".join(parts)

        return await self.llm.structured_output(
            prompt=prompt,
            response_model=QueryPlan,
            system_prompt=PLAN_SYSTEM_PROMPT,
        )


def _get(state: Any, field: str, default=None):
    return state.get(field, default) if isinstance(state, dict) else getattr(state, field, default)
