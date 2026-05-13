"""ClarifierNode: asks the user for clarification when a query is ambiguous."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from ..core.emitter import get_emitter
from ..core.state import AgentState
from ..interfaces.llm import ILLMGateway
from ..models.clarification import ClarificationResult

logger = logging.getLogger(__name__)

DEFAULT_CLARIFICATION_PROMPT = """You are an AI assistant that determines whether a user's question is clear enough to answer from a database, or whether you need to ask a clarifying question.

Respond with one of:
1. "CLEAR:" followed by any expanded understanding (Domain, Entity, Time period, Metric, Expanded query)
2. A clarification question if the query is too ambiguous.

Rules:
- If the question mentions a specific metric, entity, and time period, it is CLEAR.
- If the question is vague (e.g. "show me the data"), ask what specifically they want to see.
- If the question references a previous conversation, try to resolve it from context.
- Keep clarification questions concise and specific.
"""

_ROLE_MAP = {"human": "user", "ai": "assistant", "system": "system"}


class ClarifierNode:
    """Determines if a user query needs clarification before proceeding.

    Args:
        llm: LLM gateway for generating clarification decisions.
        system_prompt: Custom clarification prompt. If ``None``, uses the built-in default.
    """

    def __init__(
        self,
        llm: ILLMGateway,
        system_prompt: Optional[str] = None,
    ) -> None:
        self.llm = llm
        self.system_prompt = system_prompt or DEFAULT_CLARIFICATION_PROMPT

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        user_query = _get(state, "user_query", "")
        messages = _get(state, "messages", [])

        logger.info("ClarifierNode processing: %s", user_query[:100])

        emitter = get_emitter()
        if emitter:
            emitter.emit_step("Checking if your question is clear")

        pending = self._get_pending_clarification(messages)
        merged_query = None

        history_text = self._format_history(messages)

        if pending:
            original = pending["original_query"]
            prompt = f"{history_text}Original question: {original}\nUser clarified: {user_query}\n\nEvaluate the combined context."
            merged_query = f"{original} — {user_query}"
        else:
            prompt = f"{history_text}User question: {user_query}"

        response = await self.llm.complete(
            prompt=prompt,
            system_prompt=self.system_prompt,
            temperature=0.0,
        )

        result = self._parse_response(response)

        output: Dict[str, Any] = {
            "clarification_result": result,
            "needs_clarification": not result.is_clear,
            "current_node": "clarify_query",
        }

        if result.is_clear:
            original = pending["original_query"] if pending else user_query
            next_query = result.expanded_query or merged_query or original
            if next_query and next_query != user_query:
                output["user_query"] = next_query

        return output

    def _format_history(self, messages: list, max_interactions: int = 10) -> str:
        if not messages:
            return ""
        recent = messages[-(max_interactions * 2) :]
        lines: List[str] = []
        for msg in recent:
            role, content = _extract(msg)
            if role in ("user", "assistant"):
                lines.append(f"{role.capitalize()}: {content}")
        if not lines:
            return ""
        return "Conversation history:\n" + "\n".join(lines) + "\n\n"

    def _get_pending_clarification(self, messages: list) -> Optional[Dict[str, str]]:
        if len(messages) < 2:
            return None
        last_assistant_idx = -1
        last_assistant = None
        for i, msg in enumerate(reversed(messages)):
            role, _ = _extract(msg)
            if role == "assistant":
                last_assistant = msg
                last_assistant_idx = len(messages) - 1 - i
                break
        if not last_assistant:
            return None
        _, content = _extract(last_assistant)
        if not content.strip().endswith("?"):
            return None
        for msg in reversed(messages[:last_assistant_idx]):
            role, content = _extract(msg)
            if role == "user" and content:
                return {"original_query": content}
        return None

    def _parse_response(self, response: str) -> ClarificationResult:
        response = response.strip()
        if response.startswith("CLEAR:"):
            return self._parse_clear(response)
        if "?" in response or "clarification" in response.lower():
            return ClarificationResult(is_clear=False, clarification_question=response, raw_response=response)
        return ClarificationResult(is_clear=True, raw_response=response)

    def _parse_clear(self, response: str) -> ClarificationResult:
        def _extract_field(label: str) -> Optional[str]:
            m = re.search(rf"{label}:\s*(.+?)(?:\n|$)", response, re.IGNORECASE)
            return m.group(1).strip() if m else None

        return ClarificationResult(
            is_clear=True,
            domain=_extract_field("Domain"),
            entity=_extract_field("Entity"),
            time_period=_extract_field("Time period"),
            metric=_extract_field("Metric"),
            expanded_query=_extract_field("Expanded query"),
            raw_response=response,
        )


def _get(state: Any, field: str, default=None):
    return state.get(field, default) if isinstance(state, dict) else getattr(state, field, default)


def _extract(msg: Any) -> Tuple[str, str]:
    if isinstance(msg, dict):
        return msg.get("role", ""), msg.get("content", "")
    role = getattr(msg, "type", "") or getattr(msg, "role", "")
    content = getattr(msg, "content", "")
    return _ROLE_MAP.get(role, role), content
