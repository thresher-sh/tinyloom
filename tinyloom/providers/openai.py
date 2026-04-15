from __future__ import annotations
import asyncio, json, logging
from typing import AsyncIterator
import openai
from tinyloom.core.config import ModelConfig
from tinyloom.core.types import Message, StreamEvent, ToolCall, ToolDef
from tinyloom.providers.base import client_kwargs, drain_sync_queue

log = logging.getLogger(__name__)

class OpenAIProvider:
    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        kw = client_kwargs(config)
        self.client = openai.AsyncOpenAI(**kw)
        if config.sync_http: self.sync_client = openai.OpenAI(**kw)

    async def stream(self, messages: list[Message], tools: list[ToolDef], system: str = "") -> AsyncIterator[StreamEvent]:
        kwargs = self._build_kwargs(messages, system)
        kwargs["stream"] = True
        if tools: kwargs["tools"] = [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.input_schema}} for t in tools]

        try:
            tool_chunks: dict[int, dict] = {}
            assembled_text = ""

            async for chunk in self._iter_chunks(kwargs):
                if not chunk.choices: continue
                delta = chunk.choices[0].delta
                if delta.content:
                    log.debug("text delta received")
                    assembled_text += delta.content
                    yield StreamEvent(type="text", text=delta.content)
                if delta.tool_calls:
                    for tc_chunk in delta.tool_calls:
                        idx = tc_chunk.index
                        if idx not in tool_chunks: tool_chunks[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc_chunk.id: tool_chunks[idx]["id"] = tc_chunk.id
                        if tc_chunk.function and tc_chunk.function.name: tool_chunks[idx]["name"] = tc_chunk.function.name
                        if tc_chunk.function and tc_chunk.function.arguments: tool_chunks[idx]["arguments"] += tc_chunk.function.arguments

            tool_calls: list[ToolCall] = []
            for idx in sorted(tool_chunks):
                raw = tool_chunks[idx]
                try: input_data = json.loads(raw["arguments"]) if raw["arguments"] else {}
                except json.JSONDecodeError: input_data = {}
                tc = ToolCall(id=raw["id"], name=raw["name"], input=input_data)
                tool_calls.append(tc)
                log.debug("tool_call complete: %s", raw["name"])
                yield StreamEvent(type="tool_call", tool_call=tc)

            yield StreamEvent(type="done", message=Message(role="assistant", content=assembled_text, tool_calls=tool_calls))
        except openai.APIError as e:
            log.error("OpenAI API error: %s", e)
            yield StreamEvent(type="error", error=str(e))

    async def _iter_chunks(self, kwargs: dict) -> AsyncIterator:
        if self.config.sync_http:
            def _sync(q):
                with self.sync_client.chat.completions.create(**kwargs) as s:
                    for chunk in s: q.put_nowait(chunk)
            async for item in drain_sync_queue(_sync): yield item
        else:
            async with await self.client.chat.completions.create(**kwargs) as stream:
                async for chunk in stream: yield chunk

    async def chat(self, messages: list[Message], system: str = "", max_tokens: int = 8192) -> Message:
        kwargs = self._build_kwargs(messages, system)
        kwargs["max_tokens"] = max_tokens
        response = await asyncio.to_thread(self.sync_client.chat.completions.create, **kwargs) if self.config.sync_http else await self.client.chat.completions.create(**kwargs)
        return Message(role="assistant", content=response.choices[0].message.content or "")

    async def count_tokens(self, messages: list[Message], system: str = "") -> int:
        formatted = self._format_messages(messages, system)
        instructions, input_messages = (formatted[0]["content"], formatted[1:]) if formatted and formatted[0]["role"] == "system" else (None, formatted)
        try:
            count_kwargs: dict = {"model": self.config.model, "input": input_messages}
            if instructions: count_kwargs["instructions"] = instructions
            result = await asyncio.to_thread(self.sync_client.responses.input_tokens.count, **count_kwargs) if self.config.sync_http else await self.client.responses.input_tokens.count(**count_kwargs)
            return result.input_tokens
        except Exception:
            return len(" ".join(m.get("content", "") if isinstance(m.get("content"), str) else "" for m in formatted)) // 4

    def _build_kwargs(self, messages: list[Message], system: str) -> dict:
        return {"model": self.config.model, "messages": self._format_messages(messages, system), "temperature": self.config.temperature}

    def _format_messages(self, messages: list[Message], system: str) -> list[dict]:
        result: list[dict] = [{"role": "system", "content": system}] if system else []
        for msg in messages:
            if msg.role == "tool":
                result.append({"role": "tool", "tool_call_id": msg.tool_call_id, "content": msg.content})
            elif msg.role == "assistant" and msg.tool_calls:
                calls = [{"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.input)}} for tc in msg.tool_calls]
                entry: dict = {"role": "assistant", "tool_calls": calls}
                if msg.content: entry["content"] = msg.content
                result.append(entry)
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result
