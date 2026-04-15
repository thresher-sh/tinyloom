from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, TYPE_CHECKING

from tinyloom.core.types import Message, ToolCall, AgentEvent, StreamEvent
from tinyloom.core.config import Config
from tinyloom.core.hooks import HookRunner
from tinyloom.core.tools import ToolRegistry, get_builtin_tools
from tinyloom.core.compact import maybe_compact

if TYPE_CHECKING:
    from tinyloom.providers.base import LLMProvider


@dataclass
class AgentState:
    messages: list[Message] = field(default_factory=list)
    turn: int = 0


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

        if tools is not None:
            self.tools = tools
        else:
            self.tools = ToolRegistry()
            for t in get_builtin_tools():
                self.tools.register(t)

        if provider is not None:
            self.provider = provider
        else:
            from tinyloom.providers import create_provider
            self.provider = create_provider(config.model)

    async def run(self, prompt: str) -> AsyncIterator[AgentEvent]:
        """Single-shot: one prompt, run to completion. Clears existing state."""
        self.state = AgentState()
        await self._add_message(Message(role="user", content=prompt))

        yield AgentEvent(type="agent_start")
        await self.hooks.emit("agent_start", {"type": "agent_start"})

        async for evt in self._loop():
            yield evt

        yield AgentEvent(type="agent_stop")
        await self.hooks.emit("agent_stop", {"type": "agent_stop"})

    async def step(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Interactive: one user message, run until response. Accumulates state."""
        await self._add_message(Message(role="user", content=user_input))
        self.state.turn = 0

        async for evt in self._loop():
            yield evt

    async def _loop(self) -> AsyncIterator[AgentEvent]:
        while self.state.turn < self.config.max_turns:
            skipped_tool_ids: set[str] = set()

            # Compaction check
            if self.config.compaction.enabled:
                compacted = await maybe_compact(
                    self.provider,
                    self.state.messages,
                    self.config.model.context_window,
                    self.config.compaction.threshold,
                    self.config.compaction.strategy,
                )
                if compacted is not None:
                    self.state.messages = compacted
                    evt = AgentEvent(type="compaction")
                    await self.hooks.emit("compaction", {"type": "compaction"})
                    yield evt

            # LLM call
            self.state.turn += 1
            assistant_msg = Message(role="assistant")
            tool_calls: list[ToolCall] = []

            async for stream_evt in self.provider.stream(
                messages=self.state.messages,
                tools=self.tools.all_defs(),
                system=self.config.system_prompt,
            ):
                if stream_evt.type == "text":
                    evt = AgentEvent(type="text_delta", text=stream_evt.text)
                    ctx = {"type": "text_delta", "text": stream_evt.text}
                    await self.hooks.emit("text_delta", ctx)
                    if not ctx.get("skip"):
                        yield evt

                elif stream_evt.type == "tool_call":
                    tool_calls.append(stream_evt.tool_call)
                    evt = AgentEvent(type="tool_call", tool_call=stream_evt.tool_call)
                    ctx = {
                        "type": "tool_call",
                        "tool_name": stream_evt.tool_call.name,
                        "tool_call": stream_evt.tool_call,
                    }
                    await self.hooks.emit("tool_call", ctx)
                    if ctx.get("skip"):
                        skipped_tool_ids.add(stream_evt.tool_call.id)
                    else:
                        yield evt

                elif stream_evt.type == "done":
                    assistant_msg = stream_evt.message

                elif stream_evt.type == "error":
                    evt = AgentEvent(type="error", error=stream_evt.error)
                    await self.hooks.emit("error", {"type": "error", "error": stream_evt.error})
                    yield evt
                    return

            await self._add_message(assistant_msg)

            # Tool execution
            if tool_calls:
                for tc in tool_calls:
                    if tc.id in skipped_tool_ids:
                        result = f"Tool '{tc.name}' was denied by hook"
                    else:
                        result = await self.tools.execute(tc.name, tc.input)

                    evt = AgentEvent(
                        type="tool_result",
                        tool_call_id=tc.id,
                        tool_name=tc.name,
                        result=result,
                    )
                    yield evt

                    await self._add_message(Message(
                        role="tool_result",
                        content=result,
                        tool_call_id=tc.id,
                        name=tc.name,
                    ))

                continue  # Go back to LLM with tool results

            # No tool calls: response complete
            evt = AgentEvent(type="response_complete", message=assistant_msg)
            await self.hooks.emit("response_complete", {
                "type": "response_complete",
                "message": assistant_msg,
            })
            yield evt
            return

    async def _add_message(self, msg: Message):
        self.state.messages.append(msg)
        await self.hooks.emit(f"message:{msg.role}", {
            "type": f"message:{msg.role}",
            "message": msg,
        })
