# Running tinyloom in a Docker Sandbox (sbx)

tinyloom can run inside a [Docker Sandbox](https://docs.docker.com/ai/sandboxes/) microVM for full isolation. Each sandbox gets its own Docker daemon, filesystem, and network -- the agent can install packages, run commands, and modify files without touching your host system.

Unlike [microsandbox](sandbox-msb.md), Docker Sandboxes route network traffic through an HTTP/HTTPS proxy on your host, so async TLS works normally. No `sync_http` workaround is needed.

## Prerequisites

- macOS Tahoe (26)+ on Apple Silicon, Windows 11 with Hypervisor Platform, or Ubuntu 22.04+ with KVM
- `sbx` CLI installed
- An API key for your model provider
- Docker Desktop is **not** required

Install `sbx`:

```bash
# macOS
brew install docker/tap/sbx
sbx login

# Linux (Ubuntu)
curl -fsSL https://get.docker.com | sudo REPO_ONLY=1 sh
sudo apt-get install docker-sbx
sbx login
```

## API Keys

Store credentials so the sandbox proxy can inject them into outbound API requests. Keys are never exposed inside the VM:

```bash
# Anthropic
sbx secret set -g anthropic

# OpenAI
sbx secret set -g openai

# Fireworks AI (or any OpenAI-compatible provider)
export FIREWORKS_API_KEY=your-key-here
```

## End User

Install tinyloom from PyPI inside a sandbox shell and point it at your project.

### One-shot

```bash
sbx run shell ~/path/to/your/project -- -c "pip install -q tinyloom && tinyloom 'create a hello.py and run it'"
```

### Persistent sandbox

```bash
sbx create --name tinyloom shell ~/my-project
sbx run tinyloom
```

Once inside the shell:

```bash
pip install tinyloom
tinyloom "fix the failing tests"
```

Or with `uv tool`:

```bash
pip install uv
uv tool run tinyloom "fix the failing tests"
```

Installed packages persist across stops and restarts.

### Get a shell in a running sandbox

```bash
sbx exec -it tinyloom bash
```

## Developer

Work against the tinyloom source repo with full dev tooling inside a sandbox.

### Interactive

```bash
sbx run shell ~/path/to/tinyloom
```

Once inside:

```bash
export UV_PROJECT_ENVIRONMENT=/tmp/.venv
pip install uv
uv sync --extra dev
uv run tinyloom "fix the failing tests"
```

### One-shot

```bash
sbx run shell ~/path/to/tinyloom -- -c "export UV_PROJECT_ENVIRONMENT=/tmp/.venv && pip install -q uv && uv sync --extra dev -q && uv run tinyloom 'create a hello.py and run it'"
```

### Run tests

Inside the sandbox shell:

```bash
export UV_PROJECT_ENVIRONMENT=/tmp/.venv
uv run pytest tests/ -q
uv run ruff check tinyloom/ tests/
```

### Manage

```bash
sbx ls                   # list sandboxes
sbx stop tinyloom        # pause
sbx run tinyloom         # resume
sbx rm tinyloom          # delete
```

## Custom Template

For repeated use, build a template with tooling pre-installed:

```dockerfile
FROM docker/sandbox-templates:shell
USER root
RUN apt-get update && apt-get install -y curl
USER agent
RUN pip install uv
```

```bash
docker build -t your-org/tinyloom-sandbox:latest --push .
sbx run --template docker.io/your-org/tinyloom-sandbox:latest shell ~/my-project
```

## Multiple Workspaces

Mount extra directories alongside the primary workspace. Append `:ro` for read-only:

```bash
sbx run shell ~/my-project ~/shared-libs:ro ~/reference-docs:ro
```

## Network Access

Docker Sandboxes default to a network policy (Open, Balanced, or Locked Down) chosen at `sbx login`. If tinyloom can't reach your model provider:

```bash
sbx policy ls
sbx policy allow network api.anthropic.com
sbx policy allow network api.fireworks.ai
sbx policy allow network api.openai.com
```

Access host services via `host.docker.internal`:

```bash
sbx policy allow network localhost:11434
curl http://host.docker.internal:11434
```

## Port Forwarding

```bash
sbx ports tinyloom --publish 8080:3000   # host 8080 -> sandbox 3000
sbx ports tinyloom --unpublish 8080:3000
```

Services must bind to `0.0.0.0` inside the sandbox to be reachable.

## Troubleshooting

### Network policy blocks API calls

Your sandbox policy is blocking outbound traffic:

```bash
sbx policy allow network api.anthropic.com
```

### Stale sandbox

```bash
sbx rm tinyloom
sbx create --name tinyloom shell ~/my-project
```
