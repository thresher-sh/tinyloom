"""Tests for provider formatting methods (no live API calls)."""

from __future__ import annotations


from tinyloom.core.config import ModelConfig
from tinyloom.core.types import Message, ToolCall, ToolDef


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


class TestAnthropicFormatTools:
    def test_format_tools(self):
        p = _anthropic_provider()
        schema = {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}
        td = ToolDef(name="bash", description="Run a command", input_schema=schema)
        result = p._format_tools([td])
        assert result == [
            {
                "name": "bash",
                "description": "Run a command",
                "input_schema": schema,
            }
        ]


# ---------------------------------------------------------------------------
# OpenAIProvider formatting tests
# ---------------------------------------------------------------------------

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


class TestOpenAIFormatTools:
    def test_format_tools(self):
        p = _openai_provider()
        schema = {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}
        td = ToolDef(name="bash", description="Run a command", input_schema=schema)
        result = p._format_tools([td])
        assert result == [
            {
                "type": "function",
                "function": {
                    "name": "bash",
                    "description": "Run a command",
                    "parameters": schema,
                },
            }
        ]
