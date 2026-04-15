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

### 3. Run tinyloom

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
msb exec tinyloom -w /app -- uv run pytest tests/ -q
```

### 4. Manage the sandbox

```bash
msb list              # list sandboxes
msb stop tinyloom     # stop
msb start tinyloom    # restart
msb remove tinyloom   # delete
```

## Secure API Key Injection

msb supports secret injection that prevents the guest from exfiltrating keys to unauthorized hosts. The real key is only sent when requests go to the allowed host:

```bash
msb create python \
  -n tinyloom-secure \
  -m 1G -c 2 \
  -v $(pwd):/app -w /app \
  --secret "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}@api.anthropic.com"

msb exec tinyloom-secure -w /app -- uv run tinyloom "do something"
```

For OpenAI:

```bash
msb create python \
  -n tinyloom-secure \
  -m 1G -c 2 \
  -v $(pwd):/app -w /app \
  --secret "OPENAI_API_KEY=${OPENAI_API_KEY}@api.openai.com"
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

## Notes

- The project directory is mounted read-write at `/app`. The agent can modify your files.
- The `ripgrep` Python package requires Rust to compile, which isn't in the base Python image. Install the `rg` binary directly (shown above) or rely on the `grep -rn` fallback.
- msb sandboxes boot in under 100ms. Creating a fresh one per task is cheap.
- The `--replace` flag on `create` destroys and recreates an existing sandbox with the same name.
