"""Tests for TUI behavior using Textual's async test pilot."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from textual.widgets import Input

from tinyloom.core.config import Config, ModelConfig
from tinyloom.core.types import AgentEvent, Message, ToolCall
from tinyloom.tui import TinyloomApp, MessageWidget, SpinnerWidget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(events: list[AgentEvent] | None = None):
    """Build a mock agent that yields the given events from step()."""
    agent = MagicMock()
    agent.config = Config(model=ModelConfig(model="test-model"))
    agent.state = MagicMock()
    agent.state.messages = []

    async def _step(user_input):
        for evt in (events or []):
            yield evt
            await asyncio.sleep(0)

    agent.step = _step
    agent._subagent_tui = None
    agent._tui_text_filters = []
    return agent


def _slow_agent(events: list[AgentEvent], delay: float = 0.5):
    """Build a mock agent that yields events slowly (for cancellation tests)."""
    agent = MagicMock()
    agent.config = Config(model=ModelConfig(model="test-model"))
    agent.state = MagicMock()
    agent.state.messages = []

    async def _step(user_input):
        for evt in events:
            yield evt
            await asyncio.sleep(delay)

    agent.step = _step
    agent._subagent_tui = None
    agent._tui_text_filters = []
    return agent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_input_focused_on_mount():
    agent = _make_agent()
    app = TinyloomApp(agent)
    async with app.run_test() as pilot:
        inp = app.query_one("#input", Input)
        assert inp.has_focus


@pytest.mark.asyncio
async def test_input_disabled_during_streaming():
    events = [
        AgentEvent(type="text_delta", text="hello"),
        AgentEvent(type="response_complete", message=Message(role="assistant", content="hello")),
    ]
    agent = _slow_agent(events, delay=0.2)
    app = TinyloomApp(agent)
    async with app.run_test() as pilot:
        inp = app.query_one("#input", Input)
        inp.value = "test"
        await pilot.press("enter")
        await pilot.pause()
        assert inp.disabled
        # Wait for streaming to finish
        await asyncio.sleep(0.6)
        await pilot.pause()
        assert not inp.disabled


@pytest.mark.asyncio
async def test_user_message_displayed():
    agent = _make_agent([
        AgentEvent(type="response_complete", message=Message(role="assistant", content="")),
    ])
    app = TinyloomApp(agent)
    async with app.run_test() as pilot:
        inp = app.query_one("#input", Input)
        inp.value = "hello world"
        await pilot.press("enter")
        await pilot.pause()
        widgets = app.query(MessageWidget)
        texts = [w.content for w in widgets]
        assert any("hello world" in str(t) for t in texts)


@pytest.mark.asyncio
async def test_text_deltas_streamed():
    events = [
        AgentEvent(type="text_delta", text="foo"),
        AgentEvent(type="text_delta", text="bar"),
        AgentEvent(type="response_complete", message=Message(role="assistant", content="foobar")),
    ]
    agent = _make_agent(events)
    app = TinyloomApp(agent)
    async with app.run_test() as pilot:
        inp = app.query_one("#input", Input)
        inp.value = "test"
        await pilot.press("enter")
        await pilot.pause()
        await asyncio.sleep(0.1)
        await pilot.pause()
        widgets = app.query(MessageWidget)
        texts = [str(w.content) for w in widgets]
        assert any("foobar" in t for t in texts)


@pytest.mark.asyncio
async def test_escape_stops_agent():
    events = [
        AgentEvent(type="text_delta", text="start"),
        AgentEvent(type="text_delta", text="...still going"),
        AgentEvent(type="text_delta", text="...more"),
        AgentEvent(type="response_complete", message=Message(role="assistant", content="")),
    ]
    agent = _slow_agent(events, delay=0.3)
    app = TinyloomApp(agent)
    async with app.run_test() as pilot:
        inp = app.query_one("#input", Input)
        inp.value = "go"
        await pilot.press("enter")
        await asyncio.sleep(0.2)
        await pilot.press("escape")
        await pilot.pause()
        # Input should be re-enabled after escape
        assert not inp.disabled
        widgets = app.query(MessageWidget)
        texts = [str(w.content) for w in widgets]
        assert any("Stopped" in t for t in texts)


@pytest.mark.asyncio
async def test_tool_call_displayed():
    tc = ToolCall(id="tc1", name="bash", input={"cmd": "ls"})
    events = [
        AgentEvent(type="tool_call", tool_call=tc),
        AgentEvent(type="response_complete", message=Message(role="assistant", content="")),
    ]
    agent = _make_agent(events)
    app = TinyloomApp(agent)
    async with app.run_test() as pilot:
        inp = app.query_one("#input", Input)
        inp.value = "test"
        await pilot.press("enter")
        await pilot.pause()
        await asyncio.sleep(0.1)
        await pilot.pause()
        widgets = app.query(".tool-call")
        assert len(widgets) >= 1
        assert "bash" in str(widgets[0].content)


@pytest.mark.asyncio
async def test_error_displayed():
    events = [
        AgentEvent(type="error", error="something broke"),
    ]
    agent = _make_agent(events)
    app = TinyloomApp(agent)
    async with app.run_test() as pilot:
        inp = app.query_one("#input", Input)
        inp.value = "test"
        await pilot.press("enter")
        await pilot.pause()
        await asyncio.sleep(0.1)
        await pilot.pause()
        widgets = app.query(".error")
        assert len(widgets) >= 1
        assert "something broke" in str(widgets[0].content)


@pytest.mark.asyncio
async def test_empty_input_ignored():
    agent = _make_agent()
    app = TinyloomApp(agent)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        widgets = app.query(MessageWidget)
        assert len(widgets) == 0


# ---------------------------------------------------------------------------
# Spinner tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_spinner_lifecycle():
    """_show_spinner creates a SpinnerWidget, _hide_spinner removes it."""
    agent = _make_agent()
    app = TinyloomApp(agent)
    async with app.run_test() as pilot:
        assert app._spinner is None
        app._show_spinner()
        assert app._spinner is not None
        await pilot.pause()
        spinners = app.query(SpinnerWidget)
        assert len(spinners) == 1
        # Calling show again is a no-op
        app._show_spinner()
        await pilot.pause()
        assert len(app.query(SpinnerWidget)) == 1
        # Hide cleans up
        app._hide_spinner()
        assert app._spinner is None


@pytest.mark.asyncio
async def test_spinner_removed_after_response():
    """Spinner is cleaned up once the response finishes."""
    events = [
        AgentEvent(type="text_delta", text="done"),
        AgentEvent(type="response_complete", message=Message(role="assistant", content="done")),
    ]
    agent = _make_agent(events)
    app = TinyloomApp(agent)
    async with app.run_test() as pilot:
        inp = app.query_one("#input", Input)
        inp.value = "test"
        await pilot.press("enter")
        await asyncio.sleep(0.2)
        await pilot.pause()
        spinners = app.query(SpinnerWidget)
        assert len(spinners) == 0


@pytest.mark.asyncio
async def test_spinner_removed_on_escape():
    """Spinner is cleaned up when user presses escape."""
    events = [
        AgentEvent(type="text_delta", text="start"),
        AgentEvent(type="text_delta", text="...more"),
    ]
    agent = _slow_agent(events, delay=0.5)
    app = TinyloomApp(agent)
    async with app.run_test() as pilot:
        inp = app.query_one("#input", Input)
        inp.value = "go"
        await pilot.press("enter")
        await asyncio.sleep(0.1)
        await pilot.press("escape")
        await pilot.pause()
        spinners = app.query(SpinnerWidget)
        assert len(spinners) == 0


# ---------------------------------------------------------------------------
# Subagent plugin TUI integration
# ---------------------------------------------------------------------------

def test_subagent_plugin_log_widget():
    """SubagentLogWidget (inside the plugin) tracks lines and caps at MAX_LINES."""
    from tinyloom.plugins.subagent import _make_tui_hooks
    hooks = _make_tui_hooks()
    # on_mount needs a scroll callback
    hooks["on_mount"](lambda: None)

    # Simulate a subagent tool_call to create the internal log widget
    from tinyloom.core.types import ToolCall as TC
    tc = TC(id="tc1", name="subagent", input={"task": "test"})
    mounted = []
    hooks["on_tool_call"](tc, lambda w: mounted.append(w))
    assert len(mounted) == 1
    log = mounted[0]
    # Fill past max
    for i in range(10):
        log.add_line(f"line {i}")
    assert len(log._lines) == log.MAX_LINES
    assert log._lines[-1] == "line 9"


def test_subagent_plugin_event_sink():
    """set_event_sink registers a callback that receives subagent events."""
    from tinyloom.plugins import subagent as sa

    captured = []
    sa.set_event_sink(lambda evt: captured.append(evt))
    assert sa._event_sink is not None
    sa._event_sink("fake")
    assert captured == ["fake"]
    sa.set_event_sink(None)
    assert sa._event_sink is None


@pytest.mark.asyncio
async def test_subagent_tool_call_renders():
    """A subagent tool_call shows up in the TUI as a tool-call widget."""
    tc = ToolCall(id="tc1", name="subagent", input={"task": "do stuff"})
    events = [
        AgentEvent(type="tool_call", tool_call=tc),
        AgentEvent(type="tool_result", tool_call_id="tc1", tool_name="subagent", result="done"),
        AgentEvent(type="response_complete", message=Message(role="assistant", content="")),
    ]
    agent = _make_agent(events)
    # Simulate plugin activation
    from tinyloom.plugins.subagent import _make_tui_hooks
    agent._subagent_tui = _make_tui_hooks()

    app = TinyloomApp(agent)
    async with app.run_test() as pilot:
        inp = app.query_one("#input", Input)
        inp.value = "test"
        await pilot.press("enter")
        await asyncio.sleep(0.2)
        await pilot.pause()
        widgets = app.query(".tool-call")
        assert any("subagent" in str(w.content) for w in widgets)
