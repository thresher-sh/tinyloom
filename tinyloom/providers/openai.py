from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

import openai

from tinyloom.core.config import ModelConfig
from tinyloom.core.types import Message, StreamEvent, ToolCall, ToolDef

log = logging.getLogger(__name__)


class OpenAIProvider:
    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        kwargs: dict = {}
        if config.api_key:
            kwargs["api_key"] = config.api_key
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self.client = openai.AsyncOpenAI(**kwargs)
        if config.sync_http:
            self.sync_client = openai.OpenAI(**kwargs)

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        system: str = "",
    ) -> AsyncIterator[StreamEvent]:
        kwargs = self._build_kwargs(messages, system)
        kwargs["stream"] = True
        if tools:
            kwargs["tools"] = self._format_tools(tools)

        try:
            tool_chunks: dict[int, dict] = {}
            assembled_text = ""

            async for chunk in self._iter_chunks(kwargs):
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                if delta.content:
                    log.debug("text delta received")
                    assembled_text += delta.content
                    yield StreamEvent(type="text", text=delta.content)

                if delta.tool_calls:
                    for tc_chunk in delta.tool_calls:
                        idx = tc_chunk.index
                        if idx not in tool_chunks:
                            tool_chunks[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc_chunk.id:
                            tool_chunks[idx]["id"] = tc_chunk.id
                        if tc_chunk.function and tc_chunk.function.name:
                            tool_chunks[idx]["name"] = tc_chunk.function.name
                        if tc_chunk.function and tc_chunk.function.arguments:
                            tool_chunks[idx]["arguments"] += tc_chunk.function.arguments

            tool_calls: list[ToolCall] = []
            for idx in sorted(tool_chunks):
                raw = tool_chunks[idx]
                try:
                    input_data = json.loads(raw["arguments"]) if raw["arguments"] else {}
                except json.JSONDecodeError:
                    input_data = {}
                tc = ToolCall(id=raw["id"], name=raw["name"], input=input_data)
                tool_calls.append(tc)
                log.debug("tool_call complete: %s", raw["name"])
                yield StreamEvent(type="tool_call", tool_call=tc)

            done_msg = Message(
                role="assistant",
                content=assembled_text,
                tool_calls=tool_calls,
            )
            yield StreamEvent(type="done", message=done_msg)

        except openai.APIError as e:
            log.error("OpenAI API error: %s", e)
            yield StreamEvent(type="error", error=str(e))

    async def _iter_chunks(self, kwargs: dict) -> AsyncIterator:
        """Yield raw stream chunks from either the async or sync client."""
        if self.config.sync_http:
            queue: asyncio.Queue = asyncio.Queue()
            error: list[Exception] = []

            def _run() -> None:
                try:
                    with self.sync_client.chat.completions.create(**kwargs) as stream:
                        for chunk in stream:
                            queue.put_nowait(chunk)
                except Exception as e:
                    error.append(e)
                finally:
                    queue.put_nowait(None)

            task = asyncio.get_event_loop().run_in_executor(None, _run)
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk
            await task
            if error:
                raise error[0]
        else:
            async with await self.client.chat.completions.create(**kwargs) as stream:
                async for chunk in stream:
                    yield chunk

    async def chat(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 8192,
    ) -> Message:
        kwargs = self._build_kwargs(messages, system)
        kwargs["max_tokens"] = max_tokens
        if self.config.sync_http:
            response = await asyncio.to_thread(
                self.sync_client.chat.completions.create, **kwargs
            )
        else:
            response = await self.client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""
        return Message(role="assistant", content=text)

    async def count_tokens(
        self,
        messages: list[Message],
        system: str = "",
    ) -> int:
        formatted = self._format_messages(messages, system)
        instructions = None
        input_messages = formatted
        if formatted and formatted[0]["role"] == "system":
            instructions = formatted[0]["content"]
            input_messages = formatted[1:]
        try:
            count_kwargs: dict = {"model": self.config.model, "input": input_messages}
            if instructions:
                count_kwargs["instructions"] = instructions
            if self.config.sync_http:
                result = await asyncio.to_thread(
                    self.sync_client.responses.input_tokens.count, **count_kwargs
                )
            else:
                result = await self.client.responses.input_tokens.count(**count_kwargs)
            return result.input_tokens
        except Exception:
            text = " ".join(
                m.get("content", "") if isinstance(m.get("content"), str) else ""
                for m in formatted
            )
            return len(text) // 4

    def _build_kwargs(self, messages: list[Message], system: str) -> dict:
        return {
            "model": self.config.model,
            "messages": self._format_messages(messages, system),
            "temperature": self.config.temperature,
        }

    def _format_messages(self, messages: list[Message], system: str) -> list[dict]:
        """Translate Message list to OpenAI chat format.

        System prompt becomes the first message with role="system".
        tool_result → role="tool" with tool_call_id.
        assistant with tool_calls → function call format.
        """
        result: list[dict] = []

        if system:
            result.append({"role": "system", "content": system})

        for msg in messages:
            if msg.role == "tool":
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })

            elif msg.role == "assistant" and msg.tool_calls:
                calls = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.input),
                        },
                    }
                    for tc in msg.tool_calls
                ]
                entry: dict = {"role": "assistant", "tool_calls": calls}
                if msg.content:
                    entry["content"] = msg.content
                result.append(entry)

            else:
                result.append({"role": msg.role, "content": msg.content})

        return result

    def _format_tools(self, tools: list[ToolDef]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": td.name,
                    "description": td.description,
                    "parameters": td.input_schema,
                },
            }
            for td in tools
        ]
