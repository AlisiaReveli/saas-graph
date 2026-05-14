"""Tests for TavilySearchService."""

import pytest


def test_import_without_tavily(monkeypatch):
    """TavilySearchService should raise a clear error if tavily is not installed."""
    import builtins

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "tavily":
            raise ImportError("No module named 'tavily'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    from saas_graph.contrib import tavily

    with pytest.raises(ImportError, match="saas-graph\\[tavily\\]"):
        import importlib

        importlib.reload(tavily)
        tavily.TavilySearchService(api_key="test-key")
