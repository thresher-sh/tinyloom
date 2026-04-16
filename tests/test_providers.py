"""Tests for provider formatting methods (no live API calls)."""

from __future__ import annotations

from types import SimpleNamespace
from tinyloom.core.config import ModelConfig
from tinyloom.core.types import Message, ToolCall, TokenUsage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _anthropic_provider():
    from tinyloom.providers.anthropic import AnthropicProvider
    config = ModelConfig(api_key="test-key")
    return AnthropicProvider(config)


def _openai_provider():
    from tinyloom.providers.openai import OpenAIProvider
    config = ModelConfig(provider="openai", model="gpt-4o", api_key="test-key")
    return OpenAIProvider(config)


# ---------------------------------------------------------------------------
# AnthropicProvider formatting tests
# ---------------------------------------------------------------------------

class TestAnthropicFormatMessages:
    def test_user_message(self):
        p = _anthropic_provider()
        msgs = [Message(role="user", content="hello")]
        result = p._format_messages(msgs)
        assert result == [{"role": "user", "content": "hello"}]

    def test_assistant_with_tool_calls(self):
        p = _anthropic_provider()
        tc = ToolCall(id="tc1", name="bash", input={"cmd": "ls"})
        msgs = [Message(role="assistant", content="ok", tool_calls=[tc])]
        result = p._format_messages(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        content = result[0]["content"]
        # text block first, then tool_use
        assert {"type": "text", "text": "ok"} in content
        tool_block = next(b for b in content if b.get("type") == "tool_use")
        assert tool_block["id"] == "tc1"
        assert tool_block["name"] == "bash"
        assert tool_block["input"] == {"cmd": "ls"}

    def test_tool_result_becomes_user_message(self):
        p = _anthropic_provider()
        msgs = [Message(role="tool", content="file contents", tool_call_id="tc1", name="read")]
        result = p._format_messages(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        block = result[0]["content"][0]
        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "tc1"
        assert block["content"] == "file contents"

    def test_consecutive_tool_results_merge_into_one_user_message(self):
        p = _anthropic_provider()
        msgs = [
            Message(role="tool", content="result1", tool_call_id="tc1"),
            Message(role="tool", content="result2", tool_call_id="tc2"),
        ]
        result = p._format_messages(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        blocks = result[0]["content"]
        assert len(blocks) == 2
        ids = {b["tool_use_id"] for b in blocks}
        assert ids == {"tc1", "tc2"}

    def test_assistant_no_tool_calls(self):
        p = _anthropic_provider()
        msgs = [Message(role="assistant", content="just text")]
        result = p._format_messages(msgs)
        assert result == [{"role": "assistant", "content": "just text"}]


class TestOpenAIFormatMessages:
    def test_user_message(self):
        p = _openai_provider()
        msgs = [Message(role="user", content="hello")]
        result = p._format_messages(msgs, system="")
        assert result == [{"role": "user", "content": "hello"}]

    def test_system_prompt_prepended(self):
        p = _openai_provider()
        msgs = [Message(role="user", content="hi")]
        result = p._format_messages(msgs, system="You are helpful")
        assert result[0] == {"role": "system", "content": "You are helpful"}
        assert result[1] == {"role": "user", "content": "hi"}

    def test_tool_result_becomes_role_tool(self):
        p = _openai_provider()
        msgs = [Message(role="tool", content="output", tool_call_id="tc1", name="bash")]
        result = p._format_messages(msgs, system="")
        assert len(result) == 1
        assert result[0]["role"] == "tool"
        assert result[0]["tool_call_id"] == "tc1"
        assert result[0]["content"] == "output"

    def test_assistant_with_tool_calls(self):
        p = _openai_provider()
        tc = ToolCall(id="tc1", name="bash", input={"cmd": "ls"})
        msgs = [Message(role="assistant", content="", tool_calls=[tc])]
        result = p._format_messages(msgs, system="")
        assert len(result) == 1
        msg = result[0]
        assert msg["role"] == "assistant"
        calls = msg["tool_calls"]
        assert len(calls) == 1
        assert calls[0]["id"] == "tc1"
        assert calls[0]["type"] == "function"
        assert calls[0]["function"]["name"] == "bash"

    def test_assistant_text_only(self):
        p = _openai_provider()
        msgs = [Message(role="assistant", content="done")]
        result = p._format_messages(msgs, system="")
        assert result == [{"role": "assistant", "content": "done"}]


class TestOpenAIUsageExtraction:
    def test_extract_usage_with_cache(self):
        """Verify OpenAI field names normalize to TokenUsage."""
        from tinyloom.providers.openai import _extract_openai_usage
        usage = SimpleNamespace(prompt_tokens=1500, completion_tokens=300, prompt_tokens_details=SimpleNamespace(cached_tokens=1200))
        result = _extract_openai_usage(usage)
        assert result == TokenUsage(input_tokens=1500, output_tokens=300, cache_read_tokens=1200, cache_write_tokens=0)

    def test_extract_usage_prompt_tokens_details_none(self):
        """Some models don't return prompt_tokens_details."""
        from tinyloom.providers.openai import _extract_openai_usage
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50, prompt_tokens_details=None)
        result = _extract_openai_usage(usage)
        assert result == TokenUsage(input_tokens=100, output_tokens=50, cache_read_tokens=0, cache_write_tokens=0)

    def test_extract_usage_no_details_attr(self):
        """Third-party endpoints may omit prompt_tokens_details entirely."""
        from tinyloom.providers.openai import _extract_openai_usage
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50)
        result = _extract_openai_usage(usage)
        assert result == TokenUsage(input_tokens=100, output_tokens=50, cache_read_tokens=0, cache_write_tokens=0)

    def test_extract_usage_none(self):
        from tinyloom.providers.openai import _extract_openai_usage
        result = _extract_openai_usage(None)
        assert result is None

    def test_extract_usage_cached_tokens_none(self):
        """cached_tokens field exists but is None."""
        from tinyloom.providers.openai import _extract_openai_usage
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50, prompt_tokens_details=SimpleNamespace(cached_tokens=None))
        result = _extract_openai_usage(usage)
        assert result == TokenUsage(input_tokens=100, output_tokens=50, cache_read_tokens=0, cache_write_tokens=0)


