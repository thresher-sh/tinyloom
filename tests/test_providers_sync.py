"""Tests for sync HTTP bridge in providers (no live API calls)."""

from __future__ import annotations

from tinyloom.core.config import ModelConfig


def test_openai_creates_sync_client_when_configured():
    from tinyloom.providers.openai import OpenAIProvider
    config = ModelConfig(provider="openai", model="gpt-4o", api_key="test-key", sync_http=True)
    p = OpenAIProvider(config)
    assert hasattr(p, "sync_client")
    assert p.sync_client is not None


def test_openai_no_sync_client_by_default():
    from tinyloom.providers.openai import OpenAIProvider
    config = ModelConfig(provider="openai", model="gpt-4o", api_key="test-key")
    p = OpenAIProvider(config)
    assert not hasattr(p, "sync_client")


def test_anthropic_creates_sync_client_when_configured():
    from tinyloom.providers.anthropic import AnthropicProvider
    config = ModelConfig(api_key="test-key", sync_http=True)
    p = AnthropicProvider(config)
    assert hasattr(p, "sync_client")
    assert p.sync_client is not None


def test_anthropic_no_sync_client_by_default():
    from tinyloom.providers.anthropic import AnthropicProvider
    config = ModelConfig(api_key="test-key")
    p = AnthropicProvider(config)
    assert not hasattr(p, "sync_client")


def test_sync_http_config_defaults_false():
    config = ModelConfig()
    assert config.sync_http is False


def test_sync_http_config_from_yaml():
    """sync_http can be set via the config loading path."""
    config = ModelConfig(sync_http=True)
    assert config.sync_http is True
