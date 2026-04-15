from __future__ import annotations
import asyncio
from typing import AsyncIterator, Callable, Protocol, runtime_checkable
from tinyloom.core.config import ModelConfig
from tinyloom.core.types import Message, StreamEvent, ToolDef

@runtime_checkable
class LLMProvider(Protocol):
    async def stream(self, messages: list[Message], tools: list[ToolDef], system: str = "") -> AsyncIterator[StreamEvent]: ...
    async def chat(self, messages: list[Message], system: str = "", max_tokens: int = 8192) -> Message: ...
    async def count_tokens(self, messages: list[Message], system: str = "") -> int: ...

def client_kwargs(config: ModelConfig) -> dict:
    kw: dict = {}
    if config.api_key: kw["api_key"] = config.api_key
    if config.base_url: kw["base_url"] = config.base_url
    return kw

async def drain_sync_queue(run_fn: Callable[[asyncio.Queue], None]) -> AsyncIterator:
    """Run *run_fn(queue)* in a thread, yield items until None sentinel."""
    queue: asyncio.Queue = asyncio.Queue()
    error: list[Exception] = []
    def _run():
        try:
            run_fn(queue)
        except Exception as e:
            error.append(e)
        finally:
            queue.put_nowait(None)
    task = asyncio.get_event_loop().run_in_executor(None, _run)
    while True:
        item = await queue.get()
        if item is None:
            break
        yield item
    await task
    if error:
        raise error[0]
