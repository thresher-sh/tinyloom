"""Tests for tinyloom.core.types."""

from __future__ import annotations


from tinyloom.core.types import (
    AgentEvent,
    Message,
    StreamEvent,
    ToolCall,
    ToolDef,
    TokenUsage,
)


class TestTokenUsage:
    def test_defaults_are_zero(self):
        u = TokenUsage()
        assert u.input_tokens == 0
        assert u.output_tokens == 0
        assert u.cache_read_tokens == 0
        assert u.cache_write_tokens == 0

    def test_creation_with_values(self):
        u = TokenUsage(input_tokens=100, output_tokens=50, cache_read_tokens=80, cache_write_tokens=10)
        assert u.input_tokens == 100
        assert u.output_tokens == 50
        assert u.cache_read_tokens == 80
        assert u.cache_write_tokens == 10

    def test_add(self):
        a = TokenUsage(input_tokens=100, output_tokens=50, cache_read_tokens=80, cache_write_tokens=10)
        b = TokenUsage(input_tokens=200, output_tokens=30, cache_read_tokens=150, cache_write_tokens=5)
        c = a + b
        assert c.input_tokens == 300
        assert c.output_tokens == 80
        assert c.cache_read_tokens == 230
        assert c.cache_write_tokens == 15

    def test_add_does_not_mutate(self):
        a = TokenUsage(input_tokens=100)
        b = TokenUsage(input_tokens=200)
        c = a + b
        assert a.input_tokens == 100
        assert b.input_tokens == 200
        assert c.input_tokens == 300

    def test_to_dict(self):
        u = TokenUsage(input_tokens=100, output_tokens=50, cache_read_tokens=80, cache_write_tokens=10)
        assert u.to_dict() == {"input_tokens": 100, "output_tokens": 50, "cache_read_tokens": 80, "cache_write_tokens": 10}

    def test_to_dict_zeros(self):
        u = TokenUsage()
        assert u.to_dict() == {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}


class TestMessage:
    def test_message_defaults(self):
        msg = Message(role="user")
        assert msg.role == "user"
        assert msg.content == ""
        assert msg.tool_calls == []
        assert msg.tool_call_id == ""
        assert msg.name == ""
        assert msg.reasoning is None
        assert msg.reasoning_signature is None

    def test_message_with_reasoning(self):
        msg = Message(role="assistant", content="answer", reasoning="let me think", reasoning_signature="sig123")
        assert msg.reasoning == "let me think"
        assert msg.reasoning_signature == "sig123"

    def test_message_tool_calls_default_is_fresh_list(self):
        msg1 = Message(role="user")
        msg2 = Message(role="user")
        msg1.tool_calls.append(ToolCall(id="x", name="y", input={}))
        assert msg2.tool_calls == []

    def test_message_with_tool_calls(self):
        tc = ToolCall(id="tc1", name="bash", input={"cmd": "ls"})
        msg = Message(role="assistant", tool_calls=[tc])
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "bash"

    def test_tool_result_message(self):
        msg = Message(role="tool", content="result text", tool_call_id="tc1", name="bash")
        assert msg.role == "tool"
        assert msg.content == "result text"
        assert msg.tool_call_id == "tc1"
        assert msg.name == "bash"


class TestToolCall:
    def test_tool_call_creation(self):
        tc = ToolCall(id="abc", name="read_file", input={"path": "/tmp/x"})
        assert tc.id == "abc"
        assert tc.name == "read_file"
        assert tc.input == {"path": "/tmp/x"}


class TestToolDef:
    def test_tool_def_creation(self):
        schema = {"type": "object", "properties": {"path": {"type": "string"}}}
        td = ToolDef(name="read_file", description="Reads a file", input_schema=schema)
        assert td.name == "read_file"
        assert td.description == "Reads a file"
        assert td.input_schema == schema


class TestStreamEvent:
    def test_text_event(self):
        ev = StreamEvent(type="text", text="hello")
        assert ev.type == "text"
        assert ev.text == "hello"
        assert ev.tool_call is None
        assert ev.message is None
        assert ev.error == ""

    def test_tool_call_event(self):
        tc = ToolCall(id="x", name="bash", input={"cmd": "pwd"})
        ev = StreamEvent(type="tool_call", tool_call=tc)
        assert ev.type == "tool_call"
        assert ev.tool_call is tc

    def test_done_event(self):
        msg = Message(role="assistant", content="done")
        ev = StreamEvent(type="done", message=msg)
        assert ev.type == "done"
        assert ev.message is msg

    def test_error_event(self):
        ev = StreamEvent(type="error", error="something went wrong")
        assert ev.type == "error"
        assert ev.error == "something went wrong"

    def test_done_event_with_usage(self):
        msg = Message(role="assistant", content="done")
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        ev = StreamEvent(type="done", message=msg, usage=usage)
        assert ev.usage is usage

    def test_usage_defaults_to_none(self):
        ev = StreamEvent(type="text", text="hi")
        assert ev.usage is None


