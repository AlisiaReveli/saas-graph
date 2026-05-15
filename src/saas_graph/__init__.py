"""saas-graph: AI analytics assistant framework.

Connect your database. Get an AI analyst. Ship in a day.
"""

from .models.config import DatabaseType, DomainConfig, NodeConfig
from .pipeline import NLQPipeline, QueryResult

__version__ = "0.1.0"

__all__ = [
    "DatabaseType",
    "DomainConfig",
    "NLQPipeline",
    "NodeConfig",
    "QueryResult",
    "__version__",
]
