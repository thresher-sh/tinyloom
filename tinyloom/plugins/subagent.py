"""Subagent plugin — registers the 'subagent' tool and TUI live-log widgets."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Callable

from tinyloom.core.tools import Tool, ToolRegistry, get_builtin_tools

if TYPE_CHECKING:
    from tinyloom.core.agent import Agent

# ---------------------------------------------------------------------------
# Event sink — allows the TUI (or any consumer) to observe subagent events
# ---------------------------------------------------------------------------

_event_sink: Callable | None = None


def set_event_sink(sink: Callable | None):
    """Register a callback to receive live events from running subagents."""
    global _event_sink
    _event_sink = sink


# ---------------------------------------------------------------------------
# Subagent tool
# ---------------------------------------------------------------------------

def _make_tool(parent_config):
    """Create the subagent tool with the parent's config for defaults."""

    async def subagent_fn(inp: dict) -> str:
        from tinyloom.core.agent import Agent
        from tinyloom.core.hooks import HookRunner
        from copy import deepcopy

        config = deepcopy(parent_config)
        if inp.get("model"):
            config.model.model = inp["model"]
        if inp.get("system_prompt"):
            config.system_prompt = inp["system_prompt"]

        sub_registry = ToolRegistry()
        for t in get_builtin_tools():  # excludes subagent
            sub_registry.register(t)

        sub_agent = Agent(config=config, tools=sub_registry, hooks=HookRunner())

        parts = []
        async for evt in sub_agent.run(inp["task"]):
            if _event_sink is not None:
                _event_sink(evt)
            if evt.type == "text_delta":
                parts.append(evt.text)
        return "".join(parts)

    return Tool(
        name="subagent",
        description=(
            "Launch a sub-agent to handle a specific task. "
            "The sub-agent gets its own context and all tools except subagent. "
            "Use to delegate focused tasks like: 'write tests for X', 'refactor this file'. "
            "Returns the sub-agent's final text response."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "The task/prompt for the sub-agent"},
                "model": {"type": "string", "description": "Override model (optional)", "default": ""},
                "system_prompt": {"type": "string", "description": "Override system prompt (optional)", "default": ""},
            },
            "required": ["task"],
        },
        function=subagent_fn,
    )


# ---------------------------------------------------------------------------
# TUI integration — widgets + event handler injected into the app
# ---------------------------------------------------------------------------

SPINNER_FRAMES = ["|", "/", "-", "\\"]
THINKING_VERBS = [
    "thinking", "pondering", "reasoning", "analyzing",
    "processing", "considering", "evaluating", "computing",
    "deliberating", "contemplating", "synthesizing", "cogitating",
    "ruminating", "musing", "reflecting", "deducing",
]


def _make_tui_hooks():
    """Build TUI hook callbacks and the widgets they manage.

    Returns a dict that the TUI reads during tool_call / tool_result events:
        on_mount    — called when the TUI app mounts (sets up event sink)
        on_tool_call(tc, mount_widget) — called on every tool_call event
        on_tool_result(evt, mount_widget) — called on every tool_result event
        on_stop     — cleanup on cancel / escape
    """
    from textual.widgets import Static

    class SubagentLogWidget(Static):
        """Rolling log showing the last few events from a running subagent."""
        MAX_LINES = 5

        def __init__(self):
            super().__init__("")
            self._lines: list[str] = []
            self._generating = False

        def add_line(self, line: str):
            self._lines.append(line)
            if len(self._lines) > self.MAX_LINES:
                self._lines = self._lines[-self.MAX_LINES:]
            self._render_lines()

        def _render_lines(self):
            text = "\n".join(f"    [dim]{line}[/dim]" for line in self._lines)
            self.update(text)

    log_widget: SubagentLogWidget | None = None
    scroll_fn: Callable | None = None

    def _on_subagent_event(evt):
        nonlocal log_widget
        if log_widget is None:
            return
        if evt.type == "tool_call" and evt.tool_call:
            log_widget._generating = False
            preview = str(evt.tool_call.input)[:60]
            log_widget.add_line(f"> {evt.tool_call.name}({preview})")
        elif evt.type == "tool_result":
            log_widget._generating = False
            preview = (evt.result or "")[:60]
            log_widget.add_line(f"<- {preview}")
        elif evt.type == "text_delta" and not log_widget._generating:
            log_widget._generating = True
            log_widget.add_line("generating response...")
        if scroll_fn:
            scroll_fn()

    def on_mount(scroll_end_fn):
        nonlocal scroll_fn
        scroll_fn = scroll_end_fn
        set_event_sink(_on_subagent_event)

    def on_tool_call(tc, mount_widget):
        nonlocal log_widget
        if tc.name == "subagent":
            log_widget = SubagentLogWidget()
            mount_widget(log_widget)

    def on_tool_result(evt, _mount_widget):
        nonlocal log_widget
        if evt.tool_name == "subagent":
            log_widget = None

    def on_stop():
        nonlocal log_widget
        log_widget = None

    return {
        "on_mount": on_mount,
        "on_tool_call": on_tool_call,
        "on_tool_result": on_tool_result,
        "on_stop": on_stop,
    }


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------

def activate(agent: Agent):
    agent.tools.register(_make_tool(agent.config))
    agent._subagent_tui = _make_tui_hooks()
