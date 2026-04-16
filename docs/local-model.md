# Running tinyloom with a local model

Run tinyloom against a local LLM. The model server runs on the host with full GPU access, tinyloom runs in a container for isolation.

This guide covers two model servers:

- **[llmster](https://lmstudio.ai/)** (LM Studio's headless runtime) -- GUI + CLI, broad format support
- **[Ollama](https://ollama.com/)** -- simple CLI, auto-serves, easy HuggingFace imports

Both expose an OpenAI-compatible API that tinyloom connects to.

## Prerequisites

- Podman or Docker installed
- One of the model servers below

---

## Option A: llmster (LM Studio)

### Install

```bash
curl -fsSL https://lmstudio.ai/install.sh | bash
lms --version
```

### Download a model

```bash
lms get qwen/qwen3-coder-30b@q4_k_m --gguf
```

Browse other quantizations:

```bash
lms get qwen/qwen3-coder-30b -a
```

### Config

Create a `tinyloom.yaml` in your project directory:

**Podman:**

```yaml
model:
  provider: openai
  model: qwen/qwen3-coder-30b
  base_url: http://host.containers.internal:1234/v1
  context_window: 32768
  max_tokens: 4096
```

**Docker:**

```yaml
model:
  provider: openai
  model: qwen/qwen3-coder-30b
  base_url: http://host.docker.internal:1234/v1
  context_window: 32768
  max_tokens: 4096
```

The `model` field should match what `lms ps` shows after loading.

### Setup 1: Shared server, many tinyloom sessions

Start llmster once, connect as many tinyloom containers as you want.

**Start the server:**

```bash
lms load qwen/qwen3-coder-30b --gpu max --context-length 32768 --yes
lms server start --port 1234
```

Verify:

```bash
curl -s http://localhost:1234/v1/models | head
```

**Run tinyloom (Podman):**

```bash
# headless
podman run --rm -it \
  -v $(pwd):/app -w /app \
  -e OPENAI_API_KEY=local \
  python:3.11-slim \
  sh -c "pip install -q tinyloom && tinyloom 'explain this project'"

# TUI
podman run --rm -it \
  -v $(pwd):/app -w /app \
  -e OPENAI_API_KEY=local \
  -e TERM=$TERM \
  python:3.11-slim \
  sh -c "pip install -q tinyloom && tinyloom"
```

**Run tinyloom (Docker):**

```bash
# headless
docker run --rm -it \
  -v $(pwd):/app -w /app \
  -e OPENAI_API_KEY=local \
  python:3.11-slim \
  sh -c "pip install -q tinyloom && tinyloom 'explain this project'"

# TUI
docker run --rm -it \
  -v $(pwd):/app -w /app \
  -e OPENAI_API_KEY=local \
  -e TERM=$TERM \
  python:3.11-slim \
  sh -c "pip install -q tinyloom && tinyloom"
```

Open more terminals and run the same command. They all share the llmster server.

**Stop:**

```bash
lms server stop
lms unload --all
```

### Setup 2: All-in-one

Single command -- load model + launch tinyloom. Model stays loaded after the container exits.

**Podman:**

```bash
lms load qwen/qwen3-coder-30b --gpu max --context-length 32768 --yes && \
  lms server start --port 1234 && \
  podman run --rm -it \
    -v $(pwd):/app -w /app \
    -e OPENAI_API_KEY=local \
    python:3.11-slim \
    sh -c "pip install -q tinyloom && tinyloom 'explain this project'"
```

**Docker:**

```bash
lms load qwen/qwen3-coder-30b --gpu max --context-length 32768 --yes && \
  lms server start --port 1234 && \
  docker run --rm -it \
    -v $(pwd):/app -w /app \
    -e OPENAI_API_KEY=local \
    python:3.11-slim \
    sh -c "pip install -q tinyloom && tinyloom 'explain this project'"
```

**Cleanup:**

```bash
lms server stop
lms unload --all
```

### llmster model table

| Model | lms get | Size |
|---|---|---|
| Qwen3 Coder 30B | `lms get qwen/qwen3-coder-30b@q4_k_m --gguf` | ~19 GB |
| Llama 3.1 8B | `lms get llama-3.1-8b@q4_k_m --gguf` | ~5 GB |
| Qwen 2.5 7B | `lms get qwen2.5-7b@q4_k_m --gguf` | ~5 GB |
| Gemma 3 27B | `lms get google/gemma-3-27b-it@q4_k_m --gguf` | ~17 GB |

Browse: `lms get <search-term> --gguf`

---

## Option B: Ollama

### Install

**macOS:**

```bash
brew install ollama
```

**Linux:**

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Ollama auto-starts a server on port `11434` after install. Verify:

```bash
curl -s http://localhost:11434/v1/models
```

If not running, start it manually:

```bash
ollama serve
```

### Download a model

```bash
ollama pull qwen3:30b-a3b
```

Or import a GGUF from HuggingFace:

```bash
ollama create my-model --from hf.co/username/repo-name
```

Or from a local GGUF file:

```bash
echo "FROM ./path/to/model.gguf" > Modelfile
ollama create my-model -f Modelfile
```

### Config

Create a `tinyloom.yaml` in your project directory:

**Podman:**

```yaml
model:
  provider: openai
  model: qwen3:30b-a3b
  base_url: http://host.containers.internal:11434/v1
  context_window: 32768
  max_tokens: 4096
```

**Docker:**

```yaml
model:
  provider: openai
  model: qwen3:30b-a3b
  base_url: http://host.docker.internal:11434/v1
  context_window: 32768
  max_tokens: 4096
```

The `model` field must match the Ollama model name (`ollama list` to check).

### Setup 1: Shared server, many tinyloom sessions

Ollama auto-serves -- just pull the model and go.

```bash
ollama pull qwen3:30b-a3b
```

Verify:

```bash
curl -s http://localhost:11434/v1/models | head
```

**Run tinyloom (Podman):**

```bash
# headless
podman run --rm -it \
  -v $(pwd):/app -w /app \
  -e OPENAI_API_KEY=ollama \
  python:3.11-slim \
  sh -c "pip install -q tinyloom && tinyloom 'explain this project'"

# TUI
podman run --rm -it \
  -v $(pwd):/app -w /app \
  -e OPENAI_API_KEY=ollama \
  -e TERM=$TERM \
  python:3.11-slim \
  sh -c "pip install -q tinyloom && tinyloom"
```

**Run tinyloom (Docker):**

```bash
# headless
docker run --rm -it \
  -v $(pwd):/app -w /app \
  -e OPENAI_API_KEY=ollama \
  python:3.11-slim \
  sh -c "pip install -q tinyloom && tinyloom 'explain this project'"

# TUI
docker run --rm -it \
  -v $(pwd):/app -w /app \
  -e OPENAI_API_KEY=ollama \
  -e TERM=$TERM \
  python:3.11-slim \
  sh -c "pip install -q tinyloom && tinyloom"
```

Open more terminals for multiple sessions. Ollama handles concurrent requests.

### Setup 2: All-in-one

Single command -- pull model + launch tinyloom. Ollama auto-serves, no separate server start needed.

**Podman:**

```bash
ollama pull qwen3:30b-a3b && \
  podman run --rm -it \
    -v $(pwd):/app -w /app \
    -e OPENAI_API_KEY=ollama \
    python:3.11-slim \
    sh -c "pip install -q tinyloom && tinyloom 'explain this project'"
```

**Docker:**

```bash
ollama pull qwen3:30b-a3b && \
  docker run --rm -it \
    -v $(pwd):/app -w /app \
    -e OPENAI_API_KEY=ollama \
    python:3.11-slim \
    sh -c "pip install -q tinyloom && tinyloom 'explain this project'"
```

### Ollama model table

| Model | ollama pull | Size |
|---|---|---|
| Qwen3 30B MoE | `ollama pull qwen3:30b-a3b` | ~19 GB |
| Qwen3 Coder 30B | `ollama pull qwen3-coder:30b` | ~19 GB |
| Llama 3.1 8B | `ollama pull llama3.1:8b` | ~5 GB |
| Gemma 3 27B | `ollama pull gemma3:27b` | ~17 GB |
| DeepSeek Coder V2 16B | `ollama pull deepseek-coder-v2:16b` | ~9 GB |

Browse: `ollama list` (local) or [ollama.com/library](https://ollama.com/library)

---

## context_window and max_tokens

How much context you can use depends on your available VRAM. The KV cache grows with context length -- more context means more memory on top of the model weights.

- **`context_window`** -- total token budget for the conversation (input + output). tinyloom uses this to decide when to trigger compaction. Must match what the model server allocates.
- **`max_tokens`** -- max tokens the model can generate per response. Keep this well below `context_window` so there's room for conversation history.

Rough guidelines for ~17-19 GB quantized models:

| Available VRAM | context_window | max_tokens |
|---|---|---|
| 24 GB (e.g. 4090) | 8192 | 4096 |
| 32 GB (e.g. M2 Pro) | 32768 | 4096 |
| 48 GB+ (e.g. M2 Max) | 65536 | 8192 |
| 64 GB+ | 131072 | 8192 |

If you're not sure, start with `8192` and increase until you hit memory pressure.

For llmster, the `--context-length` flag and `context_window` in tinyloom should match. For Ollama, set `OLLAMA_NUM_CTX` or pass `num_ctx` in the request options.

## Troubleshooting

### Connection refused from container

The container can't reach `localhost` on your host. Make sure your `tinyloom.yaml` uses the correct gateway hostname:

| Runtime | Hostname | Default Port |
|---|---|---|
| Podman + llmster | `host.containers.internal:1234` | 1234 |
| Docker + llmster | `host.docker.internal:1234` | 1234 |
| Podman + Ollama | `host.containers.internal:11434` | 11434 |
| Docker + Ollama | `host.docker.internal:11434` | 11434 |

Then verify the server is running:

```bash
# llmster
lms server status && lms ps

# Ollama
ollama list
curl -s http://localhost:11434/v1/models
```

### TUI is tiny or can't accept input

Always use `-it` and pass `TERM`:

```bash
podman run --rm -it -e TERM=$TERM ...
```

If still wrong size, pass dimensions explicitly:

```bash
-e COLUMNS=$(tput cols) -e LINES=$(tput lines)
```

### Model too slow

Try a smaller quantization or a smaller model. For llmster, check GPU offload:

```bash
lms ps  # shows GPU layers loaded
```

Use `--gpu max` (llmster) when loading to offload as much as possible to GPU.

### "Compute error" from LM Studio

The model loaded but can't run inference. Common causes:

- Model not yet supported by LM Studio's runtime (check their release notes)
- Out of VRAM -- try a lower `--context-length` or smaller quant
- Corrupted model file -- re-download

### thinking / reasoning_effort not supported

Local models don't support `thinking: true` or `reasoning_effort` in the tinyloom config. These are for cloud models (Claude, OpenAI o-series). Remove them for local use.
