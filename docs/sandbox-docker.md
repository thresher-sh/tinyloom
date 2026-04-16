# Running tinyloom in Docker

tinyloom can run inside a plain [Docker](https://docs.docker.com/) container for isolation. This is the simplest sandbox option -- if you have Docker installed, you're ready to go.

Docker containers provide namespace-level isolation (not VM-level), which is sufficient for most use cases. The agent gets its own filesystem and network but shares the host kernel.

## Prerequisites

- Docker installed (`docker --version`)
- An API key for your model provider

## End User

Install tinyloom from PyPI inside a container and point it at your project.

### One-shot

```bash
docker run --rm -it \
  -v $(pwd):/app -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  python:3.11-slim \
  sh -c "pip install -q tinyloom && tinyloom 'create a hello.py and run it'"
```

### Persistent container

```bash
docker run -dit \
  --name tinyloom \
  -v $(pwd):/app -w /app \
  python:3.11-slim \
  sleep infinity

docker exec tinyloom pip install -q tinyloom
```

Run tinyloom:

```bash
docker exec -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  tinyloom \
  tinyloom "fix the failing tests"
```

Or with `uv tool`:

```bash
docker exec tinyloom pip install -q uv
docker exec -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  tinyloom \
  uv tool run tinyloom "fix the failing tests"
```

### Custom image

Bake tinyloom into a reusable image:

```dockerfile
FROM python:3.11-slim
RUN pip install tinyloom
WORKDIR /app
```

```bash
docker build -t tinyloom-sandbox .
docker run --rm -it \
  -v $(pwd):/app -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  tinyloom-sandbox \
  tinyloom "do something"
```

## Developer

Work against the tinyloom source repo with full dev tooling.

### One-shot

```bash
docker run --rm -it \
  -v $(pwd):/app -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  python:3.11-slim \
  sh -c "pip install -q uv && uv sync --extra dev -q && uv run tinyloom 'create a hello.py and run it'"
```

### Persistent container

```bash
docker run -dit \
  --name tinyloom-dev \
  -v $(pwd):/app -w /app \
  python:3.11-slim \
  sleep infinity

docker exec tinyloom-dev pip install -q uv
docker exec -w /app tinyloom-dev uv sync --extra dev
```

Run from source:

```bash
docker exec -w /app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  tinyloom-dev \
  uv run tinyloom "fix the failing tests"
```

Run tests:

```bash
docker exec -w /app tinyloom-dev uv run pytest tests/ -q
```

Run linter:

```bash
docker exec -w /app tinyloom-dev uv run ruff check tinyloom/ tests/
```

### Manage

```bash
docker ps                    # list running containers
docker stop tinyloom-dev     # stop
docker start tinyloom-dev    # restart
docker rm tinyloom-dev       # delete
```

## Hardened Container

Drop capabilities and restrict the container:

```bash
docker run -dit \
  --name tinyloom \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  -v $(pwd):/app -w /app \
  python:3.11-slim \
  sleep infinity
```

## Network Controls

No network (fully offline agent):

```bash
docker run --rm -it --network=none -v $(pwd):/app -w /app python:3.11-slim ...
```

Note: `--network=none` means no API calls. Install deps and pull models before cutting the network.

## Env File

Keep API keys out of shell history:

```bash
# .env (do NOT commit this)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
FIREWORKS_API_KEY=fw-...
```

```bash
docker run -dit --name tinyloom --env-file .env -v $(pwd):/app -w /app python:3.11-slim sleep infinity
```

## Troubleshooting

### Permission denied on mounted files

Run as your UID:

```bash
docker run -dit --name tinyloom --user $(id -u):$(id -g) -v $(pwd):/app -w /app python:3.11-slim sleep infinity
```

### Slow file I/O on macOS

Enable VirtioFS in Docker Desktop settings (Settings > General > VirtioFS).
