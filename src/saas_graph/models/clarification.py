from typing import Optional

from pydantic import BaseModel


class ClarificationResult(BaseModel):
    """Result from the clarification node."""

    is_clear: bool = True
    clarification_question: Optional[str] = None
    domain: Optional[str] = None
    entity: Optional[str] = None
    time_period: Optional[str] = None
    metric: Optional[str] = None
    expanded_query: Optional[str] = None
    raw_response: Optional[str] = None
