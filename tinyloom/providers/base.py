from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from tinyloom.core.types import Message, StreamEvent, ToolDef


@runtime_checkable
class LLMProvider(Protocol):
    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        system: str = "",
    ) -> AsyncIterator[StreamEvent]: ...

    async def chat(
        self,
        messages: list[Message],
        system: str = "",
        max_tokens: int = 8192,
    ) -> Message: ...

    async def count_tokens(
        self,
        messages: list[Message],
        system: str = "",
    ) -> int: ...
