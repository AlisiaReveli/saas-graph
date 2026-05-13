"""CacheNode: checks for matching golden queries before full schema linking."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..core.emitter import get_emitter
from ..core.state import AgentState
from ..interfaces.knowledge import IKnowledgeRepository

logger = logging.getLogger(__name__)


class CacheNode:
    """Hybrid search for golden (verified) query templates.

    If a golden query matches with sufficient similarity, the pipeline
    skips schema linking and jumps directly to SQL generation.
    """

    def __init__(
        self,
        knowledge_repo: IKnowledgeRepository,
        min_similarity: float = 0.7,
    ) -> None:
        self.knowledge_repo = knowledge_repo
        self.min_similarity = min_similarity

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        user_query = _get(state, "user_query", "")
        tenant_id = _get(state, "tenant_id", "")

        emitter = get_emitter()
        if emitter:
            emitter.emit_step("Checking for verified query templates")

        try:
            golden = await self.knowledge_repo.find_golden_query(
                query=user_query,
                tenant_id=tenant_id,
                min_similarity=self.min_similarity,
            )

            if golden and golden.similarity_score >= self.min_similarity:
                logger.info(
                    "Golden query hit: %s (score=%.2f)",
                    golden.name,
                    golden.similarity_score,
                )
                if emitter:
                    emitter.emit_step(f"Found verified template: {golden.name}")
                return {
                    "cache_hit": True,
                    "schema_context": golden.to_schema_context(),
                    "current_node": "cache_lookup",
                }
        except Exception as exc:
            logger.warning("Golden query lookup failed: %s", exc)

        return {"cache_hit": False, "current_node": "cache_lookup"}


def _get(state: Any, field: str, default=None):
    return state.get(field, default) if isinstance(state, dict) else getattr(state, field, default)
