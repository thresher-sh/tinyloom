from __future__ import annotations
import asyncio, logging
from typing import AsyncIterator
import anthropic
from tinyloom.core.config import ModelConfig
from tinyloom.core.types import Message, StreamEvent, ToolCall, ToolDef, TokenUsage
from tinyloom.providers.base import client_kwargs, drain_sync_queue

log = logging.getLogger(__name__)

def _extract_anthropic_usage(usage) -> TokenUsage | None:
    if usage is None: return None
    return TokenUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=getattr(usage, 'cache_read_input_tokens', 0) or 0,
        cache_write_tokens=getattr(usage, 'cache_creation_input_tokens', 0) or 0,
    )

class AnthropicProvider:
    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        kw = client_kwargs(config)
        self.client = anthropic.AsyncAnthropic(**kw)
        if config.sync_http: self.sync_client = anthropic.Anthropic(**kw)

    async def stream(self, messages: list[Message], tools: list[ToolDef], system: str = "") -> AsyncIterator[StreamEvent]:
        kwargs = self._build_kwargs(messages, system)
        kwargs["max_tokens"] = self.config.max_tokens
        if tools: kwargs["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools]

        try:
            final = None
            async for tag, value in self._iter_stream(kwargs):
                if tag == "text":
                    log.debug("text delta received")
                    yield StreamEvent(type="text", text=value)
                elif tag == "final":
                    final = value

            assembled_text = ""
            tool_calls: list[ToolCall] = []
            for block in final.content:
                if block.type == "text":
                    assembled_text += block.text
                elif block.type == "tool_use":
                    tc = ToolCall(id=block.id, name=block.name, input=block.input)
                    tool_calls.append(tc)
                    log.debug("tool_call received: %s", block.name)
                    yield StreamEvent(type="tool_call", tool_call=tc)

            usage = _extract_anthropic_usage(final.usage if final is not None else None)
            yield StreamEvent(type="done", message=Message(role="assistant", content=assembled_text, tool_calls=tool_calls), usage=usage)
        except anthropic.APIError as e:
            log.error("Anthropic API error: %s", e)
            yield StreamEvent(type="error", error=str(e))

    async def _iter_stream(self, kwargs: dict) -> AsyncIterator[tuple]:
        if self.config.sync_http:
            def _sync(q):
                with self.sync_client.messages.stream(**kwargs) as s:
                    for t in s.text_stream: q.put_nowait(("text", t))
                    q.put_nowait(("final", s.get_final_message()))
            async for item in drain_sync_queue(_sync): yield item
        else:
            async with self.client.messages.stream(**kwargs) as s:
                async for t in s.text_stream: yield ("text", t)
                yield ("final", await s.get_final_message())

    async def chat(self, messages: list[Message], system: str = "", max_tokens: int = 8192) -> Message:
        kwargs = self._build_kwargs(messages, system)
        kwargs["max_tokens"] = max_tokens
        response = await asyncio.to_thread(self.sync_client.messages.create, **kwargs) if self.config.sync_http else await self.client.messages.create(**kwargs)
        return Message(role="assistant", content="".join(block.text for block in response.content if block.type == "text"))

    async def count_tokens(self, messages: list[Message], system: str = "") -> int:
        count_kwargs: dict = {"model": self.config.model, "messages": self._format_messages(messages)}
        if system: count_kwargs["system"] = system
        result = await asyncio.to_thread(self.sync_client.messages.count_tokens, **count_kwargs) if self.config.sync_http else await self.client.messages.count_tokens(**count_kwargs)
        return result.input_tokens

    def _build_kwargs(self, messages: list[Message], system: str) -> dict:
        thinking_enabled = self.config.thinking or self.config.reasoning_effort is not None
        kwargs: dict = {"model": self.config.model, "messages": self._format_messages(messages)}
        if not thinking_enabled: kwargs["temperature"] = self.config.temperature
        if system: kwargs["system"] = system
        if thinking_enabled: kwargs["thinking"] = {"type": "adaptive"}
        if self.config.reasoning_effort: kwargs["output_config"] = {"effort": self.config.reasoning_effort}
        return kwargs

    def _format_messages(self, messages: list[Message]) -> list[dict]:
        """Translate to Anthropic format. Merges consecutive same-role messages."""
        def _as_list(content):
            if isinstance(content, str): return [{"type": "text", "text": content}] if content else []
            return content

        raw: list[dict] = []
        for msg in messages:
            if msg.role == "tool":
                raw.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": msg.tool_call_id, "content": msg.content}]})
            elif msg.role == "assistant" and msg.tool_calls:
                content = ([{"type": "text", "text": msg.content}] if msg.content else []) + [{"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input} for tc in msg.tool_calls]
                raw.append({"role": "assistant", "content": content})
            else:
                raw.append({"role": msg.role, "content": msg.content})

        merged: list[dict] = []
        for entry in raw:
            if merged and merged[-1]["role"] == entry["role"]:
                prev = merged[-1]
                prev["content"] = _as_list(prev["content"])
                prev["content"].extend(_as_list(entry["content"]))
            else:
                merged.append({"role": entry["role"], "content": entry["content"]})
        return merged
