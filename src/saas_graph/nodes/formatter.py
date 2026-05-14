"""FormatterNode: formats query results into readable markdown responses."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from ..core.emitter import get_emitter
from ..core.state import AgentState
from ..interfaces.llm import ILLMGateway

logger = logging.getLogger(__name__)


class DisplayFormat(str, Enum):
    SIMPLE = "simple"
    TABLE = "table"
    RANKING = "ranking"
    SINGLE_VALUE = "single_value"
    WEB_SEARCH = "web_search"
    ERROR = "error"
    EMPTY = "empty"
    INFORMATIVE = "informative"
    CLARIFICATION = "clarification"


class FormatterNode:
    """Formats pipeline results into user-facing markdown responses.

    Handles all output paths: success with data, empty results, errors,
    web search results, and clarification questions.

    Args:
        llm: LLM gateway for intelligent formatting.
        column_display_names: Map raw column names to friendly display names.
            E.g. ``{"patient_id": "Patient ID", "total_cost": "Total Cost ($)"}``
    """

    def __init__(
        self,
        llm: ILLMGateway,
        column_display_names: Optional[Dict[str, str]] = None,
    ) -> None:
        self.llm = llm
        self.column_names = column_display_names or {}

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        needs_clarification = _get(state, "needs_clarification", False)
        clarification_result = _get(state, "clarification_result")
        web_search_result = _get(state, "web_search_result")
        error = _get(state, "error")
        validation_errors = _get(state, "validation_errors", []) or []
        retry_count = int(_get(state, "retry_count", 0) or 0)
        max_retries = int(_get(state, "max_retries", 5) or 5)
        query_results = _get(state, "query_results", [])
        user_query = _get(state, "user_query", "")
        sql_spec = _get(state, "sql_spec")

        emitter = get_emitter()
        if emitter:
            emitter.emit_step("Preparing your answer")

        if needs_clarification and clarification_result:
            question = clarification_result.clarification_question or "Could you provide more details?"
            return {
                "formatted_response": question,
                "display_format": DisplayFormat.CLARIFICATION.value,
                "current_node": "format_response",
            }

        if web_search_result:
            return {
                "formatted_response": web_search_result,
                "display_format": DisplayFormat.WEB_SEARCH.value,
                "current_node": "format_response",
            }

        if error:
            return {
                "formatted_response": self._format_error(error),
                "display_format": DisplayFormat.ERROR.value,
                "current_node": "format_response",
            }

        exec_errors = [e for e in validation_errors if "xecution error" in str(e)]
        if exec_errors and retry_count >= max_retries:
            msg = f"Query failed after {max_retries} attempts.\n\n" + "\n".join(
                f"- {e}" for e in exec_errors[:5]
            )
            return {
                "formatted_response": self._format_error(msg),
                "display_format": DisplayFormat.ERROR.value,
                "error": msg,
                "current_node": "format_response",
            }

        if sql_spec and getattr(sql_spec, "is_fallback_sql", False) and getattr(sql_spec, "agent_output", None):
            return {
                "formatted_response": sql_spec.agent_output.strip(),
                "display_format": DisplayFormat.INFORMATIVE.value,
                "current_node": "format_response",
            }

        if not query_results:
            return {
                "formatted_response": self._format_empty(user_query),
                "display_format": DisplayFormat.EMPTY.value,
                "current_node": "format_response",
            }

        sql = sql_spec.sql if sql_spec else ""
        display_format = self._detect_format(query_results, user_query)

        if emitter:
            emitter.emit_step("Formatting the response")

        try:
            display_results = self._apply_display_names(query_results) if self.column_names else query_results
            display_hint = None
            if self.column_names:
                display_hint = "Column display names: " + ", ".join(
                    f"{k} -> {v}" for k, v in self.column_names.items()
                )
            formatted = await self.llm.format_response(
                query=user_query,
                results=display_results,
                sql=sql,
                display_format=display_format.value,
                display_hint=display_hint,
            )
            formatted = self._append_sql(formatted, sql)
            return {
                "formatted_response": formatted,
                "display_format": display_format.value,
                "current_node": "format_response",
            }
        except Exception as exc:
            logger.warning("LLM formatting failed, using fallback: %s", exc)
            formatted = self._to_markdown_table(query_results)
            formatted = self._append_sql(formatted, sql)
            return {
                "formatted_response": formatted,
                "display_format": DisplayFormat.TABLE.value,
                "current_node": "format_response",
            }

    def _apply_display_names(self, results: list) -> list:
        """Rename keys in result dicts to their display names."""
        if not results or not self.column_names:
            return results
        return [
            {self.column_names.get(k, k): v for k, v in row.items()}
            for row in results
        ]

    def _detect_format(self, results: list, query: str) -> DisplayFormat:
        if len(results) == 1 and len(results[0]) <= 3:
            return DisplayFormat.SINGLE_VALUE
        q = query.lower()
        if any(w in q for w in ("top", "highest", "lowest", "best", "worst")):
            return DisplayFormat.RANKING
        if len(results) <= 5:
            return DisplayFormat.SIMPLE
        return DisplayFormat.TABLE

    def _format_value(self, key: str, value: Any) -> str:
        if value is None:
            return "N/A"
        display_key = self.column_names.get(key, key).lower()
        if any(w in display_key for w in ("amount", "total", "cost", "revenue", "price")):
            try:
                return f"${float(value):,.2f}"
            except (ValueError, TypeError):
                return str(value)
        if "percent" in display_key or "rate" in display_key:
            try:
                return f"{float(value):.1f}%"
            except (ValueError, TypeError):
                return str(value)
        return str(value)

    def _to_markdown_table(self, results: list, max_rows: int = 20) -> str:
        if not results:
            return ""
        columns = list(results[0].keys())
        display_cols = [self.column_names.get(c, c) for c in columns]
        lines: List[str] = []
        lines.append("| " + " | ".join(display_cols) + " |")
        lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
        for row in results[:max_rows]:
            vals = [str(self._format_value(c, row.get(c, "")))[:50] for c in columns]
            lines.append("| " + " | ".join(vals) + " |")
        if len(results) > max_rows:
            lines.append(f"\n*... and {len(results) - max_rows} more rows*")
        lines.append(f"\n*Total: {len(results)} results*")
        return "\n".join(lines)

    @staticmethod
    def _format_empty(query: str) -> str:
        return (
            f"**No results found for:** {query}\n\n"
            "This could mean:\n"
            "- No data matches the specified criteria\n"
            "- The time period has no records\n"
            "- The filter conditions are too restrictive\n\n"
            "Try broadening your query or checking a different time period."
        )

    @staticmethod
    def _format_error(error: str) -> str:
        return (
            f"**Error processing your query**\n\n{error}\n\n"
            "Please try rephrasing your question."
        )

    @staticmethod
    def _append_sql(formatted: str, sql: str) -> str:
        if not sql or not sql.strip():
            return formatted
        return f"{formatted}\n\n<details>\n<summary>SQL Query</summary>\n\n```sql\n{sql.strip()}\n```\n</details>"


def _get(state: Any, field: str, default=None):
    return state.get(field, default) if isinstance(state, dict) else getattr(state, field, default)
