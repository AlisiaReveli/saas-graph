"""YAML-based schema context loader.

Reads ``schema_context.yaml`` files and produces a :class:`SchemaContext`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from ..interfaces.schema_loader import ISchemaContextLoader
from ..models.schema import (
    FilterSpec,
    GoldenQuery,
    JoinSpec,
    JoinType,
    SchemaContext,
    TableSpec,
)

logger = logging.getLogger(__name__)


class YAMLSchemaLoader(ISchemaContextLoader):
    """Loads schema context from a ``schema_context.yaml`` file.

    Expected YAML structure::

        tables:
          patients:
            description: "Patient records"
            columns:
              patient_id: { type: int, description: "..." }
            aliases:
              - { name: "ICU patients", filter: "ward = 'ICU'" }
            joins:
              - { to: prescriptions, on: "patient_id = patient_id", type: LEFT }

        business_rules:
          - name: exclude_test
            trigger_terms: [patients]
            sql_condition: "patient_type != 'TEST'"
            description: "Exclude test patients"

        golden_queries:
          - name: monthly_admissions
            question: "How many patients admitted last month?"
            sql: "SELECT COUNT(*) ..."
            tables: [patients]
    """

    def __init__(
        self,
        schema_path: Union[str, Path],
        golden_queries_path: Optional[Union[str, Path]] = None,
        business_rules_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.schema_path = Path(schema_path)
        self.golden_queries_path = Path(golden_queries_path) if golden_queries_path else None
        self.business_rules_path = Path(business_rules_path) if business_rules_path else None
        self._cache: Optional[SchemaContext] = None

    async def get_context(self, tenant_id: str = "", access_policy: Any = None) -> SchemaContext:
        if self._cache:
            return self._cache

        raw = self._load_yaml(self.schema_path)
        tables = self._parse_tables(raw.get("tables", {}))
        joins = self._parse_joins(raw.get("tables", {}))
        filters = self._parse_filters(raw.get("filters", []))
        rules = raw.get("business_rules", [])

        if self.business_rules_path and self.business_rules_path.exists():
            extra_rules = self._load_yaml(self.business_rules_path)
            if isinstance(extra_rules, list):
                rules.extend(extra_rules)

        prompt = self._build_prompt(raw, tables)

        ctx = SchemaContext(
            tables=tables,
            joins=joins,
            filters=filters,
            business_rules=rules,
            confidence=0.8,
            tenant_context_prompt=prompt,
        )
        self._cache = ctx
        return ctx

    async def refresh(self, tenant_id: str = "") -> None:
        self._cache = None

    def get_golden_queries(self) -> List[GoldenQuery]:
        source = self.golden_queries_path or self.schema_path
        if not source.exists():
            return []
        raw = self._load_yaml(source)
        entries = raw.get("golden_queries", []) if isinstance(raw, dict) else raw if isinstance(raw, list) else []
        result = []
        for entry in entries:
            result.append(
                GoldenQuery(
                    name=entry.get("name", ""),
                    canonical_question=entry.get("question", ""),
                    sql=entry.get("sql", ""),
                    required_tables=entry.get("tables", []),
                )
            )
        return result

    @staticmethod
    def _load_yaml(path: Path) -> Dict[str, Any]:
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}

    @staticmethod
    def _parse_tables(tables_raw: Dict[str, Any]) -> List[TableSpec]:
        specs = []
        for name, info in tables_raw.items():
            info = info or {}
            columns = list((info.get("columns") or {}).keys())
            specs.append(
                TableSpec(
                    table_name=name,
                    alias=name[:3],
                    description=info.get("description", ""),
                    columns=columns,
                )
            )
        return specs

    @staticmethod
    def _parse_joins(tables_raw: Dict[str, Any]) -> List[JoinSpec]:
        joins = []
        for table_name, info in tables_raw.items():
            info = info or {}
            for j in info.get("joins", []):
                on = j.get("on", "")
                parts = on.split("=")
                if len(parts) == 2:
                    from_col = parts[0].strip()
                    to_col = parts[1].strip()
                    jt = JoinType.LEFT if j.get("type", "LEFT").upper() == "LEFT" else JoinType.INNER
                    joins.append(
                        JoinSpec(
                            from_table=table_name,
                            from_column=from_col,
                            to_table=j.get("to", ""),
                            to_column=to_col,
                            join_type=jt,
                        )
                    )
        return joins

    @staticmethod
    def _parse_filters(filters_raw: list) -> List[FilterSpec]:
        return [
            FilterSpec(
                filter_type=f.get("type", "general"),
                sql_condition=f.get("sql", ""),
                description=f.get("description", ""),
                required=f.get("required", True),
            )
            for f in filters_raw
        ]

    @staticmethod
    def _build_prompt(raw: Dict[str, Any], tables: List[TableSpec]) -> str:
        lines = ["## Database Schema\n"]
        for t in tables:
            lines.append(f"### {t.table_name}")
            if t.description:
                lines.append(t.description)
            if t.columns:
                lines.append("Columns: " + ", ".join(t.columns))
            lines.append("")
        rules = raw.get("business_rules", [])
        if rules:
            lines.append("## Business Rules\n")
            for r in rules:
                lines.append(f"- **{r.get('name', '')}**: {r.get('description', '')} → `{r.get('sql_condition', '')}`")
        return "\n".join(lines)
