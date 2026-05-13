"""RouterNode: classifies queries as INTERNAL (database) or EXTERNAL (web search)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..core.emitter import get_emitter
from ..core.state import AgentState
from ..interfaces.llm import ILLMGateway
from ..interfaces.search import IWebSearchService
from ..utils.intent_analyzer import IntentAnalyzer

logger = logging.getLogger(__name__)

_ROLE_MAP = {"human": "user", "ai": "assistant", "system": "system"}


from typing import Tuple

def _extract_role_content(msg: Any) -> Tuple[str, str]:
    if isinstance(msg, dict):
        return msg.get("role", ""), msg.get("content", "")
    role = getattr(msg, "type", "") or getattr(msg, "role", "")
    content = getattr(msg, "content", "")
    return _ROLE_MAP.get(role, role), content


class RouterNode:
    """Classifies the user query and routes to the appropriate pipeline path.

    - INTERNAL queries proceed to schema linking and SQL generation.
    - EXTERNAL queries are answered via web search.
    - Follow-up queries are enriched with prior conversation context.
    """

    def __init__(
        self,
        llm: ILLMGateway,
        web_search: Optional[IWebSearchService] = None,
        intent_analyzer: Optional[IntentAnalyzer] = None,
        domain: Optional[str] = None,
    ) -> None:
        self.llm = llm
        self.web_search = web_search
        self.intent_analyzer = intent_analyzer or IntentAnalyzer()
        self.domain = domain

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        user_query = _get(state, "user_query", "")
        messages = _get(state, "messages", [])

        emitter = get_emitter()
        if emitter:
            emitter.emit_step("Reading your question")

        if messages and self.intent_analyzer.is_follow_up(user_query):
            context = _last_user_message(messages)
            if context:
                user_query = f"(Following up on: {context}) {user_query}"

        if emitter:
            emitter.emit_step("Understanding the intent")
        intent = self.intent_analyzer.analyze(user_query)

        if emitter:
            emitter.emit_step("Classifying the question")
        classification = await self.llm.classify_query(user_query)
        is_external = classification.get("classification", "INTERNAL") == "EXTERNAL"

        web_search_result = None
        if is_external and self.web_search is not None:
            try:
                if emitter:
                    emitter.emit_step("Searching the web for answers")
                optimized = await self.llm.optimize_search_query(user_query, self.domain)
                result = await self.web_search.search(optimized, domain=self.domain)
                if result.get("success") and result.get("results"):
                    web_search_result = await self.llm.summarize_web_results(user_query, result)
                else:
                    web_search_result = "No relevant web results found."
            except Exception as exc:
                logger.error("Web search failed: %s", exc)
                web_search_result = f"Unable to search: {exc}"

        return {
            "intent": intent,
            "is_external": is_external,
            "web_search_result": web_search_result,
            "user_query": user_query,
            "current_node": "classify_query",
        }


def _get(state: Any, field: str, default=None):
    if isinstance(state, dict):
        return state.get(field, default)
    return getattr(state, field, default)


def _last_user_message(messages: list) -> str:
    for msg in reversed(messages):
        role, content = _extract_role_content(msg)
        if role == "user" and content:
            return content
    return ""
