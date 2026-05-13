"""Tests for the ThinkingEmitter."""

from saas_graph.core.emitter import ThinkingEmitter, get_emitter, set_emitter


def test_emitter_context_var():
    assert get_emitter() is None
    em = ThinkingEmitter()
    token = set_emitter(em)
    assert get_emitter() is em
    set_emitter(None)
    assert get_emitter() is None


def test_emitter_collects_events():
    em = ThinkingEmitter()
    em.emit_step("step 1")
    em.emit_table("users", "User table")
    em.emit_complete()
    assert len(em.events) == 3
    assert em.events[0].event_type == "thinking_step"
    assert em.events[0].data["label"] == "step 1"
    assert em.events[1].event_type == "table_pull"
    assert em.events[2].event_type == "thinking_complete"


def test_emitter_callbacks():
    em = ThinkingEmitter()
    captured = []
    em.on_event(lambda e: captured.append(e.event_type))
    em.emit_step("hello")
    em.emit_error("oops")
    assert captured == ["thinking_step", "error"]
