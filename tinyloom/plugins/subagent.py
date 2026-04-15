"""Subagent plugin — registers the 'subagent' tool and TUI live-log widgets."""
from __future__ import annotations
import random
from typing import TYPE_CHECKING, Callable
from tinyloom.core.tools import Tool, ToolRegistry, get_builtin_tools

if TYPE_CHECKING:
    from tinyloom.core.agent import Agent

_event_sink: Callable | None = None

def set_event_sink(sink: Callable | None):
    global _event_sink
    _event_sink = sink

def _make_tool(parent_config):
    async def subagent_fn(inp: dict) -> str:
        from tinyloom.core.agent import Agent
        from tinyloom.core.hooks import HookRunner
        from copy import deepcopy

        config = deepcopy(parent_config)
        if inp.get("model"): config.model.model = inp["model"]
        if inp.get("system_prompt"): config.system_prompt = inp["system_prompt"]

        sub_agent = Agent(config=config, tools=ToolRegistry(get_builtin_tools()), hooks=HookRunner())

        parts = []
        async for evt in sub_agent.run(inp["task"]):
            if _event_sink is not None: _event_sink(evt)
            if evt.type == "text_delta": parts.append(evt.text)
        return "".join(parts)

    return Tool(
        name="subagent",
        description="Launch a sub-agent to handle a specific task. The sub-agent gets its own context and all tools except subagent. Use to delegate focused tasks like: 'write tests for X', 'refactor this file'. Returns the sub-agent's final text response.",
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

def _make_tui_hooks():
    from textual.widgets import Static

    class SubagentLogWidget(Static):
        MAX_LINES = 5
        def __init__(self):
            super().__init__("")
            self._lines: list[str] = []
            self._generating = False
        def add_line(self, line: str):
            self._lines.append(line)
            if len(self._lines) > self.MAX_LINES: self._lines = self._lines[-self.MAX_LINES:]
            self.update("\n".join(f"    [dim]{l}[/dim]" for l in self._lines))

    log_widget: SubagentLogWidget | None = None
    scroll_fn: Callable | None = None

    def _on_subagent_event(evt):
        nonlocal log_widget
        if log_widget is None: return
        if evt.type == "tool_call" and evt.tool_call:
            log_widget._generating = False
            log_widget.add_line(f"> {evt.tool_call.name}({str(evt.tool_call.input)[:60]})")
        elif evt.type == "tool_result":
            log_widget._generating = False
            log_widget.add_line(f"<- {(evt.result or '')[:60]}")
        elif evt.type == "text_delta" and not log_widget._generating:
            log_widget._generating = True
            log_widget.add_line("generating response...")
        if scroll_fn: scroll_fn()

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
        if evt.tool_name == "subagent": log_widget = None

    def on_stop():
        nonlocal log_widget
        log_widget = None

    return {"on_mount": on_mount, "on_tool_call": on_tool_call, "on_tool_result": on_tool_result, "on_stop": on_stop}

def activate(agent: Agent):
    agent.tools.register(_make_tool(agent.config))
    agent._subagent_tui = _make_tui_hooks()
