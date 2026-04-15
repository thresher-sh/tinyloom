# Building tinyloom: a complete implementation blueprint

**The entire architecture of a coding agent fits in roughly 1,500 lines of Python.** The core insight, validated by examining Claude Code, aider, Amp, Codex CLI, goose, and smolagents source code, is that an agent is just an LLM call in a loop with tool dispatch — no framework magic required. This report provides every concrete pattern, schema, and code snippet needed to build tinyloom with raw `httpx` for LLM calls, a `str_replace`-style tool system, optional MCP support, hybrid context compaction, a 25-line hook system, and a `rich`/`prompt_toolkit` TUI, all shipping as a single pip-installable package.

---

## 1. Provider-agnostic LLM streaming with raw httpx

The only external dependency needed beyond `httpx` is `httpx-sse` (~200 lines, handles SSE parsing). Both OpenAI and Anthropic stream Server-Sent Events, but their formats diverge significantly.

### HTTP endpoints and headers

| Aspect | OpenAI | Anthropic |
|---|---|---|
| Endpoint | `POST https://api.openai.com/v1/chat/completions` | `POST https://api.anthropic.com/v1/messages` |
| Auth header | `Authorization: Bearer {key}` | `x-api-key: {key}` |
| Version header | None | `anthropic-version: 2023-06-01` |
| `max_tokens` | Optional | **Required** |
| System prompt | `{"role": "system"}` message | Top-level `"system"` field |
| Tool schema key | `"parameters"` nested under `"function"` | `"input_schema"` at top level |
| Tool wrapper | `{"type": "function", "function": {...}}` | Direct `{"name": ..., "input_schema": ...}` |
| Stream sentinel | `data: [DONE]` | `event: message_stop` |
| Tool result role | `"tool"` | `"user"` with `type: "tool_result"` blocks |

### SSE format differences

OpenAI emits bare `data:` lines with no named event types. Each chunk is `data: {json}\n\n`, terminated by `data: [DONE]`. Anthropic uses named `event:` lines paired with `data:` lines — the event name (`content_block_start`, `content_block_delta`, `content_block_stop`, `message_start`, `message_delta`, `message_stop`) tells you what the data contains. The `httpx-sse` library's `aconnect_sse` handles both formats transparently via `sse.event` and `sse.data`.

### The unified streaming provider (~80 lines)

```python
import httpx, json
from httpx_sse import aconnect_sse

class LLMProvider:
    def __init__(self, provider: str, api_key: str):
        self.provider = provider
        self.api_key = api_key

    @property
    def _url(self):
        return {"openai": "https://api.openai.com/v1/chat/completions",
                "anthropic": "https://api.anthropic.com/v1/messages"}[self.provider]

    @property
    def _headers(self):
        if self.provider == "openai":
            return {"Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"}
        return {"x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"}

    def format_body(self, messages, tools, model):
        body = {"model": model, "messages": messages, "stream": True}
        if tools:
            body["tools"] = self._format_tools(tools)
        if self.provider == "anthropic":
            body["max_tokens"] = 8192
            sys_msgs = [m for m in messages if m["role"] == "system"]
            if sys_msgs:
                body["system"] = sys_msgs[0]["content"]
                body["messages"] = [m for m in messages if m["role"] != "system"]
        else:
            body["stream_options"] = {"include_usage": True}
        return body

    async def stream(self, messages, tools, model):
        body = self.format_body(messages, tools, model)
        async with httpx.AsyncClient(timeout=120) as client:
            async with aconnect_sse(client, "POST", self._url,
                                     json=body, headers=self._headers) as es:
                tool_calls = {}
                async for sse in es.aiter_sse():
                    # --- OpenAI ---
                    if self.provider == "openai":
                        if sse.data == "[DONE]": break
                        chunk = json.loads(sse.data)
                        delta = chunk["choices"][0].get("delta", {})
                        if c := delta.get("content"):
                            yield ("text_delta", c)
                        for tc in delta.get("tool_calls", []):
                            idx = tc["index"]
                            if idx not in tool_calls:
                                tool_calls[idx] = {"id": tc["id"],
                                    "name": tc["function"]["name"], "arguments": ""}
                            tool_calls[idx]["arguments"] += tc["function"].get("arguments", "")
                    # --- Anthropic ---
                    elif self.provider == "anthropic":
                        data = json.loads(sse.data)
                        if sse.event == "content_block_start":
                            blk = data["content_block"]
                            if blk["type"] == "tool_use":
                                tool_calls[data["index"]] = {"id": blk["id"],
                                    "name": blk["name"], "arguments": ""}
                        elif sse.event == "content_block_delta":
                            d = data["delta"]
                            if d["type"] == "text_delta":
                                yield ("text_delta", d["text"])
                            elif d["type"] == "input_json_delta":
                                tool_calls[data["index"]]["arguments"] += d["partial_json"]
                        elif sse.event == "message_stop":
                            break
                for tc in sorted(tool_calls.values(), key=lambda x: x.get("id","")):
                    tc["input"] = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    yield ("tool_use", tc)
```

