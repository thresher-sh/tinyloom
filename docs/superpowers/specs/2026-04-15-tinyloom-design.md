# tinyloom Design Spec

> A tiny, SDK-first, provider-agnostic coding agent harness in Python.

## Goals

- **SDK-first**: the CLI is a thin wrapper. The real value is `from tinyloom import Agent`.
- **Tiny**: simple and readable. Flat within layers, no framework magic, no abstractions without payoff.
- **Provider-agnostic**: works with any Anthropic or OpenAI-compatible endpoint via official SDKs.
- **Extensible**: plugins get the full Agent, hooks react to any event, MCP extends tools.

## Non-Goals

- Being a framework (no Chain, Pipeline, Graph, Node)
- Competing with full-featured agents (Claude Code, Cursor, aider)
- Supporting providers beyond Anthropic/OpenAI-compatible APIs

---

## Package Structure

```
tinyloom/
├── pyproject.toml
├── tinyloom/
│   ├── __init__.py              # public API exports
│   ├── __main__.py              # python -m tinyloom
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py             # Agent class + the loop
│   │   ├── types.py             # Message, ToolCall, StreamEvent, AgentEvent
│   │   ├── config.py            # Config dataclasses + YAML loader
│   │   ├── tools.py             # Tool, ToolRegistry, @tool decorator, all built-in tools
│   │   ├── hooks.py             # HookRunner
│   │   └── compact.py           # context compaction
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py              # LLMProvider protocol
│   │   ├── anthropic.py         # Anthropic SDK wrapper
│   │   └── openai.py            # OpenAI SDK wrapper
│   ├── plugins/
│   │   ├── __init__.py          # plugin loader (entry_points + config paths)
│   │   ├── todo.py              # built-in todo middleware
│   │   └── mcp.py               # MCP tool extension (opt-in)
│   ├── cli.py                   # argparse, headless JSON stream, mode dispatch
│   └── tui.py                   # Textual app (minimal v1)
├── tests/
└── tinyloom.example.yaml
```

### Layers

1. **Core** (`tinyloom/core/`): the SDK. Agent loop, types, tools (built-ins included), hooks, config, compaction. This is what `from tinyloom import ...` exposes.
2. **Providers** (`tinyloom/providers/`): one file per LLM provider wrapping its official SDK. Adding a provider means adding one file.
3. **Plugins** (`tinyloom/plugins/`): opt-in extensions. Plugin loader + built-in plugins (todo, mcp).
4. **Interfaces** (`cli.py`, `tui.py`): thin consumers of the SDK.

---

## Core Types (`core/types.py`)

```python
@dataclass
class Message:
    role: str                          # "user" | "assistant" | "tool_result"
    content: str = ""
    tool_calls: list[ToolCall]         # populated for assistant messages with tool use
    tool_call_id: str = ""             # populated for tool_result messages
    name: str = ""                     # tool name for tool_result messages

@dataclass
class ToolCall:
    id: str
    name: str
    input: dict

@dataclass
class StreamEvent:
    type: str                          # "text" | "tool_call" | "done" | "error"
    text: str = ""
    tool_call: ToolCall | None = None
    message: Message | None = None
    error: str = ""

@dataclass
class AgentEvent:
    type: str                          # "agent_start" | "text_delta" | "tool_call" |
                                       # "tool_result" | "compaction" | "response_complete" |
                                       # "agent_stop" | "error"
    text: str = ""
    tool_call: ToolCall | None = None
    tool_call_id: str = ""
    tool_name: str = ""
    result: str = ""
    message: Message | None = None
    error: str = ""

    def to_dict(self) -> dict:
        """Serialize for JSON stream output. Drops empty fields."""
```

### Two event types, two audiences

- **StreamEvent**: internal. Yielded by providers during LLM streaming. Only the agent loop sees these.
- **AgentEvent**: public. Yielded by `Agent.run()`. SDK consumers, TUI, CLI, hooks, and plugins all consume these.

---

## Hook System (`core/hooks.py`)

Hooks subscribe to `AgentEvent` types and `Message` roles. One event system for everything -- no separate hook vocabulary.

```python
class HookRunner:
    def on(self, event: str, fn: Callable): ...
    async def emit(self, event: str, **kwargs): ...
```

### Subscribing

```python
# AgentEvent types
hooks.on("tool_call", my_approval_gate)
hooks.on("text_delta", my_logger)
hooks.on("agent_stop", my_cleanup)

# Message roles
hooks.on("message:user", my_input_filter)
hooks.on("message:assistant", my_output_logger)
hooks.on("message:tool_result", my_audit_trail)
```

### Behavior

- Every `AgentEvent` passes through hooks before being yielded to consumers.
- Messages pass through hooks when appended to the conversation.
- Hooks can be sync or async (auto-detected).
- Hook exceptions are logged to stderr, not raised.
- Hooks can be registered via config (dotted import paths) or programmatically.

---

## Provider Layer (`providers/`)

### Protocol

