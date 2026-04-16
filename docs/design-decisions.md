# Design Decisions

Key decisions behind tinyloom's architecture.

## SDK-first

The `Agent` class is the product. CLI and TUI are thin consumers of it. This means you can embed tinyloom in your own Python programs, build custom interfaces, or compose agents however you want -- the CLI is just one way to use it.

## Official SDKs over raw httpx

tinyloom uses the official `anthropic` and `openai` Python SDKs rather than making raw HTTP calls. These SDKs handle streaming, retries, rate limits, and format quirks. The result is less code to maintain and fewer edge cases to hit.

## str_replace editing

The `edit` tool uses exact string matching (`str_replace`) rather than line-number or diff-based editing. This approach is proven by Claude Code, Amp, and Cursor. The match must be unique in the file, which prevents ambiguous edits.

## One event system for hooks

Hooks subscribe to the same `AgentEvent` types that SDK consumers see (`tool_call`, `text_delta`, etc.) plus `message:role` events. No separate hook vocabulary to learn. Hooks receive a mutable `ctx` dict and can cancel events by setting `ctx["skip"] = True`.

## Plugins get full Agent

A plugin receives the entire `Agent` instance. It can register tools, add hooks, read config, or modify state. This is maximum power with minimum API surface -- no restricted plugin API to maintain.

## Compaction is core

Context compaction is built in and enabled by default. When the conversation approaches the context window limit (default 80%), tinyloom either summarizes or truncates the history. This prevents context overflow errors during long sessions. It can be disabled or tuned via config.

## MCP as plugin

MCP (Model Context Protocol) support is opt-in via `tinyloom.plugins.mcp`. Not everyone needs external tool servers, so it is not loaded by default. Install with `tinyloom[mcp]`.

## Sub-agents one level deep

The `exec` tool spawns a sub-agent that gets all built-in tools except `exec` itself. This prevents infinite recursion while still allowing task delegation. Sub-agents get a fresh hook runner and no plugins -- they are lightweight and focused.

## Two event types, two audiences

- **StreamEvent**: internal, yielded by providers during LLM streaming. Only the agent loop consumes these.
- **AgentEvent**: public, yielded by `Agent.run()` and `Agent.step()`. SDK consumers, TUI, CLI, and hooks all use these.

## Provider detection

If `provider` is set in config, that is used. Otherwise, `"claude"` in the model name selects Anthropic, and everything else falls through to OpenAI (since most compatible APIs use that format). `base_url` overrides the endpoint for either provider.

## Small

Should keep as small surface as possible, shift things to plugins for beadth of features. 
Guard what goes into core very strictly!!!