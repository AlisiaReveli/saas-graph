"""OpenAI implementation of ILLMGateway."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel

from ..interfaces.llm import ILLMGateway
from ..models.intent import QueryIntent
from ..models.plan import QueryPlan
from ..models.schema import SchemaContext
from ..models.sql import SQLSpec

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class OpenAIGateway(ILLMGateway):
    """LLM gateway backed by the OpenAI API (or any compatible endpoint).

    Args:
        api_key: OpenAI API key.
        model: Model name (default ``gpt-4o``).
        base_url: Optional override for the API base URL.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
    ) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ImportError("pip install saas-graph[openai]") from exc

        self.model = model
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

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
    ) -> SQLSpec:
        system = (
            "You are an expert SQL generator. Generate a single valid PostgreSQL query.\n"
            "Return ONLY a JSON object with keys: sql, explanation, tables_used."
        )

        parts = [f"Question: {query}"]
        if schema_context.tenant_context_prompt:
            parts.append(f"\nSchema:\n{schema_context.tenant_context_prompt}")
        if schema_context.tables:
            parts.append("\nAvailable tables: " + ", ".join(t.table_name for t in schema_context.tables))
        if schema_context.joins:
            parts.append(
                "\nJoins:\n"
                + "\n".join(f"  {j.from_table}.{j.from_column} = {j.to_table}.{j.to_column}" for j in schema_context.joins)
            )
        if schema_context.golden_query:
            gq = schema_context.golden_query
            parts.append(f"\nVerified SQL template (adapt this):\n{gq.sql}")
        if query_plan:
            parts.append(f"\nPlan: {query_plan.plan_description}")
        if validation_errors:
            parts.append("\nPrevious errors:\n" + "\n".join(f"- {e}" for e in validation_errors))
        if previous_sql:
            parts.append(f"\nPrevious SQL (fix this):\n{previous_sql}")

        prompt = "\n".join(parts)
        raw = await self.complete(prompt, system_prompt=system, temperature=0.0)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            sql = self._extract_sql_from_text(raw)
            data = {"sql": sql, "explanation": "", "tables_used": []}

        return SQLSpec(
            sql=data.get("sql", raw),
            explanation=data.get("explanation", ""),
            tables_used=data.get("tables_used", []),
            generation_attempts=attempt_number,
            from_golden_query=schema_context.has_golden_query(),
        )

    async def format_response(
        self,
        query: str,
        results: List[dict],
        sql: str,
        display_format: Optional[str] = None,
        display_hint: Optional[str] = None,
        filter_descriptions: Optional[List[str]] = None,
    ) -> str:
        system = (
            "Format the following SQL query results as a clear, concise markdown response.\n"
            "Use tables for tabular data. Format currency values with $ and commas.\n"
            "Do NOT repeat the user's question as a heading."
        )
        parts = [f"User asked: {query}", f"Display format: {display_format or 'auto'}"]
        if filter_descriptions:
            parts.append("Filters applied: " + ", ".join(filter_descriptions))
        results_preview = json.dumps(results[:50], default=str)
        parts.append(f"Results ({len(results)} rows):\n{results_preview}")
        return await self.complete("\n".join(parts), system_prompt=system)

    async def classify_query(self, query: str) -> dict:
        system = (
            "Classify this query as INTERNAL (answerable from a database) or EXTERNAL "
            "(general knowledge requiring web search). Return JSON: {classification, reasoning}"
        )
        raw = await self.complete(query, system_prompt=system)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            classification = "EXTERNAL" if any(w in raw.upper() for w in ("EXTERNAL",)) else "INTERNAL"
            return {"classification": classification, "reasoning": raw}

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> str:
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        resp = await self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    async def structured_output(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
    ) -> T:
        try:
            import instructor
        except ImportError as exc:
            raise ImportError("pip install saas-graph[openai] (includes instructor)") from exc

        client = instructor.from_openai(self.client)
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return await client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_model=response_model,
        )

    async def optimize_search_query(self, user_query: str, domain: Optional[str] = None) -> str:
        system = "Rewrite this query for better web search results. Return only the optimized query."
        if domain:
            system += f" Domain context: {domain}."
        return await self.complete(user_query, system_prompt=system)

    async def summarize_web_results(self, user_query: str, search_results: dict) -> str:
        system = (
            "Summarize these web search results into a clear response. "
            "Include a References section with source links."
        )
        results_text = json.dumps(search_results.get("results", [])[:5], default=str)
        prompt = f"Question: {user_query}\n\nSearch results:\n{results_text}"
        return await self.complete(prompt, system_prompt=system)

    @staticmethod
    def _extract_sql_from_text(text: str) -> str:
        if "```sql" in text:
            parts = text.split("```sql")
            if len(parts) > 1:
                return parts[1].split("```")[0].strip()
        if "```" in text:
            parts = text.split("```")
            if len(parts) > 1:
                return parts[1].strip()
        return text.strip()
