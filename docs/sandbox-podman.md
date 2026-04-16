# Running tinyloom in Podman

tinyloom can run inside a [Podman](https://podman.io/) container for isolation. Podman is a daemonless, rootless container engine with Docker-compatible CLI. If you know Docker, you know Podman -- the commands are nearly identical.

Podman's key advantage over Docker is **rootless containers** -- no root daemon, no setuid binaries. Containers run with your user's privileges, reducing the blast radius if the agent does something unexpected.

## Prerequisites

**macOS (Apple Silicon or Intel)**

```bash
brew install podman
podman machine init
podman machine start
```

**Linux**

```bash
# Ubuntu/Debian
sudo apt-get install podman

# Fedora
sudo dnf install podman
```

**Windows**

```powershell
winget install RedHat.Podman
podman machine init
podman machine start
```

## End User

Install tinyloom from PyPI inside a container and point it at your project.

### One-shot

```bash
podman run --rm -it \
  -v $(pwd):/app -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  python:3.11-slim \
  sh -c "pip install -q tinyloom && tinyloom 'create a hello.py and run it'"
```

### Persistent container

```bash
podman run -dit \
  --name tinyloom \
  -v $(pwd):/app -w /app \
  python:3.11-slim \
  sleep infinity

podman exec tinyloom pip install -q tinyloom
```

Run tinyloom (headless):

```bash
podman exec -it -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  tinyloom \
  tinyloom "fix the failing tests"
```

Run the TUI (interactive mode -- no prompt argument):

```bash
podman exec -it -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e TERM=$TERM \
  tinyloom \
  tinyloom
```

Or with `uv tool`:

```bash
podman exec tinyloom pip install -q uv
podman exec -it -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  tinyloom \
  uv tool run tinyloom "fix the failing tests"
```

## Developer

Work against the tinyloom source repo with full dev tooling.

### One-shot

```bash
podman run --rm -it \
  -v $(pwd):/app -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e UV_PROJECT_ENVIRONMENT=/tmp/.venv \
  python:3.11-slim \
  sh -c "pip install -q uv && uv sync --extra dev -q && uv run tinyloom 'create a hello.py and run it'"
```

### Persistent container

```bash
podman run -dit \
  --name tinyloom-dev \
  -v $(pwd):/app -w /app \
  python:3.11-slim \
  sleep infinity

podman exec tinyloom-dev pip install -q uv
podman exec -e UV_PROJECT_ENVIRONMENT=/tmp/.venv -w /app tinyloom-dev uv sync --extra dev
```

Run from source (headless):

```bash
podman exec -it -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e UV_PROJECT_ENVIRONMENT=/tmp/.venv \
  tinyloom-dev \
  uv run tinyloom "fix the failing tests"
```

Run the TUI from source:

```bash
podman exec -it -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e UV_PROJECT_ENVIRONMENT=/tmp/.venv \
  -e TERM=$TERM \
  tinyloom-dev \
  uv run tinyloom
```

Run tests:

```bash
podman exec -e UV_PROJECT_ENVIRONMENT=/tmp/.venv -w /app tinyloom-dev uv run pytest tests/ -q
```

Run linter:

```bash
podman exec -e UV_PROJECT_ENVIRONMENT=/tmp/.venv -w /app tinyloom-dev uv run ruff check tinyloom/ tests/
```

### Manage

```bash
podman ps                    # list
podman stop tinyloom-dev     # stop
podman start tinyloom-dev    # restart
podman rm tinyloom-dev       # delete
```

## Rootless Mode

Podman runs rootless by default -- no configuration needed:

```bash
podman info --format '{{.Host.Security.Rootless}}'
# true
```

## Hardened Container

```bash
podman run -dit \
  --name tinyloom \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --read-only \
  --tmpfs /tmp \
  -v $(pwd):/app:z -w /app \
  python:3.11-slim \
  sleep infinity
```

Note: a fully read-only rootfs may require additional tmpfs mounts for pip/uv caches.

## Network Controls

```bash
podman run --network=none -v $(pwd):/app -w /app python:3.11-slim ...
```

## Podman vs Docker

| | Podman | Docker |
|---|---|---|
| Daemon | None (daemonless) | dockerd daemon required |
| Rootless | Default | Requires configuration |
| CLI | Docker-compatible | -- |
| macOS | Via `podman machine` (Linux VM) | Via Docker Desktop |
| Socket | Per-user, no root socket | `/var/run/docker.sock` (root) |

## Troubleshooting

### Permission denied on volume mounts

On SELinux systems (Fedora/RHEL), add `:z` to volume mounts:

```bash
podman run -v $(pwd):/app:z ...
```

### TUI is tiny or can't accept input

The TUI requires a proper terminal. Always use `-it` with `podman exec`:

```bash
# wrong -- no TTY, TUI will be tiny/broken
podman exec -w /app tinyloom tinyloom

# correct
podman exec -it -w /app -e TERM=$TERM tinyloom tinyloom
```

If the TUI still renders at the wrong size, pass the terminal dimensions explicitly:

```bash
podman exec -it -w /app \
  -e TERM=$TERM \
  -e COLUMNS=$(tput cols) \
  -e LINES=$(tput lines) \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  tinyloom \
  tinyloom
```

### Rootless networking limitations

Rootless containers can't bind to ports below 1024. Use higher port numbers or configure `net.ipv4.ip_unprivileged_port_start`.
