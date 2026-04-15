"""Tests for tinyloom.core.types."""

from __future__ import annotations


from tinyloom.core.types import (
    AgentEvent,
    Message,
    StreamEvent,
    ToolCall,
    ToolDef,
)


class TestMessage:
    def test_message_defaults(self):
        msg = Message(role="user")
        assert msg.role == "user"
        assert msg.content == ""
        assert msg.tool_calls == []
        assert msg.tool_call_id == ""
        assert msg.name == ""

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

    def test_to_dict_includes_error(self):
        ev = AgentEvent(type="error", error="boom")
        d = ev.to_dict()
        assert d == {"type": "error", "error": "boom"}