```python
class LLMProvider(Protocol):
    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        system: str = "",
    ) -> AsyncIterator[StreamEvent]: ...

    async def count_tokens(
        self,
        messages: list[Message],
        system: str = "",
    ) -> int: ...
```

Two methods. Each provider (`anthropic.py`, `openai.py`) implements this by:

1. Translating `Message` list to SDK-native format
2. Calling the SDK's streaming API
3. Yielding `StreamEvent`s
4. Using SDK/API token counting endpoint for accurate counts

### Provider detection

- `claude` in model name -> Anthropic
- Everything else -> OpenAI (most compatible APIs use this format)
- `config.model.provider` always wins if set
- `config.model.base_url` overrides the endpoint for either provider (vLLM, Ollama, Together, etc.)

---

## Agent Loop (`core/agent.py`)

### Public API

```python
class Agent:
    def __init__(
        self,
        config: Config,
        provider: LLMProvider | None = None,    # auto-detected from config if None
        tools: ToolRegistry | None = None,      # built-ins loaded if None
        hooks: HookRunner | None = None,        # empty if None
    ): ...

    async def run(self, prompt: str) -> AsyncIterator[AgentEvent]:
        """Headless: one prompt, run to completion."""

    async def step(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Interactive: one user message, run until response."""
```

### The loop

```
1. Add user message to conversation
2. Check compaction (token count vs threshold)
3. Emit events through hooks
4. Call LLM (streaming)
5. If tool calls -> execute each -> append results -> goto 2
6. If no tool calls -> response complete -> return
```

### Key details

- Every `AgentEvent` passes through `hooks.emit()` before yielding.
- Messages pass through `hooks.emit("message:{role}")` when appended.
- `max_turns` safety limit prevents runaway loops.
- The `continue` back to step 2 after tool results is the entire tool loop mechanism.
- SDK users can override any piece via constructor. Defaults work out of the box.

### 10-line SDK usage

```python
from tinyloom import Agent, load_config

agent = Agent(load_config())
async for event in agent.run("fix the failing tests"):
    if event.type == "text_delta":
        print(event.text, end="")
```

---

## Built-in Tools (`core/tools.py`)

All tools, the `Tool` dataclass, `ToolRegistry`, and `@tool` decorator live in one file.

### Tool definitions

| Tool | Params | Behavior |
|------|--------|----------|
| `read` | `path` | Read file, return line-numbered output |
| `write` | `path`, `content` | Create/overwrite file, create parent dirs |
| `edit` | `path`, `old_str`, `new_str` | str_replace, must match exactly once. Diff support planned for future. |
| `grep` | `pattern`, `path?`, `flags?` | Uses `ripgrep` Python package, falls back to system grep |
| `bash` | `command`, `timeout?` | Shell execution, captures stdout+stderr+exit code, 120s default timeout |
| `exec` | `task`, `model?`, `system_prompt?` | Spawns sub-agent in-process. One level deep only -- sub-agent gets all tools except `exec`. |

### Tool contract

```python
@tool(name="read", description="...", input_schema={...})
def read_tool(input: dict) -> str:
    ...
```

`ToolRegistry.execute()` catches exceptions and returns error strings -- never crashes the agent loop.

`exec` is async (awaited by the agent loop). Sync tools are wrapped automatically.

---

## Config (`core/config.py`)

```python
@dataclass
class ModelConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    base_url: str | None = None
    max_tokens: int = 8192
    context_window: int = 200_000
    temperature: float = 0.0

@dataclass
class CompactionConfig:
    enabled: bool = True               # on by default, disable via config
    threshold: float = 0.8             # compact at 80% of context window
    strategy: str = "summarize"        # "summarize" | "truncate"

@dataclass
class Config:
    model: ModelConfig
    system_prompt: str = "You are a skilled coding assistant..."
    compaction: CompactionConfig
    plugins: list[str] = []            # dotted paths or entry_point names
    hooks: dict[str, list[str]] = {}   # event -> [dotted.paths]
    max_turns: int = 200
```

### Loading precedence

1. Explicit path passed to `load_config(path)`
2. `./tinyloom.yaml`
3. `~/.config/tinyloom/tinyloom.yaml`
4. Defaults