### OpenAI tool call accumulation — the critical gotcha

OpenAI streams tool calls as fragments in `choices[0].delta.tool_calls`. **Only the first chunk carries `id` and `function.name`**; subsequent chunks only carry `function.arguments` string fragments. You must use the `index` field (not `id`) to correlate chunks. A real bug in litellm caused it to skip chunks where `id` was null, losing ~90% of argument data.

### Anthropic tool call accumulation

Anthropic delivers tool name and ID upfront in `content_block_start`, then streams `input_json_delta` with `partial_json` strings. You concatenate these and parse the full JSON at `content_block_stop`. No partial JSON parsing needed — just string accumulation.

### Anthropic's strict alternating messages requirement

Anthropic requires roles to alternate `user` → `assistant` → `user`. Tool results must be sent as a `role: "user"` message with content blocks of `type: "tool_result"`. Multiple tool results go in a **single** user message as separate content blocks. If you need to send a user follow-up after tool results, merge content blocks into the same message to avoid consecutive user messages.

```python
# Anthropic tool result format
{"role": "user", "content": [
    {"type": "tool_result", "tool_use_id": "toolu_01A...",
     "content": "file contents here", "is_error": False},
    {"type": "tool_result", "tool_use_id": "toolu_01B...",
     "content": "Error: not found", "is_error": True}
]}

# OpenAI tool result format (separate messages, "tool" role)
{"role": "tool", "tool_call_id": "call_abc", "content": "result text"}
```

---

## 2. Tool system: str_replace wins, five tools suffice

Every production coding agent converges on the same minimal tool set: **read_file, list_files, edit_file (str_replace), bash, and grep/search**. The Amp article ("How to Build an Agent" by Thorsten Ball) demonstrated a fully functional coding agent in ~300 lines of Go with just three of these. The choice of edit format matters enormously — aider found that **changing just the edit interface improved coding performance by +8% average** across 16 models.

### Why str_replace dominates

The `str_replace` pattern (find exact string → replace with new string) outperforms alternatives because LLMs are terrible at line numbers, terrible at producing valid unified diffs, and good at reproducing exact text snippets. Anthropic bakes the `str_replace_editor` tool into Claude's model weights — you declare `{"type": "text_editor_20250728", "name": "str_replace_based_edit_tool"}` and get a schema-free tool the model already knows.

For tinyloom's own implementation, the key design rules from Anthropic's reference implementation are: `old_str` must match **exactly one location** in the file (return an error on zero or multiple matches), and success messages should remind the model to verify: "Review the changes and make sure they are as expected."

### Minimal tool definition pattern

The pattern from Amp, smolagents, and TinyAgent converges on: a tool is a name + description + JSON schema + callable function. Auto-generate the JSON schema from Python type hints and docstrings:

```python
import inspect, json, typing

def tool_schema(func):
    """Extract JSON schema from function signature + docstring."""
    hints = typing.get_type_hints(func)
    doc = inspect.getdoc(func) or ""
    props, required = {}, []
    for name, hint in hints.items():
        if name == "return": continue
        props[name] = {"type": _python_type_to_json(hint)}
        required.append(name)
    return {
        "name": func.__name__,
        "description": doc.split("\n")[0],
        "schema": {"type": "object", "properties": props, "required": required}
    }
```

