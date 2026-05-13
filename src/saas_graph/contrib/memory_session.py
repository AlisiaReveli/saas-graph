"""In-memory session store for development and testing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from ..interfaces.session import ISessionStore
from ..models.conversation import Message, MessageRole, Session


class InMemorySessionStore(ISessionStore):

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}

    async def get_or_create(self, session_id: str, tenant_id: str = "") -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id=session_id, tenant_id=tenant_id)
        return self._sessions[session_id]

    async def add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        metadata: Optional[dict] = None,
        tenant_id: str = "",
    ) -> Optional[int]:
        session = await self.get_or_create(session_id, tenant_id)
        msg = Message(role=role, content=content, metadata=metadata or {})
        session.messages.append(msg)
        session.updated_at = datetime.now(timezone.utc)
        return len(session.messages)

    async def save(self, session: Session) -> None:
        self._sessions[session.session_id] = session

    async def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)
