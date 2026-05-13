from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class JoinType(str, Enum):
    INNER = "INNER JOIN"
    LEFT = "LEFT JOIN"
    RIGHT = "RIGHT JOIN"
    FULL = "FULL OUTER JOIN"


class TableSpec(BaseModel):
    """Specification for a database table used in a query."""

    table_name: str
    alias: Optional[str] = None
    business_name: Optional[str] = None
    columns: List[str] = Field(default_factory=list)
    description: Optional[str] = None

    @property
    def alias_or_name(self) -> str:
        return self.alias or self.table_name


class JoinSpec(BaseModel):
    """Specification for a JOIN between two tables."""

    from_table: str
    from_column: str
    to_table: str
    to_column: str
    join_type: JoinType = JoinType.LEFT

    def to_sql(
        self,
        from_alias: Optional[str] = None,
        to_alias: Optional[str] = None,
    ) -> str:
        from_ref = f"{from_alias or self.from_table}.{self.from_column}"
        to_ref = f"{to_alias or self.to_table}.{self.to_column}"
        sql = f"{self.join_type.value} {self.to_table}"
        if to_alias:
            sql += f" {to_alias}"
        sql += f" ON {from_ref} = {to_ref}"
        return sql


class FilterSpec(BaseModel):
    """A SQL filter condition to apply to queries."""

    filter_type: str = Field(description="Semantic type, e.g. 'date', 'status', 'tenant'")
    sql_condition: str
    description: Optional[str] = None
    required: bool = True


class GoldenQuery(BaseModel):
    """A verified question-to-SQL mapping that can be reused."""

    name: str
    canonical_question: str
    sql: str
    sql_template: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    required_tables: List[str] = Field(default_factory=list)
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)

    def to_schema_context(self) -> SchemaContext:
        return SchemaContext(
            tables=[TableSpec(table_name=t) for t in self.required_tables],
            golden_query=self,
            confidence=self.similarity_score,
        )


class SchemaContext(BaseModel):
    """Complete schema context passed through the pipeline to SQL generation."""

    tables: List[TableSpec] = Field(default_factory=list)
    joins: List[JoinSpec] = Field(default_factory=list)
    filters: List[FilterSpec] = Field(default_factory=list)
    golden_query: Optional[GoldenQuery] = None
    business_rules: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    tenant_context_prompt: Optional[str] = Field(
        default=None,
        description="Pre-formatted schema context for inclusion in LLM prompts",
    )

    def get_table_names(self) -> List[str]:
        return [t.table_name for t in self.tables]

    def has_golden_query(self) -> bool:
        return self.golden_query is not None and self.golden_query.similarity_score >= 0.7

    def get_required_filters(self) -> List[FilterSpec]:
        return [f for f in self.filters if f.required]
