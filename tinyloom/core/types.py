from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(input_tokens=self.input_tokens + other.input_tokens, output_tokens=self.output_tokens + other.output_tokens, cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens, cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens)

    def to_dict(self) -> dict:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens, "cache_read_tokens": self.cache_read_tokens, "cache_write_tokens": self.cache_write_tokens}

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
    reasoning: str | None = None
    reasoning_signature: str | None = None  # Anthropic encrypted thinking for multi-turn

@dataclass
class StreamEvent:
    type: str
    text: str = ""
    tool_call: ToolCall | None = None
    message: Message | None = None
    error: str = ""
    usage: TokenUsage | None = None

@dataclass
class AgentEvent(StreamEvent):
    tool_call_id: str = ""
    tool_name: str = ""
    result: str = ""
    cumulative_usage: TokenUsage | None = None

    def to_dict(self) -> dict:
        d: dict = {"type": self.type}
        for k in ("text", "tool_call_id", "tool_name", "result", "error"):
            if v := getattr(self, k):
                d[k] = v
        if (tc := self.tool_call) is not None:
            d["tool_call"] = {"id": tc.id, "name": tc.name, "input": tc.input}
        if (m := self.message) is not None:
            md: dict = {"role": m.role, "content": m.content}
            if m.reasoning: md["reasoning"] = m.reasoning
            d["message"] = md
        if self.usage is not None:
            d["usage"] = self.usage.to_dict()
        if self.cumulative_usage is not None:
            d["cumulative_usage"] = self.cumulative_usage.to_dict()
        return d
