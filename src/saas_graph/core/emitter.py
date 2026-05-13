"""Context-variable based event emitter for streaming thinking steps to clients.

Usage::

    from saas_graph.core import set_emitter, get_emitter, ThinkingEmitter

    emitter = ThinkingEmitter()
    set_emitter(emitter)

    # Inside any node:
    em = get_emitter()
    if em:
        em.emit_step("Finding relevant tables")
"""

from __future__ import annotations

import contextvars
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_emitter_var: contextvars.ContextVar[Optional["ThinkingEmitter"]] = contextvars.ContextVar(
    "saas_graph_emitter", default=None
)


def get_emitter() -> Optional[ThinkingEmitter]:
    """Get the current thinking emitter from context."""
    return _emitter_var.get()


def set_emitter(emitter: Optional[ThinkingEmitter]) -> contextvars.Token:
    """Set the thinking emitter in the current context."""
    return _emitter_var.set(emitter)


@dataclass
class ThinkingEvent:
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)


class ThinkingEmitter:
    """Collects and broadcasts pipeline progress events.

    Register callbacks to stream events to SSE clients, WebSockets, or logs.
    """

    def __init__(self) -> None:
        self._events: List[ThinkingEvent] = []
        self._callbacks: List[Callable[[ThinkingEvent], Any]] = []

    def on_event(self, callback: Callable[[ThinkingEvent], Any]) -> None:
        """Register a callback invoked for every emitted event."""
        self._callbacks.append(callback)

    @property
    def events(self) -> List[ThinkingEvent]:
        return list(self._events)

    def _emit(self, event: ThinkingEvent) -> None:
        self._events.append(event)
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception:
                logger.debug("Emitter callback error", exc_info=True)

    def emit_step(self, label: str) -> None:
        """Emit a human-readable progress step."""
        self._emit(ThinkingEvent(event_type="thinking_step", data={"label": label}))

    def emit_table(self, table_name: str, description: str = "") -> None:
        self._emit(
            ThinkingEvent(
                event_type="table_pull",
                data={"table": table_name, "description": description},
            )
        )

    def emit_column(self, table_name: str, column_name: str) -> None:
        self._emit(
            ThinkingEvent(
                event_type="column_pull",
                data={"table": table_name, "column": column_name},
            )
        )

    def emit_join(self, from_table: str, to_table: str, join_type: str = "LEFT") -> None:
        self._emit(
            ThinkingEvent(
                event_type="join_info",
                data={"from": from_table, "to": to_table, "type": join_type},
            )
        )

    def emit_filter(self, description: str, filter_type: str = "general") -> None:
        self._emit(
            ThinkingEvent(
                event_type="filter_info",
                data={"description": description, "type": filter_type},
            )
        )

    def emit_error(self, message: str) -> None:
        self._emit(ThinkingEvent(event_type="error", data={"message": message}))

    def emit_complete(self) -> None:
        self._emit(ThinkingEvent(event_type="thinking_complete", data={}))
