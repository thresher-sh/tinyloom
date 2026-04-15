from tinyloom.core.config import ModelConfig
from tinyloom.providers.base import LLMProvider


def create_provider(config: ModelConfig) -> LLMProvider:
    provider_type = config.provider
    if provider_type == "anthropic" or (not provider_type and "claude" in config.model):
        from tinyloom.providers.anthropic import AnthropicProvider
        return AnthropicProvider(config)
    else:
        from tinyloom.providers.openai import OpenAIProvider
        return OpenAIProvider(config)
