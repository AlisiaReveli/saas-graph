"""Tests for PostgresExecutor."""

import pytest

from saas_graph.models.sql import SQLSpec


def test_import_without_asyncpg(monkeypatch):
    """PostgresExecutor should raise a clear error if asyncpg is not installed."""
    import builtins

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "asyncpg":
            raise ImportError("No module named 'asyncpg'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    from saas_graph.contrib import postgres

    with pytest.raises(ImportError, match="saas-graph\\[postgres\\]"):
        # Force reimport by creating an instance
        import importlib

        importlib.reload(postgres)
        postgres.PostgresExecutor("postgresql://localhost/test")


def test_sql_spec_model():
    """SQLSpec should accept all fields and have sensible defaults."""
    spec = SQLSpec(sql="SELECT 1", tables_used=["test"])
    assert spec.sql == "SELECT 1"
    assert spec.tables_used == ["test"]
    assert spec.generation_attempts == 1
    assert spec.from_golden_query is False
    assert spec.parameters == {}
