"""Tests for in-memory cache and session stores."""

import asyncio

import pytest

from saas_graph.contrib.memory import InMemoryCache
from saas_graph.contrib.memory_session import InMemorySessionStore
from saas_graph.models.conversation import MessageRole


@pytest.mark.asyncio
async def test_cache_get_set():
    cache = InMemoryCache()
    await cache.set("k1", {"data": [1, 2, 3]})
    val = await cache.get("k1")
    assert val == {"data": [1, 2, 3]}


@pytest.mark.asyncio
async def test_cache_miss():
    cache = InMemoryCache()
    assert await cache.get("nonexistent") is None


@pytest.mark.asyncio
async def test_cache_build_key():
    cache = InMemoryCache()
    assert cache.build_key("query", "tenant1", "abc123") == "query:tenant1:abc123"


@pytest.mark.asyncio
async def test_session_store():
    store = InMemorySessionStore()
    session = await store.get_or_create("s1", "t1")
    assert session.session_id == "s1"
    assert len(session.messages) == 0

    turn = await store.add_message("s1", MessageRole.USER, "hello")
    assert turn == 1

    session = await store.get_or_create("s1", "t1")
    assert len(session.messages) == 1
    assert session.messages[0].content == "hello"