class TestOpenAIStreamOptions:
    """stream_options is always sent for usage tracking (Ollama, OpenAI, and most third-party providers support it)."""

    def test_stream_options_always_included(self):
        """stream_options should be sent for all providers including third-party."""
        config = ModelConfig(provider="openai", model="some-model", api_key="test-key", base_url="https://api.fireworks.ai/inference/v1")
        assert config.base_url is not None

    def test_stream_options_with_vanilla_openai(self):
        """stream_options should be sent for vanilla OpenAI too."""
        config = ModelConfig(provider="openai", model="gpt-4o", api_key="test-key")
        assert config.base_url is None


class TestOpenAIReasoningFieldDetection:
    """Ollama uses 'reasoning' while OpenAI uses 'reasoning_content'. Provider must handle both."""

    def test_extract_reasoning_from_ollama_style_delta(self):
        """Ollama sends reasoning in delta.reasoning, not delta.reasoning_content."""
        from tinyloom.providers.openai import _get_reasoning
        delta = SimpleNamespace(reasoning="thinking step by step", content=None, tool_calls=None)
        assert _get_reasoning(delta) == "thinking step by step"

    def test_extract_reasoning_from_openai_style_delta(self):
        """OpenAI sends reasoning in delta.reasoning_content."""
        from tinyloom.providers.openai import _get_reasoning
        delta = SimpleNamespace(reasoning_content="deep thought", content=None, tool_calls=None)
        assert _get_reasoning(delta) == "deep thought"

    def test_no_reasoning_returns_none(self):
        from tinyloom.providers.openai import _get_reasoning
        delta = SimpleNamespace(content="hello", tool_calls=None)
        assert _get_reasoning(delta) is None

    def test_extract_reasoning_from_ollama_style_message(self):
        """Non-streaming: Ollama sends reasoning in message.reasoning."""
        from tinyloom.providers.openai import _get_reasoning
        msg = SimpleNamespace(reasoning="step by step", content="answer", reasoning_content=None)
        assert _get_reasoning(msg) == "step by step"

    def test_reasoning_content_preferred_over_reasoning(self):
        """If both exist, reasoning_content wins (OpenAI canonical)."""
        from tinyloom.providers.openai import _get_reasoning
        obj = SimpleNamespace(reasoning_content="from openai", reasoning="from ollama")
        assert _get_reasoning(obj) == "from openai"


