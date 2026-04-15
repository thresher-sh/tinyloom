# Running tinyloom in a Sandbox

tinyloom can run inside a [microsandbox](https://docs.microsandbox.dev) (msb) VM for full isolation. The agent gets its own Linux kernel, filesystem, and network -- useful for running untrusted code or keeping your host safe from `bash` tool execution.

## Prerequisites

Install msb:

```bash
curl -fsSL https://install.microsandbox.dev | sh
```

Requires macOS Apple Silicon or Linux with KVM.

## Quick Start

One-shot command:

```bash
msb run python \
  -m 1G -c 2 \
  -v .:/app -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -- sh -c "pip install -q uv && uv sync --extra dev -q && uv run tinyloom 'create a hello.py and run it'"
```

API calls require `sync_http: true` in your `tinyloom.yaml`. See [TLS / connection errors](#tls--connection-errors).

## Persistent Sandbox

For repeated use, create a named sandbox and set it up once.

### 1. Create the sandbox

```bash
msb create python \
  -n tinyloom \
  -m 1G -c 2 \
  -v $(pwd):/app \
  -w /app
```

### 2. Install tooling

```bash
# Install uv
msb exec tinyloom -- pip install -q uv

# Install ripgrep (for the grep tool)
msb exec tinyloom -- sh -c "curl -fsSL https://github.com/BurntSushi/ripgrep/releases/download/14.1.1/ripgrep-14.1.1-aarch64-unknown-linux-gnu.tar.gz | tar xz && cp ripgrep-14.1.1-aarch64-unknown-linux-gnu/rg /usr/local/bin/"

# Install tinyloom deps
msb exec tinyloom -w /app -- uv sync --extra dev
```

For x86_64 Linux, replace `aarch64-unknown-linux-gnu` with `x86_64-unknown-linux-musl` in the ripgrep URL.

### 3. Configure for sandbox

Add `sync_http: true` to your `tinyloom.yaml`:

```yaml
model:
  provider: anthropic
  model: claude-sonnet-4-20250514
  sync_http: true
```

This switches the SDK clients from async to sync HTTP, which uses `ssl.SSLSocket` instead of `ssl.MemoryBIO` for TLS. Required because msb's [smoltcp](https://github.com/smoltcp-rs/smoltcp) user-space networking stack doesn't support the async TLS upgrade path. See [Troubleshooting](#tls--connection-errors).

### 4. Run tinyloom

Headless:

```bash
msb exec tinyloom -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -- uv run tinyloom "fix the failing tests"
```

Interactive shell (run tinyloom TUI inside):

```bash
msb exec tinyloom -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -t \
  -- uv run tinyloom
```

Run tests:

```bash
msb exec tinyloom -w /app \
  -- uv run pytest tests/ -q
```

### 5. Manage the sandbox

```bash
msb list              # list sandboxes
msb stop tinyloom     # stop
msb start tinyloom    # restart
msb remove tinyloom   # delete
```

## Secure API Key Injection

msb supports secret injection that prevents the guest from exfiltrating keys to unauthorized hosts. The real key is only sent when requests go to the allowed host:

```bash
# Anthropic
msb create python \
  -n tinyloom-secure \
  -m 1G -c 2 \
  -v $(pwd):/app -w /app \
  --secret "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}@api.anthropic.com"

# OpenAI
msb create python \
  -n tinyloom-secure \
  -m 1G -c 2 \
  -v $(pwd):/app -w /app \
  --secret "OPENAI_API_KEY=${OPENAI_API_KEY}@api.openai.com"

# Fireworks AI (or any OpenAI-compatible provider)
msb create python \
  -n tinyloom-secure \
  -m 1G -c 2 \
  -v $(pwd):/app -w /app \
  --secret "FIREWORKS_API_KEY=${FIREWORKS_API_KEY}@api.fireworks.ai"
```

Then run as usual:

```bash
msb exec tinyloom-secure -w /app \
  -- uv run tinyloom "do something"
```

The agent can read the env var, but the actual key value is only attached to HTTP requests headed for the allowed host. Even if the agent tries to send the key elsewhere, it won't have the real value.

## Network Controls

Restrict what the sandbox can reach:

```bash
# No network at all
msb create python -n tinyloom-offline -m 1G --no-network -v .:/app -w /app

# Block specific domains
msb create python -n tinyloom -m 1G \
  --dns-block-domain evil.com \
  --dns-block-suffix .ads.com \
  -v .:/app -w /app

# Limit concurrent connections
msb create python -n tinyloom -m 1G \
  --max-connections 10 \
  -v .:/app -w /app
```

## Volume Persistence

Named volumes survive sandbox removal:

```bash
# Create a volume for agent work
msb volume create agent-work

# Mount it
msb create python -n tinyloom -m 1G \
  -v .:/app \
  -v agent-work:/workspace \
  -w /app
```

The agent's work in `/workspace` persists across sandbox restarts and recreations.

## Auto-Shutdown

For CI or batch jobs, set timeouts:

```bash
# Kill after 10 minutes
msb run python -m 1G -v .:/app -w /app \
  --max-duration 10m \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -- uv run tinyloom "run the full test suite"

# Stop after 5 minutes idle
msb create python -n tinyloom -m 1G \
  --idle-timeout 5m \
  -v .:/app -w /app
```

## Troubleshooting

### TLS / connection errors

If you see `start_tls.failed`, `ConnectError(EndOfStream())`, or `Connection error.`:

**Root cause:** msb routes all VM network traffic through [smoltcp](https://github.com/smoltcp-rs/smoltcp), a user-space TCP/IP stack. This stack doesn't properly handle TLS handshakes done via `ssl.MemoryBIO` -- the path that Python's `anyio` → `httpcore` → `httpx` → openai/anthropic SDKs use for async HTTPS. Synchronous TLS (`ssl.SSLSocket`) works fine.

**Fix:** Set `sync_http: true` in your `tinyloom.yaml`:

```yaml
model:
  sync_http: true
```

This makes the SDK clients use sync HTTP (which uses `ssl.SSLSocket`) bridged to async via thread pools. No performance impact for a CLI tool.

Run `tinyloom -v` to see the full TLS trace if you need to debug further.

### apt-get signature errors

```
OpenPGP signature verification failed: Not live until ...
```

Clock skew. msb VMs don't run NTP and the clock freezes across `msb stop` / `msb start` cycles. Sync it before running `apt-get`:

```bash
msb exec tinyloom -- date -s "$(date -u '+%Y-%m-%d %H:%M:%S')"
```

### `.venv` recreation warning

```
warning: Ignoring existing virtual environment linked to non-existent Python interpreter
```

Harmless. The host's `.venv` is mounted into the sandbox via `-v .:/app` but was built with a different Python. uv detects this and recreates it automatically.

## Notes

- The project directory is mounted read-write at `/app`. The agent can modify your files.
- The `ripgrep` Python package requires Rust to compile, which isn't in the base Python image. Install the `rg` binary directly (shown above) or rely on the `grep -rn` fallback.
- msb sandboxes boot in under 100ms. Creating a fresh one per task is cheap.
- The `--replace` flag on `create` destroys and recreates an existing sandbox with the same name.
