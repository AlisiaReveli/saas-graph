"""saas-graph: AI analytics assistant framework.

Connect your database. Get an AI analyst. Ship in a day.
"""

from .models.config import DomainConfig, NodeConfig
from .pipeline import NLQPipeline, QueryResult

__version__ = "0.1.0"

__all__ = [
    "DomainConfig",
    "NLQPipeline",
    "NodeConfig",
    "QueryResult",
    "__version__",
]