class TestAgentEvent:
    def test_to_dict_drops_empty_fields(self):
        ev = AgentEvent(type="text", text="")
        d = ev.to_dict()
        assert d == {"type": "text"}

    def test_to_dict_includes_text(self):
        ev = AgentEvent(type="text", text="hello world")
        d = ev.to_dict()
        assert d == {"type": "text", "text": "hello world"}

    def test_to_dict_serializes_tool_call(self):
        tc = ToolCall(id="tc1", name="bash", input={"cmd": "ls"})
        ev = AgentEvent(type="tool_call", tool_call=tc)
        d = ev.to_dict()
        assert d["type"] == "tool_call"
        assert d["tool_call"] == {"id": "tc1", "name": "bash", "input": {"cmd": "ls"}}

    def test_to_dict_serializes_tool_result(self):
        ev = AgentEvent(
            type="tool_result",
            tool_call_id="tc1",
            tool_name="bash",
            result="output text",
        )
        d = ev.to_dict()
        assert d == {
            "type": "tool_result",
            "tool_call_id": "tc1",
            "tool_name": "bash",
            "result": "output text",
        }

    def test_to_dict_serializes_response_complete(self):
        msg = Message(role="assistant", content="all done")
        ev = AgentEvent(type="response_complete", message=msg)
        d = ev.to_dict()
        assert d == {
            "type": "response_complete",
            "message": {"role": "assistant", "content": "all done"},
        }

    def test_to_dict_includes_reasoning_in_message(self):
        msg = Message(role="assistant", content="answer", reasoning="thinking...")
        ev = AgentEvent(type="response_complete", message=msg)
        d = ev.to_dict()
        assert d["message"]["reasoning"] == "thinking..."

    def test_to_dict_omits_reasoning_when_none(self):
        msg = Message(role="assistant", content="answer")
        ev = AgentEvent(type="response_complete", message=msg)
        d = ev.to_dict()
        assert "reasoning" not in d["message"]

    def test_to_dict_includes_error(self):
        ev = AgentEvent(type="error", error="boom")
        d = ev.to_dict()
        assert d == {"type": "error", "error": "boom"}

    def test_to_dict_includes_usage(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50, cache_read_tokens=80, cache_write_tokens=10)
        ev = AgentEvent(type="response_complete", usage=usage)
        d = ev.to_dict()
        assert d["usage"] == {"input_tokens": 100, "output_tokens": 50, "cache_read_tokens": 80, "cache_write_tokens": 10}

    def test_to_dict_includes_cumulative_usage(self):
        cu = TokenUsage(input_tokens=500, output_tokens=200)
        ev = AgentEvent(type="agent_stop", cumulative_usage=cu)
        d = ev.to_dict()
        assert d["cumulative_usage"] == {"input_tokens": 500, "output_tokens": 200, "cache_read_tokens": 0, "cache_write_tokens": 0}

    def test_to_dict_includes_both_usage_fields(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        cu = TokenUsage(input_tokens=300, output_tokens=150)
        ev = AgentEvent(type="response_complete", usage=usage, cumulative_usage=cu)
        d = ev.to_dict()
        assert d["usage"] == {"input_tokens": 100, "output_tokens": 50, "cache_read_tokens": 0, "cache_write_tokens": 0}
        assert d["cumulative_usage"] == {"input_tokens": 300, "output_tokens": 150, "cache_read_tokens": 0, "cache_write_tokens": 0}

    def test_to_dict_omits_usage_when_none(self):
        ev = AgentEvent(type="text_delta", text="hello")
        d = ev.to_dict()
        assert "usage" not in d
        assert "cumulative_usage" not in d

    def test_to_dict_backward_compat_response_complete(self):
        """Existing response_complete events without usage still serialize correctly."""
        msg = Message(role="assistant", content="all done")
        ev = AgentEvent(type="response_complete", message=msg)
        d = ev.to_dict()
        assert d == {"type": "response_complete", "message": {"role": "assistant", "content": "all done"}}
