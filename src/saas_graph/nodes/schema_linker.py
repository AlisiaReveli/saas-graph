"""SchemaLinkerNode: discovers relevant tables, columns, and joins via semantic search."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..core.emitter import get_emitter
from ..core.state import AgentState
from ..interfaces.embedding import IEmbeddingService
from ..interfaces.knowledge import IKnowledgeRepository
from ..interfaces.schema_loader import ISchemaContextLoader
from ..models.schema import JoinSpec, SchemaContext, TableSpec

logger = logging.getLogger(__name__)


class SchemaLinkerNode:
    """Builds schema context by semantically searching for relevant database objects.

    Uses embedding-based search across tables, columns, and business rules,
    then resolves join paths between discovered tables.
    """

    def __init__(
        self,
        embedding_service: IEmbeddingService,
        schema_loader: ISchemaContextLoader,
        knowledge_repo: Optional[IKnowledgeRepository] = None,
        table_top_k: int = 6,
        table_min_score: float = 0.5,
        rule_top_k: int = 5,
    ) -> None:
        self.embedding_service = embedding_service
        self.schema_loader = schema_loader
        self.knowledge_repo = knowledge_repo
        self.table_top_k = table_top_k
        self.table_min_score = table_min_score
        self.rule_top_k = rule_top_k

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        user_query = _get(state, "user_query", "")
        tenant_id = _get(state, "tenant_id", "")

        logger.info("SchemaLinkerNode processing: %s", user_query[:100])

        emitter = get_emitter()
        if emitter:
            emitter.emit_step("Finding relevant data")

        try:
            schema_context = await self._build_context(user_query, tenant_id)

            logger.info(
                "SchemaLinker found %d tables, confidence=%.2f",
                len(schema_context.tables),
                schema_context.confidence,
            )

            if emitter:
                for t in schema_context.tables:
                    emitter.emit_table(t.table_name, t.description or "")
                for j in schema_context.joins:
                    emitter.emit_join(j.from_table, j.to_table, j.join_type.value)

            return {"schema_context": schema_context, "current_node": "resolve_schema"}

        except Exception as exc:
            logger.error("SchemaLinkerNode failed: %s", exc)
            return {"error": f"Schema linking failed: {exc}", "current_node": "resolve_schema"}

    async def _build_context(self, query: str, tenant_id: str) -> SchemaContext:
        table_names = await self.embedding_service.search_tables(
            query=query,
            tenant_id=tenant_id,
            top_k=self.table_top_k,
            min_similarity=self.table_min_score,
        )

        table_specs = [TableSpec(table_name=t, alias=t[:3]) for t in table_names]

        business_rules: List[Dict[str, Any]] = []
        if self.knowledge_repo:
            business_rules = await self.knowledge_repo.find_business_rules(
                query=query, tenant_id=tenant_id
            )

        base_context = await self.schema_loader.get_context(tenant_id=tenant_id)

        join_specs = self._resolve_joins(table_names, base_context)

        confidence = min(1.0, len(table_names) * 0.2) if table_names else 0.1

        return SchemaContext(
            tables=table_specs,
            joins=join_specs,
            filters=base_context.filters if base_context else [],
            business_rules=business_rules,
            confidence=confidence,
            tenant_context_prompt=base_context.tenant_context_prompt if base_context else None,
        )

    @staticmethod
    def _resolve_joins(
        table_names: List[str], base_context: Optional[SchemaContext]
    ) -> List[JoinSpec]:
        if not base_context or not base_context.joins:
            return []
        table_set = set(table_names)
        return [
            j
            for j in base_context.joins
            if j.from_table in table_set and j.to_table in table_set
        ]


def _get(state: Any, field: str, default=None):
    return state.get(field, default) if isinstance(state, dict) else getattr(state, field, default)
