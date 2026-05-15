"""MongoDB query executor using motor (async driver)."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

from ..interfaces.executor import IQueryExecutor
from ..models.sql import ExecutionResult, QueryMetadata, SQLSpec


class MongoDBExecutor(IQueryExecutor):
    """Execute aggregation pipelines against a MongoDB database via motor.

    The *sql_spec.sql* field is expected to contain a JSON string with
    ``collection`` and ``pipeline`` keys::

        {
            "collection": "patients",
            "pipeline": [{"$match": {"status": "active"}}, {"$limit": 100}]
        }

    Args:
        connection_uri: MongoDB connection string (e.g. ``mongodb://localhost:27017``).
        database: Database name to query against.
        max_pool_size: Maximum connection pool size.
    """

    def __init__(
        self,
        connection_uri: str,
        database: str,
        *,
        max_pool_size: int = 10,
    ) -> None:
        try:
            import motor.motor_asyncio  # noqa: F401

            del motor  # only checking availability
        except ImportError as exc:
            raise ImportError("pip install saas-graph[mongodb]") from exc

        self._connection_uri = connection_uri
        self._database_name = database
        self._max_pool_size = max_pool_size
        self._client = None

    def _get_client(self):
        from motor.motor_asyncio import AsyncIOMotorClient

        if self._client is None:
            self._client = AsyncIOMotorClient(
                self._connection_uri,
                maxPoolSize=self._max_pool_size,
            )
        return self._client

    async def execute(
        self,
        sql_spec: SQLSpec,
        tenant_id: str = "",
        timeout_seconds: float = 30.0,
        access_policy: Optional[Any] = None,
    ) -> ExecutionResult:
        start = time.perf_counter()

        def _elapsed() -> float:
            return (time.perf_counter() - start) * 1000

        try:
            query_def = json.loads(sql_spec.sql)
        except (json.JSONDecodeError, TypeError) as exc:
            return ExecutionResult(
                success=False,
                error_message=f"Invalid MongoDB query JSON: {exc}",
                sql_executed=sql_spec.sql,
                metadata=QueryMetadata(
                    execution_time_ms=_elapsed(),
                    executed_at=datetime.now(timezone.utc),
                ),
            )

        collection_name = query_def.get("collection", "")
        pipeline = query_def.get("pipeline", [])

        if not collection_name:
            return ExecutionResult(
                success=False,
                error_message="Missing 'collection' in query definition",
                sql_executed=sql_spec.sql,
                metadata=QueryMetadata(
                    execution_time_ms=_elapsed(),
                    executed_at=datetime.now(timezone.utc),
                ),
            )

        try:
            client = self._get_client()
            db = client[self._database_name]
            collection = db[collection_name]

            pipeline = _coerce_dates(pipeline)

            if pipeline:
                cursor = collection.aggregate(pipeline)
            else:
                cursor = collection.find({})

            data = []
            async for doc in cursor:
                row = _serialize_doc(doc)
                data.append(row)

            columns = list(data[0].keys()) if data else []

            return ExecutionResult(
                success=True,
                data=data,
                columns=columns,
                sql_executed=sql_spec.sql,
                metadata=QueryMetadata(
                    execution_time_ms=_elapsed(),
                    rows_returned=len(data),
                    executed_at=datetime.now(timezone.utc),
                ),
            )

        except Exception as exc:
            return ExecutionResult(
                success=False,
                error_message=str(exc),
                sql_executed=sql_spec.sql,
                metadata=QueryMetadata(
                    execution_time_ms=_elapsed(),
                    executed_at=datetime.now(timezone.utc),
                ),
            )

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


_ISO_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})$"
)


def _coerce_dates(obj: Any) -> Any:
    """Recursively convert ISO-8601 date strings to datetime objects.

    MongoDB compares BSON types strictly — a string ``"2026-04-01T00:00:00Z"``
    will never match a stored Date.  This function walks the pipeline and
    converts any value that looks like an ISO timestamp into a real
    ``datetime``, so motor sends it as a BSON Date.
    """
    if isinstance(obj, str) and _ISO_RE.match(obj):
        try:
            s = obj.replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        except ValueError:
            return obj
    if isinstance(obj, dict):
        return {k: _coerce_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_dates(item) for item in obj]
    return obj


def _serialize_doc(doc: dict) -> dict:
    """Convert MongoDB-specific types (ObjectId, datetime, etc.) to JSON-safe values."""
    from bson import ObjectId

    out = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            out[key] = str(value)
        elif isinstance(value, datetime):
            out[key] = value.isoformat()
        elif isinstance(value, dict):
            out[key] = _serialize_doc(value)
        elif isinstance(value, list):
            out[key] = [_serialize_item(v) for v in value]
        else:
            out[key] = value
    return out


def _serialize_item(value: Any) -> Any:
    from bson import ObjectId

    if isinstance(value, dict):
        return _serialize_doc(value)
    if isinstance(value, ObjectId):
        return str(value)
    return value
