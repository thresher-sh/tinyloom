[Join Discord](https://discord.gg/VVt9qmkcnr) -- [Website: thresher.sh](https://thresher.sh)

# tinyloom

A tiny, SDK-first coding agent harness in Python.

![Demo](./demo.gif)

## Why this exists

We needed an extremely tiny coding agent harness for [thresher](https://github.com/thresher-sh/thresher) and many harnesses just bring extra bloat we don't need. The harness bit is actually easy to implement -- it's all the extra bells and whistles that take a lot.

If you are looking for a bigger client, take a look at one of these:

- [pi-mono coding-agent](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent)
- [opencode](https://github.com/anomalyco/opencode)

## Safety

tinyloom has **no permission system, no approval gates, and no filesystem sandboxing** by default. The agent can read, write, delete, and execute anything your user account can. Do not run it outside of a container or sandbox on a machine you care about.

Run it in a sandbox for untrusted workloads:

- [Docker](docs/sandbox-docker.md) -- simplest option
- [Podman](docs/sandbox-podman.md) -- rootless containers
- [microsandbox](docs/sandbox-msb.md) -- lightweight sandboxing
- [Kata Containers](docs/sandbox-kata.md) -- VM-level isolation
- [E2B](docs/sandbox-sbx.md) -- cloud sandboxes

If you want tool approval or allowlists, build a [plugin](docs/creating-plugins.md) or [hook](docs/custom-hooks.md) for it.

## Install

```bash
uv tool install tinyloom   # or: pip install tinyloom
```

## Quick start

```bash
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
        elif event.type == "done" and event.usage:
            print(f"\n[tokens: {event.usage.input_tokens}in / {event.usage.output_tokens}out]")

asyncio.run(main())
```

See [docs/getting-started.md](docs/getting-started.md) for full setup instructions.

## Features

- **Built-in tools**: `read`, `write`, `edit` (str_replace), `bash`
- **Providers**: Anthropic and OpenAI-compatible APIs (vLLM, Ollama, Together, Groq, LM Studio, Azure)
- **Local models**: run against Ollama or LM Studio with full tool use and reasoning -- see [docs/local-model.md](docs/local-model.md)
- **Thinking/reasoning**: extended thinking for Anthropic, OpenAI, Ollama, Fireworks, and OpenRouter
- **Token tracking**: per-turn and cumulative token usage with cache stats
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
  max_tokens: 8192
  # thinking: true
  # reasoning_effort: medium  # low, medium, or high

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

Thinking/reasoning works with Anthropic, OpenAI reasoning models, Ollama, Fireworks, and OpenRouter. See [custom providers](docs/custom-providers.md#thinking--reasoning) for details.

## Want more features?

tinyloom is intentionally small. Extend it instead:

- **Local models?** Run Ollama or LM Studio -- see [docs/local-model.md](docs/local-model.md)
- **More tools?** Connect MCP servers -- see [docs/mcp-plugin.md](docs/mcp-plugin.md)
- **Custom logic?** Write a plugin -- see [docs/creating-plugins.md](docs/creating-plugins.md)
- **Approval gates? Logging? Filters?** Use hooks -- see [docs/custom-hooks.md](docs/custom-hooks.md) or [docs/hook-scripts.md](docs/hook-scripts.md)
- **Redact sensitive output?** Use the mask plugin -- see [docs/mask-plugin.md](docs/mask-plugin.md)
- **Different model provider?** Set `base_url` -- see [docs/custom-providers.md](docs/custom-providers.md)

## Docs

- [Getting Started](docs/getting-started.md)
- [Custom Providers](docs/custom-providers.md)
- [Local Models (Ollama / LM Studio)](docs/local-model.md)
- [Creating Plugins](docs/creating-plugins.md)
- [Custom Hooks](docs/custom-hooks.md)
- [Hook Scripts](docs/hook-scripts.md)
- [MCP Plugin](docs/mcp-plugin.md)
- [Mask Plugin](docs/mask-plugin.md)
- [Design Decisions](docs/design-decisions.md)
- Sandboxing: [Docker](docs/sandbox-docker.md) | [Podman](docs/sandbox-podman.md) | [microsandbox](docs/sandbox-msb.md) | [Kata](docs/sandbox-kata.md) | [E2B](docs/sandbox-sbx.md)

## Size

The whole thing is ~1,216 lines of Python (excluding blank lines) as of v0.2.0.

| Area | Files | Lines |
|------|-------|-------|
| **core** (agent, tools, config, compaction, hooks, types) | 7 | 439 |
| **cli** | 1 | 48 |
| **tui** | 1 | 168 |
| **providers** (anthropic, openai, base) | 4 | 276 |
| **plugins** (subagent, todo, mcp, hook_scripts, mask) | 6 | 285 |

## License

MIT
