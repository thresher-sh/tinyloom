"""Tests for tinyloom.core.agent — the agent loop."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tinyloom.core.agent import Agent
from tinyloom.core.config import Config, CompactionConfig
from tinyloom.core.hooks import HookRunner
from tinyloom.core.tools import Tool, ToolRegistry
from tinyloom.core.types import Message, ToolCall, StreamEvent, AgentEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(**overrides) -> Config:
    cfg = Config(compaction=CompactionConfig(enabled=False))
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _echo_tool() -> Tool:
    return Tool(
        name="echo",
        description="echoes input",
        input_schema={"type": "object", "properties": {"msg": {"type": "string"}}},
        function=lambda d: d.get("msg", ""),
    )


def _make_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.count_tokens = AsyncMock(return_value=1000)
    return provider


async def _text_stream(texts, messages=None, tools=None, system=""):
    """Yield text events then done."""
    full_text = "".join(texts)
    for t in texts:
        yield StreamEvent(type="text", text=t)
    yield StreamEvent(type="done", message=Message(role="assistant", content=full_text))


def _set_text_stream(provider, *texts):
    """Configure provider.stream to return a text stream."""
    async def stream(messages, tools, system=""):
        async for evt in _text_stream(list(texts), messages, tools, system):
            yield evt
    provider.stream = stream


def _set_tool_then_text_stream(provider, tool_calls_list, final_text):
    """First call returns tool_calls, second call returns text."""
    call_count_state = {"n": 0}

    async def stream(messages, tools, system=""):
        call_count_state["n"] += 1
        if call_count_state["n"] == 1:
            for tc in tool_calls_list:
                yield StreamEvent(type="tool_call", tool_call=tc)
            yield StreamEvent(type="done", message=Message(role="assistant", tool_calls=tool_calls_list))
        else:
            yield StreamEvent(type="text", text=final_text)
            yield StreamEvent(type="done", message=Message(role="assistant", content=final_text))

    provider.stream = stream


def _set_always_tool_stream(provider, tool_call):
    """Provider always returns the same tool call (for max_turns testing)."""
    async def stream(messages, tools, system=""):
        yield StreamEvent(type="tool_call", tool_call=tool_call)
        yield StreamEvent(type="done", message=Message(role="assistant", tool_calls=[tool_call]))
    provider.stream = stream


async def _collect_events(aiter) -> list[AgentEvent]:
    events = []
    async for evt in aiter:
        events.append(evt)
    return events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_simple_text_response():
    provider = _make_provider()
    _set_text_stream(provider, "Hello", " world!")

    agent = Agent(config=_config(), provider=provider, tools=ToolRegistry())
    events = await _collect_events(agent.run("hi"))

    types = [e.type for e in events]
    assert "agent_start" in types
    assert "text_delta" in types
    assert "response_complete" in types
    assert "agent_stop" in types

    text_deltas = [e.text for e in events if e.type == "text_delta"]
    assert "Hello" in text_deltas
    assert " world!" in text_deltas


@pytest.mark.asyncio
async def test_tool_call_and_response():
    provider = _make_provider()
    tc = ToolCall(id="tc_1", name="echo", input={"msg": "echoed!"})
    _set_tool_then_text_stream(provider, [tc], "Done")

    registry = ToolRegistry()
    registry.register(_echo_tool())

    agent = Agent(config=_config(), provider=provider, tools=registry)
    events = await _collect_events(agent.run("use echo"))

    types = [e.type for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "text_delta" in types

    tool_result_evt = next(e for e in events if e.type == "tool_result")
    assert tool_result_evt.result == "echoed!"
    assert tool_result_evt.tool_name == "echo"


@pytest.mark.asyncio
async def test_hooks_receive_events():
    provider = _make_provider()
    _set_text_stream(provider, "hello")

    hooks = HookRunner()
    received = []
    hooks.on("text_delta", lambda ctx: received.append(ctx["text"]))

    agent = Agent(config=_config(), provider=provider, tools=ToolRegistry(), hooks=hooks)
    await _collect_events(agent.run("hi"))

    assert "hello" in received


@pytest.mark.asyncio
async def test_skip_tool_via_hook():
    provider = _make_provider()
    tc = ToolCall(id="tc_1", name="echo", input={"msg": "should not run"})
    _set_tool_then_text_stream(provider, [tc], "Done")

    hooks = HookRunner()
    hooks.on("tool_call", lambda ctx: ctx.__setitem__("skip", True))

    registry = ToolRegistry()
    registry.register(_echo_tool())

    agent = Agent(config=_config(), provider=provider, tools=registry, hooks=hooks)
    events = await _collect_events(agent.run("do something"))

    # tool_call event should NOT be in events (it was skipped)
    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert len(tool_call_events) == 0

    # tool_result should indicate denial
    tool_result_evt = next(e for e in events if e.type == "tool_result")
    assert "denied" in tool_result_evt.result


@pytest.mark.asyncio
async def test_max_turns_limit():
    provider = _make_provider()
    tc = ToolCall(id="tc_1", name="echo", input={"msg": "loop"})
    _set_always_tool_stream(provider, tc)

    registry = ToolRegistry()
    registry.register(_echo_tool())

    agent = Agent(config=_config(max_turns=3), provider=provider, tools=registry)
    events = await _collect_events(agent.run("loop forever"))

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert len(tool_call_events) == 3


@pytest.mark.asyncio
async def test_step_accumulates_state():
    provider = _make_provider()
    _set_text_stream(provider, "reply")

    agent = Agent(config=_config(), provider=provider, tools=ToolRegistry())

    await _collect_events(agent.step("first"))
    await _collect_events(agent.step("second"))

    # 2 user messages + 2 assistant messages = 4
    assert len(agent.state.messages) == 4
    roles = [m.role for m in agent.state.messages]
    assert roles.count("user") == 2
    assert roles.count("assistant") == 2


@pytest.mark.asyncio
async def test_message_hooks_fire():
    provider = _make_provider()
    _set_text_stream(provider, "hi")

    hooks = HookRunner()
    user_messages = []
    hooks.on("message:user", lambda ctx: user_messages.append(ctx["message"]))

    agent = Agent(config=_config(), provider=provider, tools=ToolRegistry(), hooks=hooks)
    await _collect_events(agent.run("hello"))

    assert len(user_messages) == 1
    assert user_messages[0].content == "hello"


@pytest.mark.asyncio
async def test_error_event_stops_loop():
    provider = _make_provider()

    async def error_stream(messages, tools, system=""):
        yield StreamEvent(type="error", error="something broke")

    provider.stream = error_stream

    agent = Agent(config=_config(), provider=provider, tools=ToolRegistry())
    events = await _collect_events(agent.run("trigger error"))

    types = [e.type for e in events]
    assert "error" in types
    error_evt = next(e for e in events if e.type == "error")
    assert error_evt.error == "something broke"
    # Should not have response_complete after error
    assert "response_complete" not in types