### The five essential tools

| Tool | Schema (key params) | Implementation notes |
|---|---|---|
| `read_file` | `path: str` | Return line-numbered output (`cat -n` style) |
| `list_files` | `path: str, pattern: str?` | Use `glob` or `os.walk`, respect `.gitignore` |
| `edit_file` | `path: str, old_str: str, new_str: str` | Error if `old_str` matches 0 or 2+ locations |
| `bash` | `command: str` | `asyncio.create_subprocess_shell`, capture stdout+stderr, timeout |
| `grep` | `pattern: str, path: str?` | Shell out to `rg` or `grep -rn`, return matched lines |

### Sub-agent pattern

Claude Code and Amp implement sub-agents as tools — the main agent calls a `spawn_agent` tool that creates a child agent with its own context window. The child returns only a summary to the parent. This architectural pattern doubles as a context management strategy: each sub-agent gets a fresh context window, preventing bloat in the main conversation. For tinyloom, start without sub-agents and add the pattern later if needed — it's just another tool that instantiates a new agent loop.

---

## 3. MCP client: 60 lines without the SDK

### Using the official SDK (~15 lines)

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def connect_mcp(command, args):
    params = StdioServerParameters(command=command, args=args)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            result = await session.call_tool("tool_name", {"arg": "val"})
```

### Without the SDK (~60 lines)

**Critical correction**: MCP stdio uses **newline-delimited JSON**, not Content-Length headers like LSP. Each message is one JSON-RPC 2.0 object per line, terminated by `\n`.

```python
import asyncio, json

class MCPClient:
    def __init__(self, command, args=None):
        self.command, self.args = command, args or []
        self._id = 0

    async def start(self):
        self.proc = await asyncio.create_subprocess_exec(
            self.command, *self.args,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)

    async def _request(self, method, params=None):
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params: msg["params"] = params
        self.proc.stdin.write((json.dumps(msg) + "\n").encode())
        await self.proc.stdin.drain()
        line = await self.proc.stdout.readline()
        return json.loads(line)

    async def initialize(self):
        r = await self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "tinyloom", "version": "0.1.0"}})
        self.proc.stdin.write((json.dumps(
            {"jsonrpc": "2.0", "method": "initialized"}) + "\n").encode())
        await self.proc.stdin.drain()
        return r

    async def list_tools(self):
        return (await self._request("tools/list"))["result"]["tools"]

    async def call_tool(self, name, arguments):
        return await self._request("tools/call",
            {"name": name, "arguments": arguments})
```

### The .mcp.json configuration schema

All major tools (Claude Code, Cursor, Claude Desktop) use the same format:

```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
      "env": {"API_KEY": "xxx"}
    }
  }
}
```

### Converting MCP tools to LLM formats

The mapping is nearly trivial. MCP tools use `inputSchema` (camelCase JSON Schema). For OpenAI: wrap in `{"type": "function", "function": {"name": ..., "description": ..., "parameters": inputSchema}}`. For Anthropic: just rename `inputSchema` → `input_schema` (snake_case).

---

## 4. Context compaction: the hybrid approach wins

Production coding agents converge on a three-stage hybrid strategy: **prune old tool outputs first** (cheapest), **summarize remaining old messages** (preserves key context), **keep recent messages verbatim** (maintains working state).

### Trigger thresholds from real implementations

| Tool | Threshold | Notes |
|---|---|---|
| Claude Code | ~95% capacity | Users widely report this is too late |
| Goose | **80%** (configurable) | `GOOSE_AUTO_COMPACT_THRESHOLD` env var |
| Kiro | **80%** | Official docs |
| Codex CLI | Absolute token value (~180-244K) | Model-dependent |

**Recommendation for tinyloom: trigger at 80%**, which is where Goose and Kiro land. Community consensus is that 95% (Claude Code's default) causes quality degradation because the model is already struggling when compaction fires.

### Token counting for Anthropic

Anthropic provides a **free token counting API** at `POST /v1/messages/count_tokens` that accepts the same body as the messages endpoint and returns `{"input_tokens": N}`. For offline estimates, **1 token ≈ 3.5 English characters** is Anthropic's official heuristic. Every API response also includes a `usage` field with exact `input_tokens` and `output_tokens` counts — track these to know your running total.

### The compaction prompt (synthesized from Claude Code, Codex CLI, and OpenCode)

```
You are performing a context compaction. Create a detailed summary preserving:
1. What was accomplished (completed tasks, files modified)
2. Current work in progress and its state
3. Key decisions made and their rationale
4. Errors encountered and how they were resolved
5. Next steps and remaining work
6. User constraints and preferences

