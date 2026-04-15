"""Tests for tinyloom.core.compact — context compaction."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tinyloom.core.compact import (
    estimate_tokens_heuristic,
    maybe_compact,
    KEEP_RECENT_SUMMARIZE,
    KEEP_RECENT_TRUNCATE,
)
from tinyloom.core.types import Message


def _make_messages(n: int) -> list[Message]:
    return [Message(role="user", content=f"message {i}") for i in range(n)]


def _make_provider(**overrides) -> AsyncMock:
    provider = AsyncMock()
    provider.count_tokens = AsyncMock(return_value=overrides.get("token_count", 1000))
    provider.chat = AsyncMock(
        return_value=Message(role="assistant", content=overrides.get("summary_text", "summary"))
    )
    return provider


@pytest.mark.asyncio
async def test_estimate_tokens_heuristic():
    msgs = [Message(role="user", content="a" * 400)]
    result = estimate_tokens_heuristic(msgs)
    assert result == 100


@pytest.mark.asyncio
async def test_maybe_compact_returns_none_below_threshold():
    provider = _make_provider(token_count=1000)
    messages = _make_messages(5)
    result = await maybe_compact(provider, messages, context_window=200_000, threshold=0.8, strategy="summarize")
    assert result is None


@pytest.mark.asyncio
async def test_truncate_strategy():
    provider = _make_provider(token_count=170_000)
    messages = _make_messages(20)
    result = await maybe_compact(provider, messages, context_window=200_000, threshold=0.8, strategy="truncate")

    assert result is not None
    # marker + last 10
    assert len(result) == KEEP_RECENT_TRUNCATE + 1
    assert result[0].content == "[Previous conversation was truncated]"
    assert result[-1].content == messages[-1].content


@pytest.mark.asyncio
async def test_summarize_strategy():
    provider = _make_provider(token_count=170_000, summary_text="This is the summary")
    messages = _make_messages(20)
    result = await maybe_compact(provider, messages, context_window=200_000, threshold=0.8, strategy="summarize")

    assert result is not None
    # summary + last 4
    assert len(result) == KEEP_RECENT_SUMMARIZE + 1
    assert "This is the summary" in result[0].content
    assert result[-1].content == messages[-1].content


@pytest.mark.asyncio
async def test_summarize_falls_back_to_truncate_on_chat_error():
    provider = _make_provider(token_count=170_000)
    provider.chat = AsyncMock(side_effect=RuntimeError("LLM error"))
    messages = _make_messages(20)
    result = await maybe_compact(provider, messages, context_window=200_000, threshold=0.8, strategy="summarize")

    assert result is not None
    # Falls back to truncate: marker + last 10
    assert len(result) == KEEP_RECENT_TRUNCATE + 1
    assert result[0].content == "[Previous conversation was truncated]"


@pytest.mark.asyncio
async def test_maybe_compact_uses_heuristic_when_count_tokens_fails():
    provider = _make_provider()
    provider.count_tokens = AsyncMock(side_effect=RuntimeError("not implemented"))
    # 796 chars / 4 = 199 tokens, threshold at 0.8 * 250 = 200, so below limit
    messages = [Message(role="user", content="a" * 796)]
    result = await maybe_compact(provider, messages, context_window=250, threshold=0.8, strategy="truncate")
    # 199 < 200, no compaction
    assert result is None
