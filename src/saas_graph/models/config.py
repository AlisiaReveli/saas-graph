from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class NodeConfig:
    """Fine-grained configuration for individual pipeline nodes."""

    max_sql_retries: int = 5
    cache_ttl_seconds: int = 300
    execution_timeout_seconds: float = 30.0
    semantic_search_threshold: float = 0.3
    semantic_search_top_k: int = 10
    golden_query_threshold: float = 0.7
    enable_clarification: bool = True
    enable_planning: bool = True
    enable_cache: bool = False
    enable_web_search: bool = True


@dataclass
class DomainConfig:
    """Configuration that adapts the pipeline to a specific domain.

    This is the primary way users customize saas-graph for their use case.
    All domain-specific knowledge is injected through this config rather
    than hardcoded in the pipeline.
    """

    name: str = "default"
    description: str = ""

    schema_path: Optional[str] = None
    business_rules_path: Optional[str] = None
    golden_queries_path: Optional[str] = None

    column_display_names: Dict[str, str] = field(default_factory=dict)

    clarification_prompt: Optional[str] = None

    sql_instructions: List[str] = field(default_factory=list)

    tenant_id_column: Optional[str] = None

    search_domain: Optional[str] = None

    tenant_customizer: Optional[Callable[..., Any]] = None

    def get_schema_path(self) -> Optional[Path]:
        if self.schema_path:
            return Path(self.schema_path)
        return None

    def get_business_rules_path(self) -> Optional[Path]:
        if self.business_rules_path:
            return Path(self.business_rules_path)
        return None

    def get_golden_queries_path(self) -> Optional[Path]:
        if self.golden_queries_path:
            return Path(self.golden_queries_path)
        return None
