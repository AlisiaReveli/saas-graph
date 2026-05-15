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
        database_type: str = "postgres",
    ) -> SQLSpec:
        is_mongo = database_type == "mongodb"

        if is_mongo:
            system = (
                "You are an expert MongoDB query generator. Generate a valid MongoDB "
                "aggregation pipeline.\n"
                "Return ONLY a JSON object with keys: collection, pipeline, explanation, "
                "tables_used.\n"
                '- "collection": the target collection name\n'
                '- "pipeline": an array of aggregation stages '
                "(e.g. $match, $group, $sort, $project, $lookup, $unwind, $limit)\n"
                '- "explanation": brief description of what the query does\n'
                '- "tables_used": list of collection names referenced\n\n'
                "CRITICAL RULES:\n"
                "- In $group, the grouping key MUST be called '_id', never 'id'.\n"
                "- Every non-_id field in $group MUST use an accumulator "
                "($sum, $avg, $first, $last, $min, $max, $push, etc.).\n"
                "- After $group, only _id and your accumulators exist — "
                "to access original fields, use $first in the $group stage.\n"
                "- Use $lookup for joins. Place $lookup BEFORE $group when you need "
                "joined fields inside the aggregation.\n"
                "- For $lookup: localField/foreignField must match the actual field names "
                "in each collection (e.g. localField: 'product_id', "
                "foreignField: '_id').\n"
                "- DATE FILTERS: In $match, use LITERAL ISO-8601 date strings "
                'for comparisons (e.g. {"$gte": "2025-04-01T00:00:00Z"}). '
                "Do NOT use aggregation expressions like $dateSubtract, "
                "$dateFromParts, or $$NOW inside $match — those only work "
                "inside $expr. Compute the actual dates yourself and use "
                "literal strings.\n"
                "- Do NOT use SQL syntax. This is MongoDB aggregation only.\n"
            )
        else:
            system = (
                "You are an expert SQL generator. Generate a single valid PostgreSQL query.\n"
                "Return ONLY a JSON object with keys: sql, explanation, tables_used."
            )

        parts = [f"Question: {query}"]
        if is_mongo:
            from datetime import date

            parts.append(f"\nToday's date: {date.today().isoformat()}")
        if schema_context.tenant_context_prompt:
            label = "Collections" if is_mongo else "Schema"
            parts.append(f"\n{label}:\n{schema_context.tenant_context_prompt}")
        if schema_context.tables:
            label = "Available collections" if is_mongo else "Available tables"
            parts.append(
                f"\n{label}: "
                + ", ".join(t.table_name for t in schema_context.tables)
            )
        if schema_context.joins:
            if is_mongo:
                parts.append(
                    "\nRelationships (use $lookup):\n"
                    + "\n".join(
                        f"  {j.from_table}.{j.from_column} -> {j.to_table}.{j.to_column}"
                        for j in schema_context.joins
                    )
                )
            else:
                parts.append(
                    "\nJoins:\n"
                    + "\n".join(
                        f"  {j.from_table}.{j.from_column} = {j.to_table}.{j.to_column}"
                        for j in schema_context.joins
                    )
                )
        if schema_context.golden_query:
            gq = schema_context.golden_query
            parts.append(f"\nVerified query template (adapt this):\n{gq.sql}")
        if query_plan:
            parts.append(f"\nPlan: {query_plan.plan_description}")
        if validation_errors:
            parts.append(
                "\nPrevious errors:\n" + "\n".join(f"- {e}" for e in validation_errors)
            )
        if previous_sql:
            parts.append(f"\nPrevious query (fix this):\n{previous_sql}")

        prompt = "\n".join(parts)
        raw = await self.complete(prompt, system_prompt=system, temperature=0.0)

        try:
            data = json.loads(self._strip_code_fence(raw))
        except json.JSONDecodeError:
            if is_mongo:
                data = {"collection": "", "pipeline": [], "explanation": raw, "tables_used": []}
            else:
                sql = self._extract_sql_from_text(raw)
                data = {"sql": sql, "explanation": "", "tables_used": []}

        if is_mongo:
            mongo_query = json.dumps(
                {"collection": data.get("collection", ""), "pipeline": data.get("pipeline", [])},
            )
            return SQLSpec(
                sql=mongo_query,
                explanation=data.get("explanation", ""),
                tables_used=data.get("tables_used", []),
                generation_attempts=attempt_number,
                from_golden_query=schema_context.has_golden_query(),
            )

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
    def _strip_code_fence(text: str) -> str:
        """Remove markdown code fences (```json ... ```, etc.) from LLM output."""
        stripped = text.strip()
        if stripped.startswith("```"):
            first_newline = stripped.index("\n") if "\n" in stripped else len(stripped)
            stripped = stripped[first_newline + 1 :]
            if stripped.endswith("```"):
                stripped = stripped[:-3]
            return stripped.strip()
        return stripped

    @staticmethod
    def _extract_sql_from_text(text: str) -> str:
        text = text.strip()
        if "```sql" in text:
            parts = text.split("```sql")
            if len(parts) > 1:
                return parts[1].split("```")[0].strip()
        if "```json" in text:
            inner = text.split("```json")[1].split("```")[0].strip()
            try:
                data = json.loads(inner)
                if isinstance(data, dict) and "sql" in data:
                    return data["sql"]
            except (json.JSONDecodeError, KeyError):
                pass
        if "```" in text:
            parts = text.split("```")
            if len(parts) > 1:
                return parts[1].strip()
        return text.strip()