class TestAnthropicThinking:
    """Anthropic thinking/reasoning_effort support in _build_kwargs."""

    def test_thinking_disabled_by_default(self):
        p = _anthropic_provider()
        kwargs = p._build_kwargs([Message(role="user", content="hi")], system="sys")
        assert "thinking" not in kwargs
        assert "output_config" not in kwargs
        assert kwargs["temperature"] == 0.0

    def test_thinking_enabled(self):
        config = ModelConfig(api_key="test-key", thinking=True)
        from tinyloom.providers.anthropic import AnthropicProvider
        p = AnthropicProvider(config)
        kwargs = p._build_kwargs([Message(role="user", content="hi")], system="sys")
        assert kwargs["thinking"] == {"type": "adaptive"}
        assert "temperature" not in kwargs

    def test_reasoning_effort_sets_output_config(self):
        config = ModelConfig(api_key="test-key", reasoning_effort="medium")
        from tinyloom.providers.anthropic import AnthropicProvider
        p = AnthropicProvider(config)
        kwargs = p._build_kwargs([Message(role="user", content="hi")], system="sys")
        assert kwargs["output_config"] == {"effort": "medium"}
        assert kwargs["thinking"] == {"type": "adaptive"}
        assert "temperature" not in kwargs

    def test_thinking_true_without_reasoning_effort(self):
        config = ModelConfig(api_key="test-key", thinking=True)
        from tinyloom.providers.anthropic import AnthropicProvider
        p = AnthropicProvider(config)
        kwargs = p._build_kwargs([Message(role="user", content="hi")], system="")
        assert kwargs["thinking"] == {"type": "adaptive"}
        assert "output_config" not in kwargs

    def test_reasoning_effort_alone_implies_thinking(self):
        """Setting reasoning_effort without thinking=True still enables thinking."""
        config = ModelConfig(api_key="test-key", reasoning_effort="high")
        from tinyloom.providers.anthropic import AnthropicProvider
        p = AnthropicProvider(config)
        kwargs = p._build_kwargs([Message(role="user", content="hi")], system="")
        assert kwargs["thinking"] == {"type": "adaptive"}
        assert kwargs["output_config"] == {"effort": "high"}


class TestAnthropicReasoningPreservation:
    """Anthropic thinking block reconstruction in _format_messages for multi-turn."""

    def test_assistant_with_reasoning_reconstructs_thinking_block(self):
        p = _anthropic_provider()
        tc = ToolCall(id="tc1", name="bash", input={"cmd": "ls"})
        msgs = [Message(role="assistant", content="ok", tool_calls=[tc], reasoning="deep thought", reasoning_signature="sig_abc")]
        result = p._format_messages(msgs)
        assert len(result) == 1
        content = result[0]["content"]
        assert content[0] == {"type": "thinking", "thinking": "deep thought", "signature": "sig_abc"}
        assert content[1] == {"type": "text", "text": "ok"}
        assert content[2]["type"] == "tool_use"

    def test_assistant_without_reasoning_no_thinking_block(self):
        p = _anthropic_provider()
        tc = ToolCall(id="tc1", name="bash", input={"cmd": "ls"})
        msgs = [Message(role="assistant", content="ok", tool_calls=[tc])]
        result = p._format_messages(msgs)
        content = result[0]["content"]
        assert content[0] == {"type": "text", "text": "ok"}
        assert not any(b.get("type") == "thinking" for b in content)

    def test_reasoning_signature_alone_triggers_content_array(self):
        """Assistant with reasoning_signature but no tool_calls still gets content array."""
        p = _anthropic_provider()
        msgs = [Message(role="assistant", content="answer", reasoning="hmm", reasoning_signature="sig_xyz")]
        result = p._format_messages(msgs)
        content = result[0]["content"]
        assert content[0] == {"type": "thinking", "thinking": "hmm", "signature": "sig_xyz"}
        assert content[1] == {"type": "text", "text": "answer"}

    def test_reasoning_without_signature_no_thinking_block(self):
        """reasoning text without signature should not produce a thinking block (signature is required)."""
        p = _anthropic_provider()
        msgs = [Message(role="assistant", content="answer", reasoning="hmm")]
        result = p._format_messages(msgs)
        assert result[0] == {"role": "assistant", "content": "answer"}

    def test_thinking_block_ordering_preserved(self):
        """Thinking blocks must come before text and tool_use blocks."""
        p = _anthropic_provider()
        tc = ToolCall(id="tc1", name="read", input={"path": "/tmp"})
        msgs = [Message(role="assistant", content="let me check", tool_calls=[tc], reasoning="analyzing...", reasoning_signature="sig_001")]
        result = p._format_messages(msgs)
        content = result[0]["content"]
        types = [b["type"] for b in content]
        assert types == ["thinking", "text", "tool_use"]


