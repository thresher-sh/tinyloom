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
class AgentEvent(StreamEvent):
    tool_call_id: str = ""
    tool_name: str = ""
    result: str = ""

    def to_dict(self) -> dict:
        d: dict = {"type": self.type}
        for k in ("text", "tool_call_id", "tool_name", "result", "error"):
            if v := getattr(self, k):
                d[k] = v
        if (tc := self.tool_call) is not None:
            d["tool_call"] = {"id": tc.id, "name": tc.name, "input": tc.input}
        if (m := self.message) is not None:
            d["message"] = {"role": m.role, "content": m.content}
        return d
