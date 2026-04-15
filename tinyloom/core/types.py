from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict


@dataclass
class Message:
    role: str
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""
    name: str = ""


@dataclass
class StreamEvent:
    type: str
    text: str = ""
    tool_call: ToolCall | None = None
    message: Message | None = None
    error: str = ""


@dataclass
class AgentEvent:
    type: str
    text: str = ""
    tool_call: ToolCall | None = None
    tool_call_id: str = ""
    tool_name: str = ""
    result: str = ""
    message: Message | None = None
    error: str = ""

    def to_dict(self) -> dict:
        d: dict = {"type": self.type}
        if self.text:
            d["text"] = self.text
        if self.tool_call is not None:
            d["tool_call"] = {
                "id": self.tool_call.id,
                "name": self.tool_call.name,
                "input": self.tool_call.input,
            }
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_name:
            d["tool_name"] = self.tool_name
        if self.result:
            d["result"] = self.result
        if self.message is not None:
            d["message"] = {"role": self.message.role, "content": self.message.content}
        if self.error:
            d["error"] = self.error
        return d
