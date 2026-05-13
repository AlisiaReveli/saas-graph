from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class QueryType(str, Enum):
    AGGREGATION = "aggregation"
    LISTING = "listing"
    COMPARISON = "comparison"
    TREND = "trend"
    LOOKUP = "lookup"
    CALCULATION = "calculation"
    UNKNOWN = "unknown"


class TimeReference(BaseModel):
    """Parsed time reference from a user query."""

    phrase: str = Field(description="Original time phrase, e.g. 'last month'")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_relative: bool = True


class QueryIntent(BaseModel):
    """Parsed intent from a user's natural language query."""

    query_type: QueryType = QueryType.UNKNOWN
    time_reference: Optional[TimeReference] = None
    entities: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    is_follow_up: bool = False
    raw_query: str = ""
