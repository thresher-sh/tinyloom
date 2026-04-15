from __future__ import annotations

import logging
from typing import AsyncIterator

import anthropic

from tinyloom.core.config import ModelConfig
from tinyloom.core.types import Message, StreamEvent, ToolCall, ToolDef

log = logging.getLogger(__name__)


class AnthropicProvider:
    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        kwargs: dict = {}
        if config.api_key:
            kwargs["api_key"] = config.api_key
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self.client = anthropic.AsyncAnthropic(**kwargs)

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        system: str = "",
    ) -> AsyncIterator[StreamEvent]:
        kwargs = self._build_kwargs(messages, system)
        kwargs["max_tokens"] = self.config.max_tokens
        if tools:
            kwargs["tools"] = self._format_tools(tools)

        try:
            async with self.client.messages.stream(**kwargs) as stream:
                async for text_delta in stream.text_stream:
                    log.debug("text delta received")
                    yield StreamEvent(type="text", text=text_delta)

                final = await stream.get_final_message()

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

            done_msg = Message(
                role="assistant",
                content=assembled_text,
                tool_calls=tool_calls,
            )
            yield StreamEvent(type="done", message=done_msg)

        except anthropic.APIError as e:
            log.error("Anthropic API error: %s", e)
            yield StreamEvent(type="error", error=str(e))

    async def chat(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 8192,
    ) -> Message:
        kwargs = self._build_kwargs(messages, system)
        kwargs["max_tokens"] = max_tokens
        response = await self.client.messages.create(**kwargs)
        text = "".join(block.text for block in response.content if block.type == "text")
        return Message(role="assistant", content=text)

    async def count_tokens(
        self,
        messages: list[Message],
        system: str = "",
    ) -> int:
        kwargs: dict = {
            "model": self.config.model,
            "messages": self._format_messages(messages),
        }
        if system:
            kwargs["system"] = system
        result = await self.client.messages.count_tokens(**kwargs)
        return result.input_tokens

    def _build_kwargs(self, messages: list[Message], system: str) -> dict:
        kwargs: dict = {
            "model": self.config.model,
            "messages": self._format_messages(messages),
            "temperature": self.config.temperature,
        }
        if system:
            kwargs["system"] = system
        return kwargs

    def _format_messages(self, messages: list[Message]) -> list[dict]:
        """Translate Message list to Anthropic API format.

        Anthropic requires strictly alternating user/assistant roles.
        tool_result messages become user messages with tool_result content blocks.
        Consecutive same-role messages are merged.
        """
        raw: list[dict] = []

        for msg in messages:
            if msg.role == "tool":
                # tool result → user message with tool_result content block
                block = {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content,
                }
                raw.append({"role": "user", "content": [block]})

            elif msg.role == "assistant" and msg.tool_calls:
                content: list[dict] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.input,
                    })
                raw.append({"role": "assistant", "content": content})

            else:
                raw.append({"role": msg.role, "content": msg.content})

        # Merge consecutive same-role messages
        merged: list[dict] = []
        for entry in raw:
            if merged and merged[-1]["role"] == entry["role"]:
                prev = merged[-1]
                # Normalise both to list form before merging
                if isinstance(prev["content"], str):
                    prev["content"] = [{"type": "text", "text": prev["content"]}] if prev["content"] else []
                if isinstance(entry["content"], str):
                    entry_content: list = [{"type": "text", "text": entry["content"]}] if entry["content"] else []
                else:
                    entry_content = entry["content"]
                prev["content"].extend(entry_content)
            else:
                # Make a shallow copy so we can mutate safely later
                merged.append({"role": entry["role"], "content": entry["content"]})

        return merged

    def _format_tools(self, tools: list[ToolDef]) -> list[dict]:
        return [
            {
                "name": td.name,
                "description": td.description,
                "input_schema": td.input_schema,
            }
            for td in tools
        ]
