"""Drop-in FastAPI router with SSE streaming chat endpoints."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def create_router(pipeline: Any, prefix: str = "") -> Any:
    """Create a FastAPI ``APIRouter`` with analytics chat endpoints.

    Provides:
    - ``POST /chat/stream`` -- SSE streaming chat
    - ``POST /chat`` -- non-streaming chat
    - ``GET /chat/sessions`` -- list sessions (placeholder)

    Args:
        pipeline: An :class:`~saas_graph.NLQPipeline` instance.
        prefix: URL prefix for all routes.

    Returns:
        A ``fastapi.APIRouter``.

    Raises:
        ImportError: If ``fastapi`` or ``sse-starlette`` are not installed.
    """
    try:
        from fastapi import APIRouter, Request
        from fastapi.responses import JSONResponse
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise ImportError("pip install saas-graph[server]") from exc

    router = APIRouter(prefix=prefix)

    class ChatRequest(BaseModel):
        message: str
        session_id: Optional[str] = None
        tenant_id: str = ""

    class ChatResponse(BaseModel):
        success: bool
        response: str = ""
        sql: str = ""
        row_count: int = 0
        display_format: str = ""
        session_id: str = ""
        error: Optional[str] = None

    @router.post("/chat")
    async def chat(req: ChatRequest) -> ChatResponse:
        result = await pipeline.query(
            question=req.message,
            tenant_id=req.tenant_id,
            session_id=req.session_id,
        )
        return ChatResponse(
            success=result.success,
            response=result.response,
            sql=result.sql,
            row_count=result.row_count,
            display_format=result.display_format,
            session_id=result.session_id,
            error=result.error,
        )

    @router.post("/chat/stream")
    async def chat_stream(req: ChatRequest, request: Request) -> Any:
        try:
            from sse_starlette.sse import EventSourceResponse
        except ImportError as exc:
            raise ImportError("pip install saas-graph[server]") from exc

        async def event_generator():
            try:
                async for event in pipeline.query_stream(
                    question=req.message,
                    tenant_id=req.tenant_id,
                    session_id=req.session_id,
                ):
                    for node_name, state in event.items():
                        data = {
                            "node": node_name,
                            "current_node": getattr(state, "current_node", node_name),
                        }

                        if node_name == "format_response":
                            data["response"] = getattr(state, "formatted_response", "")
                            data["sql"] = getattr(state, "sql_spec", None)
                            if data["sql"] and hasattr(data["sql"], "sql"):
                                data["sql"] = data["sql"].sql
                            else:
                                data["sql"] = ""
                            data["row_count"] = getattr(state, "row_count", 0)
                            data["display_format"] = getattr(state, "display_format", "")
                            data["error"] = getattr(state, "error", None)

                        yield {"event": "message", "data": json.dumps(data, default=str)}
            except Exception as exc:
                logger.error("Stream error: %s", exc)
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(exc)}),
                }

        return EventSourceResponse(event_generator())

    return router
