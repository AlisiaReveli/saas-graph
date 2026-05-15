from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from ..models.intent import QueryIntent
    from ..models.plan import QueryPlan
    from ..models.schema import SchemaContext
    from ..models.sql import SQLSpec

T = TypeVar("T", bound=BaseModel)


class ILLMGateway(ABC):
    """Interface for all LLM interactions in the pipeline."""

    @abstractmethod
    async def generate_sql(
        self,
        query: str,
        intent: QueryIntent,
        schema_context: SchemaContext,
        query_plan: Optional[QueryPlan] = None,
        validation_errors: Optional[List[str]] = None,
        previous_sql: Optional[str] = None,
        attempt_number: int = 1,
        max_attempts: int = 5,
        database_type: str = "postgres",
    ) -> SQLSpec:
        """Generate a database query from a natural language query and schema context.

        When *database_type* is ``"mongodb"``, the returned :pyclass:`SQLSpec.sql`
        field should contain a JSON-encoded MongoDB aggregation pipeline with
        ``collection`` and ``pipeline`` keys.
        """
        ...

    @abstractmethod
    async def format_response(
        self,
        query: str,
        results: List[dict],
        sql: str,
        display_format: Optional[str] = None,
        display_hint: Optional[str] = None,
        filter_descriptions: Optional[List[str]] = None,
    ) -> str:
        """Format query results as a natural language markdown response."""
        ...

    @abstractmethod
    async def classify_query(self, query: str) -> dict:
        """Classify a query as INTERNAL (database) or EXTERNAL (web search).

        Returns a dict with at least ``classification`` (str) and ``reasoning`` (str).
        """
        ...

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> str:
        """Simple text completion."""
        ...

    @abstractmethod
    async def structured_output(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
    ) -> T:
        """Generate structured output conforming to a Pydantic model."""
        ...

    async def optimize_search_query(self, user_query: str, domain: Optional[str] = None) -> str:
        """Optimize a user query for web search. Override for custom logic."""
        return user_query

    async def summarize_web_results(self, user_query: str, search_results: dict) -> str:
        """Summarize web search results into a coherent response."""
        return str(search_results)

    async def select_relevant_tables(
        self,
        query: str,
        available_tables: Dict[str, str],
    ) -> List[str]:
        """Use LLM to select tables relevant to the user's query."""
        return list(available_tables.keys())