Be concise but detailed enough that work can continue seamlessly.
```

When injecting the summary into a new context, prefix it with: "A previous session produced this summary. Build on this work and avoid duplicating effort."

### Aider's complementary approach: repo map

Rather than compacting conversations, aider compresses the **codebase representation** using tree-sitter to extract function/class signatures, then ranks them with PageRank personalized to the chat context. The result is a token-budgeted structural overview (default **1024 tokens**) that fits in the system prompt. This prevents context bloat proactively — a pattern tinyloom should consider for large codebases.

---

## 5. Hook system: 25 lines, dict of callables

After analyzing TinyAgent, smolagents, the Claude Agent SDK, and pluggy, the clear winner for a tiny project is a simple dict mapping event names to lists of callables. No dependencies, trivially async-compatible, and extensible enough for real use.

```python
from collections import defaultdict
import inspect

class Hooks:
    def __init__(self):
        self._hooks = defaultdict(list)

    def on(self, event, fn):
        self._hooks[event].append(fn)
        return fn  # allows @hooks.on("event") decorator use

    async def emit(self, event, ctx=None):
        ctx = ctx or {}
        for fn in self._hooks.get(event, []):
            r = fn(ctx)
            if inspect.isawaitable(r): await r
```

### Essential lifecycle events for a coding agent

Based on what Claude Agent SDK, TinyAgent, and smolagents expose, tinyloom needs these **six core events**: `before_llm_call` (for prompt caching, message cleanup), `after_llm_call` (cost tracking, logging), `before_tool_execution` (permission/approval gates — this is the critical safety hook), `after_tool_execution` (audit trail), `on_streaming_token` (live UI updates), and `on_error` (recovery). Two additional events worth supporting: `on_agent_start`/`on_agent_end` for session bookkeeping and `on_compaction` for re-injecting critical context after summarization.

### The approval hook pattern

The simplest effective safety pattern is a tiered system: read-only tools (read_file, list_files, grep) auto-approve; write tools (edit_file, bash) prompt the user. Claude Code's more sophisticated model uses four permission levels and regex-matched hook matchers, but a two-tier system suffices for tinyloom:

```python
@hooks.on("before_tool_execution")
async def approve_writes(ctx):
    if ctx["tool_name"] in ("edit_file", "bash", "write_file"):
        answer = input(f"Allow {ctx['tool_name']}? [y/N] ")
        if answer.lower() != "y":
            ctx["skip"] = True
```

---

## 6. TUI: rich for output, prompt_toolkit when you need concurrent I/O

### The proven Python stack

Aider uses `prompt_toolkit` for input and `rich` for output — this is the established pattern. For a minimal first version, **rich alone suffices**: `Console.input()` for styled prompts and `Live` + `Markdown` for streaming output.

```python
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

console = Console()
md_text = ""
with Live(Markdown(""), console=console, refresh_per_second=8) as live:
    async for chunk in llm_stream:
        md_text += chunk
        live.update(Markdown(md_text))
```

**Key insight: Rich does not support incremental markdown parsing.** You must recreate `Markdown(full_accumulated_text)` on each update. In practice this is fast enough — Rich renders the full markdown tree each refresh cycle.

### Adding concurrent I/O with prompt_toolkit

When you need the user to type while output streams (a nice-to-have, not essential), prompt_toolkit's `patch_stdout()` context manager makes any `print()` call write above the input prompt instead of corrupting it:

```python
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import PromptSession

async def main():
    session = PromptSession()
    with patch_stdout():
        while True:
            user_input = await session.prompt_async("You> ")
            await stream_response(user_input)  # prints above prompt
