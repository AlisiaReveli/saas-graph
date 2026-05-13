from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..models.schema import SchemaContext


class ISchemaContextLoader(ABC):
    """Interface for loading tenant-specific schema context.

    Implementations may read from YAML files, database tables,
    or auto-discover schema from the database itself.
    """

    @abstractmethod
    async def get_context(
        self,
        tenant_id: str = "",
        access_policy: Optional[Any] = None,
    ) -> SchemaContext:
        """Load the full schema context for a tenant.

        Returns a :class:`SchemaContext` containing tables, columns,
        joins, filters, business rules, and aliases.
        """
        ...

    async def refresh(self, tenant_id: str = "") -> None:
        """Force-refresh cached schema context for a tenant."""
        pass
