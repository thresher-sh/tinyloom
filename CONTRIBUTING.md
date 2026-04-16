# Contributing to tinyloom

## Setup

```bash
git clone https://github.com/thresher-sh/tinyloom.git
cd tinyloom
uv sync --extra dev
```

## Running tests

```bash
uv run pytest tests/ -q
```

Always add or update tests when changing code. If fixing a bug, write a failing test first, then fix the code to make it pass.

## Linting

```bash
uv run ruff check tinyloom/ tests/
```

## Code style

tinyloom is intentionally compact. Follow what's already there:

- One-line `if` statements for simple branches: `if x: do_thing()`
- Ternary style over `if/else` blocks
- Single blank line between functions and classes (not two)
- 200-column soft limit (configured in `pyproject.toml`)
- No docstrings on internal functions unless the logic is non-obvious
- No type annotations on code you didn't change

## Philosophy

Read the full conventions in `CLAUDE.md`, but the short version:

- **Complexity is the enemy.** Fight it. Say no to unnecessary features and abstractions.
- **Don't abstract too early.** Let structure emerge from working code. A little duplication is better than a premature abstraction.
- **Build deep modules.** Simple interface, complex internals. Don't push complexity onto callers.
- **Ship simple.** A working thing that ships beats a perfect thing that doesn't.
- **Respect existing code.** Understand why it exists before changing it.

## Making changes

1. Fork and create a branch
2. Write a failing test for your change
3. Make the change
4. Run `uv run pytest tests/ -q` -- all tests must pass
5. Run `uv run ruff check tinyloom/ tests/` -- no new warnings from your code
6. Commit with a short one-line message
7. Open a PR

## What we'll merge

- Bug fixes with a regression test
- Provider compatibility fixes (new local model servers, third-party APIs)
- Plugin contributions
- Doc improvements
- Performance improvements with profiling data

## What we probably won't merge

- Large refactors or architectural changes without prior discussion
- New dependencies (tinyloom's dependency footprint is intentionally small)
- Features that add complexity without clear value
- Style-only changes to code you didn't otherwise modify
- Changes in core that could have been a plugin

## Running against a local model

For testing against local models without API keys:

```bash
ollama pull qwen3:30b-a3b
```

Create a `tinyloom.yaml` with the Podman gateway hostname:

```yaml
model:
  provider: openai
  model: qwen3:30b-a3b
  base_url: http://host.containers.internal:11434/v1
  context_window: 8192
  max_tokens: 4096
```

Run tinyloom in a Podman container:

```bash
podman run --rm -it \
  -v $(pwd):/app -w /app \
  -e OPENAI_API_KEY=ollama \
  python:3.11-slim \
  sh -c "pip install -q tinyloom && tinyloom 'hello' --verbose"
```

See [docs/local-model.md](docs/local-model.md) for Docker, TUI mode, and full setup details.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
