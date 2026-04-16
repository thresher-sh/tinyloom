# Running tinyloom in microsandbox

tinyloom can run inside a [microsandbox](https://docs.microsandbox.dev) (msb) VM for full isolation. The agent gets its own Linux kernel, filesystem, and network -- useful for running untrusted code or keeping your host safe from `bash` tool execution.

## Prerequisites

Install msb:

```bash
curl -fsSL https://install.microsandbox.dev | sh
```

Requires macOS Apple Silicon or Linux with KVM.

API calls require `sync_http: true` in your `tinyloom.yaml`. See [TLS / connection errors](#tls--connection-errors).

## End User

Install tinyloom from PyPI inside a sandbox and point it at your project.

### One-shot

```bash
msb run python \
  -m 1G -c 2 \
  -v .:/app -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -- sh -c "pip install -q tinyloom && tinyloom 'create a hello.py and run it'"
```

### Persistent sandbox

```bash
msb create python \
  -n tinyloom \
  -m 1G -c 2 \
  -v $(pwd):/app \
  -w /app

msb exec tinyloom -- pip install -q tinyloom
```

Run tinyloom:

```bash
msb exec tinyloom -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -- tinyloom "fix the failing tests"
```

Or with `uv tool`:

```bash
msb exec tinyloom -- pip install -q uv
msb exec tinyloom -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -- uv tool run tinyloom "fix the failing tests"
```

Interactive TUI:

```bash
msb exec tinyloom -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -t \
  -- tinyloom
```

## Developer

Work against the tinyloom source repo with full dev tooling.

### One-shot

```bash
msb run python \
  -m 1G -c 2 \
  -v .:/app -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -- sh -c "pip install -q uv && uv sync --extra dev -q && uv run tinyloom 'create a hello.py and run it'"
```

### Persistent sandbox

```bash
msb create python \
  -n tinyloom-dev \
  -m 1G -c 2 \
  -v $(pwd):/app \
  -w /app

# Install tooling
msb exec tinyloom-dev -- pip install -q uv

# Install ripgrep (for the grep tool)
msb exec tinyloom-dev -- sh -c "curl -fsSL https://github.com/BurntSushi/ripgrep/releases/download/14.1.1/ripgrep-14.1.1-aarch64-unknown-linux-gnu.tar.gz | tar xz && cp ripgrep-14.1.1-aarch64-unknown-linux-gnu/rg /usr/local/bin/"

# Install tinyloom deps
msb exec tinyloom-dev -w /app -- uv sync --extra dev
```

For x86_64 Linux, replace `aarch64-unknown-linux-gnu` with `x86_64-unknown-linux-musl` in the ripgrep URL.

Run from source:

```bash
msb exec tinyloom-dev -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -- uv run tinyloom "fix the failing tests"
```

Run tests:

```bash
msb exec tinyloom-dev -w /app -- uv run pytest tests/ -q
```

Run linter:

```bash
msb exec tinyloom-dev -w /app -- uv run ruff check tinyloom/ tests/
```

### Manage

```bash
msb list                  # list sandboxes
msb stop tinyloom-dev     # stop
msb start tinyloom-dev    # restart
msb remove tinyloom-dev   # delete
```

## Configuration

Add `sync_http: true` to your `tinyloom.yaml`:

```yaml
model:
  provider: anthropic
  model: claude-sonnet-4-20250514
  sync_http: true
```

This switches the SDK clients from async to sync HTTP, which uses `ssl.SSLSocket` instead of `ssl.MemoryBIO` for TLS. Required because msb's [smoltcp](https://github.com/smoltcp-rs/smoltcp) user-space networking stack doesn't support the async TLS upgrade path.

## Secure API Key Injection

msb supports secret injection that prevents the guest from exfiltrating keys to unauthorized hosts:

```bash
# Anthropic
msb create python -n tinyloom -m 1G -c 2 \
  -v $(pwd):/app -w /app \
  --secret "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}@api.anthropic.com"

# OpenAI
msb create python -n tinyloom -m 1G -c 2 \
  -v $(pwd):/app -w /app \
  --secret "OPENAI_API_KEY=${OPENAI_API_KEY}@api.openai.com"

# Fireworks AI
msb create python -n tinyloom -m 1G -c 2 \
  -v $(pwd):/app -w /app \
  --secret "FIREWORKS_API_KEY=${FIREWORKS_API_KEY}@api.fireworks.ai"
```

The actual key value is only attached to HTTP requests headed for the allowed host.

## Network Controls

```bash
# No network at all
msb create python -n tinyloom-offline -m 1G --no-network -v .:/app -w /app

# Block specific domains
msb create python -n tinyloom -m 1G \
  --dns-block-domain evil.com \
  --dns-block-suffix .ads.com \
  -v .:/app -w /app

# Limit concurrent connections
msb create python -n tinyloom -m 1G --max-connections 10 -v .:/app -w /app
```

## Auto-Shutdown

```bash
# Kill after 10 minutes
msb run python -m 1G -v .:/app -w /app --max-duration 10m \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -- tinyloom "run the full test suite"

# Stop after 5 minutes idle
msb create python -n tinyloom -m 1G --idle-timeout 5m -v .:/app -w /app
```

## Troubleshooting

### TLS / connection errors

If you see `start_tls.failed`, `ConnectError(EndOfStream())`, or `Connection error.`:

Set `sync_http: true` in your `tinyloom.yaml`. See [Configuration](#configuration).

### apt-get signature errors

Clock skew. Sync time before running apt-get:

```bash
msb exec tinyloom -- date -s "$(date -u '+%Y-%m-%d %H:%M:%S')"
```

### `.venv` recreation warning

Harmless. The host's `.venv` is mounted into the sandbox but was built with a different Python. uv detects this and recreates it automatically.

## Notes

- The project directory is mounted read-write at `/app`. The agent can modify your files.
- The `ripgrep` Python package requires Rust to compile, which isn't in the base Python image. Install the `rg` binary directly (shown above).
- msb sandboxes boot in under 100ms. Creating a fresh one per task is cheap.
- The `--replace` flag on `create` destroys and recreates an existing sandbox with the same name.
