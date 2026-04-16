# Changelog

## 0.2.0

### Added

- **Token usage tracking** -- `TokenUsage` dataclass with per-turn and cumulative stats (input, output, cache read/write). Available via `StreamEvent.usage` and `AgentEvent.cumulative_usage`.
- **Thinking/reasoning support** -- extended thinking for Anthropic (adaptive thinking + reasoning_effort), OpenAI reasoning models, Ollama, Fireworks, and OpenRouter. Reasoning tokens preserved across multi-turn conversations.
- **Local model support** -- new `docs/local-model.md` guide for running tinyloom against Ollama and LM Studio (llmster). Includes Podman and Docker setups with correct container networking.
- **Ollama reasoning field compatibility** -- OpenAI provider now handles both `reasoning_content` (OpenAI) and `reasoning` (Ollama) fields via `_get_reasoning()` helper.
- **Sandbox docs** -- dedicated guides for Docker, Podman, Kata Containers, and E2B sandboxes with TUI-specific instructions (`-it` flags, `TERM` propagation, terminal size fixes).
- **Mask plugin** -- redact sensitive words from agent output.
- **`TokenUsage` exported** in public API (`tinyloom.__all__`).

### Fixed

- **Compaction crash with local models** -- `count_tokens` returning `None` (from providers that don't support `/v1/responses/input_tokens`) no longer crashes `maybe_compact`. Falls back to heuristic estimator.
- **TUI broken in containers** -- sandbox docs now include `-it` flags and `TERM` env var for proper TUI rendering. Added troubleshooting for terminal size issues.
- **Container networking on macOS** -- docs use `host.containers.internal` (Podman) and `host.docker.internal` (Docker) instead of `localhost`, which doesn't work from inside containers on macOS.

### Changed

- **`stream_options` always sent** -- usage tracking via `stream_options: {"include_usage": true}` is now sent for all providers, not just vanilla OpenAI. Ollama and most third-party providers support it.

## 0.1.3

- Fix pypi-publish workflow SHA.

## 0.1.1

- Mask plugin for redacting sensitive output.
- Hook support for plugins on TUI events.
- Demo video and gif.

## 0.1.0

Initial release.

- Agent loop with tool execution, hooks, and compaction.
- Built-in tools: `read`, `write`, `edit`, `bash`.
- Anthropic and OpenAI-compatible providers.
- Context compaction (summarize and truncate strategies).
- Plugin system with entry_points and config loading.
- Plugins: subagent, todo, MCP, hook_scripts.
- CLI with headless (JSONL) and interactive (TUI) modes.
- Textual TUI with streaming, slash commands.
- Hook system with sync/async support, mutation, and skip.
- YAML config with env var overrides and `.env` loading.