```

### Minimum viable TUI

The absolute minimum is `readline` + `print` with ANSI codes — no dependencies. The user waits for streaming to finish, then types. This is acceptable for a coding agent where turns are long.

---

## 7. CLI headless mode with JSONL streaming

### Event schema (modeled on Claude Code's `--output-format stream-json`)

Emit one JSON object per line to stdout. Every event has a `type` field:

```python
# Init event
{"type": "system", "session_id": "...", "model": "claude-sonnet-4-..."}

# Text from assistant
{"type": "assistant", "content": [{"type": "text", "text": "Planning..."}]}

# Tool use
{"type": "assistant", "content": [{"type": "tool_use", "id": "toolu_1",
    "name": "bash", "input": {"command": "ls"}}]}

# Tool result
{"type": "tool_result", "tool_use_id": "toolu_1", "output": "README.md\nsrc/"}

# Final result
{"type": "result", "subtype": "success", "result": "Done.",
    "duration_ms": 12345, "total_cost_usd": 0.003}
```

### Mode detection pattern

```python
import sys

def main():
    if args.headless or not sys.stdin.isatty():
        prompt = args.prompt or sys.stdin.read().strip()
        for event in agent_loop(prompt):
            if args.output_format == "stream-json":
                print(json.dumps(event), flush=True)
            elif args.output_format == "text":
                if event["type"] == "assistant":
                    for block in event["content"]:
                        if block["type"] == "text":
                            print(block["text"], end="", flush=True)
    else:
        run_interactive()
```

---

## 8. Project structure for a tiny pip-installable package

### File layout (~1,500 lines total)

```
tinyloom/
├── pyproject.toml
├── README.md
├── src/
│   └── tinyloom/
│       ├── __init__.py          # version, public API
│       ├── __main__.py          # 5 lines: python -m tinyloom
│       ├── cli.py               # ~150 lines: argparse, mode dispatch
│       ├── agent.py             # ~400 lines: core loop, LLM provider
│       ├── tools.py             # ~300 lines: built-in tools + schema gen
│       ├── mcp.py               # ~100 lines: MCP client
│       ├── tui.py               # ~250 lines: rich/prompt_toolkit UI
│       ├── compact.py           # ~100 lines: context compaction
│       └── hooks.py             # ~50 lines: hook system
```

### Minimal pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "tinyloom"
version = "0.1.0"
description = "A minimal coding agent harness"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "httpx-sse>=0.4",
    "rich>=13.0",
]

[project.optional-dependencies]
tui = ["prompt-toolkit>=3.0"]
mcp = ["mcp>=1.0,<2"]
dev = ["pytest", "ruff"]

[project.scripts]
tinyloom = "tinyloom.cli:main"
```

### Entry point pattern

```python
# src/tinyloom/cli.py
import asyncio, argparse, sys

def main() -> int:
    parser = argparse.ArgumentParser(prog="tinyloom")
    parser.add_argument("prompt", nargs="?")
    parser.add_argument("-p", "--print", dest="headless", action="store_true")
    parser.add_argument("--model", default="claude-sonnet-4-20250514")
    parser.add_argument("--output-format",
        choices=["text", "json", "stream-json"], default="text")
    args = parser.parse_args()
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130

# src/tinyloom/__main__.py
from tinyloom.cli import main
if __name__ == "__main__":
    raise SystemExit(main())
```

---

## Conclusion: the architectural recipe

The core agent loop is deceptively simple — Amp proved it in 300 lines of Go, and tinyloom can match that density in Python. The key implementation decisions that emerge from this research: use `httpx` + `httpx-sse` with a thin provider abstraction layer (not SDKs), implement the `str_replace` edit pattern (not diffs or line numbers), trigger context compaction at **80%** capacity using a three-stage hybrid (prune tool outputs → summarize → keep recent verbatim), and build the hook system as a 25-line dict-of-callables that gates tool execution for safety. MCP support adds ~60 lines if you roll your own client or ~15 using the SDK. The `rich` library alone handles both streaming markdown and styled prompts for the first version, with `prompt_toolkit` available as an optional upgrade for concurrent I/O. Everything ships as a single `pip install tinyloom` package with three core dependencies.