API keys always from env vars (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`). Never in YAML.

---

## Compaction (`core/compact.py`)

Core feature, on by default, configurable to disable.

### Flow

1. Ask the provider's `count_tokens()` for current conversation size
2. If below `threshold * context_window` -- do nothing
3. If above -- compact using configured strategy

### Strategies

- **`summarize`** (default): ask the LLM to summarize the conversation. Replace everything except the last ~4 messages with the summary. Summary prompt captures: what was accomplished, what's in progress, key decisions, errors resolved, next steps.
- **`truncate`**: drop oldest messages, keep last ~10, prepend a truncation marker.

### Details

- Fires `AgentEvent(type="compaction")` through hooks. Plugins can subscribe to re-inject state (e.g., todo plugin re-injects current task list).
- System prompt is never compacted -- always sent separately via provider's native mechanism.

---

## Plugins (`plugins/`)

### Plugin contract

A plugin is any callable that takes an `Agent`:

```python
def activate(agent: Agent):
    agent.tools.register(my_tool)
    agent.hooks.on("tool_call", my_hook)
```

### Plugin discovery

1. Python `entry_points` (group `tinyloom.plugins`) for installed packages
2. Dotted paths from config `plugins:` list

### Built-in plugins

**`todo`** (opt-in via config):
- Registers a `todo` tool with actions: create, update_status, list
- Subscribes to `agent_stop` -- if incomplete tasks exist, prompts agent to finish
- Subscribes to `message:assistant` for tracking

**`mcp`** (opt-in via config, requires `mcp` optional dependency):
- Reads `.mcp.json` (local then `~/.config/tinyloom/.mcp.json`)
- Launches MCP servers via `mcp` SDK
- Registers discovered tools with `mcp_` prefix

Config to enable:
```yaml
plugins:
  - tinyloom.plugins.todo
  - tinyloom.plugins.mcp
```

---

## CLI (`cli.py`)

Thin argparse wrapper over the SDK.

### Modes

```bash
tinyloom "fix the tests"          # headless: JSONL stream to stdout
tinyloom                          # interactive: Textual TUI
echo "task" | tinyloom --stdin    # pipe mode
```

### Flags

- `prompt` (positional, optional) -- triggers headless mode
- `-m / --model` -- override model
- `-p / --provider` -- override provider
- `--config` -- config file path
- `--stdin` -- read prompt from stdin
- `--system` -- override system prompt
- `--json` -- force JSON output
- `--no-plugins` -- disable all plugins
- `--version`

### Detection

Prompt provided or stdin piped -> headless. Otherwise TUI.

### Headless output

JSONL -- one `AgentEvent.to_dict()` per line, flushed immediately.

---

## TUI (`tui.py`)

Minimal Textual app. Single file.

### Features (v1)

- Input prompt at bottom
- Scrolling message area
- Streaming assistant text rendered as markdown
- Tool calls: name + truncated input
- Tool results: dimmed/truncated
- Status bar: model name, token count
- Compaction notification

### Slash commands

`/help`, `/clear`, `/model`, `/tokens`, `/quit`

### Not in v1

- No concurrent input while streaming
- No syntax highlighting in tool results
- No file tree or diff views

---

## Dependencies

```toml
[project]
dependencies = [
    "anthropic>=0.40",
    "openai>=1.50",
    "pyyaml>=6.0",
    "textual>=1.0",
    "ripgrep>=0.1",
]

[project.optional-dependencies]
mcp = ["mcp>=1.0,<2"]
dev = ["pytest", "pytest-asyncio", "ruff"]
```

### Why each

- `anthropic` / `openai`: official SDKs handle streaming, token counting, retries, format quirks
- `pyyaml`: config loading
- `textual`: TUI (bundles rich)
- `ripgrep`: grep tool (system grep as fallback)
- `mcp`: optional, only for MCP plugin

### Transitive (not declared)

- `httpx`: dep of both SDKs
- `rich`: bundled with textual

---

## JSONL Stream Schema

Headless mode emits one JSON object per line:

```jsonl
{"type": "agent_start"}
{"type": "text_delta", "text": "I'll help you fix that."}
{"type": "tool_call", "tool_call": {"id": "tc_01", "name": "read", "input": {"path": "main.py"}}}
{"type": "tool_result", "tool_call_id": "tc_01", "tool_name": "read", "result": "..."}
{"type": "text_delta", "text": "Fixed the bug."}
{"type": "response_complete", "message": {"role": "assistant", "content": "..."}}
{"type": "agent_stop"}
```

### Event types

| type | fields | when |
|------|--------|------|
| `agent_start` | -- | agent begins |
| `text_delta` | `text` | incremental LLM text |
| `tool_call` | `tool_call` | LLM requests a tool |
| `tool_result` | `tool_call_id`, `tool_name`, `result` | tool executed |
| `compaction` | -- | context was compacted |
| `response_complete` | `message` | LLM finished (no tool calls) |
| `agent_stop` | -- | agent done |
| `error` | `error` | something went wrong |

---

## Key Design Decisions

1. **SDK-first**: `Agent` class has a clean public API. CLI and TUI are thin consumers.
2. **Official SDKs over raw httpx**: battle-tested streaming, token counting, retries. Your code stays tiny.
3. **Textual over rich+prompt_toolkit**: proper app framework, bundles rich.
4. **str_replace editing**: proven by Claude Code, Amp, Cursor. Diff support planned for future.
5. **One event system**: hooks subscribe to `AgentEvent` types and `Message` roles. Same types SDK consumers use.
6. **Plugins get full Agent**: maximum power, minimum API surface.
7. **Compaction is core**: safety rail, on by default, configurable to disable.
8. **MCP is a plugin**: opt-in, not everyone needs it.
9. **Sub-agents one level deep**: simple, no recursion risk.
10. **ripgrep Python package**: no dependency on system rg binary.
