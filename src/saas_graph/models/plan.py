from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GoldenQueryReference(BaseModel):
    """Reference to a matching golden query found during planning."""

    id: Optional[str] = None
    name: str
    canonical_question: str
    sql_template: Optional[str] = None
    similarity_score: float = 0.0
    required_tables: List[str] = Field(default_factory=list)
    required_joins: List[str] = Field(default_factory=list)


class QueryPlan(BaseModel):
    """Execution plan generated before SQL creation."""

    plan_description: str = ""
    tables_to_use: List[str] = Field(default_factory=list)
    joins_required: List[str] = Field(default_factory=list)
    required_filters: List[str] = Field(default_factory=list)
    date_filter: Optional[str] = None
    business_rules: List[str] = Field(default_factory=list)
    special_instructions: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    golden_query_matches: List[GoldenQueryReference] = Field(default_factory=list)
    filter_sql_conditions: List[str] = Field(default_factory=list)
    tenant_context_prompt: Optional[str] = None
    table_info: Dict[str, Any] = Field(default_factory=dict)
