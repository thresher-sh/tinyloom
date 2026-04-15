"""Tests for tinyloom.core.compact — context compaction."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tinyloom.core.compact import (
    estimate_tokens_heuristic,
    maybe_compact,
    _get_summary_provider,
    KEEP_RECENT_SUMMARIZE,
    KEEP_RECENT_TRUNCATE,
)
from tinyloom.core.config import Config, CompactionConfig
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


# ---------------------------------------------------------------------------
# Compaction model/provider config tests
# ---------------------------------------------------------------------------


def test_get_summary_provider_returns_default_when_no_config():
    default = _make_provider()
    result = _get_summary_provider(default, None)
    assert result is default


def test_get_summary_provider_returns_default_when_no_overrides():
    default = _make_provider()
    config = Config()  # compaction.model and .provider are both None
    result = _get_summary_provider(default, config)
    assert result is default


def test_get_summary_provider_creates_new_when_model_set():
    default = _make_provider()
    config = Config(
        compaction=CompactionConfig(model="claude-haiku-4-5-20251001"),
    )
    with patch("tinyloom.providers.create_provider") as mock_create:
        mock_create.return_value = _make_provider()
        result = _get_summary_provider(default, config)
        mock_create.assert_called_once()
        mc = mock_create.call_args[0][0]
        assert mc.model == "claude-haiku-4-5-20251001"
        # provider stays as main config's default
        assert mc.provider == "anthropic"


def test_get_summary_provider_creates_new_when_provider_set():
    default = _make_provider()
    config = Config(
        compaction=CompactionConfig(provider="openai"),
    )
    with patch("tinyloom.providers.create_provider") as mock_create:
        mock_create.return_value = _make_provider()
        result = _get_summary_provider(default, config)
        mock_create.assert_called_once()
        mc = mock_create.call_args[0][0]
        assert mc.provider == "openai"
        # model stays as main config's default
        assert mc.model == "claude-sonnet-4-20250514"


def test_get_summary_provider_creates_new_with_both_overrides():
    default = _make_provider()
    config = Config(
        compaction=CompactionConfig(
            model="gpt-4o-mini",
            provider="openai",
        ),
    )
    with patch("tinyloom.providers.create_provider") as mock_create:
        mock_create.return_value = _make_provider()
        result = _get_summary_provider(default, config)
        mock_create.assert_called_once()
        mc = mock_create.call_args[0][0]
        assert mc.model == "gpt-4o-mini"
        assert mc.provider == "openai"


@pytest.mark.asyncio
async def test_maybe_compact_passes_config_to_summarize():
    """Ensure maybe_compact uses a compaction-specific provider when config says so."""
    default_provider = _make_provider(token_count=170_000)
    compact_provider = _make_provider(
        token_count=170_000,
        summary_text="Compact summary from cheaper model",
    )
    config = Config(
        compaction=CompactionConfig(model="claude-haiku-4-5-20251001"),
    )
    messages = _make_messages(20)

    with patch("tinyloom.providers.create_provider", return_value=compact_provider):
        result = await maybe_compact(
            default_provider, messages, context_window=200_000,
            threshold=0.8, strategy="summarize", config=config,
        )
    assert result is not None
    assert "Compact summary from cheaper model" in result[0].content
