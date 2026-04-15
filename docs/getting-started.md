# Getting Started

## Install

```bash
uv add tinyloom
# or
pip install tinyloom
```

For MCP support:

```bash
uv add 'tinyloom[mcp]'
```

## Set your API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Or for OpenAI-compatible providers:

```bash
export OPENAI_API_KEY=sk-...
```

## CLI usage

Headless (runs to completion, outputs JSONL):

```bash
tinyloom "fix the bug in main.py"
```

Interactive TUI:

```bash
tinyloom
```

Pipe mode:

```bash
echo "add tests for utils.py" | tinyloom --stdin
```

Override model or provider:

```bash
tinyloom -m gpt-4o -p openai "explain this code"
```

## SDK usage

```python
import asyncio
from tinyloom import Agent, load_config

async def main():
    agent = Agent(load_config())
    async for event in agent.run("create a hello.py"):
        if event.type == "text_delta":
            print(event.text, end="")

asyncio.run(main())
```

For interactive (multi-turn) conversations, use `agent.step()`:

```python
async def chat():
    agent = Agent(load_config())
    while True:
        user_input = input("> ")
        async for event in agent.step(user_input):
            if event.type == "text_delta":
                print(event.text, end="")
        print()
```

## Config

Copy the example config:

```bash
cp tinyloom.example.yaml tinyloom.yaml
```

Config is loaded from (first match wins):

1. Path passed to `load_config(path)`
2. `./tinyloom.yaml`
3. `~/.config/tinyloom/tinyloom.yaml`
4. Built-in defaults

Minimal `tinyloom.yaml`:

```yaml
model:
  provider: anthropic
  model: claude-sonnet-4-20250514

system_prompt: You are a skilled coding assistant. Be concise.
```

## Using OpenAI

Set your key and configure the provider:

```bash
export OPENAI_API_KEY=sk-...
```

```yaml
model:
  provider: openai
  model: gpt-4o
```

Any OpenAI-compatible API works -- see [custom providers](custom-providers.md) for vLLM, Ollama, and others.

## Event types

When consuming the SDK or reading JSONL output, these are the events you will see:

| Event | Key fields | Description |
|-------|-----------|-------------|
| `agent_start` | -- | Agent begins |
| `text_delta` | `text` | Incremental LLM text |
| `tool_call` | `tool_call` | LLM requests a tool |
| `tool_result` | `tool_call_id`, `tool_name`, `result` | Tool executed |
| `compaction` | -- | Context was compacted |
| `response_complete` | `message` | LLM finished (no more tool calls) |
| `agent_stop` | -- | Agent done |
| `error` | `error` | Something went wrong |