class TestOpenAIThinking:
    """OpenAI reasoning_effort support in _build_kwargs."""

    def test_reasoning_disabled_by_default(self):
        p = _openai_provider()
        kwargs = p._build_kwargs([Message(role="user", content="hi")], system="sys")
        assert "reasoning_effort" not in kwargs
        assert kwargs["temperature"] == 0.0

    def test_reasoning_effort_passed_through(self):
        config = ModelConfig(provider="openai", model="o3-mini", api_key="test-key", reasoning_effort="medium")
        from tinyloom.providers.openai import OpenAIProvider
        p = OpenAIProvider(config)
        kwargs = p._build_kwargs([Message(role="user", content="hi")], system="")
        assert kwargs["reasoning_effort"] == "medium"
        assert "temperature" not in kwargs

    def test_thinking_true_omits_temperature(self):
        config = ModelConfig(provider="openai", model="o3-mini", api_key="test-key", thinking=True)
        from tinyloom.providers.openai import OpenAIProvider
        p = OpenAIProvider(config)
        kwargs = p._build_kwargs([Message(role="user", content="hi")], system="")
        assert "temperature" not in kwargs
        assert "reasoning_effort" not in kwargs

    def test_reasoning_effort_with_fireworks_base_url(self):
        """reasoning_effort works the same way with third-party base_url."""
        config = ModelConfig(provider="openai", model="accounts/fireworks/models/deepseek-r1", api_key="test-key", base_url="https://api.fireworks.ai/inference/v1", reasoning_effort="low")
        from tinyloom.providers.openai import OpenAIProvider
        p = OpenAIProvider(config)
        kwargs = p._build_kwargs([Message(role="user", content="hi")], system="")
        assert kwargs["reasoning_effort"] == "low"
        assert "temperature" not in kwargs

    def test_reasoning_effort_alone_implies_thinking(self):
        """Setting reasoning_effort without thinking=True still omits temperature."""
        config = ModelConfig(provider="openai", model="o3-mini", api_key="test-key", reasoning_effort="high")
        from tinyloom.providers.openai import OpenAIProvider
        p = OpenAIProvider(config)
        kwargs = p._build_kwargs([Message(role="user", content="hi")], system="")
        assert "temperature" not in kwargs
        assert kwargs["reasoning_effort"] == "high"


class TestOpenAIReasoningPreservation:
    """OpenAI reasoning_content preservation in _format_messages for multi-turn (Fireworks/OpenRouter)."""

    def test_assistant_with_reasoning_includes_reasoning_content(self):
        p = _openai_provider()
        tc = ToolCall(id="tc1", name="bash", input={"cmd": "ls"})
        msgs = [Message(role="assistant", content="ok", tool_calls=[tc], reasoning="deep thought")]
        result = p._format_messages(msgs, system="")
        assert result[0]["reasoning_content"] == "deep thought"

    def test_assistant_without_reasoning_no_reasoning_content(self):
        p = _openai_provider()
        tc = ToolCall(id="tc1", name="bash", input={"cmd": "ls"})
        msgs = [Message(role="assistant", content="ok", tool_calls=[tc])]
        result = p._format_messages(msgs, system="")
        assert "reasoning_content" not in result[0]

    def test_text_only_assistant_with_reasoning(self):
        p = _openai_provider()
        msgs = [Message(role="assistant", content="answer", reasoning="let me think")]
        result = p._format_messages(msgs, system="")
        assert result[0]["content"] == "answer"
        assert result[0]["reasoning_content"] == "let me think"

    def test_text_only_assistant_without_reasoning(self):
        p = _openai_provider()
        msgs = [Message(role="assistant", content="answer")]
        result = p._format_messages(msgs, system="")
        assert "reasoning_content" not in result[0]

    def test_user_message_never_gets_reasoning(self):
        p = _openai_provider()
        msgs = [Message(role="user", content="hello")]
        result = p._format_messages(msgs, system="")
        assert "reasoning_content" not in result[0]


class TestAnthropicUsageExtraction:
    def test_extract_usage_with_cache(self):
        """Verify Anthropic field names map correctly to TokenUsage."""
        from tinyloom.providers.anthropic import _extract_anthropic_usage
        usage = SimpleNamespace(input_tokens=1500, output_tokens=300, cache_read_input_tokens=1200, cache_creation_input_tokens=50)
        result = _extract_anthropic_usage(usage)
        assert result == TokenUsage(input_tokens=1500, output_tokens=300, cache_read_tokens=1200, cache_write_tokens=50)

    def test_extract_usage_no_cache_fields(self):
        """Older API responses may lack cache fields."""
        from tinyloom.providers.anthropic import _extract_anthropic_usage
        usage = SimpleNamespace(input_tokens=100, output_tokens=50)
        result = _extract_anthropic_usage(usage)
        assert result == TokenUsage(input_tokens=100, output_tokens=50, cache_read_tokens=0, cache_write_tokens=0)

    def test_extract_usage_none(self):
        from tinyloom.providers.anthropic import _extract_anthropic_usage
        result = _extract_anthropic_usage(None)
        assert result is None

