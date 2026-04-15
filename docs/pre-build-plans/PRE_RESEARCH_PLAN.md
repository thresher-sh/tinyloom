# tinyloom — Implementation Plan

> An extremely small, provider-agnostic coding agent harness in Python.
> "An LLM, a loop, and enough tokens." — Thorsten Ball

**Target: ~1500–2000 lines of Python total.** Every design decision optimizes for smallness.

---

## Table of Contents

1. [Philosophy & Core Insight](#1-philosophy--core-insight)
2. [Architecture Overview](#2-architecture-overview)
3. [File Structure](#3-file-structure)
4. [Dependency Inventory](#4-dependency-inventory)
5. [Implementation Order](#5-implementation-order)
6. [Module Specifications](#6-module-specifications)
   - 6.1 [config.py — Configuration](#61-configpy)
   - 6.2 [llm.py — Provider-Agnostic LLM Client](#62-llmpy)
   - 6.3 [tools.py — Tool System](#63-toolspy)
   - 6.4 [agent.py — The Core Loop](#64-agentpy)
   - 6.5 [Built-in Tools](#65-built-in-tools)
   - 6.6 [mcp.py — MCP Client](#66-mcppy)
   - 6.7 [hooks.py — Lifecycle Hooks](#67-hookspy)
   - 6.8 [plugins.py — Plugin/Extension System](#68-pluginspy)
   - 6.9 [compaction.py — Context Compaction](#69-compactionpy)
   - 6.10 [tui.py — Terminal UI](#610-tuipy)
   - 6.11 [cli.py — CLI Entry Point](#611-clipy)
7. [Config Schema (tinyloom.yaml)](#7-config-schema)
8. [JSON Stream Output Schema](#8-json-stream-output-schema)
9. [Key Design Decisions & Rationale](#9-key-design-decisions--rationale)
10. [Implementation Phases](#10-implementation-phases)

---

## 1. Philosophy & Core Insight

The Thorsten Ball insight is the foundation: a coding agent is **a loop that sends messages to an LLM, checks if it wants to call tools, executes them, sends results back, and repeats**. Everything else is infrastructure around that loop.

**Design principles:**
- **Tiny over featureful.** If a feature adds >100 lines without being in the core spec, it doesn't go in.
- **stdlib over dependency.** Use Python's standard library wherever reasonable.
- **Flat over nested.** Minimal class hierarchies. Dataclasses and functions over deep OOP.
- **Convention over configuration.** Sensible defaults. Config is optional.
- **The agent loop is sacred.** It must fit on one screen (~60 lines). All complexity lives outside it.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                     cli.py                          │
│              (entry point, arg parsing)             │
├──────────────────┬──────────────────────────────────┤
│    tui.py        │         headless mode            │
│  (interactive)   │      (JSON stream stdout)        │
├──────────────────┴──────────────────────────────────┤
│                    agent.py                          │
│         ┌──────────────────────────┐                │
│         │   THE LOOP               │                │
│         │                          │                │
│         │  1. get input            │                │
│         │  2. call LLM             │ ◄── hooks.py   │
│         │  3. tool calls?          │     (lifecycle) │
│         │     yes → execute tool   │                │
│         │     send result → goto 2 │                │
│         │     no → yield response  │                │
│         │  4. goto 1               │                │
│         └──────────────────────────┘                │
├──────────┬───────────┬──────────────────────────────┤
│ llm.py   │ tools.py  │ compaction.py                │
│(provider │(registry, │(token counting,              │
│ adapter) │ built-ins)│ summarization)               │
├──────────┴───────────┴──────────────────────────────┤
│  mcp.py          │  plugins.py                      │
│  (MCP client,    │  (entry_points loader)           │
│  .mcp.json)      │                                  │
├──────────────────┴──────────────────────────────────┤
│                  config.py                           │
│            (tinyloom.yaml loader)                    │
└─────────────────────────────────────────────────────┘
```

---

## 3. File Structure

```
tinyloom/
├── pyproject.toml              # packaging, deps, entry_points
├── README.md
├── tinyloom/
│   ├── __init__.py             # version, public API (~10 lines)
│   ├── config.py               # YAML config loader (~80 lines)
│   ├── llm.py                  # provider-agnostic LLM calls (~200 lines)
│   ├── tools.py                # Tool base + registry (~80 lines)
│   ├── agent.py                # THE core agent loop (~150 lines)
│   ├── builtins/               # built-in tool implementations
│   │   ├── __init__.py         # exports all built-in tools (~10 lines)
│   │   ├── read.py             # read file (~25 lines)
│   │   ├── write.py            # write file (~30 lines)
│   │   ├── edit.py             # str_replace edit (~45 lines)
│   │   ├── grep.py             # grep/search (~35 lines)
│   │   ├── bash.py             # shell command (~40 lines)
│   │   └── exec.py             # sub-agent spawner (~50 lines)
│   ├── mcp.py                  # MCP client (~120 lines)
│   ├── hooks.py                # lifecycle hook system (~60 lines)
│   ├── plugins.py              # plugin loader (~40 lines)
│   ├── compaction.py           # context compaction (~100 lines)
│   ├── events.py               # event types for JSON stream (~40 lines)
│   ├── tui.py                  # rich-based TUI (~150 lines)
│   └── cli.py                  # CLI entry point (~100 lines)
├── tinyloom.example.yaml       # example config
└── tests/
    └── ...
```

**Estimated total: ~1350 lines of Python.** Leaves headroom for edge cases.

---

## 4. Dependency Inventory

**Core (required):**
```toml
[project]
dependencies = [
    "httpx>=0.27",          # HTTP client for LLM APIs (async support, streaming)
    "pyyaml>=6.0",          # config file parsing
    "rich>=13.0",           # TUI rendering, markdown, syntax highlighting
    "prompt-toolkit>=3.0",  # TUI input with history, completion
    "tiktoken>=0.7",        # token counting for OpenAI models
]
```

**Optional (for MCP support):**
```toml
[project.optional-dependencies]
mcp = ["mcp>=1.0"]         # official MCP Python SDK
```

**Why these and not others:**
- **httpx over requests**: native async, streaming support, HTTP/2. We need streaming for LLM responses.
- **httpx over litellm**: litellm is ~50k lines. We need ~200 lines of adapter code. Rolling our own keeps us tiny and dependency-free from a massive transitive tree.
- **rich over textual**: textual is a full TUI framework (overkill). rich gives us pretty printing, markdown, live display, and spinners.
- **tiktoken for token counting**: battle-tested, fast. For Anthropic models we estimate with a simple heuristic (chars/4) since Anthropic doesn't publish a tokenizer — this is good enough for compaction thresholds.

---

## 5. Implementation Order

Build in this exact sequence. Each phase produces a working (increasingly capable) agent.

```
Phase 1: "Hello World Agent" (can chat)
  → config.py → llm.py → agent.py (no tools) → cli.py (minimal)

Phase 2: "Tool-Using Agent" (can code)
  → tools.py → builtins/* → agent.py (tool loop)

Phase 3: "Interactive Agent" (nice to use)
  → tui.py → events.py → cli.py (full)

Phase 4: "Extensible Agent" (production-ready)
  → hooks.py → plugins.py → mcp.py → compaction.py

Phase 5: Polish
  → exec.py (sub-agents) → tinyloom.yaml schema → README
```

---

## 6. Module Specifications

### 6.1 config.py

**Purpose:** Load and validate configuration from `tinyloom.yaml` and environment variables.

**~80 lines.**

```python
"""
Key design: a single frozen dataclass hierarchy. No pydantic needed.
Env vars override YAML. API keys ALWAYS come from env vars, never YAML.
"""
from dataclasses import dataclass, field
from pathlib import Path
import os
import yaml


@dataclass
class ModelConfig:
    provider: str = "anthropic"              # "anthropic" | "openai"
    model: str = "claude-sonnet-4-20250514"
    base_url: str | None = None              # custom endpoint override
    api_key: str | None = None               # populated from env at load time
    max_tokens: int = 8192                   # max output tokens per response
    context_window: int = 200_000            # total context window size
    temperature: float = 0.0


@dataclass
class CompactionConfig:
    enabled: bool = True
    threshold: float = 0.7                   # compact at 70% of context_window
    strategy: str = "summarize"              # "summarize" | "truncate"


@dataclass
class MCPServer:
    command: str = ""                        # e.g. "npx"
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class Config:
    model: ModelConfig = field(default_factory=ModelConfig)
    system_prompt: str = "You are a skilled coding assistant..."
    compaction: CompactionConfig = field(default_factory=CompactionConfig)
    mcp_servers: dict[str, MCPServer] = field(default_factory=dict)
    allowed_tools: list[str] | None = None   # None = all tools allowed
    hooks: dict[str, list[str]] = field(default_factory=dict)  # event -> [dotted.paths]
    plugins: list[str] = field(default_factory=list)
    max_turns: int = 200                     # safety limit on agent loop


def load_config(path: str | Path | None = None) -> Config:
    """
    Load config with this precedence:
    1. Explicit path argument
    2. ./tinyloom.yaml
    3. ~/.config/tinyloom/tinyloom.yaml
    4. Defaults

    Environment variable overrides:
    - TINYLOOM_MODEL → model.model
    - TINYLOOM_PROVIDER → model.provider
    - TINYLOOM_BASE_URL → model.base_url
    - ANTHROPIC_API_KEY → model.api_key (when provider=anthropic)
    - OPENAI_API_KEY → model.api_key (when provider=openai)
    """
    # Implementation: find file, yaml.safe_load, recursive merge into
    # dataclass defaults, then apply env var overrides.
    # Return frozen Config.
    ...
```

**Key rules:**
- Config file is optional. Everything has a sensible default.
- API keys come from standard env vars (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`), never stored in YAML.
- `base_url` enables pointing at any OpenAI/Anthropic-compatible endpoint (vLLM, Ollama, LiteLLM proxy, Azure, etc.)

---

### 6.2 llm.py

**Purpose:** Thin adapter that speaks to both OpenAI and Anthropic APIs. This is the critical module that makes tinyloom provider-agnostic.

**~200 lines.**

```python
"""
Two functions that matter:
  - chat()        → full response (for compaction summaries)
  - chat_stream() → async generator of events (for the agent loop)

Both accept a universal message format and return universal types.
Tool definitions are sent in the provider's native format.
"""
from dataclasses import dataclass, field
from typing import AsyncIterator
import json
import httpx


# ── Universal message types ──────────────────────────────────────

@dataclass
class Message:
    role: str                    # "user" | "assistant" | "tool_result"
    content: str = ""
    tool_calls: list["ToolCall"] = field(default_factory=list)
    tool_call_id: str = ""       # for tool_result messages
    name: str = ""               # tool name for tool_result


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class StreamEvent:
    """Yielded by chat_stream(). Exactly one field is set."""
    type: str                    # "text" | "tool_call" | "done" | "error"
    text: str = ""               # for type="text" (incremental delta)
    tool_call: ToolCall | None = None  # for type="tool_call" (complete)
    message: Message | None = None     # for type="done" (full assembled message)
    error: str = ""              # for type="error"


# ── Tool definition (provider-agnostic) ──────────────────────────

@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict           # JSON Schema object


# ── Provider adapter ─────────────────────────────────────────────

class LLMClient:
    """
    Thin wrapper around httpx that translates between our universal
    format and provider-specific API formats.
    """
    def __init__(self, config: "ModelConfig"):
        self.config = config
        self.client = httpx.AsyncClient(timeout=300)
        self._provider = self._detect_provider()

    def _detect_provider(self) -> str:
        """
        Detect from config.provider, or infer from model name.
        'claude' in model → anthropic, 'gpt/o1/o3' → openai.
        config.provider always wins if set.
        """
        ...

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        system: str = "",
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream a chat completion. Yields StreamEvents.
        Final event is always type="done" with the full assembled message.
        """
        if self._provider == "anthropic":
            async for event in self._stream_anthropic(messages, tools, system):
                yield event
        else:
            async for event in self._stream_openai(messages, tools, system):
                yield event

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        system: str = "",
    ) -> Message:
        """Non-streaming. Used for compaction summaries."""
        # Collect all events from chat_stream, return the final message.
        ...

    # ── Anthropic adapter ────────────────────────────────────────

    async def _stream_anthropic(self, messages, tools, system):
        """
        POST to /v1/messages with stream=true.

        Key format differences from OpenAI:
        - system prompt is a top-level param, not a message
        - tool results are sent as user messages with type="tool_result"
        - tool calls come as content blocks with type="tool_use"
        - streaming uses SSE with event types:
            message_start, content_block_start, content_block_delta,
            content_block_stop, message_delta, message_stop

        Message format translation:
        - Our Message(role="assistant", tool_calls=[...])
          → their { role: "assistant", content: [{type: "tool_use", ...}] }
        - Our Message(role="tool_result", tool_call_id=X, content=Y)
          → their { role: "user", content: [{type: "tool_result", tool_use_id: X, content: Y}] }
        """
        url = (self.config.base_url or "https://api.anthropic.com") + "/v1/messages"
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "stream": True,
            "messages": self._format_messages_anthropic(messages),
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [
                {"name": t.name, "description": t.description,
                 "input_schema": t.input_schema}
                for t in tools
            ]

        async with self.client.stream("POST", url, json=body, headers=headers) as resp:
            # Parse SSE events, accumulate tool_use blocks,
            # yield StreamEvent(type="text") for text deltas,
            # yield StreamEvent(type="tool_call") for complete tool calls,
            # yield StreamEvent(type="done") at message_stop
            ...

    def _format_messages_anthropic(self, messages: list[Message]) -> list[dict]:
        """
        Translate universal messages → Anthropic format.

        Critical rules:
        - Consecutive same-role messages must be merged (Anthropic requires
          alternating user/assistant)
        - tool_result messages become user messages with content blocks
        - assistant messages with tool_calls get content blocks of type tool_use
        """
        ...

    # ── OpenAI adapter ───────────────────────────────────────────

    async def _stream_openai(self, messages, tools, system):
        """
        POST to /v1/chat/completions with stream=true.

        Key format differences from Anthropic:
        - system prompt is a message with role="system"
        - tool calls come in the 'tool_calls' field of assistant messages
        - tool results are messages with role="tool"
        - streaming uses SSE with choices[0].delta

        Message format translation:
        - Our Message(role="tool_result", tool_call_id=X, content=Y)
          → their { role: "tool", tool_call_id: X, content: Y }
        - Our ToolCall → their { id, type: "function", function: {name, arguments} }
        """
        url = (self.config.base_url or "https://api.openai.com") + "/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "stream": True,
            "messages": self._format_messages_openai(messages, system),
        }
        if tools:
            body["tools"] = [
                {"type": "function", "function": {
                    "name": t.name, "description": t.description,
                    "parameters": t.input_schema,
                }}
                for t in tools
            ]

        async with self.client.stream("POST", url, json=body, headers=headers) as resp:
            # Parse SSE, accumulate tool_call deltas (OpenAI sends them
            # incrementally across multiple chunks), yield events
            ...

    def _format_messages_openai(self, messages, system) -> list[dict]:
        """
        Translate universal messages → OpenAI format.
        System prompt becomes first message with role="system".
        """
        ...

    # ── Token counting ───────────────────────────────────────────

    def count_tokens(self, messages: list[Message]) -> int:
        """
        Estimate token count for the conversation.
        - OpenAI models: use tiktoken with the correct encoding
        - Anthropic models: estimate as len(text) / 4
          (Anthropic doesn't publish a tokenizer; this is close enough
          for compaction threshold decisions)
        """
        ...
```

**Critical implementation notes:**

1. **SSE parsing:** Both APIs use Server-Sent Events. Parse with a simple line-by-line reader — don't pull in an SSE library. Pattern:
   ```python
   async for line in resp.aiter_lines():
       if line.startswith("data: "):
           data = json.loads(line[6:])
           # process event
   ```

2. **OpenAI tool call streaming quirk:** OpenAI streams tool calls incrementally — the `function.arguments` field arrives in chunks across multiple SSE events. You must accumulate these chunks by `tool_call.index` and only yield the complete ToolCall when the stream signals the call is done.

3. **Anthropic message merging:** Anthropic requires strictly alternating user/assistant messages. When the agent loop sends `[assistant_with_tool_calls, tool_result, tool_result]`, the multiple tool_result messages must be merged into a single user message with multiple content blocks.

4. **base_url makes this universal:** By allowing `base_url` override, tinyloom works with any OpenAI-compatible API (vLLM, Ollama, Together, Groq, LM Studio, Azure OpenAI, etc.) and any Anthropic-compatible proxy.

---

### 6.3 tools.py

**Purpose:** Tool definition, registration, and dispatch.

**~80 lines.**

```python
"""
A tool is a dataclass + a function. That's it.
The registry is a dict. No metaclasses, no decorators-that-return-decorators.
"""
from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict            # JSON Schema
    function: Callable[[dict], str]  # takes parsed input dict, returns string result

    def to_def(self) -> "ToolDef":
        """Convert to LLM-facing ToolDef (no function reference)."""
        from tinyloom.llm import ToolDef
        return ToolDef(name=self.name, description=self.description,
                       input_schema=self.input_schema)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all_defs(self) -> list["ToolDef"]:
        return [t.to_def() for t in self._tools.values()]

    def execute(self, name: str, input_data: dict) -> str:
        """
        Execute a tool by name. Returns result string.
        If tool not found, returns error string (don't crash — let the LLM retry).
        Catches exceptions and returns them as error strings too.
        """
        tool = self._tools.get(name)
        if not tool:
            return f"Error: unknown tool '{name}'"
        try:
            return tool.function(input_data)
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"
```

**Helper to define tools concisely:**

```python
def tool(name: str, description: str, input_schema: dict):
    """Decorator to turn a function into a Tool."""
    def decorator(fn):
        return Tool(name=name, description=description,
                    input_schema=input_schema, function=fn)
    return decorator
```

**Usage in builtins:**
```python
@tool(
    name="read",
    description="Read the contents of a file at the given path.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to read"}
        },
        "required": ["path"]
    }
)
def read_tool(input: dict) -> str:
    path = input["path"]
    return Path(path).read_text()
```

---

### 6.4 agent.py

**Purpose:** THE LOOP. This is the beating heart.

**~150 lines.**

```python
"""
The agent loop. Must fit on one screen.
Everything complex lives in other modules.
"""
import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable

from tinyloom.llm import LLMClient, Message, ToolCall, StreamEvent
from tinyloom.tools import ToolRegistry
from tinyloom.hooks import HookRunner
from tinyloom.compaction import maybe_compact
from tinyloom.events import AgentEvent, event
from tinyloom.config import Config


@dataclass
class AgentState:
    messages: list[Message] = field(default_factory=list)
    turn: int = 0


class Agent:
    def __init__(
        self,
        config: Config,
        tool_registry: ToolRegistry,
        hooks: HookRunner,
        llm: LLMClient | None = None,
    ):
        self.config = config
        self.tools = tool_registry
        self.hooks = hooks
        self.llm = llm or LLMClient(config.model)
        self.state = AgentState()

    async def run(self, initial_prompt: str | None = None) -> AsyncIterator[AgentEvent]:
        """
        Run the agent. Yields AgentEvents for the UI/CLI to consume.

        This is the entire agent algorithm:
        1. Add user message
        2. Maybe compact context
        3. Call LLM (streaming)
        4. If LLM made tool calls → execute them → goto 2
        5. If LLM produced text → yield it → wait for next user message → goto 1
        """
        await self.hooks.run("agent_start", agent=self)
        yield event("agent_start")

        if initial_prompt:
            self._add_user_message(initial_prompt)

        while self.state.turn < self.config.max_turns:
            # ── Compaction check ─────────────────────────────
            if self.config.compaction.enabled:
                compacted = await maybe_compact(
                    self.llm, self.state.messages,
                    self.config.model.context_window,
                    self.config.compaction.threshold,
                    self.config.compaction.strategy,
                )
                if compacted:
                    self.state.messages = compacted
                    yield event("compaction")

            # ── LLM call ─────────────────────────────────────
            self.state.turn += 1
            await self.hooks.run("pre_llm", messages=self.state.messages)

            assistant_msg = Message(role="assistant")
            tool_calls: list[ToolCall] = []

            async for stream_evt in self.llm.chat_stream(
                messages=self.state.messages,
                tools=self.tools.all_defs(),
                system=self.config.system_prompt,
            ):
                if stream_evt.type == "text":
                    yield event("text_delta", text=stream_evt.text)
                elif stream_evt.type == "tool_call":
                    tool_calls.append(stream_evt.tool_call)
                    yield event("tool_call", tool_call=stream_evt.tool_call)
                elif stream_evt.type == "done":
                    assistant_msg = stream_evt.message

            await self.hooks.run("post_llm", message=assistant_msg)
            self.state.messages.append(assistant_msg)

            # ── Tool execution ───────────────────────────────
            if tool_calls:
                for tc in tool_calls:
                    await self.hooks.run("pre_tool", tool_name=tc.name, input=tc.input)

                    result = self.tools.execute(tc.name, tc.input)

                    await self.hooks.run("post_tool", tool_name=tc.name, result=result)

                    yield event("tool_result", tool_call_id=tc.id,
                                tool_name=tc.name, result=result)

                    self.state.messages.append(Message(
                        role="tool_result",
                        tool_call_id=tc.id,
                        name=tc.name,
                        content=result,
                    ))

                continue  # ← goto 2: call LLM again with tool results

            # ── No tool calls: response complete ─────────────
            yield event("response_complete", message=assistant_msg)
            break  # wait for next user message

        await self.hooks.run("agent_stop", agent=self)
        yield event("agent_stop")

    def _add_user_message(self, text: str):
        self.state.messages.append(Message(role="user", content=text))

    async def step(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """
        Process one user message. For interactive mode.
        Adds the message then runs the loop until the LLM responds
        without tool calls (or hits max_turns).
        """
        self._add_user_message(user_input)
        # Reset turn counter for this interaction
        self.state.turn = 0
        async for evt in self.run():
            if evt.type == "agent_start":
                continue  # skip for step mode
            yield evt
```

**Critical notes about the loop:**

1. **The `continue` is the entire tool loop mechanism.** When tool calls are present, we execute them, append results, and `continue` — which goes back to the top and calls the LLM again. This is exactly the Thorsten Ball pattern.

2. **Streaming + tool calls:** The LLM streams text and tool calls. We accumulate tool calls from stream events. Only after the stream is done do we execute tools. This is correct — you can't execute a tool call until you have the complete input JSON.

3. **The loop is an AsyncIterator.** It yields events, and the consumer (TUI or CLI) decides how to render them. This decouples the agent logic from presentation completely.

---

### 6.5 Built-in Tools

Each tool is one small file in `tinyloom/builtins/`. All tools follow the same pattern: a `@tool` decorated function.

#### read.py (~25 lines)
```python
from pathlib import Path
from tinyloom.tools import tool

@tool(
    name="read",
    description=(
        "Read the contents of a file at the given path. "
        "Returns the file contents as a string. "
        "Use this to examine existing files before editing them."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative or absolute file path to read"
            }
        },
        "required": ["path"]
    }
)
def read_tool(input: dict) -> str:
    p = Path(input["path"])
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    if not p.is_file():
        raise ValueError(f"Not a file: {p}")
    content = p.read_text(encoding="utf-8", errors="replace")
    # Optionally add line numbers for large files
    if content.count("\n") > 50:
        lines = content.splitlines(True)
        return "".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))
    return content
```

#### write.py (~30 lines)
```python
from pathlib import Path
from tinyloom.tools import tool

@tool(
    name="write",
    description=(
        "Write content to a file. Creates the file if it doesn't exist. "
        "Creates parent directories as needed. "
        "WARNING: This overwrites the entire file. For partial edits, use the 'edit' tool."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to write to"},
            "content": {"type": "string", "description": "Complete file content to write"}
        },
        "required": ["path", "content"]
    }
)
def write_tool(input: dict) -> str:
    p = Path(input["path"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(input["content"], encoding="utf-8")
    return f"Successfully wrote {len(input['content'])} bytes to {p}"
```

#### edit.py (~45 lines)
```python
from pathlib import Path
from tinyloom.tools import tool

@tool(
    name="edit",
    description=(
        "Edit a file by replacing an exact string match with new content. "
        "The old_str must match exactly ONE location in the file. "
        "If old_str is empty and the file doesn't exist, creates the file with new_str. "
        "Always read the file first to see the exact content before editing."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to edit"},
            "old_str": {
                "type": "string",
                "description": "Exact string to find and replace (must be unique in file)"
            },
            "new_str": {
                "type": "string",
                "description": "Replacement string"
            }
        },
        "required": ["path", "old_str", "new_str"]
    }
)
def edit_tool(input: dict) -> str:
    p = Path(input["path"])
    old_str = input["old_str"]
    new_str = input["new_str"]

    if old_str == new_str:
        raise ValueError("old_str and new_str must be different")

    if not p.exists():
        if old_str == "":
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(new_str, encoding="utf-8")
            return f"Created new file: {p}"
        raise FileNotFoundError(f"File not found: {p}")

    content = p.read_text(encoding="utf-8")
    count = content.count(old_str)
    if count == 0:
        raise ValueError(f"old_str not found in {p}")
    if count > 1:
        raise ValueError(f"old_str found {count} times in {p} (must be unique)")

    new_content = content.replace(old_str, new_str, 1)
    p.write_text(new_content, encoding="utf-8")
    return f"Successfully edited {p}"
```

#### grep.py (~35 lines)
```python
import subprocess
from tinyloom.tools import tool

@tool(
    name="grep",
    description=(
        "Search for a pattern in files using ripgrep (rg) or grep. "
        "Returns matching lines with file paths and line numbers. "
        "Use this to find code, definitions, usages, etc."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Search pattern (regex)"},
            "path": {
                "type": "string",
                "description": "Directory or file to search in. Defaults to '.'",
                "default": "."
            },
            "flags": {
                "type": "string",
                "description": "Additional flags, e.g. '-i' for case-insensitive",
                "default": ""
            }
        },
        "required": ["pattern"]
    }
)
def grep_tool(input: dict) -> str:
    pattern = input["pattern"]
    path = input.get("path", ".")
    flags = input.get("flags", "")

    # Try ripgrep first, fall back to grep
    for cmd_base in ["rg", "grep -rn"]:
        cmd = f"{cmd_base} {flags} {pattern!r} {path}"
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            if result.returncode <= 1:  # 0=found, 1=not found
                return result.stdout or "No matches found."
        except FileNotFoundError:
            continue
    return "Error: neither 'rg' nor 'grep' available"
```

#### bash.py (~40 lines)
```python
import subprocess
from tinyloom.tools import tool

@tool(
    name="bash",
    description=(
        "Execute a shell command and return its output. "
        "Use this for running tests, installing packages, git operations, "
        "listing directories, or any shell operation. "
        "Commands run in the current working directory. "
        "Timeout: 120 seconds."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 120)",
                "default": 120
            }
        },
        "required": ["command"]
    }
)
def bash_tool(input: dict) -> str:
    cmd = input["command"]
    timeout = input.get("timeout", 120)

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd="."
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
```

#### exec.py (~50 lines)
```python
"""
The sub-agent tool. Spawns a NEW instance of tinyloom with a
specific prompt/config, runs it to completion, returns its output.
This is how tinyloom does "multi-agent" — by forking itself.
"""
import asyncio
import json
from tinyloom.tools import tool

@tool(
    name="exec",
    description=(
        "Launch a sub-agent to handle a specific task. "
        "The sub-agent is a fresh instance of tinyloom with its own context. "
        "Use this to delegate focused tasks like: "
        "'write tests for module X', 'refactor this file', 'research this API'. "
        "The sub-agent has access to all the same tools. "
        "Returns the sub-agent's final text response."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "The task/prompt for the sub-agent"
            },
            "model": {
                "type": "string",
                "description": "Override model for sub-agent (optional)",
                "default": ""
            },
            "system_prompt": {
                "type": "string",
                "description": "Override system prompt for sub-agent (optional)",
                "default": ""
            }
        },
        "required": ["task"]
    }
)
def exec_tool(input: dict) -> str:
    """
    Implementation approach: Don't shell out to `tinyloom` CLI.
    Instead, import and instantiate a new Agent directly in-process.
    This avoids subprocess overhead and shares the config.

    The sub-agent runs headless with no user interaction —
    it gets one prompt and runs to completion.
    """
    from tinyloom.agent import Agent
    from tinyloom.config import load_config

    config = load_config()
    if input.get("model"):
        config.model.model = input["model"]
    if input.get("system_prompt"):
        config.system_prompt = input["system_prompt"]

    # Build a sub-agent with the same tools (except exec, to prevent infinite recursion)
    # Implementation: create registry, register all builtins except exec,
    # instantiate Agent, run it with the task as initial_prompt,
    # collect all text events, return concatenated response.

    async def _run_sub():
        from tinyloom.builtins import get_all_tools
        from tinyloom.tools import ToolRegistry
        from tinyloom.hooks import HookRunner

        registry = ToolRegistry()
        for t in get_all_tools():
            if t.name != "exec":  # prevent recursion
                registry.register(t)

        sub_agent = Agent(config=config, tool_registry=registry, hooks=HookRunner())
        output_parts = []
        async for evt in sub_agent.run(initial_prompt=input["task"]):
            if evt.type == "text_delta":
                output_parts.append(evt.text)
            elif evt.type == "response_complete":
                break
        return "".join(output_parts)

    return asyncio.run(_run_sub())
```

#### builtins/\_\_init\_\_.py
```python
from tinyloom.builtins.read import read_tool
from tinyloom.builtins.write import write_tool
from tinyloom.builtins.edit import edit_tool
from tinyloom.builtins.grep import grep_tool
from tinyloom.builtins.bash import bash_tool
from tinyloom.builtins.exec import exec_tool

ALL_TOOLS = [read_tool, write_tool, edit_tool, grep_tool, bash_tool, exec_tool]

def get_all_tools():
    return list(ALL_TOOLS)
```

---

### 6.6 mcp.py

**Purpose:** Load MCP servers from `.mcp.json`, connect to them, and register their tools.

**~120 lines.**

```python
"""
MCP (Model Context Protocol) client.

Reads .mcp.json to discover MCP servers.
Launches them as subprocesses (stdio transport).
Discovers their tools and wraps them as tinyloom Tools.

.mcp.json format (same as Claude Code / Cursor):
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "env": {}
    }
  }
}
"""
import json
from pathlib import Path
from typing import Any

from tinyloom.tools import Tool, ToolRegistry


def load_mcp_json(path: str | Path | None = None) -> dict:
    """
    Find and load .mcp.json. Search order:
    1. Explicit path
    2. ./.mcp.json
    3. ~/.config/tinyloom/.mcp.json
    """
    candidates = [path, Path(".mcp.json"), Path.home() / ".config/tinyloom/.mcp.json"]
    for p in candidates:
        if p and Path(p).exists():
            return json.loads(Path(p).read_text())
    return {}


async def register_mcp_tools(registry: ToolRegistry, mcp_config: dict):
    """
    For each server in mcp_config["mcpServers"]:
    1. Launch the server subprocess (stdio transport)
    2. Send initialize request
    3. Call tools/list to discover tools
    4. Wrap each tool as a tinyloom Tool
    5. Register it

    Uses the official `mcp` Python SDK if available.
    Falls back to a minimal stdio JSON-RPC implementation.
    """
    servers = mcp_config.get("mcpServers", {})

    for server_name, server_config in servers.items():
        try:
            tools = await _connect_and_discover(server_name, server_config)
            for tool in tools:
                registry.register(tool)
        except Exception as e:
            # Log warning but don't crash — MCP servers are optional
            import sys
            print(f"Warning: MCP server '{server_name}' failed: {e}", file=sys.stderr)


async def _connect_and_discover(name: str, config: dict) -> list[Tool]:
    """
    Connect to an MCP server via stdio and discover its tools.

    Minimal implementation (no mcp SDK dependency):
    1. Launch subprocess with config["command"] + config["args"]
    2. Send JSON-RPC: {"method": "initialize", ...}
    3. Send JSON-RPC: {"method": "tools/list"}
    4. For each tool, create a Tool where the function sends
       {"method": "tools/call", "params": {"name": ..., "arguments": ...}}
    """
    try:
        # Try the official MCP SDK first
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command=config["command"],
            args=config.get("args", []),
            env=config.get("env"),
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                mcp_tools = await session.list_tools()

                result = []
                for mt in mcp_tools.tools:
                    # Capture session and tool name in closure
                    result.append(_mcp_tool_to_tinyloom(session, mt))
                return result

    except ImportError:
        # Fallback: minimal JSON-RPC over stdio
        return await _minimal_mcp_connect(name, config)


def _mcp_tool_to_tinyloom(session, mcp_tool) -> Tool:
    """Wrap an MCP tool as a tinyloom Tool."""
    tool_name = mcp_tool.name

    def call_mcp(input_data: dict) -> str:
        """Synchronous wrapper around async MCP call."""
        import asyncio
        result = asyncio.run(session.call_tool(tool_name, arguments=input_data))
        # MCP tool results have .content which is a list of content blocks
        return "\n".join(
            block.text for block in result.content
            if hasattr(block, "text")
        )

    return Tool(
        name=f"mcp_{tool_name}",  # prefix to avoid name collisions
        description=mcp_tool.description or f"MCP tool: {tool_name}",
        input_schema=mcp_tool.inputSchema or {"type": "object", "properties": {}},
        function=call_mcp,
    )
```

**Important notes:**
- MCP servers stay running as long as the agent session is active. The session object holds the subprocess.
- The `mcp` SDK handles the lifecycle. If using the minimal fallback, we manage the subprocess ourselves.
- Tool names are prefixed with `mcp_` to avoid collisions with builtins.
- MCP is the ONLY optional dependency. Everything else works without it.

---

### 6.7 hooks.py

**Purpose:** Simple lifecycle hook system. Hooks are async callables.

**~60 lines.**

```python
"""
Hooks are async functions called at specific points in the agent lifecycle.

Events:
  agent_start  — agent begins running
  agent_stop   — agent finishes
  pre_llm      — before each LLM call (receives messages)
  post_llm     — after each LLM response (receives message)
  pre_tool     — before tool execution (receives tool_name, input)
  post_tool    — after tool execution (receives tool_name, result)
  compaction   — after context is compacted

Hooks receive **kwargs — they pick what they need.
"""
from typing import Callable, Any


HookFn = Callable[..., Any]  # async or sync callable


class HookRunner:
    def __init__(self):
        self._hooks: dict[str, list[HookFn]] = {}

    def on(self, event: str, fn: HookFn):
        """Register a hook for an event."""
        self._hooks.setdefault(event, []).append(fn)

    async def run(self, event: str, **kwargs):
        """Run all hooks for an event. Exceptions are logged, not raised."""
        for fn in self._hooks.get(event, []):
            try:
                result = fn(**kwargs)
                # Support both sync and async hooks
                if hasattr(result, "__await__"):
                    await result
            except Exception as e:
                import sys
                print(f"Hook error ({event}): {e}", file=sys.stderr)

    def register_from_config(self, config_hooks: dict[str, list[str]]):
        """
        Load hooks from config. Format:
          hooks:
            pre_tool:
              - mypackage.hooks.log_tool_call
            post_tool:
              - mypackage.hooks.validate_output

        Each value is a dotted path to an importable callable.
        """
        for event, paths in config_hooks.items():
            for dotted_path in paths:
                module_path, _, func_name = dotted_path.rpartition(".")
                import importlib
                module = importlib.import_module(module_path)
                fn = getattr(module, func_name)
                self.on(event, fn)
```

---

### 6.8 plugins.py

**Purpose:** Load third-party extensions via Python entry_points.

**~40 lines.**

```python
"""
Plugins use Python's entry_points mechanism (PEP 621).

A plugin is a package that declares an entry point:

    [project.entry-points."tinyloom.plugins"]
    my_plugin = "my_package:activate"

The `activate` function receives the Agent and can:
  - Register new tools
  - Register hooks
  - Modify config
  - Whatever else they want
"""
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tinyloom.agent import Agent


def load_plugins(agent: "Agent"):
    """Discover and activate all installed tinyloom plugins."""
    try:
        from importlib.metadata import entry_points
        eps = entry_points(group="tinyloom.plugins")
    except Exception:
        return

    for ep in eps:
        try:
            activate_fn = ep.load()
            activate_fn(agent)
        except Exception as e:
            import sys
            print(f"Plugin error ({ep.name}): {e}", file=sys.stderr)


def load_plugins_from_config(agent: "Agent", plugin_paths: list[str]):
    """
    Load plugins from config:
      plugins:
        - mypackage.plugin_module:activate
    """
    for path in plugin_paths:
        module_path, _, func_name = path.rpartition(":")
        if not func_name:
            func_name = "activate"
        import importlib
        module = importlib.import_module(module_path)
        fn = getattr(module, func_name)
        fn(agent)
```

---

### 6.9 compaction.py

**Purpose:** Prevent context window overflow by compacting the conversation.

**~100 lines.**

```python
"""
When the conversation approaches the context window limit,
we compact it to free up space.

Two strategies:
  1. "summarize" — ask the LLM to summarize the conversation so far,
     replace everything except the system prompt and last few messages
  2. "truncate" — drop the oldest messages, keeping a system message
     that says "[earlier conversation truncated]"

Token counting:
  - OpenAI models: tiktoken
  - Anthropic models: len(text) // 4 (good enough for threshold decisions)
"""
from tinyloom.llm import LLMClient, Message


def estimate_tokens(messages: list[Message], model: str = "") -> int:
    """
    Estimate total token count for a conversation.
    """
    text = ""
    for msg in messages:
        text += msg.content
        for tc in msg.tool_calls:
            text += tc.name + str(tc.input)

    # Try tiktoken for OpenAI models
    if any(prefix in model for prefix in ("gpt", "o1", "o3", "o4")):
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model(model)
            return len(enc.encode(text))
        except Exception:
            pass

    # Fallback: ~4 chars per token (works well enough for threshold checks)
    return len(text) // 4


async def maybe_compact(
    llm: LLMClient,
    messages: list[Message],
    context_window: int,
    threshold: float,
    strategy: str,
) -> list[Message] | None:
    """
    Check if compaction is needed and perform it.
    Returns compacted messages, or None if no compaction needed.
    """
    current_tokens = estimate_tokens(messages, llm.config.model)
    limit = int(context_window * threshold)

    if current_tokens < limit:
        return None

    if strategy == "truncate":
        return _truncate(messages)
    else:
        return await _summarize(llm, messages)


def _truncate(messages: list[Message]) -> list[Message]:
    """Keep the last N messages that fit in ~50% of context."""
    marker = Message(role="user", content="[Previous conversation was truncated]")
    # Keep last 10 messages (heuristic — keeps enough recent context)
    recent = messages[-10:]
    return [marker] + recent


async def _summarize(llm: LLMClient, messages: list[Message]) -> list[Message]:
    """
    Ask the LLM to summarize the conversation, then replace
    old messages with the summary.
    """
    # Build a summary prompt
    conversation_text = "\n".join(
        f"[{m.role}]: {m.content[:500]}" for m in messages
    )

    summary_prompt = [Message(
        role="user",
        content=(
            "Summarize the following conversation concisely. "
            "Include: what task is being worked on, what files were modified, "
            "what's been accomplished, and what still needs to be done. "
            "Be specific about file names and code changes.\n\n"
            f"{conversation_text}"
        )
    )]

    summary_msg = await llm.chat(summary_prompt)

    # Replace conversation with: summary + last 4 messages
    summary = Message(
        role="user",
        content=f"[Conversation summary: {summary_msg.content}]"
    )
    recent = messages[-4:]
    return [summary] + recent
```

---

### 6.10 tui.py

**Purpose:** Interactive terminal UI using rich + prompt_toolkit.

**~150 lines.**

```python
"""
Minimal TUI:
  - Colored prompt (user input with history)
  - Streaming assistant text (with markdown rendering)
  - Tool call display (name + truncated input)
  - Spinner during LLM calls
  - Status bar showing model name and token estimate

Uses:
  - rich: for markdown rendering, syntax highlighting, panels, spinners
  - prompt_toolkit: for input with history, multi-line support, ctrl-c handling
"""
import asyncio
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from tinyloom.agent import Agent
from tinyloom.events import AgentEvent


class TUI:
    def __init__(self, agent: Agent):
        self.agent = agent
        self.console = Console()
        self.session = PromptSession(
            history=FileHistory(".tinyloom_history"),
        )

    async def run(self):
        """Main interactive loop."""
        self.console.print(
            Panel(
                f"[bold]tinyloom[/bold] — {self.agent.config.model.model}\n"
                "Type your message. Ctrl+C to exit. /help for commands.",
                style="dim",
            )
        )

        while True:
            try:
                # Get user input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.session.prompt("\n❯ ")
                )
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[dim]Goodbye![/dim]")
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                self._handle_command(user_input)
                continue

            # Process through agent
            await self._process(user_input)

    async def _process(self, user_input: str):
        """Stream agent response to the terminal."""
        text_buffer = ""

        async for evt in self.agent.step(user_input):
            if evt.type == "text_delta":
                text_buffer += evt.text
                # Print incrementally (simple approach)
                print(evt.text, end="", flush=True)

            elif evt.type == "tool_call":
                tc = evt.tool_call
                input_preview = str(tc.input)[:100]
                self.console.print(
                    f"\n[green]⚡ {tc.name}[/green]([dim]{input_preview}[/dim])"
                )

            elif evt.type == "tool_result":
                result_preview = evt.result[:200] if evt.result else "(empty)"
                self.console.print(f"[dim]   → {result_preview}[/dim]")

            elif evt.type == "response_complete":
                if text_buffer:
                    print()  # newline after streamed text

            elif evt.type == "compaction":
                self.console.print("[dim yellow]⟳ Context compacted[/dim yellow]")

            elif evt.type == "error":
                self.console.print(f"[red]Error: {evt.error}[/red]")

    def _handle_command(self, cmd: str):
        """Handle /slash commands."""
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()

        if command == "/help":
            self.console.print(
                "[bold]Commands:[/bold]\n"
                "  /help     — show this help\n"
                "  /clear    — clear conversation history\n"
                "  /compact  — force context compaction\n"
                "  /model    — show current model\n"
                "  /tokens   — show estimated token count\n"
                "  /quit     — exit"
            )
        elif command == "/clear":
            self.agent.state.messages.clear()
            self.console.print("[dim]Conversation cleared.[/dim]")
        elif command == "/model":
            self.console.print(f"Model: {self.agent.config.model.model}")
        elif command == "/tokens":
            from tinyloom.compaction import estimate_tokens
            tokens = estimate_tokens(
                self.agent.state.messages,
                self.agent.config.model.model
            )
            window = self.agent.config.model.context_window
            self.console.print(f"Tokens: ~{tokens:,} / {window:,} ({tokens/window:.0%})")
        elif command == "/quit":
            raise KeyboardInterrupt
        else:
            self.console.print(f"[red]Unknown command: {command}[/red]")
```

---

### 6.11 cli.py

**Purpose:** Entry point. Parses args, wires everything together, launches TUI or headless mode.

**~100 lines.**

```python
"""
Usage:
  tinyloom                          # interactive TUI
  tinyloom "fix the tests"          # headless: run prompt, JSON stream to stdout
  tinyloom -m gpt-4o "do X"        # override model
  tinyloom --config my.yaml "X"     # custom config
  echo "task" | tinyloom --stdin    # pipe mode
"""
import argparse
import asyncio
import json
import sys

from tinyloom.config import load_config
from tinyloom.llm import LLMClient
from tinyloom.tools import ToolRegistry
from tinyloom.builtins import get_all_tools
from tinyloom.hooks import HookRunner
from tinyloom.plugins import load_plugins, load_plugins_from_config
from tinyloom.mcp import load_mcp_json, register_mcp_tools
from tinyloom.agent import Agent


def main():
    parser = argparse.ArgumentParser(description="tinyloom — tiny coding agent")
    parser.add_argument("prompt", nargs="?", help="Prompt (headless mode)")
    parser.add_argument("-m", "--model", help="Override model")
    parser.add_argument("-p", "--provider", help="Override provider")
    parser.add_argument("--config", help="Config file path")
    parser.add_argument("--stdin", action="store_true", help="Read prompt from stdin")
    parser.add_argument("--json", action="store_true", help="Force JSON output")
    parser.add_argument("--system", help="Override system prompt")
    parser.add_argument("--no-mcp", action="store_true", help="Disable MCP")
    parser.add_argument("--no-plugins", action="store_true", help="Disable plugins")
    args = parser.parse_args()

    asyncio.run(_run(args))


async def _run(args):
    # ── Load config ──────────────────────────────────────
    config = load_config(args.config)
    if args.model:
        config.model.model = args.model
    if args.provider:
        config.model.provider = args.provider
    if args.system:
        config.system_prompt = args.system

    # ── Build tool registry ──────────────────────────────
    registry = ToolRegistry()
    for tool in get_all_tools():
        if config.allowed_tools is None or tool.name in config.allowed_tools:
            registry.register(tool)

    # ── Load MCP tools ───────────────────────────────────
    if not args.no_mcp:
        mcp_config = load_mcp_json()
        # Also merge MCP servers from tinyloom.yaml
        for name, srv in config.mcp_servers.items():
            mcp_config.setdefault("mcpServers", {})[name] = {
                "command": srv.command, "args": srv.args, "env": srv.env
            }
        if mcp_config.get("mcpServers"):
            await register_mcp_tools(registry, mcp_config)

    # ── Build hooks ──────────────────────────────────────
    hooks = HookRunner()
    hooks.register_from_config(config.hooks)

    # ── Build agent ──────────────────────────────────────
    llm = LLMClient(config.model)
    agent = Agent(config=config, tool_registry=registry, hooks=hooks, llm=llm)

    # ── Load plugins ─────────────────────────────────────
    if not args.no_plugins:
        load_plugins(agent)
        load_plugins_from_config(agent, config.plugins)

    # ── Determine mode ───────────────────────────────────
    prompt = args.prompt
    if args.stdin:
        prompt = sys.stdin.read().strip()

    if prompt:
        # Headless mode: JSON stream to stdout
        await _run_headless(agent, prompt)
    else:
        # Interactive TUI
        from tinyloom.tui import TUI
        tui = TUI(agent)
        await tui.run()


async def _run_headless(agent: Agent, prompt: str):
    """Run headless with JSON stream output."""
    async for evt in agent.run(initial_prompt=prompt):
        # Emit each event as a JSON line
        print(json.dumps(evt.to_dict()), flush=True)


if __name__ == "__main__":
    main()
```

**pyproject.toml entry point:**
```toml
[project.scripts]
tinyloom = "tinyloom.cli:main"
```

---

### 6.12 events.py

**Purpose:** Event types for the JSON stream and UI.

**~40 lines.**

```python
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class AgentEvent:
    type: str
    text: str = ""
    tool_call: Any = None   # ToolCall or None
    tool_call_id: str = ""
    tool_name: str = ""
    result: str = ""
    message: Any = None     # Message or None
    error: str = ""

    def to_dict(self) -> dict:
        """Serialize for JSON output. Drops None fields."""
        d = {"type": self.type}
        if self.text:
            d["text"] = self.text
        if self.tool_call:
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
        if self.message:
            d["message"] = {"role": self.message.role, "content": self.message.content}
        if self.error:
            d["error"] = self.error
        return d


def event(type: str, **kwargs) -> AgentEvent:
    return AgentEvent(type=type, **kwargs)
```

---

## 7. Config Schema

**`tinyloom.example.yaml`:**

```yaml
# tinyloom configuration
# All fields are optional — defaults work out of the box.

model:
  provider: anthropic                    # anthropic | openai
  model: claude-sonnet-4-20250514    # any model identifier
  # base_url: https://my-proxy.com/v1  # custom endpoint
  max_tokens: 8192                       # max output tokens per response
  context_window: 200000                 # total context window
  temperature: 0.0

system_prompt: |
  You are a skilled coding assistant. You have access to tools for
  reading, writing, and editing files, searching code, and running
  shell commands. Be concise. When editing files, always read them
  first to see the exact content.

compaction:
  enabled: true
  threshold: 0.7            # compact at 70% of context window
  strategy: summarize       # summarize | truncate

# Tool whitelist (null = all tools allowed)
# allowed_tools:
#   - read
#   - write
#   - edit
#   - grep
#   - bash

# MCP servers (merged with .mcp.json)
mcp_servers:
  # example:
  # filesystem:
  #   command: npx
  #   args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]

# Lifecycle hooks (dotted paths to importable callables)
hooks:
  # pre_tool:
  #   - my_hooks.log_tool_call
  # post_tool:
  #   - my_hooks.validate_output

# Plugins (dotted paths with optional :function)
plugins:
  # - my_plugin_package:activate

max_turns: 200              # safety limit per interaction
```

---

## 8. JSON Stream Output Schema

In headless mode (`tinyloom "prompt"`), stdout is newline-delimited JSON (JSONL). Each line is one event:

```jsonl
{"type": "agent_start"}
{"type": "text_delta", "text": "I'll help you "}
{"type": "text_delta", "text": "fix that bug. "}
{"type": "text_delta", "text": "Let me read the file first."}
{"type": "tool_call", "tool_call": {"id": "tc_01", "name": "read", "input": {"path": "main.py"}}}
{"type": "tool_result", "tool_call_id": "tc_01", "tool_name": "read", "result": "import sys\n..."}
{"type": "text_delta", "text": "I see the issue. "}
{"type": "text_delta", "text": "The bug is on line 42..."}
{"type": "tool_call", "tool_call": {"id": "tc_02", "name": "edit", "input": {"path": "main.py", "old_str": "x = 1", "new_str": "x = 2"}}}
{"type": "tool_result", "tool_call_id": "tc_02", "tool_name": "edit", "result": "Successfully edited main.py"}
{"type": "text_delta", "text": "Fixed! The variable was set incorrectly."}
{"type": "response_complete", "message": {"role": "assistant", "content": "I'll help you fix that bug..."}}
{"type": "agent_stop"}
```

**Event types:**

| type | fields | when |
|---|---|---|
| `agent_start` | — | agent begins |
| `text_delta` | `text` | incremental LLM text |
| `tool_call` | `tool_call` | LLM requests a tool |
| `tool_result` | `tool_call_id`, `tool_name`, `result` | tool execution complete |
| `compaction` | — | context was compacted |
| `response_complete` | `message` | LLM finished (no more tool calls) |
| `agent_stop` | — | agent done |
| `error` | `error` | something went wrong |

---

## 9. Key Design Decisions & Rationale

**1. httpx, not litellm.**
Litellm is ~50k LOC with 100+ transitive deps. We need two HTTP adapters (~200 lines). The cost of litellm is too high for "extremely small codebase."

**2. String replacement for editing, not diffs/patches.**
This is proven by Claude Code, Amp, Cursor, and others. LLMs are excellent at generating exact string matches. It's simpler to implement and less error-prone than generating unified diffs.

**3. `exec` spawns in-process, not via subprocess.**
Shelling out to `tinyloom` CLI would require serializing config, parsing args again, etc. In-process is simpler, faster, and shares config. We prevent infinite recursion by excluding `exec` from sub-agent tools.

**4. Async throughout.**
LLM streaming is inherently async. Making the agent loop async from the start avoids painful refactors later. The TUI uses `run_in_executor` for prompt_toolkit input.

**5. Events as the universal output interface.**
Both TUI and headless mode consume the same `AsyncIterator[AgentEvent]`. This ensures feature parity and makes testing easy (just collect events).

**6. MCP is the extension mechanism for tools.**
Rather than inventing a custom tool plugin format, we lean on MCP — an industry standard. Third parties write MCP servers, tinyloom consumes them. The `plugins` system exists for non-tool extensions (hooks, config modifications, etc.).

**7. No agent "framework" abstractions.**
No `Chain`, no `Pipeline`, no `Graph`, no `Node`. Just a while loop with an if statement. The ampcode article proves this is all you need.

---

## 10. Implementation Phases

### Phase 1: Chatbot (~Day 1)
**Goal:** `tinyloom "hello"` works and gets a response from Claude.

Files to build:
1. `pyproject.toml` (deps, entry point)
2. `tinyloom/__init__.py`
3. `tinyloom/config.py`
4. `tinyloom/llm.py` (Anthropic streaming only — skip OpenAI for now)
5. `tinyloom/events.py`
6. `tinyloom/agent.py` (no tool support yet)
7. `tinyloom/hooks.py` (stub)
8. `tinyloom/tools.py` (empty registry)
9. `tinyloom/cli.py` (headless only)

Test: `ANTHROPIC_API_KEY=xxx tinyloom "what is 2+2"` → JSON stream with text_delta events.

### Phase 2: Tools (~Day 2)
**Goal:** Agent can read/write/edit files, grep, run bash.

Files to build:
1. `tinyloom/builtins/read.py`
2. `tinyloom/builtins/write.py`
3. `tinyloom/builtins/edit.py`
4. `tinyloom/builtins/grep.py`
5. `tinyloom/builtins/bash.py`
6. `tinyloom/builtins/__init__.py`
7. Update `agent.py` — add tool execution loop
8. Update `llm.py` — send tool definitions, handle tool_use responses

Test: `tinyloom "create a hello.py that prints hello world, then run it"` → creates file + runs it.

### Phase 3: Interactive TUI (~Day 3)
**Goal:** `tinyloom` (no args) launches interactive mode.

Files to build:
1. `tinyloom/tui.py`
2. Update `cli.py` — interactive vs headless routing

Test: Launch `tinyloom`, have a multi-turn conversation editing files.

### Phase 4: OpenAI Support (~Day 3-4)
**Goal:** `tinyloom -p openai -m gpt-4o "fix tests"` works.

Files to update:
1. `llm.py` — implement `_stream_openai` and `_format_messages_openai`

Test: Same workflows with OpenAI models.

### Phase 5: Extensions (~Day 4-5)
**Goal:** MCP, hooks, plugins, compaction, exec all work.

Files to build:
1. `tinyloom/mcp.py`
2. `tinyloom/plugins.py`
3. `tinyloom/compaction.py`
4. `tinyloom/builtins/exec.py`
5. Update `hooks.py` — register from config
6. Update `cli.py` — wire in MCP, plugins

Test: Add an MCP server to `.mcp.json`, verify its tools appear. Test compaction with a long conversation.

### Phase 6: Polish (~Day 5-6)
1. Error handling edge cases
2. `tinyloom.example.yaml` with documentation
3. README.md
4. Basic tests
5. Ctrl+C handling, graceful shutdown
6. `--version` flag