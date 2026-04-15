# tinyloom

A tiny, SDK-first coding agent harness in Python.

## Why this exists

We needed an extremely tiny coding agent harness for [thresher](https://github.com/thresher-sh/thresher) and many harnesses just bring extra bloat we don't need. The harness bit is actually easy to implement -- it's all the extra bells and whistles that take a lot.

If you are looking for a bigger client, take a look at one of these:

- [pi-mono coding-agent](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent)
- [opencode](https://github.com/anomalyco/opencode)

## Safety

tinyloom has **no permission system, no approval gates, and no filesystem sandboxing** by default. The agent can read, write, delete, and execute anything your user account can. Do not run it outside of a container or sandbox on a machine you care about.

Use [microsandbox](docs/sandbox.md) or another isolation layer for untrusted workloads. If you want tool approval or allowlists, build a [plugin](docs/creating-plugins.md) or [hook](docs/custom-hooks.md) for it.

## Quick start

```bash
uv add tinyloom
export ANTHROPIC_API_KEY=sk-ant-...
```

CLI:

```bash
tinyloom "fix the bug in main.py"   # headless, JSONL output
tinyloom                            # interactive TUI
```

SDK:

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

See [docs/getting-started.md](docs/getting-started.md) for full setup instructions.

## Features

- **Built-in tools**: `read`, `write`, `edit` (str_replace), `bash`
- **Providers**: Anthropic and OpenAI-compatible APIs (vLLM, Ollama, Together, Groq, LM Studio, Azure)
- **Compaction**: automatic context summarization when approaching the context window limit
- **Hooks**: react to any agent event (tool calls, messages, errors) with sync or async functions
- **Plugins**: extend the agent with tools, hooks, and custom logic
- **MCP**: connect to Model Context Protocol servers for external tools
- **TUI**: interactive terminal interface with streaming, slash commands, and token tracking
- **Sub-agents**: delegate focused tasks with the `subagent` plugin

## Config

Copy the example and edit:

```bash
cp tinyloom.example.yaml tinyloom.yaml
```

```yaml
model:
  provider: anthropic
  model: claude-sonnet-4-20250514
  context_window: 200000

system_prompt: You are a skilled coding assistant. Be concise.

compaction:
  enabled: true
  threshold: 0.8
  strategy: summarize

plugins:
  - tinyloom.plugins.todo
  - tinyloom.plugins.mcp
  - tinyloom.plugins.hook_scripts

max_turns: 200
```

API keys go in environment variables, not config. See [.env.example](.env.example).

## Want more features?

tinyloom is intentionally small. Extend it instead:

- **More tools?** Connect MCP servers -- see [docs/mcp-plugin.md](docs/mcp-plugin.md)
- **Custom logic?** Write a plugin -- see [docs/creating-plugins.md](docs/creating-plugins.md)
- **Approval gates? Logging? Filters?** Use hooks -- see [docs/custom-hooks.md](docs/custom-hooks.md) or [docs/hook-scripts.md](docs/hook-scripts.md)
- **Different model provider?** Set `base_url` -- see [docs/custom-providers.md](docs/custom-providers.md)

## Docs

- [Getting Started](docs/getting-started.md)
- [Creating Plugins](docs/creating-plugins.md)
- [Custom Hooks](docs/custom-hooks.md)
- [Hook Scripts](docs/hook-scripts.md)
- [MCP Plugin](docs/mcp-plugin.md)
- [Custom Providers](docs/custom-providers.md)
- [Design Decisions](docs/design-decisions.md)
- [Running in a Sandbox](docs/sandbox.md)

## Size

The whole thing is ~1,110 lines of Python (excluding blank lines) as of 2026.04.15.

| Area | Files | Lines |
|------|-------|-------|
| **core** (agent, tools, config, compaction, hooks, types) | 7 | 411 |
| **cli** | 1 | 48 |
| **tui** | 1 | 152 |
| **providers** (anthropic, openai, base) | 4 | 220 |
| **plugins** (subagent, todo, mcp, hook_scripts) | 5 | 263 |

## License

MIT
