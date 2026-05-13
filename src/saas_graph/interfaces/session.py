from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..models.conversation import MessageRole, Session


class ISessionStore(ABC):
    """Interface for conversation session persistence."""

    @abstractmethod
    async def get_or_create(self, session_id: str, tenant_id: str = "") -> Session:
        """Get an existing session or create a new one."""
        ...

    @abstractmethod
    async def add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        metadata: Optional[dict] = None,
        tenant_id: str = "",
    ) -> Optional[int]:
        """Append a message to a session. Returns turn number when available."""
        ...

    @abstractmethod
    async def save(self, session: Session) -> None:
        """Persist session state."""
        ...

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID. Returns ``None`` if not found."""
        return None
