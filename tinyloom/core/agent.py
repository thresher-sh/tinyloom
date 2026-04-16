from __future__ import annotations
from dataclasses import dataclass, field
from typing import AsyncIterator
from tinyloom.core.types import Message, ToolCall, AgentEvent, TokenUsage
from tinyloom.core.config import Config
from tinyloom.core.hooks import HookRunner
from tinyloom.core.tools import ToolRegistry, get_builtin_tools
from tinyloom.core.compact import maybe_compact
from tinyloom.providers import create_provider
from tinyloom.providers.base import LLMProvider

@dataclass
class AgentState:
    messages: list[Message] = field(default_factory=list)
    turn: int = 0
    cumulative_usage: TokenUsage = field(default_factory=TokenUsage)

class Agent:
    def __init__(
        self,
        config: Config,
        provider: LLMProvider | None = None,
        tools: ToolRegistry | None = None,
        hooks: HookRunner | None = None,
    ):
        self.config = config
        self.hooks = hooks or HookRunner()
        self.state = AgentState()
        self.tools = tools if tools is not None else ToolRegistry(get_builtin_tools())
        self.provider = provider if provider is not None else create_provider(config.model)

    async def run(self, prompt: str) -> AsyncIterator[AgentEvent]:
        """Single-shot: one prompt, run to completion. Clears existing state."""
        self.state = AgentState()
        await self._add_message(Message(role="user", content=prompt))
        async for evt in self._emit("agent_start"): yield evt
        async for evt in self._loop(): yield evt
        async for evt in self._emit("agent_stop", cumulative_usage=self.state.cumulative_usage): yield evt

    async def step(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Interactive: one user message, run until response. Accumulates state."""
        await self._add_message(Message(role="user", content=user_input))
        self.state.turn = 0
        async for evt in self._loop(): yield evt

    async def _loop(self) -> AsyncIterator[AgentEvent]:
        while self.state.turn < self.config.max_turns:
            skipped_tool_ids: set[str] = set()

            if self.config.compaction.enabled:
                compacted = await maybe_compact(self.provider, self.state.messages, self.config)
                if compacted is not None:
                    self.state.messages = compacted
                    async for evt in self._emit("compaction"): yield evt

            self.state.turn += 1
            assistant_msg = Message(role="assistant")
            tool_calls: list[ToolCall] = []
            tool_defs = self.tools.all_defs()
            turn_usage: TokenUsage | None = None

            async for stream_evt in self.provider.stream(
                messages=self.state.messages,
                tools=tool_defs,
                system=self.config.get_system_prompt([t.name for t in tool_defs]),
            ):
                if stream_evt.type == "text":
                    evt = AgentEvent(type="text_delta", text=stream_evt.text)
                    ctx = {"type": "text_delta", "text": stream_evt.text}
                    await self.hooks.emit("text_delta", ctx)
                    if not ctx.get("skip"): yield evt

                elif stream_evt.type == "tool_call":
                    tc = stream_evt.tool_call
                    tool_calls.append(tc)
                    evt = AgentEvent(type="tool_call", tool_call=tc)
                    ctx = {"type": "tool_call", "tool_name": tc.name, "tool_call": tc}
                    await self.hooks.emit("tool_call", ctx)
                    if ctx.get("skip"):
                        skipped_tool_ids.add(tc.id)
                    else:
                        yield evt

                elif stream_evt.type == "done":
                    assistant_msg = stream_evt.message
                    turn_usage = stream_evt.usage
                    if turn_usage is not None: self.state.cumulative_usage = self.state.cumulative_usage + turn_usage

                elif stream_evt.type == "error":
                    evt = AgentEvent(type="error", error=stream_evt.error)
                    await self.hooks.emit("error", {"type": "error", "error": stream_evt.error})
                    yield evt
                    return

            await self._add_message(assistant_msg)

            if tool_calls:
                for tc in tool_calls:
                    if tc.id in skipped_tool_ids:
                        result = f"Tool '{tc.name}' was denied by hook"
                    else:
                        result = await self.tools.execute(tc.name, tc.input)

                    yield AgentEvent(type="tool_result", tool_call_id=tc.id, tool_name=tc.name, result=result)
                    await self._add_message(Message(role="tool_result", content=result, tool_call_id=tc.id, name=tc.name))

                continue  # Go back to LLM with tool results

            async for evt in self._emit("response_complete", message=assistant_msg, usage=turn_usage, cumulative_usage=self.state.cumulative_usage): yield evt
            return

    async def _emit(self, event_type: str, **kw) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(type=event_type, **kw)
        await self.hooks.emit(event_type, {"type": event_type, **kw})

    async def _add_message(self, msg: Message):
        self.state.messages.append(msg)
        await self.hooks.emit(f"message:{msg.role}", {"type": f"message:{msg.role}", "message": msg})
